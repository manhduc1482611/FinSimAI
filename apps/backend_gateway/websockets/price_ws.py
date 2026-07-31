"""Broadcast biến động giá cổ phiếu real-time theo chu kỳ thời gian nén.

``PriceBroadcaster`` là nguồn dữ liệu phát (broadcast) độc lập với DB: nó chạy một
task nền, định kỳ lấy snapshot giá từ ``price_source``, so với trạng thái đã phát
gần nhất, rồi đẩy từng ``price_tick`` tới phòng ``prices:{SYMBOL}`` (và ``prices:all``).

Khi chạy multi-worker (Redis hoạt động):
- Vòng phát dùng leader election (lock Redis ``finsim:ws:leader:price``) — chỉ đúng
  1 worker đọc DB + phát tick, không lãng phí N worker cùng SELECT mỗi giây, không
  phát trùng message.
- Tick được publish qua Backplane (Redis Pub/Sub) → mọi worker đẩy xuống client local.
- Leader ghi snapshot giá vào Redis cache để worker bất kỳ trả ``price_snapshot``
  cho client mới subscribe mà không cần đọc DB.
- Mất Redis → leader election fail-closed (không worker nào tự xưng leader) để tránh
  split-brain: N worker cùng SELECT DB + phát trùng tin. Chỉ khi chạy 1 instance
  (``ws_local_mode=true``) worker mới tự phát độc lập với Redis.

Client subscribe bằng message:
    {"action": "subscribe", "channels": ["prices:ACB", "prices:*"]}
    {"action": "unsubscribe", "channels": ["prices:ACB"]}
    {"action": "snapshot"}          # lấy lại trạng thái giá hiện tại
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from core.cache import get_cache
from core.config import settings
from core.database import async_session_factory
from fastapi import WebSocket
from models.company import Company
from sqlalchemy import select

from websockets.connection_manager import (
    ClientConnection,
    ConnectionManager,
    build_message,
    connection_manager,
)
from websockets.leader import LeaderElection
from websockets.simtime import format_sim_label, real_to_sim_epoch, sim_day_of

logger = logging.getLogger(__name__)

PriceSource = Callable[[], Awaitable[list[dict[str, Any]]]]

PRICE_ROOM_PREFIX = "prices:"
ALL_SYMBOLS_ROOM = "prices:*"


async def default_price_source() -> list[dict[str, Any]]:
    """Lấy snapshot giá của mọi công ty đang hoạt động từ DB."""
    async with async_session_factory() as session:
        rows = (
            await session.execute(
                select(
                    Company.id,
                    Company.symbol,
                    Company.name,
                    Company.sector,
                    Company.current_price,
                    Company.market_cap,
                    Company.updated_at,
                ).where(Company.is_active.is_(True))
            )
        ).all()

    return [
        {
            "company_id": r[0],
            "symbol": r[1],
            "name": r[2],
            "sector": r[3],
            "price": float(r[4]),
            "market_cap": float(r[5]) if r[5] is not None else None,
            "updated_at": r[6],
        }
        for r in rows
    ]


class PriceBroadcaster:
    """So khớp snapshot → tick, phát tới phòng theo mã cổ phiếu."""

    def __init__(
        self,
        manager: ConnectionManager,
        price_source: PriceSource | None = None,
        *,
        tick_seconds: float | None = None,
        sim_anchor: datetime | None = None,
        leader_lock_key: str | None = None,
        snapshot_key: str | None = None,
        snapshot_ttl: int = 60,
        snapshot_local_ttl: float | None = None,
        local_mode: bool | None = None,
    ) -> None:
        self.manager = manager
        self.price_source = price_source or default_price_source
        self.tick_seconds = (
            tick_seconds if tick_seconds is not None else settings.ws_price_tick_seconds
        )
        self.sim_anchor = sim_anchor or datetime.fromtimestamp(
            settings.ws_sim_anchor_epoch, tz=timezone.utc
        )
        self._task: asyncio.Task | None = None
        self._last_price: dict[str, float] = {}
        self._session: dict[str, dict[str, Any]] = {}
        self._current: dict[str, dict[str, Any]] = {}
        # Leader election fail-closed: chỉ 1 worker đọc DB + phát tick, không lãng
        # phí N worker cùng SELECT mỗi giây, không phát trùng. Mất Redis → không ai
        # tự xưng leader (tránh split-brain). local_mode (1 instance/test) → luôn leader.
        self._leader_lock_key = leader_lock_key or "finsim:ws:leader:price"
        self._leader_token = str(uuid.uuid4())
        self._leader_ttl = max(int(self.tick_seconds * 3), 3)
        self._local_mode = settings.ws_local_mode if local_mode is None else local_mode
        self._election = LeaderElection(
            self._leader_lock_key,
            token=self._leader_token,
            ttl=self._leader_ttl,
            local_mode=self._local_mode,
        )
        self._state_loaded = False
        # Cache snapshot trên Redis để worker bất kỳ phục vụ price_snapshot cho
        # client mới subscribe mà không cần tự đọc DB; leader mới cũng dùng nó để
        # kế thừa trạng thái phiên (open/high/low/prev_close) khi chuyển giao.
        self._snapshot_key = snapshot_key or "finsim:ws:prices:snapshot"
        self._snapshot_ttl = snapshot_ttl
        # Cache RAM ngắn hạn của worker phụ (không phải leader): nạp snapshot từ
        # Redis 1 lần, giữ ``snapshot_local_ttl`` giây — 1.000 client kết nối mới
        # cùng lúc chỉ gây 1 lệnh HGETALL, không phải 1.000 (chống Thundering Herd).
        self.snapshot_local_ttl = (
            snapshot_local_ttl
            if snapshot_local_ttl is not None
            else settings.ws_snapshot_local_cache_ttl_seconds
        )
        self._local_snapshot_cache: dict[str, dict[str, Any]] = {}
        self._local_snapshot_ts = 0.0

    # ── Lifecycle ────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="price-broadcaster")
            logger.info("Price broadcaster started (tick=%.1fs)", self.tick_seconds)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    # ── State ────────────────────────────────────────────────────────
    def current_snapshots(self) -> dict[str, dict[str, Any]]:
        return {symbol: dict(tick) for symbol, tick in self._current.items()}

    # ── Leadership ───────────────────────────────────────────────────
    async def _load_state_from_cache(self) -> None:
        """Kế thừa trạng thái phiên từ Redis khi trở thành leader (failover).

        Leader cũ lưu tick mới nhất (chứa đủ open/high/low/prev_close/sim_day) trong
        snapshot cache. Leader mới tái tạo ``_session``/``_last_price``/``_current``
        từ đó để chỉ số biến động giá không bị reset sai lệch khi chuyển giao.
        """
        cached = await self.fetch_cached_snapshots()
        for symbol, tick in cached.items():
            self._current[symbol] = tick
            self._last_price[symbol] = tick["price"]
            self._session[symbol] = {
                "sim_day": tick["sim_day"],
                "open": tick["open"],
                "high": tick["high"],
                "low": tick["low"],
                "prev_close": tick["prev_close"],
            }
        if cached:
            logger.info(
                "Price leader took over — restored %d session(s) from cache",
                len(cached),
            )

    # ── Snapshot cache (Redis) ───────────────────────────────────────
    async def _persist_snapshots(self) -> None:
        try:
            client = get_cache()
            mapping = {
                symbol: json.dumps(tick, ensure_ascii=False, default=str)
                for symbol, tick in self._current.items()
            }
            if mapping:
                await client.hset(self._snapshot_key, mapping=mapping)
                await client.expire(self._snapshot_key, self._snapshot_ttl)
        except Exception:
            pass  # Redis hỏng: snapshot chỉ phục vụ từ worker leader (in-memory)

    async def fetch_cached_snapshots(self) -> dict[str, dict[str, Any]]:
        try:
            client = get_cache()
            raw = await client.hgetall(self._snapshot_key)
            return {symbol: json.loads(v) for symbol, v in raw.items()}
        except Exception:
            return {}

    async def snapshots_for_delivery(self) -> dict[str, dict[str, Any]]:
        """Snapshot dùng để trả cho client mới subscribe.

        - Leader: dùng state trong RAM (luôn mới nhất).
        - Worker phụ (state rỗng): nạp từ Redis HGETALL nhưng GIỮ trong RAM
          ``snapshot_local_ttl`` giây — 1.000 client kết nối mới trong cùng giây chỉ
          gây 1 lệnh HGETALL thay vì 1.000 (tránh Thundering Herd Redis).
        """
        snapshots = self.current_snapshots()
        if snapshots:
            return snapshots
        now = time.monotonic()
        if self._local_snapshot_cache and now - self._local_snapshot_ts < self.snapshot_local_ttl:
            return dict(self._local_snapshot_cache)
        snapshots = await self.fetch_cached_snapshots()
        if snapshots:
            self._local_snapshot_cache = dict(snapshots)
            self._local_snapshot_ts = now
        return snapshots

    # ── Loop ─────────────────────────────────────────────────────────
    async def _run_loop(self) -> None:
        while True:
            try:
                was_leader = self._election.is_leader
                if await self._election.acquire():
                    if not was_leader or not self._state_loaded:
                        # Leader mới (hoặc lần đầu chạy): kế thừa state từ Redis.
                        await self._load_state_from_cache()
                        self._state_loaded = True
                    snapshots = await self.price_source()
                    if not self._election.is_leader:
                        # Lock có thể HẾT HẠN trong lúc đọc DB (đợt SELECT chậm, GC
                        # pause) và leader khác đã thay thế. KHÔNG tin trạng thái RAM
                        # giữa hai nhịp acquire: nếu không còn leader, bỏ broadcast —
                        # nếu vẫn phát, 2 leader cùng đẩy tick trùng xuống client.
                        logger.warning(
                            "Price leadership lost while reading DB — skip broadcast"
                        )
                    else:
                        await self.process_snapshots(snapshots)
                        await self._persist_snapshots()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Price broadcast tick failed")
            await asyncio.sleep(self.tick_seconds)

    async def process_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tính các tick thay đổi và broadcast. Trả về danh sách tick đã gửi."""
        now = datetime.now(timezone.utc)
        sim_epoch = real_to_sim_epoch(now, self.sim_anchor)
        sim_day = sim_day_of(sim_epoch)

        ticks: list[dict[str, Any]] = []
        for snap in snapshots:
            tick = self._build_tick(snap, sim_epoch, sim_day)
            if tick is not None:
                ticks.append(tick)

        for tick in ticks:
            message = build_message("price_tick", tick)
            await self.manager.broadcast_to_room(
                f"{PRICE_ROOM_PREFIX}{tick['symbol']}", message
            )
            await self.manager.broadcast_to_room(ALL_SYMBOLS_ROOM, message)
        return ticks

    def _build_tick(
        self,
        snap: dict[str, Any],
        sim_epoch: float,
        sim_day: int,
    ) -> dict[str, Any] | None:
        symbol = snap["symbol"]
        price = round(float(snap["price"]), 2)
        session = self._session.get(symbol)

        if session is not None and session["sim_day"] == sim_day:
            # Cùng phiên: chỉ phát tick khi giá thay đổi.
            if self._last_price.get(symbol) == price:
                return None
            session["high"] = max(session["high"], price)
            session["low"] = min(session["low"], price)
        else:
            # Phiên mới (hoặc sim day mới): luôn phát tick kể cả giá đứng yên,
            # để mở phiên với open/high/low mới + prev_close đúng ngày trước.
            session = {
                "sim_day": sim_day,
                "open": price,
                "high": price,
                "low": price,
                "prev_close": self._last_price.get(symbol, price),
            }
            self._session[symbol] = session

        self._last_price[symbol] = price
        prev_close = session["prev_close"]
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 4) if prev_close else 0.0

        tick: dict[str, Any] = {
            "symbol": symbol,
            "company_id": str(snap.get("company_id", "")),
            "name": snap.get("name"),
            "sector": snap.get("sector"),
            "price": price,
            "open": session["open"],
            "high": session["high"],
            "low": session["low"],
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "market_cap": snap.get("market_cap"),
            "sim_day": session["sim_day"],
            "simulated_at": format_sim_label(sim_epoch),
        }
        self._current[symbol] = tick
        return tick


