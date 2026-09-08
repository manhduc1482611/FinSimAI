"""Test lịch sử hội thoại Mentor — persistence + REST + LLM history (A3.2)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest
from core.dependencies import get_current_user, get_db
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models.mentor import MentorMessage
from realtime import mentor_ws as mentor_ws_module
from realtime.connection_manager import ConnectionManager
from realtime.mentor_ws import MentorStreamProvider, create_mentor_endpoint
from services.mentor_history import (
    LLM_HISTORY_LIMIT,
    recent_messages,
    save_exchange,
    to_llm_history,
)


class _FakeUser:
    def __init__(self, user_id: str = "u-1") -> None:
        self.id = user_id


class _FakeDB:
    """AsyncSession giả: bắt add_all cho persistence, trả row cài sẵn cho query."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = 0
        self.query_result: list[Any] = []

    def add_all(self, rows: list[Any]) -> None:
        self.added.extend(rows)

    async def commit(self) -> None:
        self.committed += 1

    async def rollback(self) -> None:
        return None

    async def execute(self, stmt: Any) -> SimpleNamespace:
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: self.query_result),
            scalar=lambda: 0,
        )


class _SessionCtx:
    def __init__(self, db: _FakeDB) -> None:
        self._db = db

    async def __aenter__(self) -> _FakeDB:
        return self._db

    async def __aexit__(self, *exc: object) -> None:
        return None


def _row(role: str, content: str, minutes_ago: int) -> MentorMessage:
    return MentorMessage(
        user_id=uuid.uuid4(),
        session_id="s-1",
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


def _receive_until(
    ws: Any, predicate: Any, limit: int = 100
) -> dict[str, Any]:
    for _ in range(limit):
        message = ws.receive_json()
        if predicate(message):
            return cast(dict[str, Any], message)
    raise AssertionError("Không nhận được tin mong đợi trong giới hạn")


# ── Service: recent_messages + to_llm_history ───────────────────────────────
async def test_recent_messages_returns_oldest_first() -> None:
    db = _FakeDB()
    # DB trả theo created_at DESC (mới nhất trước).
    db.query_result = [
        _row("user", "tin mới", 0),
        _row("mentor", "đáp mới", 1),
        _row("user", "tin cũ", 5),
    ]

    rows = await recent_messages(db, uuid.uuid4(), limit=12)

    contents = [r.content for r in rows]
    assert contents == ["tin cũ", "đáp mới", "tin mới"], "Phải đảo thành cũ → mới"


async def test_recent_messages_query_has_limit_clause() -> None:
    """LIMIT phải nằm trong SQL (fake DB không tự cắt) — chống quét cả bảng."""
    db = _FakeDB()
    db.query_result = [_row("user", str(i), i) for i in range(20)]

    captured: dict[str, Any] = {}

    async def _capture(stmt: Any) -> SimpleNamespace:
        captured["stmt"] = stmt
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: db.query_result),
            scalar=lambda: 0,
        )

    db.execute = _capture  # type: ignore[method-assign]

    rows = await recent_messages(db, uuid.uuid4(), limit=LLM_HISTORY_LIMIT)

    sql = str(captured["stmt"].compile(compile_kwargs={"literal_binds": True}))
    assert f"LIMIT {LLM_HISTORY_LIMIT}" in sql.upper().replace("\n", " ")
    assert len(rows) == len(db.query_result)


async def test_save_exchange_persists_user_and_mentor_rows() -> None:
    db = _FakeDB()

    await save_exchange(
        db,  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        session_id="s-9",
        user_message="Tôi nên mua không?",
        mentor_reply="Bạn dựa trên dữ liệu nào?",
        focus="fomo",
        prompt_version="qbank-3.1.0",
    )

    assert [r.role for r in db.added] == ["user", "mentor"]
    assert db.added[1].focus == "fomo"
    assert db.committed == 1


def test_to_llm_history_shape() -> None:
    rows = [_row("user", "câu hỏi", 2), _row("mentor", "câu hỏi phản biện", 1)]
    history = to_llm_history(rows)
    assert history == [
        {"role": "user", "content": "câu hỏi"},
        {"role": "mentor", "content": "câu hỏi phản biện"},
    ]


# ── WS: lưu hội thoại khi stream hoàn tất ───────────────────────────────────
class _ChunkProvider:
    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        mode: str = "socratic",
        snapshot: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        yield "phần "
        yield "hai"


