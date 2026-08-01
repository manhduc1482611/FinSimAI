"""Backplane — lớp phát tán multi-worker dựa trên Redis Pub/Sub.

Vấn đề: ``ConnectionManager`` lưu kết nối trong RAM của từng process. Khi chạy Uvicorn
nhiều worker (``uvicorn --workers N``) hoặc nhiều replica Kubernetes, một broadcast
in-process chỉ tới được client của chính worker đó, không bao giờ chạm tới client
nằm ở worker khác.

Giải pháp:
- Worker phát (publisher) đẩy message tới client local của chính nó NGAY LẬP TỨC
  (không chờ echo từ Redis — tránh phụ thuộc tuyệt đối vào độ trễ Pub/Sub), đồng thời
  publish envelope ``{"room", "payload", "sender"}`` lên channel ``finsim:ws:<room>``
  đúng 1 lần cho các worker khác.
- Đăng ký ĐỘNG (dynamic subscription): worker chỉ subscribe channel của những room
  đang có ít nhất 1 client local (theo dõi qua ``ConnectionManager``). Không dùng
  ``psubscribe("finsim:ws:*")`` vì pattern-subscribe gửi MỌI message tới MỌI worker —
  với 10 worker × 5.000 room, một tick ``prices:ACB`` bắt 9 worker khác phải giải mã
  JSON + gọi ``broadcast_local_room`` dù không có client nào đăng ký ACB. Dynamic
  subscription cắt bỏ chi phí CPU/event-loop vô ích đó; subscribe theo đúng channel
  (exact channel, không pattern) qua hook ``on_room_changed`` khi room có client đầu
  tiên / rỗng.
- Message do chính worker phát (``sender`` trùng ``_publisher_id``) bị bỏ qua — vì nó
  đã tự broadcast local rồi → mỗi worker nhận đúng 1 bản, không trùng lặp.

Recovery (chống "một đi không trở lại"):
- Khi Redis không khả dụng, Backplane rơi về local-only và chạy một task nền dò lại
  Redis (ping + re-subscribe các room đang có client) theo Exponential Backoff. Redis
  quay lại → tự phục hồi Pub/Sub mà không cần restart dịch vụ. Nếu không có Redis,
  local-only vẫn đúng cho mọi client trong 1 process (dev/test/1 instance).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from typing import Any

from core.cache import get_cache

from realtime.connection_manager import ConnectionManager, connection_manager

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL_PREFIX = "finsim:ws:"
# Giữ lại để mô tả vùng channel (log/ghi chú); không dùng pattern-subscribe.
DEFAULT_ROOM_CHANNEL_PATTERN = DEFAULT_CHANNEL_PREFIX + "*"

# Backoff dò lại Redis: 1s → 2s → 4s → ... → 30s (cap), mỗi lần sleep nhân
# jitter ±50% để N worker không cùng nhịp (xem ``Backplane._jittered``).
RETRY_INITIAL_DELAY = 1.0
RETRY_MAX_DELAY = 30.0

# Endpoint REST mà client có thể fallback khi realtime bị degraded (mất Redis).
RESYNC_HINTS = [
    "/api/v1/companies",
    "/api/v1/trades/orders",
    "/api/v1/trades/portfolio",
]


class Backplane:
    """Relay Redis Pub/Sub giữa các worker của WebSocket layer.

    Subscribe theo room đang có client local (dynamic), exact channel — tránh
    pattern-subscribe gửi mọi message tới mọi worker.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        *,
        channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
        retry_initial: float = RETRY_INITIAL_DELAY,
        retry_max: float = RETRY_MAX_DELAY,
    ) -> None:
        self.manager = manager
        self.channel_prefix = channel_prefix
        self._pubsub: Any = None
        self._task: asyncio.Task | None = None
        self._retry_task: asyncio.Task | None = None
        self._stopped = False
        self._fallback_mode = False
        # Trạng thái realtime đã thông báo (None = chưa thông báo): dùng để chỉ phát
        # ``feed_status`` khi CHUYỂN trạng thái, không spam lặp mỗi tick.
        self._status: str | None = None
        self._retry_initial = retry_initial
        self._retry_max = retry_max
        # Các channel đang subscribe (chỉ những room có client local).
        self._subscribed: set[str] = set()
        # Serialize mọi thao tác subscribe/unsubscribe: join/leave chạy đan xen tốc
        # độ cao, lệnh I/O Redis có thể hoàn thành lệch thứ tự → lock để room không
        # bị "lệch trạng thái" (subscribe nhưng đã rỗng client local, hay ngược lại).
        self._sub_lock = asyncio.Lock()
        # Định danh worker: subscriber bỏ qua message do chính mình publish
        # (vì publisher đã tự broadcast local) để không gửi trùng.
        self._publisher_id = uuid.uuid4().hex

    # ── Helpers ──────────────────────────────────────────────────
    def _channel(self, room: str) -> str:
        return f"{self.channel_prefix}{room}"

    def _room_from_channel(self, channel: Any) -> str | None:
        if not channel or not isinstance(channel, str):
            return None
        if not channel.startswith(self.channel_prefix):
            return None
        room = channel[len(self.channel_prefix) :]
        return room if room else None

    def _envelope(self, room: str, payload: str, *, reliable: bool = False) -> str:
        return json.dumps(
            {
                "room": room,
                "payload": payload,
                "sender": self._publisher_id,
                # QoS của tin để worker nhận relay đúng kênh (reliable → không drop).
                "qos": "reliable" if reliable else "best_effort",
            },
            ensure_ascii=False,
        )

    # ── Trạng thái realtime (mục 5 — degraded mode) ──────────────
    @property
    def status(self) -> str:
        """Trạng thái hiện tại của cầu nối Redis (cho welcome frame của client mới)."""
        return self._status or ("degraded" if self._fallback_mode else "live")

    async def _set_status(
        self,
        status: str,
        reason: str,
        *,
        resync_via: list[str] | None = None,
    ) -> None:
        """Broadcast ``feed_status`` khi trạng thái THAY ĐỔI (không spam lặp lại).

        Redis là SPOF của lớp realtime: mất Redis → leader election fail-closed làm
        feed đóng băng 5-10s mà client không hay biết. Tín hiệu này giúp client biết
        ngay nên fallback qua REST thay vì "chết lặng".
        """
        if self._status == status:
            return
        self._status = status
        try:
            await self.manager.broadcast_status(status, reason, resync_via=resync_via)
        except Exception:
            logger.exception("Failed to broadcast WS feed status")

    # ── Lifecycle ────────────────────────────────────────────────
    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stopped = False
        self._fallback_mode = False
        self._subscribed.clear()
        pubsub: Any = None
        try:
            client = get_cache()
            pubsub = client.pubsub()
            await self._activate_pubsub(pubsub)
        except Exception:
            logger.warning(
                "Redis Pub/Sub unavailable — backplane chạy local-only, sẽ thử lại",
                exc_info=True,
            )
            if pubsub is not None:
                await self._close_pubsub(pubsub)
            self._pubsub = None
            self._fallback_mode = True
            await self._set_status(
                "degraded", "realtime_bridge_down", resync_via=RESYNC_HINTS
            )
            self._schedule_reconnect()
            return
        logger.info("WS backplane started (%d room channel(s))", len(self._subscribed))

    async def stop(self) -> None:
        self._stopped = True
        for task in (self._task, self._retry_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self._retry_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass
            self._pubsub = None
        self._subscribed.clear()

    # ── Dynamic subscription (chỉ room có client local) ──────────
    async def on_room_changed(self, room: str, count: int) -> None:
        """Hook do ``ConnectionManager`` gọi khi room có client vào/rời.

        Count > 0 → đảm bảo worker này subscribe channel của room (nhận tin từ
        worker khác). Count == 0 → unsubscribe để không còn bắt tin thừa.

        Mọi thao tác sub/unsub được serialize bằng ``_sub_lock`` và quyết định
        luôn dựa trên SỐ CLIENT HIỆN TẠI (đọc lại từ manager) chứ không phải
        ``count`` truyền vào: khi join/leave chạy đan xen tốc độ cao, một sự kiện
        "rỗng" cũ không thể unsubscribe nhầm room vừa có client mới (hay để lọt
        subscribe cho room đã rỗng).
        """
        if self._pubsub is None or self._fallback_mode:
            return
        channel = self._channel(room)
        async with self._sub_lock:
            count = self.manager.connection_count(room)
            try:
                if count > 0:
                    if channel not in self._subscribed:
                        await self._pubsub.subscribe(channel)
                        self._subscribed.add(channel)
                else:
                    if channel in self._subscribed:
                        await self._pubsub.unsubscribe(channel)
                        self._subscribed.discard(channel)
            except Exception:
                logger.warning(
                    "WS backplane room sub/unsub failed (room=%s)", room, exc_info=True
                )

    # ── Recovery (dò lại Redis theo exponential backoff) ─────────
    def _schedule_reconnect(self) -> None:
        if self._stopped:
            return
        if self._retry_task is not None and not self._retry_task.done():
            return
        self._retry_task = asyncio.create_task(
            self._reconnect_loop(), name="ws-backplane-reconnect"
        )

    @staticmethod
    def _jittered(delay: float) -> float:
        """Nhiễu ngẫu nhiên ±50% quanh backoff cơ bản (chống Thundering Herd).

        N worker rơi Redis cùng lúc, nếu cùng dãy 1s→2s→4s→...→30s sẽ ping Redis
        đồng loạt đúng nhịp nhau khi nó quay lại. Jitter tách pha để các worker
        dò lại lệch nhau — giảm xung CPU/Redis lúc phục hồi.
        """
        return delay * random.uniform(0.5, 1.5)

    async def _reconnect_loop(self) -> None:
        delay = self._retry_initial
        while not self._stopped and self._fallback_mode:
            await asyncio.sleep(self._jittered(delay))
            if self._stopped or not self._fallback_mode:
                break
            try:
                client = get_cache()
                await client.ping()
                pubsub = client.pubsub()
            except Exception:
                delay = min(delay * 2, self._retry_max)
                logger.warning("Redis reconnect attempt failed — retry in %.1fs", delay)
                continue
            if self._stopped:
                await self._close_pubsub(pubsub)
                break
            try:
                await self._activate_pubsub(pubsub)
            except Exception:
                # Re-subscribe/activate thất bại (Redis rớt lại giữa chừng): đóng
                # pubsub mới, quay về local-only và thử lại — không để rò handle.
                self._fallback_mode = True
                await self._close_pubsub(pubsub)
                delay = min(delay * 2, self._retry_max)
                continue
            self._fallback_mode = False
            logger.info(
                "WS backplane reconnected to Redis (%d room channel(s))",
                len(self._subscribed),
            )
            await self._set_status("live", "realtime_restored")
            break

    async def _activate_pubsub(self, pubsub: Any) -> None:
        """Cài pubsub mới: dừng listener cũ + đóng pubsub cũ, rồi mới subscribe lại.

        Chống hai rò rỉ khi reconnect nhiều lần:
        (1) handle PubSub cũ bị gán đè mà không ``aclose()`` → tích tụ trong event
            loop khi mạng chập chờn;
        (2) listener cũ vẫn SỐNG (publish lỗi nhưng subscribe không chết) → sau khi
            cài pubsub mới sẽ có HAI listener cùng relay → message bị trùng.
        """
        # 1) Dừng listener cũ (nếu còn sống).
        old_task = self._task
        self._task = None
        if old_task is not None and not old_task.done():
            old_task.cancel()
            try:
                await old_task
            except asyncio.CancelledError:
                pass
        # 2) Đóng pubsub cũ.
        old_pubsub = self._pubsub
        self._pubsub = pubsub
        if old_pubsub is not None:
            await self._close_pubsub(old_pubsub)
        if self._stopped:
            await self._close_pubsub(self._pubsub)
            self._pubsub = None
            return
        # 3) Subscribe lại room đang có client (serialize với on_room_changed).
        async with self._sub_lock:
            channels = [self._channel(room) for room in self.manager.rooms_with_clients()]
            if channels:
                await self._pubsub.subscribe(*channels)
            self._subscribed = set(channels)
        # 4) Chạy listener mới.
        self._task = asyncio.create_task(self._listen(), name="ws-backplane")

    @staticmethod
    async def _close_pubsub(pubsub: Any) -> None:
        try:
            await pubsub.aclose()
        except Exception:
            pass

    # ── Publish (phía worker phát) ───────────────────────────────
    async def publish_room(
        self,
        room: str,
        payload: str,
        *,
        reliable: bool = False,
    ) -> int:
        """Publish message (đã serialize) tới mọi worker.

        ``reliable=True`` → client local nhận qua kênh reliable (không drop, tràn →
        đóng kết nối để resync) và envelope mang ``qos=reliable`` để worker khác relay
        đúng kênh. Mặc định ``False`` (best-effort — tick giá có thể drop).

        Trả về số client local đã nhận. Worker phát broadcast local NGAY (không chờ
        echo Pub/Sub) — client kết nối thẳng tại worker này không bị ảnh hưởng bởi
        độ trễ/nghẽn của Redis Pub/Sub. Các worker khác nhận qua subscriber.
        """
        if reliable:
            local_sent = self.manager.broadcast_local_room_reliable(room, payload)
        else:
            local_sent = self.manager.broadcast_local_room(room, payload)
        if self._fallback_mode:
            return local_sent
        try:
            client = get_cache()
            await client.publish(
                self._channel(room), self._envelope(room, payload, reliable=reliable)
            )
        except Exception:
            logger.warning(
                "Redis publish failed → rơi local-only + dò lại (room=%s)",
                room,
                exc_info=True,
            )
            self._fallback_mode = True
            await self._set_status(
                "degraded", "realtime_bridge_down", resync_via=RESYNC_HINTS
            )
            self._schedule_reconnect()
        return local_sent

    async def publish_user(
        self,
        user_id: str,
        payload: str,
        *,
        reliable: bool = False,
    ) -> int:
        return await self.publish_room(
            self.manager.user_room(user_id), payload, reliable=reliable
        )

    # ── Subscriber (mọi worker) ──────────────────────────────────
    async def _listen(self) -> None:
        try:
            async for message in self._pubsub.listen():
                if self._stopped:
                    break
                if message.get("type") not in ("message", "pmessage"):
                    continue
                channel = message.get("channel")
                data = message.get("data")
                room = self._room_from_channel(channel)
                if room is None or not data:
                    continue
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                self._relay(room, data)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WS backplane listener stopped — sẽ dò lại Redis")
            self._fallback_mode = True
            await self._set_status(
                "degraded", "realtime_bridge_down", resync_via=RESYNC_HINTS
            )
            self._schedule_reconnect()

    def _relay(self, room: str, data: str) -> None:
        """Giải nén envelope; bỏ qua message do chính worker này phát."""
        sender = None
        payload = data
        reliable = False
        try:
            envelope = json.loads(data)
            if isinstance(envelope, dict) and isinstance(envelope.get("payload"), str):
                sender = envelope.get("sender")
                payload = envelope["payload"]
                reliable = envelope.get("qos") == "reliable"
        except (json.JSONDecodeError, TypeError):
            pass  # message legacy (chưa có envelope): coi toàn bộ là payload
        if sender == self._publisher_id:
            return
        if reliable:
            # Tin giao dịch: không drop — tràn → đóng kết nối để client resync.
            self.manager.broadcast_local_room_reliable(room, payload)
        else:
            self.manager.broadcast_local_room(room, payload)


backplane = Backplane(connection_manager)
