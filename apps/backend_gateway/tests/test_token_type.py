"""Access/refresh token boundary — P0 hardening.

Lỗ hổng: ``_resolve_user`` chỉ decode JWT rồi lấy ``sub`` mà KHÔNG kiểm tra claim
``type``, nên refresh token (sống 30 ngày) gọi được mọi API như access token. Các
test cũ chỉ kiểm tra chiều ngược lại (``/auth/refresh`` từ chối access token).

Bộ test này khoá bất biến hai chiều:
- access token  → xác thực ở REST, bị ``/auth/refresh`` từ chối (đã có ở test khác).
- refresh token → BỊ TỪ CHỐI ở REST (chính là lỗ hổng này).
- token thiếu claim ``type`` (định dạng cũ) → từ chối (fail-closed).
"""

import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from core.config import settings
from core.dependencies import get_current_user, get_db
from core.security import create_access_token, create_refresh_token
from fastapi import Depends, FastAPI

TEST_SECRET = "test-secret-for-token-type-tests-0123456789abcdef"


class _Result:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _Session:
    """Session giả: trả về cùng một user cho mọi SELECT."""

    def __init__(self, user: Any) -> None:
        self._user = user

    async def execute(self, stmt: Any) -> _Result:
        return _Result(self._user)


def _make_user(*, active: bool = True) -> Any:
    return SimpleNamespace(id=uuid.uuid4(), is_active=active)


def _make_app(user: Any) -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    async def me(current_user: Any = Depends(get_current_user)) -> dict[str, str]:
        return {"id": str(current_user.id)}

    app.dependency_overrides[get_db] = lambda: _Session(user)
    return app


async def _get(app: FastAPI, token: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.get("/me", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)


def _access(user_id: uuid.UUID) -> str:
    return create_access_token(
        data={"sub": str(user_id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )


def _refresh(user_id: uuid.UUID) -> str:
    return create_refresh_token(
        data={"sub": str(user_id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_days=settings.refresh_token_expire_days,
    )


@pytest.mark.asyncio
async def test_access_token_authenticates_rest() -> None:
    user = _make_user()
    resp = await _get(_make_app(user), _access(user.id))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(user.id)


@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access_token() -> None:
    """Bất biến chính: refresh token KHÔNG dùng được như access token ở REST."""
    user = _make_user()
    resp = await _get(_make_app(user), _refresh(user.id))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_without_type_claim_rejected() -> None:
    """Token định dạng cũ (không có ``type``) bị từ chối — fail-closed."""
    import jwt

    user = _make_user()
    legacy = jwt.encode(
        {"sub": str(user.id)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = await _get(_make_app(user), legacy)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_for_inactive_user_rejected() -> None:
    user = _make_user(active=False)
    resp = await _get(_make_app(user), _access(user.id))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_with_unknown_user_rejected() -> None:
    user = _make_user()
    app = _make_app(None)  # DB không tìm thấy user
    resp = await _get(app, _access(user.id))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_token_rejected() -> None:
    user = _make_user()
    app = _make_app(user)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/me")
    assert resp.status_code == 401