def _ws_app(provider: Any) -> FastAPI:
    app = FastAPI()
    app.add_websocket_route(
        "/ws/mentor",
        create_mentor_endpoint(
            ConnectionManager(),
            cast(MentorStreamProvider, provider),
            _allow_auth,
            rate_limit_enabled=False,
        ),
    )
    return app


async def _allow_auth(websocket: Any) -> Any:
    return _FakeUser()


def test_completed_ask_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    saved_db = _FakeDB()
    monkeypatch.setattr(
        mentor_ws_module, "async_session_factory", lambda: _SessionCtx(saved_db)
    )
    app = _ws_app(_ChunkProvider())

    with TestClient(app) as client, client.websocket_connect("/ws/mentor") as ws:
        _receive_until(ws, lambda m: m["type"] == "mentor_ready")
        ws.send_json({"action": "ask", "session_id": "s-1", "message": "Nên mua không?"})
        _receive_until(ws, lambda m: m["type"] == "mentor_end")

    roles = [r.role for r in saved_db.added]
    assert roles == ["user", "mentor"], "Một lượt hỏi-đáp = 2 tin (user + mentor)"
    mentor_row = saved_db.added[1]
    assert mentor_row.content == "phần hai", "Các chunk phải được ghép trọn vẹn"
    assert mentor_row.focus is not None, "Focus phải được detect để cá nhân hóa sau này"
    assert saved_db.committed == 1


def test_cancelled_ask_is_not_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    saved_db = _FakeDB()
    monkeypatch.setattr(
        mentor_ws_module, "async_session_factory", lambda: _SessionCtx(saved_db)
    )

    class _CancellableProvider:
        """Giống SlowProvider của test_mentor_ws: treo giữa stream tới khi release."""

        def __init__(self) -> None:
            import asyncio

            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def stream(
            self,
            *,
            user_id: str,
            message: str,
            session_id: str,
            mode: str = "socratic",
            snapshot: dict[str, Any] | None = None,
        ) -> AsyncIterator[str]:
            self.started.set()
            await self.release.wait()
            yield "đầu"

    provider = _CancellableProvider()
    app = _ws_app(provider)

    with TestClient(app) as client, client.websocket_connect("/ws/mentor") as ws:
        _receive_until(ws, lambda m: m["type"] == "mentor_ready")
        ws.send_json({"action": "ask", "session_id": "s-1", "message": "Nên bán không?"})
        start = _receive_until(ws, lambda m: m["type"] == "mentor_start")
        assert start["data"]["session_id"] == "s-1"

        ws.send_json({"action": "cancel", "session_id": "s-1"})
        cancelled = _receive_until(ws, lambda m: m["type"] == "mentor_cancelled")
        assert cancelled["data"]["session_id"] == "s-1"

        provider.release.set()
        # Ping/pong để chắc chắn vòng lặp server còn sống sau cancel.
        ws.send_json({"action": "ping"})
        _receive_until(ws, lambda m: m["type"] == "pong")

    assert saved_db.added == [], "Phiên bị cancel không được ghi vào lịch sử"


# ── REST: GET /mentor/history ───────────────────────────────────────────────
def _rest_app(db: _FakeDB, *, deny_auth: bool = False) -> FastAPI:
    from api.v1.mentor_history import router as mentor_history_router

    app = FastAPI()
    app.include_router(mentor_history_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    if deny_auth:
        from fastapi import HTTPException, status

        def _deny() -> None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

        app.dependency_overrides[get_current_user] = _deny
    else:
        app.dependency_overrides[get_current_user] = lambda: _FakeUser(user_id="u-1")
    return app


def test_history_endpoint_returns_items_oldest_first() -> None:
    db = _FakeDB()
    db.query_result = [_row("mentor", "đáp mới", 0), _row("user", "hỏi cũ", 3)]
    client = TestClient(_rest_app(db))

    resp = client.get("/api/v1/mentor/history")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["content"] for item in body["items"]] == ["hỏi cũ", "đáp mới"]
    assert set(body["items"][0]) >= {"id", "session_id", "role", "content", "created_at"}


def test_history_requires_auth() -> None:
    client = TestClient(_rest_app(_FakeDB(), deny_auth=True))

    resp = client.get("/api/v1/mentor/history")

    assert resp.status_code == 401
