import asyncio
import logging
import uuid
from decimal import Decimal

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


async def _fetch_price_values(
    current_price: float,
    volatility: float,
    dt_years: float,
    seed: int | None,
) -> Decimal | None:
    result = await math_client.generate_next_prices(
        current_price=current_price,
        mu=0.0,
        sigma=volatility,
        dt_years=dt_years,
        n_steps=1,
        seed=seed,
    )
    if not result["success"] or not result["prices"]:
        return None
    return Decimal(str(round(result["prices"][0], 2)))


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
) -> int:
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
                market_cap=price_or_err * shares_outstanding,
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
    company.market_cap = new_price * company.shares_outstanding
    await db.commit()
    return True


async def get_portfolio_summary(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
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
    holdings = []
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
