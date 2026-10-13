import asyncio
import logging
import math
import random
import time
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from clients.math_client import math_client
from core.config import settings
from models.company import Company
from models.news import News
from models.trade import Portfolio
from models.user import User
from realtime.simtime import (
    REAL_SECONDS_PER_SIM_DAY,
    real_to_sim_epoch,
    sim_day_of,
    sim_now,
)
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Giá tham chiếu (giá đóng cửa phiên trước) theo NGÀY MÔ PHỎNG cho từng công ty:
# ``company_id -> (sim_day, reference_price)``. Dùng để neo biên trần/sàn ±7%
# vào mốc cố định trong ngày thay vì giá đang chạy — nếu neo vào giá đang chạy,
# trần/sàn trôi theo giá và biên mất tác dụng. Chỉ leader cập nhật giá nên cache
# trong RAM là nhất quán; khi leader failover, tham chiếu khởi tạo lại bằng giá
# hiện tại (coi như mở một phiên mới).
_DAY_REFERENCE: dict[uuid.UUID, tuple[int, Decimal]] = {}

# Cơ chế "tin tức → giá": tin tức trong cửa sổ (ngày mô phỏng) bẻ drift GBM (``mu``)
# theo hướng ``sentiment × impact``, phân rã theo độ tuổi. Không có tin tức → momentum
# = 0 → ``mu = 0.0`` (hành vi cũ: GBM trần với trung bình 0).
_NEWS_WINDOW_SIM_DAYS = 7
_NEWS_HALF_LIFE_SIM_DAYS = 3.0
_NEWS_DRIFT_SCALE = 2.0  # mu annualized tối đa khi momentum bão hoà ±1


def _sentiment_sign(sentiment: str | None) -> int:
    """Hướng tin tức: positive → +1, negative → -1, neutral/thiếu → 0."""
    normalized = (sentiment or "").strip().lower()
    if normalized == "positive":
        return 1
    if normalized == "negative":
        return -1
    return 0


def _news_weight(sentiment: str | None, impact_score: float, age_seconds: float) -> float:
    """Trọng số một tin: hướng × mức ảnh hưởng (impact/10) × phân rã theo tuổi (ngày sim)."""
    age_sim_days = max(age_seconds, 0.0) / REAL_SECONDS_PER_SIM_DAY
    return (
        _sentiment_sign(sentiment)
        * (float(impact_score) / 10.0)
        * math.exp(-age_sim_days / _NEWS_HALF_LIFE_SIM_DAYS)
    )


def _aggregate_news_momentum(
    entries: Iterable[tuple[str | None, float, float]],
) -> float:
    """Tổng hợp các tin ``(sentiment, impact_score, age_seconds)`` → momentum [-1, 1].

    Dùng ``tanh`` để chặn mềm: nhiều tin cùng hướng bão hoà dần thay vì tích luỹ tuyến
    tính, giữ ``mu`` trong ngưỡng hợp lý cho GBM (không để một tràng tin dương đẩy giá
    dính trần trong nhiều phiên).
    """
    total = sum(_news_weight(*entry) for entry in entries)
    return math.tanh(total)


async def _fetch_news_momentum_map(
    db: AsyncSession,
    company_ids: Iterable[uuid.UUID],
    contest_id: uuid.UUID | None,
) -> dict[uuid.UUID, float]:
    """Tin tức trong cửa sổ → momentum mỗi công ty (tin riêng + tin vĩ mô cùng scope).

    - Công ty thị trường chính (``contest_id NULL``): macro news là bài
      ``company_id IS NULL AND contest_id IS NULL`` (thị trường / vĩ mô).
    - Công ty trong contest: macro news là bài ``company_id IS NULL`` gắn đúng contest
      đó — tránh tin vĩ mô của thị trường chính chi phối cả contest.
    - Chỉ xét tin ``simulated_at <= sim_now()`` (chống look-ahead: tin chưa phát hành
      không được dịch chuyển giá hiện tại).
    """
    ids = [cid for cid in company_ids if cid is not None]
    if not ids:
        return {}
    now = sim_now()
    since = now - timedelta(seconds=_NEWS_WINDOW_SIM_DAYS * REAL_SECONDS_PER_SIM_DAY)
    macro_scope = (
        and_(News.company_id.is_(None), News.contest_id.is_(None))
        if contest_id is None
        else and_(News.company_id.is_(None), News.contest_id == contest_id)
    )
    stmt = (
        select(
            News.company_id,
            News.sentiment,
            News.impact_score,
            News.simulated_at,
        )
        .where(
            News.simulated_at >= since,
            News.simulated_at <= now,
            or_(News.company_id.in_(ids), macro_scope),
        )
    )
    rows = (await db.execute(stmt)).all()

    company_weight: dict[uuid.UUID, float] = {cid: 0.0 for cid in ids}
    macro_weight = 0.0
    for company_id, sentiment, impact_score, simulated_at in rows:
        weight = _news_weight(sentiment, impact_score, (now - simulated_at).total_seconds())
        if company_id is None:
            macro_weight += weight
        elif company_id in company_weight:
            company_weight[company_id] += weight

    if not macro_weight and not any(company_weight.values()):
        return {}
    return {
        cid: math.tanh(own + macro_weight)
        for cid, own in company_weight.items()
    }


