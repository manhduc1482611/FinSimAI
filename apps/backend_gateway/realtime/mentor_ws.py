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
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from clients.mentor_client import mentor_client
from core.config import settings
from core.database import async_session_factory
from core.ratelimit import check_rate
from fastapi import WebSocket
from services.mentor_history import (
    LLM_HISTORY_LIMIT,
    recent_messages,
    save_exchange,
    to_llm_history,
)
from services.mentor_metadata import to_metadata_dict
from services.trade_snapshot import trade_snapshot_service

from realtime.auth import get_ws_user, revalidate_user
from realtime.connection_manager import (
    ClientConnection,
    ConnectionManager,
    build_message,
    connection_manager,
)
from realtime.mentor_engine import (
    concept_reply_text,
    detect_focus,
    reply_to_text,
    socratic_reply,
    strategy_reply_text,
    trade_challenge_text,
)

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 16

# Những mode hợp lệ trong chỉ định "AI Mentor 3 chế độ" (kế hoạch v2.0).
_MENTOR_MODES = ("socratic", "concept", "trade_now", "plan")

# Nguồn nội dung mặc định là question-bank mirror của prompt YAML v3.1.0
# (A3.4: ghi nguồn để truy vết chất lượng theo phiên bản).
_DETERMINISTIC_PROMPT_VERSION = "qbank-3.1.0"


class MentorStreamProvider(Protocol):
    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        mode: str = "socratic",
        snapshot: dict[str, Any] | None = None,
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
    """Phản hồi deterministic cho cả 3 chế độ (0 token Gemini).

    Đây là nguồn mặc định của Mentor — Mentor luôn trả lời mà không tốn lượt AI:
    - mode ``concept``: giải thích khái niệm từ glossary (nếu khớp), kèm câu
      hỏi Socratic dẫn dắt.
    - mode ``plan``: render khung chiến lược từ framework bank đã duyệt (docs
      v2.0 mục 4.2) — không nêu mã/giá mục tiêu/dự đoán.
    - mode ``trade_now``: phản biện lúc giao dịch dựa trên energy risk-flags do
      backend tính từ snapshot.
    - mode ``socratic``: question-bank phản biện chuẩn.
    """

    def __init__(self, company: str = "") -> None:
        self._company = company

    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        mode: str = "socratic",
        snapshot: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        if mode == "concept":
            text = concept_reply_text(message)
            if text is not None:
                async for chunk in _chunk_text(text):
                    yield chunk
                return
        if mode == "plan":
            # Khung chiến lược từ bank đã duyệt (0 token) — không rơi về socratic.
            portfolio_text = (snapshot or {}).get("text", "")
            reply = strategy_reply_text(message, portfolio_text=portfolio_text)
            async for chunk in _chunk_text(reply):
                yield chunk
            return
        if mode == "trade_now" and snapshot is not None:
            # Phản biện theo dấu hiệu rủi ro từ snapshot có thật (backend tính).
            challenge = trade_challenge_text(snapshot)
            async for chunk in _chunk_text(challenge):
                yield chunk
            return
        reply = socratic_reply(message, company=self._company)
        async for chunk in _chunk_text(reply_to_text(reply)):
            yield chunk


