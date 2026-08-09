import asyncio
import logging
import math
import random
import time
import uuid
from decimal import Decimal
from typing import Any

from clients.math_client import math_client
from models.company import Company
from models.trade import Portfolio
from models.user import User
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def make_seed(base: int | None, company_id: uuid.UUID) -> int | None:
    if base is None:
        return None
    return base ^ (company_id.int & 0x7FFFFFFF)


def _fallback_price(
    current_price: float,
    sigma: float,
    dt_years: float,
    seed: int | None,
) -> float:
    """GBM nội bộ dùng stdlib — chỉ chạy khi Math Engine không khả dụng."""
    rng = random.Random(seed) if seed is not None else random.Random()
    mu = 0.0
    return current_price * math.exp(
        (mu - 0.5 * sigma * sigma) * dt_years
        + sigma * math.sqrt(dt_years) * rng.gauss(0.0, 1.0)
    )


_LAST_FALLBACK_LOG = 0.0


async def _fetch_price_values(
    current_price: float,
    volatility: float,
    dt_years: float,
    seed: int | None,
) -> Decimal | None:
    global _LAST_FALLBACK_LOG
    result = await math_client.generate_next_prices(
        current_price=current_price,
        mu=0.0,
        sigma=volatility,
        dt_years=dt_years,
        n_steps=1,
        seed=seed,
    )
    if not result["success"] or not result["prices"]:
        now = time.monotonic()
        if now - _LAST_FALLBACK_LOG > 60.0:
            _LAST_FALLBACK_LOG = now
            logger.warning(
                "Math Engine unavailable — dùng GBM fallback nội bộ cho giá thị trường"
            )
        return Decimal(str(round(_fallback_price(current_price, volatility, dt_years, seed), 2)))
    # Math Engine trả path `[start, step1, ...]` (n_steps phần tử mới + 1 phần tử
    # đầu = giá hiện tại). Phải lấy phần tử CUỐI (giá mới) — lấy `[0]` khiến giá
    # ghi về đúng giá cũ, thị trường đứng yên.
    return Decimal(str(round(result["prices"][-1], 2)))


async def _fetch_price(
    company: Company,
    dt_years: float,
    seed: int | None,
) -> Decimal | None:
    return await _fetch_price_values(
        current_price=float(company.current_price),
        volatility=float(company.volatility),
        dt_years=dt_years,
        seed=seed,
    )


async def update_all_prices(
    db: AsyncSession,
    dt_years: float = 1.0 / 252,
    seed: int | None = None,
    contest_id: uuid.UUID | None = None,
) -> int:
    """Cập nhật giá một scope nhất định.

    - ``contest_id`` cung cấp → chỉ công ty của contest đó.
    - ``contest_id=None`` → thị trường chính (dòng ``contest_id IS NULL``).

    Contest ``draft``/``ended`` không có công ty (pipeline chỉ sinh công ty lúc
    ``active``), nên không cần lọc thêm theo status.
    """
    stmt = (
        select(
            Company.id,
            Company.symbol,
            Company.current_price,
            Company.volatility,
            Company.shares_outstanding,
        )
        .where(Company.is_active.is_(True))
    )
    if contest_id is not None:
        stmt = stmt.where(Company.contest_id == contest_id)
    else:
        stmt = stmt.where(Company.contest_id.is_(None))
    rows = (await db.execute(stmt)).all()
    await db.commit()

    sem = asyncio.Semaphore(20)

    async def _fetch_throttled(
        current_price: Decimal,
        volatility: Decimal,
        seed: int | None,
    ) -> Decimal | None:
        async with sem:
            return await _fetch_price_values(
                current_price=float(current_price),
                volatility=float(volatility),
                dt_years=dt_years,
                seed=seed,
            )

    tasks = [
        asyncio.ensure_future(
            _fetch_throttled(current_price, volatility, make_seed(seed, company_id))
        )
        for company_id, symbol, current_price, volatility, shares_outstanding in rows
    ]
    prices = await asyncio.gather(*tasks, return_exceptions=True)

    updated = 0
    for (
        (company_id, symbol, current_price, volatility, shares_outstanding),
        price_or_err,
    ) in zip(rows, prices):
        if isinstance(price_or_err, Exception):
            logger.error("Price update failed for %s: %s", symbol, price_or_err)
            continue
        if price_or_err is None:
            continue
        await db.execute(
            update(Company)
            .where(Company.id == company_id)
            .values(
                current_price=price_or_err,
                updated_at=func.now(),
            )
        )
        updated += 1

    if updated:
        await db.commit()

    logger.info("Updated prices for %d / %d companies", updated, len(rows))
    return updated


async def update_company_price(
    company_id: uuid.UUID,
    db: AsyncSession,
    dt_years: float = 1.0 / 252,
    seed: int | None = None,
) -> bool:
    company = await db.get(Company, company_id)
    if not company or not company.is_active:
        return False

    new_price = await _fetch_price(company, dt_years, make_seed(seed, company.id))
    if new_price is None:
        return False

    company.current_price = new_price
    await db.commit()
    return True


async def get_portfolio_summary(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict[str, Any]:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        return {}

    pf_stmt = (
        select(Portfolio, Company)
        .join(Company, Portfolio.company_id == Company.id)
        .where(Portfolio.user_id == user_id, Portfolio.quantity > 0)
    )
    result = await db.execute(pf_stmt)
    rows = result.all()

    total_nav = u.cash_balance + u.frozen_cash
    holdings: list[dict[str, Any]] = []
    for pf, comp in rows:
        mv = pf.quantity * comp.current_price
        cb = pf.quantity * pf.average_buy_price
        holdings.append({
            "company_id": comp.id,
            "symbol": comp.symbol,
            "quantity": pf.quantity,
            "avg_buy_price": pf.average_buy_price,
            "current_price": comp.current_price,
            "market_value": mv,
            "unrealized_pnl": mv - cb,
        })
        total_nav += mv

    return {
        "holdings": holdings,
        "cash_balance": u.cash_balance,
        "frozen_cash": u.frozen_cash,
        "total_nav": total_nav,
    }
