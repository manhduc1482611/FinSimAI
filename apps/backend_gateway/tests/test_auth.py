import asyncio
import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import WebSocket, status
from realtime import auth as auth_module
from realtime.auth import TicketStore, get_ws_user, revalidate_user
from starlette.exceptions import WebSocketException


class FakeWebSocket:
    def __init__(self, ticket: str | None) -> None:
        self.query_params = {"ticket": ticket} if ticket is not None else {}


def _ws(ticket: str | None) -> WebSocket:
    return cast(WebSocket, FakeWebSocket(ticket))


class FakeSession:
    def __init__(self, user: object) -> None:
        self.user = user

    async def get(self, model: Any, user_id: Any) -> Any:
        return self.user

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def install_local_ticket_store(monkeypatch: pytest.MonkeyPatch) -> TicketStore:
    """Dùng TicketStore RAM (local_mode) để test không phụ thuộc Redis."""
    store = TicketStore(local_mode=True)
    monkeypatch.setattr(auth_module, "ticket_store", store)
    return store


@pytest.mark.asyncio
async def test_get_ws_user_accepts_valid_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4(), is_active=True)
    monkeypatch.setattr(auth_module, "async_session_factory", lambda: FakeSession(user))
    store = install_local_ticket_store(monkeypatch)

    ticket = await store.issue(str(user.id))
    result = await get_ws_user(_ws(ticket))
    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_ws_user_rejects_missing_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_factory() -> None:
        raise AssertionError("Không được gọi DB khi thiếu ticket")

    monkeypatch.setattr(auth_module, "async_session_factory", fake_factory)
    with pytest.raises(WebSocketException) as exc_info:
        await get_ws_user(_ws(None))
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_get_ws_user_rejects_unknown_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_factory() -> None:
        raise AssertionError("Không được gọi DB khi ticket không tồn tại")

    monkeypatch.setattr(auth_module, "async_session_factory", fake_factory)
    install_local_ticket_store(monkeypatch)
    with pytest.raises(WebSocketException) as exc_info:
        await get_ws_user(_ws("not-a-real-ticket"))
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_ticket_is_single_use(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_local_ticket_store(monkeypatch)
    ticket = await store.issue(str(uuid.uuid4()))

    assert await store.consume(ticket) is not None
    assert await store.consume(ticket) is None


@pytest.mark.asyncio
async def test_ticket_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    store = install_local_ticket_store(monkeypatch)
    ticket = await store.issue(str(uuid.uuid4()), ttl=0.05)
    await asyncio.sleep(0.07)
    assert await store.consume(ticket) is None


@pytest.mark.asyncio
async def test_get_ws_user_rejects_nonexistent_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "async_session_factory", lambda: FakeSession(None))
    store = install_local_ticket_store(monkeypatch)
    ticket = await store.issue(str(uuid.uuid4()))

    with pytest.raises(WebSocketException) as exc_info:
        await get_ws_user(_ws(ticket))
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_get_ws_user_rejects_inactive_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4(), is_active=False)
    monkeypatch.setattr(auth_module, "async_session_factory", lambda: FakeSession(user))
    store = install_local_ticket_store(monkeypatch)
    ticket = await store.issue(str(user.id))

    with pytest.raises(WebSocketException) as exc_info:
        await get_ws_user(_ws(ticket))
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_get_ws_user_caches_active_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """2 lần handshake cùng user → chỉ 1 lần query DB (chống Herd Postgres reconnect)."""
    calls = 0
    user = SimpleNamespace(id=uuid.uuid4(), is_active=True)

    class CountingSession:
        def __init__(self) -> None:
            nonlocal calls
            calls += 1
            self.user = user

        async def get(self, model: Any, user_id: Any) -> Any:
            return self.user

        async def __aenter__(self) -> "CountingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    monkeypatch.setattr(auth_module, "async_session_factory", CountingSession)
    auth_module._user_cache.clear()
    store = install_local_ticket_store(monkeypatch)

    ticket1 = await store.issue(str(user.id))
    assert (await get_ws_user(_ws(ticket1))).id == user.id
    ticket2 = await store.issue(str(user.id))
    assert (await get_ws_user(_ws(ticket2))).id == user.id
    assert calls == 1


