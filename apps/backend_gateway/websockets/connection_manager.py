"""ConnectionManager — quản lý kết nối WebSocket, phòng chat và nhóm pub/sub.

Kiến trúc:
- Mỗi kết nối client có HAI ``asyncio.Queue`` outbound (bounded) + một writer task:
  * ``queue`` (best-effort): tick giá, snapshot, control — drop-oldest khi client đọc
    chậm (tin cũ nhất bị loại bỏ để bảo vệ toàn bộ server khỏi backpressure).
  * ``reliable_queue`` (QoS cao): trade fill / order update / notification — KHÔNG bao
    giờ bị drop; nếu queue đầy, kết nối bị đóng (1011) để client reconnect + resync
    qua REST. Không có "mất tin giao dịch thầm lặng".
  * Writer luôn gửi reliable trước, rồi mới đến best-effort.
- "Phòng" (room) đóng vai trò nhóm pub/sub: ``join_room`` / ``leave_room`` /
  ``broadcast_to_room``. Tin cá nhân dùng phòng đặc biệt ``user:{user_id}``.
- Khi một ``Backplane`` (Redis Pub/Sub) được attach, mọi ``broadcast_to_room`` được
  chuyển qua Redis: worker phát tự broadcast local ngay cho client của chính mình,
  đồng thời publish message lên Redis cho các worker khác (mỗi worker có subscriber
  riêng nhận và đẩy xuống client local; message do chính worker phát bị bỏ qua để
  không trùng). Nhờ vậy broadcast hoạt động đúng khi chạy nhiều worker
  (``uvicorn --workers N``) hoặc nhiều replica Kubernetes, thay vì chỉ trong RAM của
  một process đơn lẻ.
- JSON của một message chỉ được serialize đúng 1 lần trước khi rải tới N client
  (tránh đốt CPU khi broadcast 1 tick cho 1.000+ client trong cùng một vòng lặp).

Trạng thái realtime:
- ``broadcast_status`` gửi frame ``feed_status`` tới MỌI kết nối local (không qua
  backplane) để client biết feed đang ``live``/``degraded`` và resync qua REST khi
  Redis (SPOF của lớp realtime) mất kết nối — không để client "chết lặng" 5-10s.
- ``realtime_status`` được nhúng vào frame ``welcome`` để client mới biết trạng
  thái nguồn ngay khi mở socket.

Heartbeat:
- ``handle_connection`` dùng ``receive_text()`` với timeout làm nhịp heartbeat.
- Client passive (chỉ lắng nghe ``prices:*``, không bao giờ gửi text) KHÔNG bị kick:
  server chỉ gửi keepalive ``{"action": "ping"}``; client nào trả lời sẽ nhận ``pong``.
  Kết nối chết được phát hiện bởi transport (``WebSocketDisconnect``) hoặc bởi writer
  khi gửi thất bại — không dựa vào việc client trả lời JSON text.
- Nếu cấp ``on_validate`` (kiểm tra lại user còn active), nó được gọi
  định kỳ mỗi chu kỳ heartbeat; trả False → kết nối bị đóng (1008). Tránh phiên sống
  lâu với tài khoản đã bị khóa.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from core.config import settings
from fastapi import WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from websockets.backplane import Backplane

logger = logging.getLogger(__name__)

OnMessageHandler = Callable[[Any, dict[str, Any]], Awaitable[None]]
OnConnectionEvent = Callable[[Any], Awaitable[None]]
OnValidate = Callable[[Any], Awaitable[bool]]

DEFAULT_MAX_QUEUE_SIZE = 256

AUTH_REJECT_CLOSE_CODE = 1008
# Close code chuẩn khi server đang rolling restart/graceful shutdown. Client nhận
# code này sẽ reconnect theo exponential backoff + jitter (tránh Thundering Herd lên
# POST /auth/ws-ticket khi N worker cùng khởi động lại). Khác 1001 "going away"
# (không có hẹn tái kết nối ngay).
SERVER_RESTART_CLOSE_CODE = 1012


def build_message(message_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bọc payload vào envelope chuẩn của toàn bộ luồng WebSocket."""
    return {
        "type": message_type,
        "data": data if data is not None else {},
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@dataclass
class ClientConnection:
    websocket: WebSocket
    connection_id: str
    user_id: str | None = None
    rooms: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.monotonic)
    queue: asyncio.Queue = field(init=False)
    reliable_queue: asyncio.Queue = field(init=False)
    writer_task: asyncio.Task | None = field(default=None, init=False)
    dropped_messages: int = field(default=0, init=False)
    reliable_overflow: bool = field(default=False, init=False)
    closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.queue = asyncio.Queue()
        self.reliable_queue = asyncio.Queue()


