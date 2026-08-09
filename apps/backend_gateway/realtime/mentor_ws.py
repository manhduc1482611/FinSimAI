"""Streaming phản hồi của Mentor (phương pháp Socratic) qua WebSocket.

Client gửi câu hỏi, server trả về chuỗi chunk:
    {"action": "ask", "message": "...", "session_id": "..."}       (client → server)
    {"type": "mentor_start", "data": {...}}                         (server)
    {"type": "mentor_chunk", "data": {"session_id", "text"}}        (server, nhiều lần)
    {"type": "mentor_end", "data": {"session_id", "reason"}}        (server)
    {"action": "cancel", "session_id": "..."}                       (client → server)

``MentorStreamProvider`` là interface trừu tượng. Nguồn mặc định là
``HybridMentorStream``: deterministic question-bank (0 token Gemini) làm chính,
gọi ai_engine/Gemini CHỈ khi ``MENTOR_LLM_MODE=on`` + giới hạn lượt — mọi lỗi
quota/mạng đều tự rơi về deterministic, không sửa giao thức WebSocket.

Chống rò rỉ tài nguyên:
- Mỗi chunk gửi qua ``manager.send`` đều kiểm tra kết quả: nếu client đã ngắt kết
  nối hoặc queue đầy (trả ``False``), vòng lặp dừng ngay — không gọi AI/LLM thêm.
- Khi user gửi câu hỏi mới hoặc ``cancel``, task cũ bị cancel và đánh dấu
  ``cancelled``; server KHÔNG ``await`` task cũ trên luồng đọc WebSocket (tránh chặn
  reader khi task cũ mắc kẹt ở network), chỉ huỷ nền và chạy task mới.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from clients.mentor_client import mentor_client
from core.config import settings
from fastapi import WebSocket

from realtime.auth import get_ws_user, revalidate_user
from realtime.connection_manager import (
    ClientConnection,
    ConnectionManager,
    build_message,
    connection_manager,
)
from realtime.mentor_engine import reply_to_text, socratic_reply

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 16


class MentorStreamProvider(Protocol):
    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """Yield từng đoạn text phản hồi của Mentor."""
        ...


def _chunk_text(text: str, size: int = _CHUNK_SIZE) -> AsyncIterator[str]:
    """Chia nhỏ text thành chunk để stream (0 token AI)."""

    async def _generate() -> AsyncIterator[str]:
        for i in range(0, len(text), size):
            await asyncio.sleep(0.02)
            yield text[i : i + size]

    return _generate()


class DeterministicMentorStream:
    """Phản hồi Socratic deterministic (question-bank, 0 token Gemini).

    Đây là nguồn mặc định của Mentor — Mentor luôn trả lời mà không tốn lượt AI.
    """

    def __init__(self, company: str = "") -> None:
        self._company = company

    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        reply = socratic_reply(message, company=self._company)
        async for chunk in _chunk_text(reply_to_text(reply)):
            yield chunk


class HybridMentorStream:
    """Mentor chính: deterministic mặc định, Gemini tuỳ chọn + giới hạn lượt.

    Gemini chỉ được gọi khi ``MENTOR_LLM_MODE=on`` VÀ cấu hình ``AI_ENGINE_URL``
    — và ngay khi đó vẫn bị ai_engine giới hạn bởi token bucket (RPM/BURST).
    Mọi lỗi (quota, mạng, timeout, ai_engine down) → tự rơi về deterministic,
    không bao giờ để người chơi đợi mất phản hồi.
    """

    def __init__(
        self,
        deterministic: DeterministicMentorStream | None = None,
        client: Any | None = None,
    ) -> None:
        self._deterministic = deterministic or DeterministicMentorStream()
        self._client = client if client is not None else mentor_client

    @property
    def llm_enabled(self) -> bool:
        return settings.mentor_llm_mode == "on" and bool(settings.ai_engine_url)

    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        text: str | None = None
        if self.llm_enabled:
            reply = await self._client.ask(
                message=message,
                user_id=user_id,
                session_id=session_id,
            )
            if reply and isinstance(reply.get("questions"), list):
                questions = [str(q) for q in reply["questions"]]
                tip = str(reply.get("coaching_tip") or "")
                disclaimer = str(reply.get("disclaimer") or "")
                text = "\n".join([*questions, "", f"Bài tập: {tip}", "", disclaimer])
        if text is None:
            async for chunk in self._deterministic.stream(
                user_id=user_id, message=message, session_id=session_id
            ):
                yield chunk
            return
        async for chunk in _chunk_text(text):
            yield chunk


mentor_stream_provider = HybridMentorStream()


@dataclass
class _AskSession:
    """Phiên streaming Mentor: generation + cờ cancelled để dừng task cũ nhanh."""

    generation: int
    task: asyncio.Task[None] | None = field(default=None, init=False)
    cancelled: bool = field(default=False, init=False)


def create_mentor_endpoint(
    manager: ConnectionManager | None = None,
    provider: MentorStreamProvider | None = None,
    auth_provider: Callable[[WebSocket], Any] | None = None,
    *,
    heartbeat_seconds: float | None = None,
    revalidate_auth: bool | None = None,
) -> Callable[[WebSocket], Any]:
    manager = manager or connection_manager
    stream_provider = cast(Any, provider or mentor_stream_provider)
    auth = auth_provider or get_ws_user
    heartbeat = (
        heartbeat_seconds if heartbeat_seconds is not None else settings.ws_heartbeat_seconds
    )
    # Chỉ bật revalidation giữa phiên khi dùng auth JWT mặc định (custom auth trong
    # test không có token → không revalidate để tránh đóng oan kết nối).
    do_revalidate = (
        revalidate_auth if revalidate_auth is not None else (auth_provider is None)
    )

    active_sessions: dict[str, _AskSession] = {}

    async def _run_ask(
        conn: ClientConnection,
        user_id: str,
        session_id: str,
        message: str,
        session: _AskSession,
    ) -> None:
        try:
            if session.cancelled:
                return
            if not await manager.send(
                conn,
                build_message(
                    "mentor_start",
                    {"session_id": session_id, "user_id": user_id},
                ),
            ):
                return
            async for chunk in stream_provider.stream(
                user_id=user_id, message=message, session_id=session_id
            ):
                if session.cancelled:
                    return
                if not await manager.send(
                    conn,
                    build_message("mentor_chunk", {"session_id": session_id, "text": chunk}),
                ):
                    return
            if not await manager.send(
                conn,
                build_message("mentor_end", {"session_id": session_id, "reason": "complete"}),
            ):
                return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Mentor stream failed for %s", conn.connection_id)
            if not session.cancelled:
                await manager.send(
                    conn,
                    build_message(
                        "mentor_error",
                        {"session_id": session_id, "message": "Mentor streaming failed"},
                    ),
                )
        finally:
            if active_sessions.get(conn.connection_id) is session:
                active_sessions.pop(conn.connection_id, None)

    async def mentor_ws_endpoint(websocket: WebSocket) -> None:
        user = await auth(websocket)
        user_id = str(user.id)
        user_room = manager.user_room(user.id)

        async def on_validate(conn: ClientConnection) -> bool:
            return await revalidate_user(user_id)

        async def on_connect(conn: ClientConnection) -> None:
            await manager.join_room(conn, user_room)
            await manager.send(
                conn,
                build_message(
                    "mentor_ready",
                    {"user_id": user_id, "realtime_status": manager.realtime_status()},
                ),
            )

        async def on_disconnect(conn: ClientConnection) -> None:
            session = active_sessions.pop(conn.connection_id, None)
            if session is not None and session.task is not None and not session.task.done():
                session.cancelled = True
                session.task.cancel()

        async def on_message(conn: ClientConnection, payload: dict[str, Any]) -> None:
            action = payload.get("action")
            session_id = payload.get("session_id") or ""
            if action == "ask":
                message = payload.get("message")
                if not isinstance(message, str) or not message.strip():
                    await manager.send(
                        conn,
                        build_message(
                            "error",
                            {"code": "invalid_message", "message": "message không được trống"},
                        ),
                    )
                    return
                prev = active_sessions.get(conn.connection_id)
                generation = (prev.generation + 1) if prev is not None else 1
                session = _AskSession(generation=generation)
                if prev is not None and prev.task is not None and not prev.task.done():
                    # Không await task cũ (tránh block reader khi task cũ mắc kẹt ở
                    # network/LLM): cờ cancelled + task.cancel() đủ để nó tự dừng.
                    prev.cancelled = True
                    prev.task.cancel()
                task = asyncio.create_task(
                    _run_ask(conn, str(user.id), session_id, message, session),
                    name=f"mentor-ask-{conn.connection_id}",
                )
                session.task = task
                active_sessions[conn.connection_id] = session
            elif action == "cancel":
                current = active_sessions.get(conn.connection_id)
                if current is not None and current.task is not None and not current.task.done():
                    current.cancelled = True
                    current.task.cancel()
                    await manager.send(
                        conn,
                        build_message(
                            "mentor_cancelled",
                            {"session_id": session_id},
                        ),
                    )
            else:
                await manager.send(
                    conn,
                    build_message("error", {"code": "unknown_action", "action": action}),
                )

        await manager.handle_connection(
            websocket,
            on_message,
            user_id=str(user.id),
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            on_validate=on_validate if do_revalidate else None,
            heartbeat_seconds=heartbeat,
        )

    return mentor_ws_endpoint
