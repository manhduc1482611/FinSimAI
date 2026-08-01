"""Xác thực WebSocket bằng single-use ticket — không lộ JWT trong query param.

Vấn đề (critique vòng 5): client WebSocket không đặt được custom header, thói quen
cũ là truyền ``?token=<JWT>``. JWT đó sẽ nằm nguyên trong URL → rò rỉ vào access log
(Nginx/HAProxy/Cloudflare), lịch sử trình duyệt và APM trace. Ai đọc được log là
"mượn" được phiên của người dùng.

Giải pháp (single-use ticket):
1. Client đăng nhập REST bình thường (JWT trong header ``Authorization: Bearer``),
   rồi gọi ``POST /api/v1/auth/ws-ticket`` → nhận ticket ngẫu nhiên
   (``secrets.token_urlsafe``) sống rất ngắn (``ws_ticket_ttl_seconds``, mặc định
   15s) và chỉ dùng được đúng 1 lần.
2. WS handshake: ``/ws/...?ticket=<ticket>``. Server tiêu thụ ticket nguyên tử
   (``GETDEL`` trên Redis) → lấy user_id → nạp user còn active.
3. Dù ticket có lộ trong log, nó "chết" sau 15s và chỉ tác dụng 1 lần — JWT gốc
   không bao giờ nằm trong URL.

Lưu trữ ticket:
- Chế độ multi-worker (mặc định): Redis ``SET`` khi cấp + ``GETDEL`` khi tiêu thụ
  (nguyên tử, chống replay). Redis hỏng → ``consume`` trả None → từ chối bắt tay
  (1008), fail-closed.
- ``ws_local_mode`` (1 instance / dev / test, không phụ thuộc Redis): lưu trong RAM
  module với TTL — vẫn single-use nhờ ``pop``.

Revalidation giữa phiên (``revalidate_user``):
- Kiểm tra user còn active mỗi chu kỳ heartbeat (chống tài khoản bị khoá/xoá giữa
  phiên). Kết quả cache trong RAM theo user_id với TTL ``ws_revalidate_cache_ttl_seconds``
  (mặc định 60s): 10k client duy trì kết nối không tạo ~333 query/s lên Postgres.
- Lỗi DB → trả ``True`` giữ kết nối, KHÔNG cache kết quả (Postgres chập chờn 1-2s
  không được phép đóng toàn bộ client đồng loạt khi DB quay lại).
- Không còn ``exp`` trong URL nên revalidation chỉ cần bắt "user bị khoá/xoá",
  không cần bắt "token hết hạn giữa phiên" như cách truyền JWT cũ.
"""

from __future__ import annotations

import logging
import secrets
import time
import uuid
from collections import OrderedDict

from core.cache import get_cache
from core.config import settings
from core.database import async_session_factory
from fastapi import WebSocket, status
from models.user import User
from starlette.exceptions import WebSocketException

logger = logging.getLogger(__name__)

TICKET_PREFIX = "finsim:ws:ticket:"

# Cache revalidation: user_id -> (expires_at_monotonic, is_active).
# OrderedDict để evict theo LRU (move_to_end khi truy cập, popitem(last=False) khi
# vượt ngưỡng) — KHÔNG clear() toàn bộ (tránh Thundering Herd: hàng chục nghìn
# kết nối cùng query Postgres ở nhịp heartbeat kế tiếp sau khi cache bị xả sạch).
_revalidate_cache: OrderedDict[str, tuple[float, bool]] = OrderedDict()
_REVALIDATE_CACHE_MAX = 20_000
_REVALIDATE_TRIM_INTERVAL = 60.0
_last_trim: float = 0.0