class HybridMentorStream:
    """Mentor chính: deterministic mặc định, Gemini tuỳ chọn + giới hạn lượt.

    Gemini chỉ được gọi khi ``MENTOR_LLM_MODE=on`` VÀ cấu hình ``AI_ENGINE_URL``
    — và ngay khi đó vẫn bị ai_engine giới hạn bởi token bucket (RPM/BURST).
    Mọi lỗi (quota, mạng, timeout, ai_engine down) → tự rơi về deterministic,
    không bao giờ để người chơi đợi mất phản hồi.

    ``history_provider`` (A3.2): lấy history hội thoại từ DB trước khi gọi LLM
    — continuity giữa các phiên thay vì phụ thuộc client gửi lại.
    """

    def __init__(
        self,
        deterministic: DeterministicMentorStream | None = None,
        client: Any | None = None,
        history_provider: Callable[[str], Awaitable[list[dict[str, str]]]] | None = None,
    ) -> None:
        self._deterministic = deterministic or DeterministicMentorStream()
        self._client = client if client is not None else mentor_client
        self._history_provider = history_provider

    @property
    def llm_enabled(self) -> bool:
        return settings.mentor_llm_mode == "on" and bool(settings.ai_engine_url)

    async def stream(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        mode: str = "socratic",
        snapshot: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        text: str | None = None
        if self.llm_enabled:
            history: list[dict[str, str]] | None = None
            if self._history_provider is not None:
                try:
                    history = await self._history_provider(user_id) or None
                except Exception:  # noqa: BLE001 - history là tối ưu, không chặn trả lời
                    logger.warning("history_provider lỗi — gọi LLM không history", exc_info=True)
            reply = await self._client.ask(
                message=message,
                user_id=user_id,
                session_id=session_id,
                history=history,
                mode=mode,
                trade_snapshot=snapshot,
            )
            if reply and isinstance(reply.get("questions"), list):
                questions = [str(q) for q in reply["questions"]]
                tip = str(reply.get("coaching_tip") or "")
                disclaimer = str(reply.get("disclaimer") or "")
                text = "\n".join([*questions, "", f"Bài tập: {tip}", "", disclaimer])
        if text is None:
            async for chunk in self._deterministic.stream(
                user_id=user_id,
                message=message,
                session_id=session_id,
                mode=mode,
                snapshot=snapshot,
            ):
                yield chunk
            return
        async for chunk in _chunk_text(text):
            yield chunk


async def _db_history_provider(user_id: str) -> list[dict[str, str]]:
    """Nguồn history mặc định: 12 tin gần nhất từ bảng mentor_messages."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return []
    try:
        async with async_session_factory() as db:
            rows = await recent_messages(db, user_uuid, LLM_HISTORY_LIMIT)
            return to_llm_history(rows)
    except Exception:  # noqa: BLE001 - DB lỗi → LLM chạy không history
        logger.warning("Không tải được lịch sử mentor từ DB", exc_info=True)
        return []


async def save_exchange_safe(
    user_id: str,
    session_id: str,
    message: str,
    reply_text: str,
    *,
    mode: str = "socratic",
    metadata: dict[str, Any] | None = None,
) -> None:
    """Lưu 1 lượt hỏi-đáp vào mentor_messages; mọi lỗi chỉ log, không ảnh hưởng chat."""
    try:
        async with async_session_factory() as db:
            save_kwargs: dict[str, Any] = {}
            if metadata:
                save_kwargs["metadata_json"] = metadata
            await save_exchange(
                db,
                user_id=user_id,
                session_id=session_id,
                user_message=message,
                mentor_reply=reply_text,
                focus=detect_focus(message).value,
                prompt_version=_DETERMINISTIC_PROMPT_VERSION,
                mode=mode,
                **save_kwargs,
            )
    except Exception:  # noqa: BLE001 - persistence phải tuyệt đối không hỏng phiên
        logger.warning("Lưu lịch sử mentor thất bại (session=%s)", session_id, exc_info=True)


mentor_stream_provider = HybridMentorStream(history_provider=_db_history_provider)


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
    rate_limit_enabled: bool | None = None,
) -> Callable[[WebSocket], Any]:
    manager = manager or connection_manager
    stream_provider = cast(Any, provider or mentor_stream_provider)
    auth = auth_provider or get_ws_user
    heartbeat = (
        heartbeat_seconds if heartbeat_seconds is not None else settings.ws_heartbeat_seconds
    )
    do_rate_limit = (
        rate_limit_enabled
        if rate_limit_enabled is not None
        else settings.mentor_rate_limit_enabled
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
        mode: str,
        mode_snapshot: dict[str, Any] | None,
        session: _AskSession,
    ) -> None:
        chunks: list[str] = []
        try:
            if session.cancelled:
                return
            if not await manager.send(
                conn,
                build_message(
                    "mentor_start",
                    {"session_id": session_id, "user_id": user_id, "mode": mode},
                ),
            ):
                return
            async for chunk in stream_provider.stream(
                user_id=user_id,
                message=message,
                session_id=session_id,
                mode=mode,
                snapshot=mode_snapshot,
            ):
                if session.cancelled:
                    return
                chunks.append(chunk)
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
            # Lưu hội thoại (A3.2): chỉ khi stream hoàn tất trọn vẹn — phiên bị
            # cancel giữa chừng không ghi reply dở dang vào lịch sử/LLM.
            if len(chunks) > 0 and not session.cancelled:
                metadata = None
                if mode_snapshot:
                    try:
                        snap = mode_snapshot.get("_trade_snapshot")
                        ts_meta = None
                        if snap is not None:
                            ts_meta = {
                                "symbol": snap.selected_symbol,
                                "total_nav": (
                                    float(snap.total_nav)
                                    if snap.total_nav is not None
                                    else None
                                ),
                                "cash_balance": (
                                    float(snap.cash_balance)
                                    if snap.cash_balance is not None
                                    else None
                                ),
                                "holdings": len(snap.holdings),
                                "open_orders": len(snap.open_orders),
                                "allocation_pct": (
                                    snap.holdings[0]["allocation_pct"]
                                    if snap.holdings
                                    and snap.holdings[0].get("allocation_pct") is not None
                                    else None
                                ),
                                "pnl_pct": (
                                    snap.holdings[0]["pnl_pct"]
                                    if snap.holdings
                                    and snap.holdings[0].get("pnl_pct") is not None
                                    else None
                                ),
                            }
                        metadata = to_metadata_dict(
                            mode=mode,
                            prompt_version=_DETERMINISTIC_PROMPT_VERSION,
                            focus=detect_focus(message).value,
                            trade_snapshot=ts_meta,
                        )
                    except Exception:  # noqa: BLE001 - metadata là audit phụ
                        logger.warning(
                            "Dựng metadata mentor lỗi (session=%s)", session_id, exc_info=True
                        )
                await save_exchange_safe(
                    user_id,
                    session_id,
                    message,
                    "".join(chunks),
                    mode=mode,
                    metadata=metadata,
                )
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
                # Mode hợp lệ — mặc định socratic (kế hoạch 3 chế độ v2.0).
                # Client có thể gửi ở top-level (``mode``/``selected_symbol``) hoặc
                # gộp trong ``trade_context`` (plan v2.0 mục 5.3.1) — hỗ trợ cả hai.
                trade_context = payload.get("trade_context")
                trade_ctx = trade_context if isinstance(trade_context, dict) else {}
                raw_mode = payload.get("mode") or trade_ctx.get("mode") or "socratic"
                mode = raw_mode if raw_mode in _MENTOR_MODES else "socratic"
                selected_symbol = payload.get("selected_symbol") or trade_ctx.get("selected_symbol")
                if selected_symbol is not None and not isinstance(selected_symbol, str):
                    selected_symbol = None

                # Rate limit per-user (GĐ 1.6): trả lỗi rõ ràng, KHÔNG tạo task.
                if do_rate_limit and not await check_rate(
                    f"mentor:{user_id}:minute",
                    max_attempts=settings.mentor_rate_limit_per_minute,
                    window_seconds=60,
                ):
                    await manager.send(
                        conn,
                        build_message(
                            "mentor_error",
                            {
                                "session_id": session_id,
                                "code": "rate_limited",
                                "message": (
                                    "Bạn đã gửi quá nhiều câu liên tiếp. Hãy chờ một "
                                    "chút rồi thử lại."
                                ),
                            },
                        ),
                    )
                    return
                if do_rate_limit and not await check_rate(
                    f"mentor:{user_id}:day",
                    max_attempts=settings.mentor_rate_limit_per_day,
                    window_seconds=86400,
                ):
                    await manager.send(
                        conn,
                        build_message(
                            "mentor_error",
                            {
                                "session_id": session_id,
                                "code": "daily_limit",
                                "message": (
                                    "Bạn đã dùng hết lượt hỏi mentor hôm nay. Quay lại "
                                    "vào ngày mai nhé."
                                ),
                            },
                        ),
                    )
                    return

                # Trade snapshot từ DB (Chế độ 3) — nguồn chân lý, không tin client.
                mode_snapshot = None
                if mode in ("trade_now", "plan"):
                    try:
                        async with async_session_factory() as db:
                            snap = await trade_snapshot_service.get_snapshot(
                                db, user_id, selected_symbol
                            )
                            mode_snapshot = {
                                "_trade_snapshot": snap,
                                "text": snap.to_prompt_text(),
                            }
                    except Exception:  # noqa: BLE001 - snapshot lỗi → vẫn mentor an toàn
                        logger.warning(
                            "Không lấy được trade snapshot (user=%s)", user_id, exc_info=True
                        )

                prev = active_sessions.get(conn.connection_id)
                generation = (prev.generation + 1) if prev is not None else 1
                session = _AskSession(generation=generation)
                if prev is not None and prev.task is not None and not prev.task.done():
                    # Không await task cũ (tránh block reader khi task cũ mắc kẹt ở
                    # network/LLM): cờ cancelled + task.cancel() đủ để nó tự dừng.
                    prev.cancelled = True
                    prev.task.cancel()
                task = asyncio.create_task(
                    _run_ask(
                        conn,
                        str(user.id),
                        session_id,
                        message,
                        mode,
                        mode_snapshot,
                        session,
                    ),
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