price_broadcaster = PriceBroadcaster(connection_manager)


def _normalize_channels(channels: Any) -> list[str]:
    if not isinstance(channels, list):
        return []
    result: list[str] = []
    for channel in channels:
        if isinstance(channel, str) and channel.startswith(PRICE_ROOM_PREFIX):
            result.append(channel)
    return result


async def _send_snapshot(
    manager: ConnectionManager,
    conn: ClientConnection,
    broadcaster: PriceBroadcaster,
) -> None:
    wants_all = ALL_SYMBOLS_ROOM in conn.rooms
    symbols = {
        room[len(PRICE_ROOM_PREFIX):]
        for room in conn.rooms
        if room.startswith(PRICE_ROOM_PREFIX) and room != ALL_SYMBOLS_ROOM
    }
    if not wants_all and not symbols:
        return

    # Ưu tiên snapshot local (leader); worker phụ dùng cache RAM TTL ngắn nạp từ
    # Redis — tránh mỗi client mới gây 1 lệnh HGETALL và không cần đọc DB.
    snapshots = await broadcaster.snapshots_for_delivery()

    for symbol, tick in snapshots.items():
        if wants_all or symbol in symbols:
            await manager.send(conn, build_message("price_snapshot", tick))


async def _handle_subscribe(
    manager: ConnectionManager,
    conn: ClientConnection,
    action: str,
    channels: Any,
    broadcaster: PriceBroadcaster,
) -> None:
    normalized = _normalize_channels(channels)
    if not normalized:
        await manager.send(
            conn,
            build_message(
                "error",
                {
                    "code": "invalid_channels",
                    "message": "channels phải là list dạng ['prices:SYMBOL', 'prices:*']",
                },
            ),
        )
        return

    for channel in normalized:
        if action == "subscribe":
            await manager.join_room(conn, channel)
        else:
            await manager.leave_room(conn, channel)

    if action == "subscribe":
        await _send_snapshot(manager, conn, broadcaster)

    await manager.send(
        conn,
        build_message(
            "subscribed" if action == "subscribe" else "unsubscribed",
            {"channels": normalized, "active_rooms": sorted(conn.rooms)},
        ),
    )


def create_price_endpoint(
    manager: ConnectionManager | None = None,
    broadcaster: PriceBroadcaster | None = None,
    *,
    heartbeat_seconds: float | None = None,
) -> Callable[[WebSocket], Any]:
    manager = manager or connection_manager
    broadcaster = broadcaster or price_broadcaster
    heartbeat = (
        heartbeat_seconds if heartbeat_seconds is not None else settings.ws_heartbeat_seconds
    )

    async def price_ws_endpoint(websocket: WebSocket) -> None:
        async def on_message(conn: ClientConnection, payload: dict[str, Any]) -> None:
            action = payload.get("action")
            if action in ("subscribe", "unsubscribe"):
                await _handle_subscribe(manager, conn, action, payload.get("channels"), broadcaster)
            elif action == "snapshot":
                await _send_snapshot(manager, conn, broadcaster)
            else:
                await manager.send(
                    conn,
                    build_message("error", {"code": "unknown_action", "action": action}),
                )

        await manager.handle_connection(
            websocket,
            on_message,
            heartbeat_seconds=heartbeat,
        )

    return price_ws_endpoint