@pytest.mark.asyncio
async def test_get_ws_user_db_error_fails_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Postgres chập chờn lúc handshake → 1008 sạch (không 500), client retry backoff."""

    class FailingSession:
        async def get(self, model: Any, user_id: Any) -> Any:
            raise ConnectionError("db down")

        async def __aenter__(self) -> "FailingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    monkeypatch.setattr(auth_module, "async_session_factory", lambda: FailingSession())
    auth_module._user_cache.clear()
    store = install_local_ticket_store(monkeypatch)
    ticket = await store.issue(str(uuid.uuid4()))

    with pytest.raises(WebSocketException) as exc_info:
        await get_ws_user(_ws(ticket))
    assert exc_info.value.code == status.WS_1008_POLICY_VIOLATION
    # Lỗi DB không cache kết quả — lần handshake sau phải thử lại DB thật.
    assert auth_module._user_cache == {}


@pytest.mark.asyncio
async def test_revalidate_user_caches_by_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Revalidation cache: 2 lần gọi liên tiếp chỉ query DB 1 lần (chống DDoS pool)."""
    calls = 0
    user_id = str(uuid.uuid4())

    class CountingSession:
        def __init__(self) -> None:
            nonlocal calls
            calls += 1
            self.user = SimpleNamespace(id=uuid.UUID(user_id), is_active=True)

        async def get(self, model: Any, user_id: Any) -> Any:
            return self.user

        async def __aenter__(self) -> "CountingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    monkeypatch.setattr(auth_module, "async_session_factory", CountingSession)
    auth_module._revalidate_cache.clear()

    assert await revalidate_user(user_id) is True
    assert await revalidate_user(user_id) is True
    assert calls == 1


@pytest.mark.asyncio
async def test_revalidate_user_false_when_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=uuid.uuid4(), is_active=False)
    monkeypatch.setattr(auth_module, "async_session_factory", lambda: FakeSession(user))
    auth_module._revalidate_cache.clear()

    assert await revalidate_user(str(user.id)) is False


@pytest.mark.asyncio
async def test_revalidate_user_db_error_keeps_alive_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Postgres chập chờn → trả True giữ kết nối, KHÔNG cache kết quả âm."""

    class FailingSession:
        def __init__(self, down: bool) -> None:
            self.down = down

        async def get(self, model: Any, user_id: Any) -> Any:
            if self.down:
                raise ConnectionError("db down")
            return SimpleNamespace(id=uuid.UUID(user_id), is_active=True)

        async def __aenter__(self) -> "FailingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    state = {"down": True}
    monkeypatch.setattr(
        auth_module, "async_session_factory", lambda: FailingSession(state["down"])
    )
    auth_module._revalidate_cache.clear()
    user_id = str(uuid.uuid4())

    assert await revalidate_user(user_id) is True
    assert user_id not in auth_module._revalidate_cache

    state["down"] = False
    assert await revalidate_user(user_id) is True
    assert await revalidate_user(user_id) is True  # cache hit, không nhiễm lỗi cũ


@pytest.mark.asyncio
async def test_revalidate_user_false_for_invalid_uuid() -> None:
    assert await revalidate_user("not-a-uuid") is False


def test_trim_cache_evicts_lru_not_clear_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vượt ngưỡng → chỉ đá entry cũ nhất (LRU), giữ phần còn lại (tránh Herd)."""
    import time

    monkeypatch.setattr(auth_module, "_REVALIDATE_CACHE_MAX", 2)
    auth_module._revalidate_cache.clear()
    now = time.monotonic()
    auth_module._revalidate_cache["u1"] = (now + 60, True)
    auth_module._revalidate_cache["u2"] = (now + 60, True)
    auth_module._revalidate_cache["u3"] = (now + 60, True)

    auth_module._trim_cache(now)

    assert len(auth_module._revalidate_cache) == 2
    assert "u1" not in auth_module._revalidate_cache  # cũ nhất bị đá
    assert "u2" in auth_module._revalidate_cache
    assert "u3" in auth_module._revalidate_cache


def test_trim_cache_removes_only_expired_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    auth_module._revalidate_cache.clear()
    now = time.monotonic()
    auth_module._revalidate_cache["fresh"] = (now + 60, True)
    auth_module._revalidate_cache["stale"] = (now - 1, False)

    auth_module._trim_cache(now)

    assert "fresh" in auth_module._revalidate_cache
    assert "stale" not in auth_module._revalidate_cache
