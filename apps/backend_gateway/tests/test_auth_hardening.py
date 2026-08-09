"""Tests cho P4 — harden auth: rate limit đăng nhập + refresh token xoay vòng.

- ``core.ratelimit.check_rate``: nhánh Redis (fake pipeline) + nhánh fallback RAM.
- Endpoint ``/auth/refresh``: chỉ nhận JWT ``type=refresh``, xoay vòng cặp token,
  từ chối user bị khoá.
- ``/auth/login``: vượt ngưỡng → 429; login đúng → trả kèm refresh_token.
"""

import uuid
from typing import Any

import httpx
import pytest
from core.config import settings
from core.dependencies import get_db
from core.security import create_access_token, create_refresh_token, hash_password
from fastapi import FastAPI
from models.user import User

from api.v1.auth import router
from core import ratelimit

INTERNAL_KEY = "test-internal-key-123"


@pytest.fixture(autouse=True)
def _clear_ratelimit_memory() -> Any:
    """RAM fallback của rate limiter là state toàn module — dọn giữa các test."""
    ratelimit._memory.clear()
    yield
    ratelimit._memory.clear()


# ────────────────────────────────────────────────────────────────────────────
# rate limiter module
# ────────────────────────────────────────────────────────────────────────────
class _FakePipe:
    def __init__(self, redis: "_FakeRedis") -> None:
        self._redis = redis
        self._key: str | None = None

    def incr(self, key: str) -> "_FakePipe":
        self._key = key
        self._redis.counts[key] = self._redis.counts.get(key, 0) + 1
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipe":
        return self

    async def execute(self) -> list[Any]:
        return [self._redis.counts.get(self._key or "", 0), True]


class _FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def pipeline(self) -> _FakePipe:
        return _FakePipe(self)


@pytest.mark.asyncio
async def test_ratelimit_redis_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(ratelimit, "get_cache", lambda: fake)
    for i in range(3):
        assert await ratelimit.check_rate("u1", max_attempts=3, window_seconds=60) is True
    assert await ratelimit.check_rate("u1", max_attempts=3, window_seconds=60) is False
    # key khác không bị ảnh hưởng
    assert await ratelimit.check_rate("u2", max_attempts=3, window_seconds=60) is True


@pytest.mark.asyncio
async def test_ratelimit_memory_fallback_when_redis_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_cache", boom)
    for i in range(2):
        assert await ratelimit.check_rate("u1", max_attempts=2, window_seconds=60) is True
    assert await ratelimit.check_rate("u1", max_attempts=2, window_seconds=60) is False


@pytest.mark.asyncio
async def test_ratelimit_memory_window_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_cache", boom)
    now = 1_000.0
    assert await ratelimit.check_rate(
        "u1", max_attempts=1, window_seconds=60, now=now
    ) is True
    # cùng cửa sổ → hết lượt
    assert await ratelimit.check_rate(
        "u1", max_attempts=1, window_seconds=60, now=now + 30
    ) is False
    # cửa sổ mới → reset
    assert await ratelimit.check_rate(
        "u1", max_attempts=1, window_seconds=60, now=now + 61
    ) is True


# ────────────────────────────────────────────────────────────────────────────
# /auth/refresh contract
# ────────────────────────────────────────────────────────────────────────────
class _UserSession:
    def __init__(self, user: Any) -> None:
        self._user = user

    async def execute(self, stmt: Any) -> Any:
        return _Result(self._user)

    async def get(self, model: Any, obj_id: Any) -> Any:
        return self._user


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _post(app: FastAPI, path: str, json: dict[str, Any]) -> httpx.Response:
    async with await _client(app) as c:
        return await c.post(path, json=json)


def _install(app: FastAPI, user: Any) -> None:
    app.dependency_overrides[get_db] = lambda: _UserSession(user)


def _make_user(*, active: bool = True) -> Any:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    return type(
        "FakeUser",
        (),
        {
            "id": uuid.uuid4(),
            "is_active": active,
            "email": "user@example.com",
            "username": "user",
            "password_hash": hash_password("secret123"),
            "display_name": None,
            "created_at": now,
        },
    )()


def _refresh_token_for(user_id: uuid.UUID) -> str:
    return create_refresh_token(
        data={"sub": str(user_id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_days=settings.refresh_token_expire_days,
    )


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    user = _make_user()
    app = _make_app()
    _install(app, user)
    resp = await _post(app, "/auth/refresh", {"refresh_token": _refresh_token_for(user.id)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == settings.access_token_expire_minutes * 60


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    user = _make_user()
    app = _make_app()
    _install(app, user)
    access = create_access_token(
        data={"sub": str(user.id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=5,
    )
    resp = await _post(app, "/auth/refresh", {"refresh_token": access})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_garbage_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    app = _make_app()
    _install(app, _make_user())
    resp = await _post(app, "/auth/refresh", {"refresh_token": "not-a-jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    user = _make_user(active=False)
    app = _make_app()
    _install(app, user)
    resp = await _post(app, "/auth/refresh", {"refresh_token": _refresh_token_for(user.id)})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    app = _make_app()
    _install(app, None)  # db.get trả None
    token = _refresh_token_for(uuid.uuid4())
    resp = await _post(app, "/auth/refresh", {"refresh_token": token})
    assert resp.status_code == 401


# ────────────────────────────────────────────────────────────────────────────
# /auth/login rate limit
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_login_rate_limited_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")
    monkeypatch.setattr(settings, "login_rate_limit_max", 3)
    monkeypatch.setattr(settings, "login_rate_limit_window_seconds", 60)

    def boom() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_cache", boom)

    app = _make_app()
    app.dependency_overrides[get_db] = lambda: _UserSession(None)
    payload = {"email": "victim@example.com", "password": "wrong-pass"}

    for i in range(3):
        resp = await _post(app, "/auth/login", payload)
        assert resp.status_code == 401

    resp = await _post(app, "/auth/login", payload)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    # Tài khoản khác CÙNG IP cũng bị chặn (giới hạn theo IP — chống spam nhiều account).
    resp2 = await _post(app, "/auth/login", {"email": "other@example.com", "password": "x"})
    assert resp2.status_code == 429


@pytest.mark.asyncio
async def test_login_returns_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-for-auth-tests-0123456789abcdef")

    def boom() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr(ratelimit, "get_cache", boom)

    user = _make_user()
    app = _make_app()
    _install(app, user)
    resp = await _post(app, "/auth/login", {"email": "user@example.com", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0