class ConnectionManager:
    """Đăng ký, dọn dẹp và định tuyến thông điệp giữa các WebSocket client."""

    def __init__(
        self,
        max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE,
        write_timeout: float | None = None,
        reliable_max_queue_size: int | None = None,
    ) -> None:
        self.max_queue_size = max_queue_size
        # Timeout cứng khi ghi socket: client treo (Slowloris / TCP zero-window) bị
        # đóng sau write_timeout giây thay vì giữ writer thành zombie.
        self.write_timeout = (
            write_timeout
            if write_timeout is not None
            else settings.ws_write_timeout_seconds
        )
        # Ngưỡng riêng cho kênh reliable (trade/notification): tràn → đóng kết nối,
        # KHÔNG drop. Mặc định bằng max_queue_size.
        self.reliable_max_queue_size = (
            reliable_max_queue_size
            if reliable_max_queue_size is not None
            else max_queue_size
        )
        self._connections: dict[str, ClientConnection] = {}
        self._rooms: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()
        self._backplane: Backplane | None = None

    # ── Backplane (Redis Pub/Sub, multi-worker) ──────────────────
    def attach_backplane(self, backplane: Backplane) -> None:
        """Bật chế độ phát tán qua Redis: broadcast → publish → mọi worker đẩy local."""
        self._backplane = backplane

    def detach_backplane(self) -> None:
        self._backplane = None

    # ── Introspection ────────────────────────────────────────────
    @property
    def active_connections(self) -> int:
        return len(self._connections)

    def connection_count(self, room: str) -> int:
        return len(self._rooms.get(room, ()))

    def room_connection_ids(self, room: str) -> set[str]:
        return set(self._rooms.get(room, ()))

    def rooms_with_clients(self) -> set[str]:
        """Tập room đang có ít nhất 1 client local — dùng cho dynamic subscription."""
        return {room for room, members in self._rooms.items() if members}

    @staticmethod
    def user_room(user_id: str | uuid.UUID) -> str:
        return f"user:{user_id}"

    def realtime_status(self) -> str:
        """Trạng thái nguồn realtime hiện tại (đưa vào frame ``welcome``).

        Khi Backplane báo ``degraded`` (mất cầu nối Redis — SPOF của lớp realtime)
        trả về ``degraded`` để client mới biết ngay nên resync qua REST; ngược lại
        ``live``.
        """
        backplane = self._backplane
        if backplane is not None:
            status = getattr(backplane, "status", None)
            if status:
                return status
        return "live"

    # ── Lifecycle ────────────────────────────────────────────────
    async def connect(self, websocket: WebSocket, user_id: str | None = None) -> ClientConnection:
        await websocket.accept()
        conn = ClientConnection(
            websocket=websocket,
            connection_id=str(uuid.uuid4()),
            user_id=user_id,
        )
        conn.writer_task = asyncio.create_task(
            self._writer(conn), name=f"ws-writer-{conn.connection_id}"
        )
        async with self._lock:
            self._connections[conn.connection_id] = conn
        logger.info("WS connected: %s (user=%s)", conn.connection_id, user_id)
        return conn

    async def disconnect(
        self,
        conn: ClientConnection,
        *,
        code: int = 1000,
        reason: str = "bye",
    ) -> None:
        if conn.closed:
            return
        conn.closed = True
        if (
            conn.writer_task
            and not conn.writer_task.done()
            and conn.writer_task is not asyncio.current_task()
        ):
            conn.writer_task.cancel()
        rooms = set(conn.rooms)
        async with self._lock:
            self._connections.pop(conn.connection_id, None)
            for room in rooms:
                self._leave_room_unlocked(conn, room)
        for room in rooms:
            await self._notify_room_activity(room)
        try:
            await conn.websocket.close(code=code, reason=reason)
        except Exception:
            pass
        logger.info("WS disconnected: %s", conn.connection_id)

    async def shutdown_connections(
        self,
        code: int = SERVER_RESTART_CLOSE_CODE,
        reason: str = "server restart — reconnect",
    ) -> int:
        """Đóng MỌI kết nối đang hoạt động với close code chuẩn khi server shutdown.

        Gọi trong ``stop_ws_background`` (lifespan shutdown). Client nhận 1012 sẽ biết
        server đang restart có chủ đích → backoff + reconnect, không "chết lặng" rồi
        dồn dập mở socket mới cùng lúc.
        """
        connection_ids = list(self._connections)
        closed = 0
        for connection_id in connection_ids:
            conn = self._connections.get(connection_id)
            if conn is None:
                continue
            try:
                await self.disconnect(conn, code=code, reason=reason)
                closed += 1
            except Exception:
                logger.exception(
                    "WS shutdown disconnect failed for %s", connection_id
                )
        return closed

    async def handle_connection(
        self,
        websocket: WebSocket,
        on_message: OnMessageHandler | None = None,
        *,
        user_id: str | None = None,
        on_connect: OnConnectionEvent | None = None,
        on_disconnect: OnConnectionEvent | None = None,
        on_validate: OnValidate | None = None,
        heartbeat_seconds: float = 30.0,
    ) -> None:
        """Chạy vòng đời trọn vẹn của một kết nối: accept → read/heartbeat → cleanup."""
        conn = await self.connect(websocket, user_id=user_id)
        heartbeat_interval = max(heartbeat_seconds, 0.1)
        last_validate = time.monotonic()
        close_code = 1000
        close_reason = "bye"
        try:
            try:
                if on_connect is not None:
                    await on_connect(conn)
                else:
                    await self.send(
                        conn,
                        build_message(
                            "welcome",
                            {
                                "connection_id": conn.connection_id,
                                "realtime_status": self.realtime_status(),
                            },
                        ),
                    )
            except Exception:
                # Lỗi join room / transient không được làm sập cả kết nối: log và
                # tiếp tục vòng đời (client có thể subscribe lại qua action "subscribe").
                logger.exception("WS on_connect error for %s", conn.connection_id)

            while True:
                # Kiểm tra lại auth định kỳ mỗi chu kỳ heartbeat (kể cả khi client
                # vẫn đang gửi tin): bắt token hết hạn / tài khoản bị khóa giữa phiên.
                if (
                    on_validate is not None
                    and (time.monotonic() - last_validate) >= heartbeat_interval
                ):
                    last_validate = time.monotonic()
                    try:
                        valid = await on_validate(conn)
                    except Exception:
                        # DB chập chờn 1-2s → KHÔNG đóng socket: giữ kết nối và thử
                        # lại ở nhịp heartbeat sau (thay vì đóng hàng loạt client
                        # đúng lúc vào chu kỳ revalidate).
                        logger.warning(
                            "WS %s revalidation error — keep alive, retry next beat",
                            conn.connection_id,
                            exc_info=True,
                        )
                        valid = True
                    if not valid:
                        logger.info(
                            "WS %s revalidation failed — closing", conn.connection_id
                        )
                        close_code = AUTH_REJECT_CLOSE_CODE
                        close_reason = "token expired or user inactive"
                        break

                try:
                    raw = await asyncio.wait_for(
                        websocket.receive_text(), timeout=heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    # Client im lặng (passive listener) KHÔNG bị kick: chỉ gửi
                    # keepalive. Kết nối chết do transport sẽ được writer phát hiện
                    # khi send thất bại, hoặc receive_text trả về disconnect.
                    await self.send(conn, build_message("ping"))
                    continue
                except (WebSocketDisconnect, RuntimeError) as exc:
                    logger.info("WS %s closed by client: %s", conn.connection_id, exc)
                    break

                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    await self.send(
                        conn,
                        build_message(
                            "error",
                            {"code": "invalid_json", "message": "Message must be valid JSON"},
                        ),
                    )
                    continue

                if not isinstance(payload, dict):
                    await self.send(
                        conn,
                        build_message(
                            "error",
                            {"code": "invalid_message", "message": "Message must be a JSON object"},
                        ),
                    )
                    continue

                action = payload.get("action")
                if action == "ping":
                    await self.send(conn, build_message("pong"))
                    continue

                if on_message is not None:
                    try:
                        await on_message(conn, payload)
                    except Exception:
                        logger.exception("WS on_message error for %s", conn.connection_id)
                        await self.send(
                            conn,
                            build_message(
                                "error",
                                {"code": "internal_error", "message": "Failed to process message"},
                            ),
                        )
        finally:
            if on_disconnect is not None:
                try:
                    await on_disconnect(conn)
                except Exception:
                    logger.exception("WS on_disconnect error for %s", conn.connection_id)
            await self.disconnect(conn, code=close_code, reason=close_reason)

    # ── Rooms (pub/sub) ──────────────────────────────────────────
    async def join_room(self, conn: ClientConnection, room: str) -> None:
        async with self._lock:
            self._rooms.setdefault(room, set()).add(conn.connection_id)
            conn.rooms.add(room)
        await self._notify_room_activity(room)

    async def leave_room(self, conn: ClientConnection, room: str) -> None:
        async with self._lock:
            self._leave_room_unlocked(conn, room)
        await self._notify_room_activity(room)

    async def _notify_room_activity(self, room: str) -> None:
        """Báo Backplane thay đổi số client local của room → sub/unsub channel.

        Backplane chỉ subscribe channel của room đang có ít nhất 1 client local
        (dynamic subscription) để không nhận/phải xử lý message của những room
        không có client ở worker này.
        """
        backplane = self._backplane
        if backplane is None:
            return
        try:
            await backplane.on_room_changed(room, self.connection_count(room))
        except Exception:
            logger.exception("Backplane room sync failed for %s", room)

    def _leave_room_unlocked(self, conn: ClientConnection, room: str) -> None:
        room_set = self._rooms.get(room)
        if room_set is None:
            conn.rooms.discard(room)
            return
        room_set.discard(conn.connection_id)
        if not room_set:
            self._rooms.pop(room, None)
        conn.rooms.discard(room)

    # ── Delivery ─────────────────────────────────────────────────
    @staticmethod
    def _serialize(message: dict[str, Any]) -> str:
        return json.dumps(message, ensure_ascii=False, default=str)

    def _enqueue_str(self, conn: ClientConnection, payload: str) -> bool:
        if conn.closed or conn.writer_task is None or conn.writer_task.done():
            return False
        if self.max_queue_size > 0 and conn.queue.qsize() >= self.max_queue_size:
            try:
                conn.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            conn.dropped_messages += 1
        try:
            conn.queue.put_nowait(payload)
        except asyncio.QueueFull:
            return False
        return True

    def _enqueue(self, conn: ClientConnection, message: dict[str, Any]) -> bool:
        return self._enqueue_str(conn, self._serialize(message))

    def _enqueue_reliable_str(self, conn: ClientConnection, payload: str) -> bool:
        """Xếp tin vào kênh reliable (trade/notification) — KHÔNG drop, tràn → đóng.

        Nếu client đọc chậm tới mức reliable queue đầy, đóng kết nối (1011) để
        client reconnect và resync qua REST. Mất kết nối còn hơn "mất tin giao dịch
        thầm lặng": client luôn biết nó không nhận đủ tin và có đường quay lại.
        """
        if conn.closed or conn.writer_task is None or conn.writer_task.done():
            return False
        if (
            self.reliable_max_queue_size > 0
            and conn.reliable_queue.qsize() >= self.reliable_max_queue_size
        ):
            conn.reliable_overflow = True
            self._schedule_overflow_disconnect(conn)
            return False
        try:
            conn.reliable_queue.put_nowait(payload)
        except asyncio.QueueFull:
            conn.reliable_overflow = True
            self._schedule_overflow_disconnect(conn)
            return False
        return True

    def _schedule_overflow_disconnect(self, conn: ClientConnection) -> None:
        try:
            asyncio.get_running_loop().create_task(self._disconnect_on_overflow(conn))
        except RuntimeError:
            pass

    async def _disconnect_on_overflow(self, conn: ClientConnection) -> None:
        try:
            await self.disconnect(
                conn,
                code=1011,
                reason="reliable queue overflow — reconnect to resync",
            )
        except Exception:
            logger.exception(
                "WS disconnect on reliable overflow failed for %s", conn.connection_id
            )

    async def send(self, conn: ClientConnection, message: dict[str, Any]) -> bool:
        return self._enqueue(conn, message)

    async def send_reliable(self, conn: ClientConnection, message: dict[str, Any]) -> bool:
        return self._enqueue_reliable_str(conn, self._serialize(message))

    async def broadcast_to_room(
        self,
        room: str,
        message: dict[str, Any] | str,
    ) -> int:
        """Gửi message (dict hoặc chuỗi JSON đã serialize) tới mọi client trong phòng.

        Khi có backplane: publish lên Redis 1 lần, mọi worker subscriber sẽ broadcast
        local. Khi không có backplane (test / 1 worker): broadcast local trực tiếp.
        """
        payload = message if isinstance(message, str) else self._serialize(message)
        if self._backplane is not None:
            return await self._backplane.publish_room(room, payload)
        return self.broadcast_local_room(room, payload)

    async def broadcast_to_room_reliable(
        self,
        room: str,
        message: dict[str, Any] | str,
    ) -> int:
        """Broadcast kênh reliable: không drop tin, tràn → đóng kết nối (1011)."""
        payload = message if isinstance(message, str) else self._serialize(message)
        if self._backplane is not None:
            return await self._backplane.publish_room(room, payload, reliable=True)
        return self.broadcast_local_room_reliable(room, payload)

    async def broadcast_to_user(
        self,
        user_id: str | uuid.UUID,
        message: dict[str, Any] | str,
    ) -> int:
        return await self.broadcast_to_room(self.user_room(user_id), message)

    async def broadcast_to_user_reliable(
        self,
        user_id: str | uuid.UUID,
        message: dict[str, Any] | str,
    ) -> int:
        return await self.broadcast_to_room_reliable(self.user_room(user_id), message)

    async def broadcast_status(
        self,
        status: str,
        reason: str,
        *,
        resync_via: list[str] | None = None,
    ) -> int:
        """Thông báo trạng thái nguồn realtime (``feed_status``) cho MỌI kết nối local.

        Broadcast local trực tiếp (không qua backplane): đây chính là tín hiệu khi
        Redis — cầu nối giữa các worker — mất, nên không thể dựa vào Redis để lan
        truyền. Mỗi worker tự phát cho client của chính nó khi nó phát hiện mất/khôi
        phục Redis.
        """
        data: dict[str, Any] = {
            "status": status,
            "reason": reason,
            "since": datetime.now(timezone.utc).isoformat(),
        }
        if resync_via:
            data["resync_via"] = resync_via
        return self._broadcast_to_connections(
            set(self._connections), self._serialize(build_message("feed_status", data))
        )

    async def broadcast(self, message: dict[str, Any]) -> int:
        return self._broadcast_to_connections(set(self._connections), self._serialize(message))

    def broadcast_local_room(self, room: str, payload: str) -> int:
        """Broadcast local (trong process) một payload đã serialize tới phòng.

        Được dùng bởi: (1) publisher của Backplane — phát ngay cho client local để
        không chờ echo Pub/Sub; (2) subscriber — relay tin từ worker khác; (3) chế độ
        fallback local-only. Không bao giờ publish lại lên Redis để tránh vòng lặp.
        """
        return self._broadcast_to_connections(self.room_connection_ids(room), payload)

    def broadcast_local_room_reliable(self, room: str, payload: str) -> int:
        """Broadcast local kênh reliable (không drop, tràn → đóng kết nối)."""
        return self._broadcast_reliable_to_connections(
            self.room_connection_ids(room), payload
        )

    def _broadcast_to_connections(self, connection_ids: set[str], payload: str) -> int:
        if not connection_ids:
            return 0
        sent = 0
        for connection_id in connection_ids:
            conn = self._connections.get(connection_id)
            if conn is None:
                continue
            if self._enqueue_str(conn, payload):
                sent += 1
        return sent

    def _broadcast_reliable_to_connections(
        self, connection_ids: set[str], payload: str
    ) -> int:
        if not connection_ids:
            return 0
        sent = 0
        for connection_id in connection_ids:
            conn = self._connections.get(connection_id)
            if conn is None:
                continue
            if self._enqueue_reliable_str(conn, payload):
                sent += 1
        return sent

    # ── Writer ───────────────────────────────────────────────────
    async def _writer(self, conn: ClientConnection) -> None:
        try:
            while True:
                payload = await self._next_payload(conn)
                # Timeout cứng khi ghi socket: nếu client mạng yếu/cố tình ngắt ACK
                # (TCP zero-window), send_text có thể treo vô hạn mà không bắn ngoại
                # lệnh → writer thành zombie giữ RAM. Quá hạn → đóng kết nối.
                await asyncio.wait_for(
                    conn.websocket.send_text(payload), timeout=self.write_timeout
                )
        except asyncio.TimeoutError:
            logger.warning(
                "WS writer send timeout for %s — closing (client stalled)",
                conn.connection_id,
            )
        except asyncio.CancelledError:
            raise
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as exc:
            logger.info("WS writer stopped for %s: %s", conn.connection_id, exc)
        except Exception:
            logger.exception("WS writer error for %s", conn.connection_id)
        finally:
            # Writer chết → dọn dẹp ngay (đánh dấu closed, rời rooms, đóng socket)
            # để tránh Zombie Connection khi reader kẹt ở receive_text.
            if not conn.closed:
                try:
                    await self.disconnect(conn)
                except Exception:
                    logger.exception("WS writer cleanup failed for %s", conn.connection_id)

    async def _next_payload(self, conn: ClientConnection) -> str:
        """Lấy message kế tiếp để ghi socket — luôn ưu tiên kênh reliable.

        Khi chờ, chờ đồng thời trên CẢ HAI queue (nếu chỉ chờ best-effort, tin
        reliable mới đến sẽ không được phát hiện tới khi có tin best-effort hoặc
        timeout). Không bao giờ làm rơi message: nếu cả hai hoàn thành cùng lúc,
        tin reliable được gửi trước còn tin best-effort được nhét ngược về queue.
        """
        while True:
            if not conn.reliable_queue.empty():
                return conn.reliable_queue.get_nowait()
            try:
                return conn.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

            reliable_get = asyncio.ensure_future(conn.reliable_queue.get())
            unreliable_get = asyncio.ensure_future(conn.queue.get())
            try:
                done, _ = await asyncio.wait(
                    {reliable_get, unreliable_get},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in (reliable_get, unreliable_get):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(
                    *(t for t in (reliable_get, unreliable_get) if not t.done()),
                    return_exceptions=True,
                )
            if reliable_get in done and not reliable_get.cancelled():
                if unreliable_get in done and not unreliable_get.cancelled():
                    # Cả hai hoàn thành cùng lúc: không bỏ mất tin best-effort,
                    # nhét ngược về cuối queue (queue vừa rỗng nên không tràn).
                    try:
                        conn.queue.put_nowait(unreliable_get.result())
                    except asyncio.QueueFull:
                        pass
                return reliable_get.result()
            if unreliable_get in done and not unreliable_get.cancelled():
                return unreliable_get.result()


connection_manager = ConnectionManager()
