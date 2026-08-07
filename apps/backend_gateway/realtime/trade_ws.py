"""Đẩy thông báo khớp lệnh mua/bán real-time cho client.

``TradeNotifier`` là kênh đẩy kết quả khớp lệnh:
- Đường Event-Driven (chính): trading_service gọi ``notify_transactions(...)`` ngay
  sau khi ``match_orders`` hoàn tất → message đi qua Backplane (Redis Pub/Sub) tới
  phòng ``user:{user_id}``, mọi worker đều nhận và đẩy tức thì cho client của mình.
- Đường bù phát (catch-up): task nền poll bảng ``transactions`` theo watermark để
  không bỏ sót giao dịch tạo bởi process không gọi ``notify_transactions`` hoặc
  client offline. Khi chạy multi-worker, poll chỉ do leader chạy (lock Redis) nên
  DB không bị N worker cùng hỏi; dedupe qua Redis SETNX để không đẩy trùng.
- Leader election fail-closed: mất Redis → không worker nào tự poll (tránh split-brain
  khi N worker cùng SELECT + đẩy trùng). Watermark được lưu trên Redis để leader mới
  kế thừa đúng vị trí dừng của leader cũ khi chuyển giao (không quét lại từ đầu).
- QoS: trade fill / order update đi qua kênh RELIABLE (``broadcast_to_user_reliable``) —
  không bao giờ bị drop-oldest như tick giá. Nếu client đọc chậm tới mức hàng đợi
  reliable đầy, kết nối bị đóng (1011) để client reconnect + resync qua REST.

Client nhận tin qua kết nối ``/ws/trades`` (bắt buộc single-use ticket — xem
``websockets/auth.py``). Mỗi lần khớp lệnh nhận:
    {"type": "trade_fill", "data": {symbol, side, quantity, price, total, ...}}
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, cast

from core.cache import get_cache
from core.config import settings
from core.database import async_session_factory
from fastapi import WebSocket
from models.company import Company
from models.trade import Transaction
from sqlalchemy import select

from realtime.auth import get_ws_user, revalidate_user
from realtime.connection_manager import (
    ClientConnection,
    ConnectionManager,
    build_message,
    connection_manager,
)
from realtime.leader import LeaderElection

logger = logging.getLogger(__name__)

TransactionRow = dict[str, Any]
# Watermark tổ hợp (created_at, id) để không bỏ sót giao dịch cùng microsecond
# (Postgres `now()` giữ nguyên trong một transaction — hai lệnh trong cùng commit
# match_orders sẽ có created_at trùng nhau).
Watermark = tuple[datetime, str]
PollSource = Callable[[Watermark | None], Awaitable[list[TransactionRow]]]
SymbolResolver = Callable[[Any], Awaitable[dict[str, str] | None]]
# Giải quyết symbol cho cả batch bằng MỘT query (IN) — map company_id → {symbol, name}.
BatchSymbolResolver = Callable[[list[Any]], Awaitable[dict[str, dict[str, str]]]]

DEDUP_PREFIX = "finsim:ws:dedup:trade:"
# Số thứ tự tăng dần THEO KÊNH user (Redis INCR, pipeline cho batch) gắn vào mỗi tin
# trade_fill / order_update. Client dò thấy "nhảy cóc" (seq 1 → 3) tức đã mất tin
# giữa chừng → gọi REST resync thay vì chết lặng. Đây là lưới an toàn phía client cho
# kênh Reliable khi Redis Pub/Sub rớt (Streams là giải pháp giai đoạn 3).
SEQ_PREFIX = "finsim:ws:seq:"
WATERMARK_KEY = "finsim:ws:trade:watermark"


class TradeNotifier:
    """Đẩy tin khớp lệnh tới người dùng sở hữu lệnh."""

    def __init__(
        self,
        manager: ConnectionManager,
        *,
        poll_source: PollSource | None = None,
        symbol_resolver: SymbolResolver | None = None,
        batch_symbol_resolver: SymbolResolver | None = None,
        poll_interval: float | None = None,
        dedup_ttl: int = 300,
        local_mode: bool | None = None,
    ) -> None:
        self.manager = manager
        self._poll_source = poll_source or self._default_poll_source
        self._symbol_resolver = symbol_resolver or self._default_symbol_resolver
        if batch_symbol_resolver is not None:
            self._batch_symbol_resolver: BatchSymbolResolver = cast(
                BatchSymbolResolver, batch_symbol_resolver
            )
        elif symbol_resolver is not None:
            # Resolver tùy chỉnh theo từng giao dịch: batch chỉ là vòng lặp gom
            # (giữ đúng hành vi per-item đã inject, không đụng DB thật).
            async def _per_item_batch(
                company_ids: list[Any],
            ) -> dict[str, dict[str, str]]:
                result: dict[str, dict[str, str]] = {}
                for cid in company_ids:
                    entry = await symbol_resolver(cid)
                    if entry:
                        result[str(cid)] = entry
                return result

            self._batch_symbol_resolver = _per_item_batch
        else:
            self._batch_symbol_resolver = self._default_batch_symbol_resolver
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.ws_trade_poll_seconds
        )
        self._task: asyncio.Task[None] | None = None
        self._watermark: Watermark | None = None
        self._seen_ids: deque[str] = deque(maxlen=2000)
        self._dedup_ttl = dedup_ttl
        # Số thứ tự per-channel dự phòng khi Redis hỏng (fallback cục bộ vẫn tăng dần).
        self._local_seq: dict[str, int] = {}
        # Leader election fail-closed: chỉ 1 worker poll DB; mất Redis → không ai tự
        # xưng leader (tránh split-brain). local_mode (1 instance/test) → luôn leader.
        self._leader_lock_key = "finsim:ws:leader:trade"
        self._leader_token = str(uuid.uuid4())
        self._leader_ttl = (
            max(int(self.poll_interval * 3), 3) if self.poll_interval else 3
        )
        self._local_mode = settings.ws_local_mode if local_mode is None else local_mode
        self._election = LeaderElection(
            self._leader_lock_key,
            token=self._leader_token,
            ttl=self._leader_ttl,
            local_mode=self._local_mode,
        )
        self._state_loaded = False
        # Watermark lưu trên Redis: leader mới kế thừa đúng vị trí dừng khi failover.
        self._watermark_key = WATERMARK_KEY

    # ── Lifecycle ────────────────────────────────────────────────────
    async def start(self) -> None:
        if self.poll_interval is None:
            logger.info("Trade notifier poll disabled — event-driven only")
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="trade-notifier")
            logger.info("Trade notifier started (poll=%.1fs)", self.poll_interval)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    # ── Push API (Event-Driven) ──────────────────────────────────────
    async def notify_transactions(self, transactions: list[TransactionRow]) -> int:
        """Đẩy ngay kết quả khớp lệnh. Trả về số tin đã xếp hàng.

        Message đi qua ``manager.broadcast_to_user``: khi có Backplane thì publish
        lên Redis để mọi worker nhận; khi không thì broadcast local. Giao dịch được
        đánh dấu delivered (Redis SETNX, gom pipeline 1 round-trip) để vòng poll
        catch-up không đẩy trùng.
        """
        return await self._push_transactions(transactions)

    async def _push_transactions(self, transactions: list[TransactionRow]) -> int:
        """Đẩy tin khớp lệnh; CLAIM-FIRST: giành quyền phát (SETNX) TRƯỚC broadcast.

        Giao dịch chỉ được gửi tới client sau khi claim SETNX thành công. Nếu poll
        catch-up (leader) SELECT DB đúng giữa lúc này, nó thấy vệt delivered đã tồn
        tại → bỏ qua → KHÔNG đẩy trùng trade_fill. (Cách cũ broadcast-tồi-mark mở
        cửa sổ race: poll đọc DB giữa send và SETNX → đẩy trùng.)
        """
        enriched: list[tuple[str, TransactionRow, TransactionRow]] = []
        # Batch-resolve symbol: gom toàn bộ company_id còn thiếu của batch vào MỘT
        # query (IN) thay vì N lần `session.get` như cách cũ (chống N+1 khi push
        # nhiều giao dịch cùng lúc từ match_orders).
        missing_ids = [
            tx.get("company_id")
            for tx in transactions
            if not tx.get("symbol") and tx.get("company_id") is not None
        ]
        resolved = await self._batch_resolve(missing_ids)
        for tx in transactions:
            payload = await self._enrich(tx, resolved)
            if payload is None:
                continue
            tx_id = str(tx.get("transaction_id") or "")
            enriched.append((tx_id, tx, payload))

        claimed = await self._claim_delivered(enriched)
        seqs = await self._assign_seqs(claimed)

        sent = 0
        for (tx_id, tx, payload), seq in zip(claimed, seqs):
            if tx_id:
                self._seen_ids.append(tx_id)
            created_at = tx.get("created_at")
            if tx_id and created_at is not None:
                candidate: Watermark = (created_at, tx_id)
                if self._watermark is None or candidate > self._watermark:
                    self._watermark = candidate
            message = build_message("trade_fill", payload)
            message["seq"] = seq
            sent += await self.manager.broadcast_to_user_reliable(
                payload["user_id"], message
            )
        await self._persist_watermark()
        if sent:
            logger.info("Pushed %d trade fill(s)", sent)
        return sent

    async def _claim_delivered(
        self, entries: list[tuple[str, TransactionRow, TransactionRow]]
    ) -> list[tuple[str, TransactionRow, TransactionRow]]:
        """Giành quyền phát từng giao dịch bằng Redis SETNX (pipeline 1 round-trip).

        Chỉ những giao dịch claim thành công (chưa ai phát) được phép broadcast —
        đóng cửa sổ race giữa event-push và poll catch-up. Redis hỏng → coi như
        claim thành công (kênh push chính không bị chặn bởi Redis; ``_seen_ids`` +
        watermark là lưới an toàn trong RAM của leader).
        """
        if not entries:
            return entries
        try:
            client = cast(Any, get_cache())
            pipe = client.pipeline()
            for tx_id, _tx, _payload in entries:
                if tx_id:
                    pipe.set(f"{DEDUP_PREFIX}{tx_id}", "1", nx=True, ex=self._dedup_ttl)
            results = await pipe.execute()
        except Exception:
            return entries
        claimed: list[tuple[str, TransactionRow, TransactionRow]] = []
        result_iter = iter(results)
        for tx_id, tx, payload in entries:
            if tx_id and not next(result_iter):
                continue
            claimed.append((tx_id, tx, payload))
        return claimed

    async def _assign_seqs(
        self, entries: list[tuple[str, TransactionRow, TransactionRow]]
    ) -> list[int]:
        """Cấp số thứ tự tăng dần cho mỗi tin, gom pipeline (1 round-trip/batch).

        Key theo kênh ``user:{user_id}`` (Redis ``INCR``). Redis hỏng → fallback số
        thứ tự trong RAM (vẫn tăng dần, không trùng, nhưng mất tính "toàn cục").
        """
        channels = [f"user:{payload['user_id']}" for _tx_id, _tx, payload in entries]
        try:
            client = cast(Any, get_cache())
            pipe = client.pipeline()
            for channel in channels:
                pipe.incr(f"{SEQ_PREFIX}{channel}")
            results = await pipe.execute()
            return [int(r) for r in results]
        except Exception:
            return self._local_assign_seqs(channels)

    def _local_assign_seqs(self, channels: list[str]) -> list[int]:
        seqs: list[int] = []
        for channel in channels:
            self._local_seq[channel] = self._local_seq.get(channel, 0) + 1
            seqs.append(self._local_seq[channel])
        return seqs

    async def _next_user_seq(self, user_id: str) -> int:
        """Số thứ tự kế tiếp của một kênh (dùng cho ``notify_order_update`` đơn lẻ)."""
        channel = f"user:{user_id}"
        try:
            client = cast(Any, get_cache())
            return int(await client.incr(f"{SEQ_PREFIX}{channel}"))
        except Exception:
            self._local_seq[channel] = self._local_seq.get(channel, 0) + 1
            return self._local_seq[channel]

    async def notify_order_update(self, order: dict[str, Any]) -> int:
        """Đẩy thay đổi trạng thái lệnh (filled/cancelled/rejected/...)."""
        user_id = order.get("user_id")
        if user_id is None:
            return 0
        message = build_message(
            "order_update",
            {
                "order_id": str(order["order_id"]),
                "company_id": str(order.get("company_id") or ""),
                "symbol": order.get("symbol"),
                "status": order.get("status"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "filled_quantity": order.get("filled_quantity"),
                "simulated_at": order.get("simulated_at"),
            },
        )
        message["seq"] = await self._next_user_seq(str(user_id))
        return await self.manager.broadcast_to_user_reliable(user_id, message)

    # ── Watermark trên Redis (kế thừa khi failover) ─────────────────
    async def _persist_watermark(self) -> None:
        if self._watermark is None:
            return
        try:
            client = cast(Any, get_cache())
            wm_ts, wm_id = self._watermark
            await client.set(
                self._watermark_key,
                json.dumps([wm_ts.isoformat(), wm_id], ensure_ascii=False),
                ex=3600,
            )
        except Exception:
            pass  # Redis hỏng: watermark chỉ sống trong RAM worker leader

    async def _load_watermark(self) -> None:
        try:
            client = cast(Any, get_cache())
            raw = await client.get(self._watermark_key)
            if raw:
                ts_str, wm_id = json.loads(raw)
                self._watermark = (datetime.fromisoformat(ts_str), wm_id)
        except Exception:
            pass  # Redis hỏng: watermark = None → poll từ đầu (dedupe SETNX bảo vệ)

    async def _already_delivered_batch(self, tx_ids: list[str]) -> list[bool]:
        """Kiểm tra delivered hàng loạt bằng Redis Pipeline (1 round-trip)."""
        if not tx_ids:
            return []
        try:
            client = cast(Any, get_cache())
            pipe = client.pipeline()
            for tx_id in tx_ids:
                pipe.exists(f"{DEDUP_PREFIX}{tx_id}")
            results = await pipe.execute()
            return [bool(r) for r in results]
        except Exception:
            return [False] * len(tx_ids)

    async def _run_loop(self) -> None:
        while True:
            try:
                was_leader = self._election.is_leader
                if await self._election.acquire():
                    if not was_leader or not self._state_loaded:
                        # Leader mới (hoặc lần đầu chạy): kế thừa watermark từ Redis.
                        await self._load_watermark()
                        self._state_loaded = True
                    await self._poll_once()
                    await self._persist_watermark()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Trade notifier poll failed")
            await asyncio.sleep(self.poll_interval)

    async def _poll_once(self) -> None:
        rows = await self._poll_source(self._watermark)
        to_check: list[str] = []
        to_push: list[TransactionRow] = []
        for row in rows:
            tx_id = str(row.get("transaction_id") or "")
            if not tx_id:
                to_push.append(row)
            elif tx_id not in self._seen_ids:
                to_check.append(tx_id)
                to_push.append(row)

        # Dedupe check gom pipeline (1 round-trip cho toàn bộ batch).
        if to_check:
            delivered = await self._already_delivered_batch(to_check)
            skip = {tx_id for tx_id, is_delivered in zip(to_check, delivered) if is_delivered}
            to_push = [
                row
                for row in to_push
                if str(row.get("transaction_id") or "") not in skip
            ]

        # Watermark luôn vượt qua TOÀN BỘ batch đã đọc (kể cả tin đã delivered):
        # tránh poll lặp lại vĩnh viễn một tin delivered cuối bảng khi không có
        # tin mới nào để đẩy watermark lên. Tin đã delivered không được phát lại
        # (claim-first trong _push_transactions), chỉ dùng để dịch watermark.
        for row in rows:
            tx_id = str(row.get("transaction_id") or "")
            created_at = row.get("created_at")
            if tx_id and created_at is not None:
                candidate: Watermark = (created_at, tx_id)
                if self._watermark is None or candidate > self._watermark:
                    self._watermark = candidate

        if to_push:
            await self._push_transactions(to_push)

    # ── Enrichment ───────────────────────────────────────────────────
    async def _batch_resolve(
        self, company_ids: list[Any]
    ) -> dict[str, dict[str, str]]:
        """Giải symbol hàng loạt; lỗi hạ tầng (DB/Redis) → {} để fallback per-item."""
        if not company_ids:
            return {}
        try:
            return await self._batch_symbol_resolver(company_ids)
        except Exception:
            logger.warning("Batch symbol resolution failed — falling back per-item")
            return {}

    async def _enrich(
        self, tx: TransactionRow, resolved: dict[str, dict[str, str]] | None = None
    ) -> TransactionRow | None:
        symbol = tx.get("symbol")
        company_name = tx.get("company_name")
        if not symbol:
            entry = resolved.get(str(tx.get("company_id"))) if resolved else None
            if entry is None:
                entry = await self._symbol_resolver(tx.get("company_id"))
            if entry is None:
                return None
            symbol = entry.get("symbol")
            company_name = entry.get("name")

        quantity = float(tx.get("quantity", 0) or 0)
        price = float(tx.get("price", 0) or 0)
        return {
            "transaction_id": str(tx.get("transaction_id") or uuid.uuid4()),
            "order_id": str(tx.get("order_id") or ""),
            "company_id": str(tx.get("company_id") or ""),
            "user_id": str(tx["user_id"]),
            "symbol": symbol,
            "company_name": company_name,
            "side": tx.get("side"),
            "quantity": quantity,
            "price": price,
            "total": round(quantity * price, 2),
            "simulated_at": tx.get("simulated_at"),
        }

    async def _default_symbol_resolver(self, company_id: Any) -> dict[str, str] | None:
        if company_id is None:
            return None
        async with async_session_factory() as session:
            company = await session.get(Company, company_id)
        if company is None:
            return None
        return {"symbol": company.symbol, "name": company.name}

    async def _default_batch_symbol_resolver(
        self, company_ids: list[Any]
    ) -> dict[str, dict[str, str]]:
        """Giải symbol toàn bộ company_id còn thiếu trong MỘT query ``IN``.

        Cách cũ (per-item ``session.get``) chạy N round-trip cho N giao dịch thiếu
        symbol — nghẽn DB khi một ``match_orders`` tạo nhiều khớp cùng lúc.
        """
        if not company_ids:
            return {}
        async with async_session_factory() as session:
            stmt = (
                select(Company.id, Company.symbol, Company.name)
                .where(Company.id.in_(company_ids))
            )
            rows = (await session.execute(stmt)).all()
        return {str(r[0]): {"symbol": r[1], "name": r[2]} for r in rows}

    async def _default_poll_source(self, watermark: Watermark | None) -> list[TransactionRow]:
        async with async_session_factory() as session:
            stmt = (
                select(
                    Transaction.id,
                    Transaction.order_id,
                    Transaction.user_id,
                    Transaction.company_id,
                    Transaction.side,
                    Transaction.quantity,
                    Transaction.price,
                    Transaction.simulated_at,
                    Transaction.created_at,
                    Company.symbol,
                    Company.name,
                )
                .join(Company, Transaction.company_id == Company.id)
                .order_by(Transaction.created_at.asc(), Transaction.id.asc())
                .limit(500)
            )
            if watermark is not None:
                wm_ts, _wm_id = watermark
                # Lookback window: Postgres `now()` = thời điểm START transaction, không
                # phải commit. Giao dịch bắt đầu TRƯỚC watermark nhưng commit SAU poll
                # sẽ bị `created_at > wm_ts` bỏ sót vĩnh viễn. Đọc từ
                # `wm_ts - lookback` để bắt nhóm "commit lệch thời gian" này; tin đã
                # phát được dedupe (SETNX + seen_ids) chặn đẩy trùng.
                start_ts = wm_ts - timedelta(
                    seconds=max(settings.ws_trade_lookback_seconds, 0.0)
                )
                stmt = stmt.where(Transaction.created_at >= start_ts)
            rows = (await session.execute(stmt)).all()

        return [
            {
                "transaction_id": r[0],
                "order_id": r[1],
                "user_id": str(r[2]),
                "company_id": str(r[3]),
                "side": r[4],
                "quantity": float(r[5]),
                "price": float(r[6]),
                "simulated_at": r[7],
                "created_at": r[8],
                "symbol": r[9],
                "company_name": r[10],
            }
            for r in rows
        ]


trade_notifier = TradeNotifier(connection_manager)


def create_trade_endpoint(
    manager: ConnectionManager | None = None,
    notifier: TradeNotifier | None = None,
    auth_provider: Callable[[WebSocket], Any] | None = None,
    *,
    heartbeat_seconds: float | None = None,
    revalidate_auth: bool | None = None,
) -> Callable[[WebSocket], Any]:
    manager = manager or connection_manager
    notifier = notifier or trade_notifier
    auth = auth_provider or get_ws_user
    heartbeat = (
        heartbeat_seconds if heartbeat_seconds is not None else settings.ws_heartbeat_seconds
    )
    # Chỉ bật revalidation giữa phiên khi dùng auth JWT mặc định (custom auth trong
    # test không có token → không revalidate để tránh đóng oan kết nối).
    do_revalidate = (
        revalidate_auth if revalidate_auth is not None else (auth_provider is None)
    )

    async def trade_ws_endpoint(websocket: WebSocket) -> None:
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
                    "welcome",
                    {
                        "user_id": user_id,
                        "channel": user_room,
                        "realtime_status": manager.realtime_status(),
                    },
                ),
            )

        async def on_message(conn: ClientConnection, payload: dict[str, Any]) -> None:
            action = payload.get("action")
            if action == "subscribe":
                await manager.join_room(conn, user_room)
                await manager.send(conn, build_message("subscribed", {"channel": user_room}))
            elif action == "unsubscribe":
                await manager.leave_room(conn, user_room)
                await manager.send(conn, build_message("unsubscribed", {"channel": user_room}))
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
            on_validate=on_validate if do_revalidate else None,
            heartbeat_seconds=heartbeat,
        )

    return trade_ws_endpoint
