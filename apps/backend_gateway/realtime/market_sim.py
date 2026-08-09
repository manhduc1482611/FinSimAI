"""Ticker thị trường mô phỏng — nối vòng lõi: giá di chuyển + lệnh khớp.

Trước đây ``match_orders`` (trading_service) và ``update_all_prices`` (market_service)
chưa được bất kỳ route/cron/worker nào gọi: lệnh đặt xong treo ``pending`` mãi,
giá đứng yên, feed giá/khớp lệnh real-time không có dữ liệu để phát.

Module này là trigger đó. Mỗi nhịp (tick):
1. ``update_prices`` — gọi Math Engine sinh giá GBM mới → ghi DB.
   (PriceBroadcaster tự đọc DB mỗi tick nên phát ``price_tick`` khi giá đổi.)
2. ``match_orders`` — khớp lệnh ``pending``/``partially_filled`` → tạo Transaction
   → TradeNotifier đẩy ``trade_fill`` real-time (poll catch-up bù nếu push lỗi).

Chỉ leader chạy (fail-closed, cùng cơ chế ``LeaderElection`` của PriceBroadcaster):
1 worker duy nhất ghi DB, tránh N worker cùng chạy GBM + khớp lệnh trùng.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from core.config import settings
from core.database import async_session_factory

from realtime.leader import LeaderElection

logger = logging.getLogger(__name__)

# 1 phút thực = 1 ngày giao dịch ảo (khớp realtime.simtime: ratio = 1440).
SECONDS_PER_SIM_DAY = 60.0
TRADING_DAYS_PER_YEAR = 252.0

# Chặn cú nhảy giá bất thường sau downtime / leader failover / GC pause:
# mỗi tick được coi là tối đa 1 ngày giao dịch ảo (1 phút thực).
MAX_DT_SECONDS = SECONDS_PER_SIM_DAY


def sim_dt_years(elapsed_seconds: float) -> float:
    """Quy đổi thời gian thực giữa 2 nhịp sang ``dt_years`` cho GBM.

    Theo mô hình nén: 1 phút thực = 1 ngày giao dịch ảo = 1/252 năm.
    """
    sim_days = max(elapsed_seconds, 0.0) / SECONDS_PER_SIM_DAY
    return sim_days / TRADING_DAYS_PER_YEAR


async def default_update_prices(dt_years: float) -> None:
    """Cập nhật giá mọi công ty đang hoạt động qua Math Engine (GBM)."""
    from services.market_service import update_all_prices

    async with async_session_factory() as session:
        await update_all_prices(session, dt_years=dt_years)


async def _companies_with_actionable_orders(db: Any) -> list[Any]:
    """Danh sách công ty có lệnh chờ khớp (pending / partially_filled)."""
    from models.trade import Order
    from sqlalchemy import select

    stmt = (
        select(Order.company_id)
        .where(
            Order.status.in_(["pending", "partially_filled"]),
            Order.quantity > Order.filled_quantity,
        )
        .distinct()
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def default_match_orders() -> None:
    """Khớp lệnh theo từng công ty; lỗi 1 công ty không chặn các công ty còn lại."""
    from services.trading_service import match_orders

    async with async_session_factory() as session:
        company_ids = await _companies_with_actionable_orders(session)

    for company_id in company_ids:
        async with async_session_factory() as session:
            try:
                await match_orders(company_id, session)
            except Exception:
                logger.exception("match_orders failed for company %s", company_id)


class MarketSim:
    """Ticker thị trường mô phỏng: dịch chuyển giá rồi khớp lệnh theo chu kỳ."""

    def __init__(
        self,
        *,
        tick_seconds: float | None = None,
        leader_lock_key: str | None = None,
        local_mode: bool | None = None,
        update_prices: Callable[[float], Awaitable[None]] | None = None,
        match_orders: Callable[[], Awaitable[None]] | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.tick_seconds = (
            tick_seconds if tick_seconds is not None else settings.ws_market_tick_seconds
        )
        self._leader_lock_key = leader_lock_key or "finsim:ws:leader:market_sim"
        self._leader_token = str(uuid.uuid4())
        self._leader_ttl = max(int(self.tick_seconds * 3), 3)
        self._local_mode = settings.ws_local_mode if local_mode is None else local_mode
        self._election = LeaderElection(
            self._leader_lock_key,
            token=self._leader_token,
            ttl=self._leader_ttl,
            local_mode=self._local_mode,
        )
        self._update_prices = update_prices or default_update_prices
        self._match_orders = match_orders or default_match_orders
        self._now = now or time.monotonic
        self._task: asyncio.Task[None] | None = None
        self._last_tick_ts: float | None = None

    @property
    def is_leader(self) -> bool:
        return self._election.is_leader

    @property
    def last_tick_ts(self) -> float | None:
        return self._last_tick_ts

    # ── Lifecycle ────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop(), name="market-sim")
            logger.info("Market sim started (tick=%.1fs)", self.tick_seconds)

    async def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _run_loop(self) -> None:
        while True:
            try:
                # Fail-closed: mất Redis (ngoài local_mode) → không tự xưng leader
                # → không ghi DB, tránh split-brain giữa các worker.
                if await self._election.acquire():
                    await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Market sim tick failed")
            await asyncio.sleep(self.tick_seconds)

    async def tick(self) -> None:
        """Một nhịp thị trường: giá di chuyển trước, rồi khớp lệnh theo giá mới."""
        now_ts = self._now()
        if self._last_tick_ts is None:
            # Nhịp đầu chỉ ghi mốc — không nhảy giá từ trạng thái "chưa có lịch sử".
            self._last_tick_ts = now_ts
            return

        elapsed = min(max(now_ts - self._last_tick_ts, 0.0), MAX_DT_SECONDS)
        self._last_tick_ts = now_ts
        await self._update_prices(sim_dt_years(elapsed))
        await self._match_orders()


market_sim = MarketSim()