def _current_sim_day() -> int:
    """Ngày giao dịch mô phỏng hiện tại (đồng hồ nén, neo ``ws_sim_anchor_epoch``)."""
    anchor = datetime.fromtimestamp(settings.ws_sim_anchor_epoch, tz=timezone.utc)
    return sim_day_of(real_to_sim_epoch(sim_now(), anchor))


def _reference_price(
    company_id: uuid.UUID, sim_day: int, current_price: Decimal
) -> Decimal:
    """Trả giá tham chiếu của công ty trong ``sim_day`` hiện tại.

    Sang ngày mô phỏng mới (hoặc lần đầu thấy công ty) thì lấy giá hiện tại làm
    tham chiếu; trong cùng ngày luôn trả mốc đã chốt → biên ±7% không trôi.
    """
    cached = _DAY_REFERENCE.get(company_id)
    if cached is None or cached[0] != sim_day:
        _DAY_REFERENCE[company_id] = (sim_day, current_price)
        return current_price
    return cached[1]


def make_seed(base: int | None, company_id: uuid.UUID) -> int | None:
    if base is None:
        return None
    return base ^ (company_id.int & 0x7FFFFFFF)


def _fallback_price(
    current_price: float,
    sigma: float,
    dt_years: float,
    seed: int | None,
    mu: float = 0.0,
) -> float:
    """GBM nội bộ dùng stdlib — chỉ chạy khi Math Engine không khả dụng."""
    rng = random.Random(seed) if seed is not None else random.Random()
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
    reference_price: float | None = None,
    mu: float = 0.0,
) -> Decimal | None:
    global _LAST_FALLBACK_LOG
    result = await math_client.generate_next_prices(
        current_price=current_price,
        mu=mu,
        sigma=volatility,
        dt_years=dt_years,
        n_steps=1,
        seed=seed,
        reference_price=reference_price,
    )
    if not result["success"] or not result["prices"]:
        now = time.monotonic()
        if now - _LAST_FALLBACK_LOG > 60.0:
            _LAST_FALLBACK_LOG = now
            logger.warning(
                "Math Engine unavailable — dùng GBM fallback nội bộ cho giá thị trường"
            )
        return Decimal(
            str(round(_fallback_price(current_price, volatility, dt_years, seed, mu), 2))
        )
    # Math Engine trả path `[start, step1, ...]` (n_steps phần tử mới + 1 phần tử
    # đầu = giá hiện tại). Phải lấy phần tử CUỐI (giá mới) — lấy `[0]` khiến giá
    # ghi về đúng giá cũ, thị trường đứng yên.
    return Decimal(str(round(result["prices"][-1], 2)))


async def _fetch_price(
    company: Company,
    dt_years: float,
    seed: int | None,
    mu: float = 0.0,
) -> Decimal | None:
    reference = _reference_price(company.id, _current_sim_day(), company.current_price)
    return await _fetch_price_values(
        current_price=float(company.current_price),
        volatility=float(company.volatility),
        dt_years=dt_years,
        seed=seed,
        reference_price=float(reference),
        mu=mu,
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

    # Cùng một ngày mô phỏng cho cả lượt cập nhật → mọi công ty neo vào giá
    # tham chiếu đã chốt trong ngày, không trôi theo từng nhịp.
    sim_day = _current_sim_day()
    momentum_map = await _fetch_news_momentum_map(
        db, (company_id for company_id, *_ in rows), contest_id
    )
    sem = asyncio.Semaphore(20)

    async def _fetch_throttled(
        company_id: uuid.UUID,
        current_price: Decimal,
        volatility: Decimal,
        seed: int | None,
        momentum: float,
    ) -> Decimal | None:
        reference = _reference_price(company_id, sim_day, current_price)
        async with sem:
            return await _fetch_price_values(
                current_price=float(current_price),
                volatility=float(volatility),
                dt_years=dt_years,
                seed=seed,
                reference_price=float(reference),
                mu=_NEWS_DRIFT_SCALE * momentum,
            )

    tasks = [
        asyncio.ensure_future(
            _fetch_throttled(
                company_id,
                current_price,
                volatility,
                make_seed(seed, company_id),
                momentum_map.get(company_id, 0.0),
            )
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

    momentum = (
        await _fetch_news_momentum_map(db, {company.id}, company.contest_id)
    ).get(company.id, 0.0)
    new_price = await _fetch_price(
        company, dt_years, make_seed(seed, company.id), mu=_NEWS_DRIFT_SCALE * momentum
    )
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
