"""Daily Digest & Weekly Report — tóm tắt hiệu suất & kỷ luật theo chu kỳ.

- ``build_daily_digest``: biến động danh mục trong ngày (P/L thực hiện + chưa
  thực hiện), tổng phí & thuế, điểm kỷ luật thay đổi, cổ tức/chia tách hôm nay.
- ``build_weekly_report``: tổng hợp các digest trong tuần + so sánh với vị thế.

Kết quả lưu vào bảng ``reports`` (unique user+kind+period) → gọi lại không tạo
trùng. Số liệu lấy từ transaction/portfolio/company thật nên luôn khớp.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from core.config import settings
from models.company import Company
from models.corporate_action import CorporateAction
from models.discipline import DisciplineScoreHistory
from models.report import Report
from models.trade import Portfolio, Transaction
from models.user import User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

KIND_DAILY = "daily"
KIND_WEEKLY = "weekly"


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def _period_bounds(day: date) -> tuple[datetime, datetime]:
    """Mốc [start, end) của ngày theo timezone app."""
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def _d(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


async def _market_value(db: AsyncSession, user_id: object) -> Decimal:
    rows = await db.execute(
        select(func.sum(Portfolio.quantity * Company.current_price))
        .join(Company, Portfolio.company_id == Company.id)
        .where(Portfolio.user_id == user_id)
    )
    return _d(rows.scalar_one())


async def _cash_components(db: AsyncSession, user_id: object) -> dict[str, Decimal]:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return {"cash": Decimal("0"), "frozen": Decimal("0"), "settling": Decimal("0")}
    return {
        "cash": _d(user.cash_balance),
        "frozen": _d(user.frozen_cash),
        "settling": _d(user.settling_cash),
    }


async def build_daily_digest(db: AsyncSession, user: User, day: date | None = None) -> dict:
    """Tạo digest hằng ngày. ``day`` mặc định là hôm nay (theo timezone app)."""
    day = day or datetime.now(_tz()).date()
    start, end = _period_bounds(day)

    cash = await _cash_components(db, user.id)
    mv = await _market_value(db, user.id)
    nav = cash["cash"] + cash["frozen"] + cash["settling"] + mv

    # Giao dịch trong ngày (theo created_at trong kỳ).
    txs = (
        await db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user.id,
                Transaction.created_at >= start,
                Transaction.created_at < end,
            )
        )
    ).scalars().all()
    buy_val = sum((_d(tx.quantity) * _d(tx.price)) for tx in txs if tx.side == "buy")
    sell_val = sum((_d(tx.quantity) * _d(tx.price)) for tx in txs if tx.side == "sell")
    total_fee = sum(_d(tx.fee) for tx in txs)
    total_tax = sum(_d(tx.tax) for tx in txs)
    order_count = len(txs)

    # Điểm kỷ luật thay đổi trong ngày.
    dh = await db.execute(
        select(func.coalesce(func.sum(DisciplineScoreHistory.score_delta), 0)).where(
            DisciplineScoreHistory.user_id == user.id,
            DisciplineScoreHistory.created_at >= start,
            DisciplineScoreHistory.created_at < end,
        )
    )
    discipline_delta = int(dh.scalar_one() or 0)

    # Sự kiện doanh nghiệp đã đủ hạn hôm nay.
    events = (
        await db.execute(
            select(CorporateAction)
            .join(Company, CorporateAction.company_id == Company.id)
            .where(
                CorporateAction.applied_at >= start,
                CorporateAction.applied_at < end,
            )
        )
    ).scalars().all()
    event_summary = [
        {
            "type": e.action_type,
            "company_id": str(e.company_id),
        }
        for e in events
    ]

    payload = {
        "period": day.isoformat(),
        "nav": str(nav),
        "cash": str(cash["cash"]),
        "settling": str(cash["settling"]),
        "market_value": str(mv),
        "buy_volume": str(buy_val),
        "sell_volume": str(sell_val),
        "orders": order_count,
        "fee": str(total_fee),
        "tax": str(total_tax),
        "discipline_delta": discipline_delta,
        "corporate_events": event_summary,
    }
    return payload


async def upsert_report(
    db: AsyncSession, user_id: object, kind: str, period: date, payload: dict
) -> Report:
    existing = (
        await db.execute(
            select(Report).where(
                Report.user_id == user_id,
                Report.kind == kind,
                Report.period == period,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.payload = payload
        await db.commit()
        await db.refresh(existing)
        return existing
    report = Report(user_id=user_id, kind=kind, period=period, payload=payload)
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


async def build_daily_digest_persisted(
    db: AsyncSession, user: User, day: date | None = None
) -> dict:
    day = day or datetime.now(_tz()).date()
    payload = await build_daily_digest(db, user, day)
    await upsert_report(db, user.id, KIND_DAILY, day, payload)
    return payload


async def get_reports(db: AsyncSession, user_id: object, kind: str, limit: int = 20) -> list[dict]:
    rows = (
        await db.execute(
            select(Report)
            .where(Report.user_id == user_id, Report.kind == kind)
            .order_by(Report.period.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "period": r.period.isoformat(),
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]