# Cache user nạp tại bắt tay WS (sau khi ticket hợp lệ): user_id -> (expires, User).
# Chống Thundering Herd Postgres khi rolling restart: N client reconnect cùng lúc, mỗi
# user chỉ phải SELECT 1 lần trong TTL ``ws_user_cache_ttl_seconds`` thay vì N lần.
# User vừa bị khoá được phát hiện muộn nhất sau TTL này — revalidation heartbeat
# (TTL riêng) vẫn kiểm tra lại giữa phiên nên cửa sổ sai sót rất hẹp.
_user_cache: OrderedDict[str, tuple[float, "User"]] = OrderedDict()
_USER_CACHE_MAX = 20_000


class TicketStore:
    """Cấp + tiêu thụ ticket single-use; Redis (GETDEL) hoặc RAM khi ``local_mode``."""

    def __init__(self, *, local_mode: bool | None = None) -> None:
        self._local_mode = settings.ws_local_mode if local_mode is None else local_mode
        self._memory: dict[str, tuple[float, str]] = {}

    async def issue(self, user_id: str, ttl: float | None = None) -> str:
        """Cấp ticket mới. Trả ticket ngẫu nhiên (không mang thông tin user)."""
        ticket = secrets.token_urlsafe(32)
        ttl = settings.ws_ticket_ttl_seconds if ttl is None else ttl
        if self._local_mode:
            self._memory[ticket] = (time.monotonic() + ttl, user_id)
            return ticket
        client = get_cache()
        await client.set(f"{TICKET_PREFIX}{ticket}", user_id, ex=int(ttl))
        return ticket

    async def consume(self, ticket: str) -> str | None:
        """Tiêu thụ ticket 1 lần. Trả user_id, hoặc None nếu thiếu/sai/hết hạn."""
        if self._local_mode:
            entry = self._memory.pop(ticket, None)
            if entry is None:
                return None
            expires_at, user_id = entry
            if time.monotonic() > expires_at:
                return None
            return user_id
        try:
            client = get_cache()
            return await client.getdel(f"{TICKET_PREFIX}{ticket}")
        except Exception:
            # Redis hỏng → không xác minh được ticket → fail-closed (từ chối).
            logger.warning("WS ticket consume failed (Redis unavailable)")
            return None


# Store dùng chung cho toàn bộ process; test có thể gán instance khác (local_mode).
ticket_store = TicketStore()


async def create_ws_ticket(user_id: str) -> str:
    """Cấp single-use ticket cho user — gọi từ REST ``POST /auth/ws-ticket``."""
    return await ticket_store.issue(user_id)


async def consume_ws_ticket(ticket: str) -> str | None:
    """Tiêu thụ ticket 1 lần. Trả user_id hoặc None (thiếu/sai/hết hạn/dùng lại)."""
    return await ticket_store.consume(ticket)


async def _load_active_user(user_id: str) -> User:
    """Nạp user từ DB theo id; raise nếu không tồn tại hoặc bị tạm khóa.

    Kết quả user ACTIVE được cache trong RAM theo user_id (TTL ngắn
    ``ws_user_cache_ttl_seconds``): 5.000 client reconnect cùng lúc sau rolling
    restart không tạo 5.000 SELECT — mỗi user chỉ query DB 1 lần. User không tồn
    tại / bị khoá KHÔNG được cache (bắt ngay lần handshake sau khi được kích hoạt).
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid user id",
        ) from None

    now = time.monotonic()
    entry = _user_cache.get(user_id)
    if entry is not None and entry[0] > now:
        _user_cache.move_to_end(user_id)
        return entry[1]

    try:
        async with async_session_factory() as session:
            user = await session.get(User, user_uuid)
    except Exception:
        # Postgres chập chờn trong lúc handshake: từ chối sạch (1008) để client
        # reconnect có backoff, KHÔNG cache — thay vì văng lỗi DB ra thành 500.
        logger.warning(
            "WS user lookup DB error — fail handshake, client will retry",
            exc_info=True,
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User lookup failed — retry with backoff",
        ) from None

    if user is None or not user.is_active:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User not found or inactive",
        )

    ttl = max(settings.ws_user_cache_ttl_seconds, 0.0)
    _user_cache[user_id] = (now + ttl, user)
    _user_cache.move_to_end(user_id)
    while len(_user_cache) > _USER_CACHE_MAX:
        _user_cache.popitem(last=False)
    return user


async def get_ws_user(websocket: WebSocket) -> User:
    """Xác thực bắt tay WebSocket bằng single-use ticket (query param ``?ticket=``).

    Raise ``WebSocketException`` (1008) khi: thiếu ticket, ticket sai/hết hạn/đã
    dùng, hoặc user không tồn tại / bị tạm khóa.
    """
    ticket = websocket.query_params.get("ticket")
    if not ticket:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing ws ticket — POST /api/v1/auth/ws-ticket first",
        )
    user_id = await consume_ws_ticket(ticket)
    if user_id is None:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid or expired ws ticket",
        )
    return await _load_active_user(user_id)


def _trim_cache(now: float) -> None:
    """Dọn cache theo phần: bỏ entry hết hạn, rồi evict LRU nếu vượt ngưỡng.

    KHÔNG ``clear()`` toàn bộ — xả sạch sẽ khiến mọi kết nối cùng query Postgres
    ở nhịp revalidate kế tiếp (Thundering Herd). Thay vào đó chỉ đá những entry
    cũ nhất (LRU), giữ phần lớn cache còn nóng cho lần heartbeat sau.
    """
    expired = [k for k, (expires_at, _) in _revalidate_cache.items() if expires_at <= now]
    for key in expired:
        _revalidate_cache.pop(key, None)
    while len(_revalidate_cache) > _REVALIDATE_CACHE_MAX:
        _revalidate_cache.popitem(last=False)


async def revalidate_user(user_id: str) -> bool:
    """Kiểm tra user còn active giữa phiên (chống tài khoản bị khoá/xoá).

    Trả ``False`` khi kết nối nên bị đóng: user bị xóa hoặc bị khóa
    (``is_active = False``). Kết quả được cache theo user_id trong TTL
    ``ws_revalidate_cache_ttl_seconds`` để không query Postgres trên từng nhịp
    heartbeat của từng kết nối. Cache evict theo LRU + hết hạn (không clear toàn bộ).

    Lỗi DB (không phải ``WebSocketException``) → trả ``True`` giữ kết nối và thử lại
    nhịp sau, KHÔNG cache kết quả: một đợt Postgres chập chờn 1-2s không được phép
    làm toàn bộ client tới chu kỳ heartbeat bị đóng socket đồng loạt.
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        return False

    now = time.monotonic()
    entry = _revalidate_cache.get(user_id)
    if entry is not None and entry[0] > now:
        _revalidate_cache.move_to_end(user_id)
        return entry[1]

    try:
        async with async_session_factory() as session:
            user = await session.get(User, user_uuid)
        active = user is not None and user.is_active
    except Exception:
        # Postgres chập chờn (timeout / connection pool cạn / asyncpg restart):
        # KHÔNG đóng kết nối và KHÔNG cache kết quả — trả True giữ phiên, nhịp
        # heartbeat sau sẽ thử lại. Nếu cache âm (False) ở đây, hàng chục nghìn
        # kết nối dùng chung user sẽ bị đóng đồng loạt ngay khi DB quay lại.
        logger.warning(
            "WS revalidation DB error — giữ kết nối, thử lại nhịp sau", exc_info=True
        )
        return True

    ttl = max(settings.ws_revalidate_cache_ttl_seconds, 0.0)
    _revalidate_cache[user_id] = (now + ttl, active)
    _revalidate_cache.move_to_end(user_id)

    global _last_trim
    if (
        len(_revalidate_cache) > _REVALIDATE_CACHE_MAX
        or now - _last_trim >= _REVALIDATE_TRIM_INTERVAL
    ):
        _trim_cache(now)
        _last_trim = now
    return active
