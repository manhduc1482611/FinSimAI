"""Áp dụng sự kiện doanh nghiệp đúng hạn (Corporate Actions) — chống look-ahead.

Generator (chạy mỗi nhịp trong ``MarketSim.tick``) duyệt các ``CorporateAction``
đã đủ hạn (``applied_at IS NULL`` và ``ex_date <= now``) và hiện thực hoá chúng
một cách idempotent:
- ``cash_dividend``: trả tiền mặt (config["cash_amount_per_share"]) cho mọi
  portfolio giữ cổ tại ngày ghi nhận; ghi vào cash_balance.
- ``stock_split``: nhân ``shares_outstanding`` với ratio, chia ``current_price``,
  điều chỉnh ``average_buy_price`` và ``quantity`` của mọi portfolio giữ cổ —
  TỔNG GIÁ TRỊ không đổi.
- ``news_shock`` / ``rights`` / ``delisting``: hiện bỏ qua tự động (chỉ đánh dấu
  applied để không chạy lại); để lại cho tầng sinh tin tức/công khai sau.

Chỉ leader thực thi; lỗi 1 event không chặn các event khác.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

from models.company import Company
from models.corporate_action import CorporateAction
from models.trade import Portfolio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _d(value: object) -> Decimal:
    return Decimal(str(value))


def _div(a: Decimal, b: Decimal) -> Decimal:
    return a / b if b and b != 0 else Decimal("0")


async def _apply_cash_dividend(
    db: AsyncSession, event: CorporateAction, company: Company, now: datetime
) -> None:
    per_share = _d(event.config.get("cash_amount_per_share", 0))
    if per_share <= 0:
        return

    pf_rows = (
        await db.execute(
            select(Portfolio).where(Portfolio.company_id == company.id).with_for_update()
        )
    ).scalars().all()

    # Gộp theo user để cập nhật cash_balance 1 lần mỗi user (giảm số lock).
    totals: dict[object, Decimal] = {}
    for pf in pf_rows:
        if pf.quantity <= 0:
            continue
        amount = (pf.quantity * per_share).quantize(Decimal("0.01"), ROUND_DOWN)
        if amount > 0:
            totals[pf.user_id] = totals.get(pf.user_id, Decimal("0.00")) + amount

    from models.user import User

    for user_id, amount in totals.items():
        user = (
            await db.execute(select(User).where(User.id == user_id).with_for_update())
        ).scalar_one_or_none()
        if user is not None:
            user.cash_balance = (user.cash_balance or Decimal("0.00")) + amount


async def _apply_stock_split(
    db: AsyncSession, event: CorporateAction, company: Company, now: datetime
) -> None:
    ratio_x = _d(event.config.get("split_ratio", 1))  # vd 2 → 1:2 (nhân đôi cổ)
    if ratio_x <= 1:
        return
    ratio = _d(str(ratio_x))

    old_shares = company.shares_outstanding
    old_price = company.current_price

    new_shares = (old_shares * ratio).quantize(Decimal("1"), ROUND_DOWN)
    new_price = _div(old_price, ratio).quantize(Decimal("0.01"))

    company.shares_outstanding = new_shares
    company.current_price = new_price

    pf_rows = (
        await db.execute(
            select(Portfolio).where(Portfolio.company_id == company.id).with_for_update()
        )
    ).scalars().all()
    for pf in pf_rows:
        if pf.quantity <= 0:
            continue
        new_qty = (pf.quantity * ratio).quantize(Decimal("0.0001"), ROUND_DOWN)
        pf.quantity = new_qty
        pf.frozen_quantity = (pf.frozen_quantity * ratio).quantize(
            Decimal("0.0001"), ROUND_DOWN
        )
        # Giá vốn giảm theo tỷ lệ → tổng giá trị giữ nguyên.
        pf.average_buy_price = _div(pf.average_buy_price, ratio).quantize(Decimal("0.01"))


async def apply_due_events(db: AsyncSession, now: datetime | None = None) -> int:
    """Áp dụng mọi sự kiện đã đủ hạn; trả về số event đã xử lý. Idempotent."""
    now = now or _now_utc()
    stmt = (
        select(CorporateAction)
        .where(
            CorporateAction.is_active.is_(True),
            CorporateAction.applied_at.is_(None),
            CorporateAction.ex_date <= now,
        )
        .order_by(CorporateAction.ex_date)
    )
    events = (await db.execute(stmt)).scalars().all()
    if not events:
        return 0

    applied = 0
    for event in events:
        company = await db.get(Company, event.company_id)
        if company is None:
            continue
        try:
            if event.action_type == "cash_dividend":
                await _apply_cash_dividend(db, event, company, now)
            elif event.action_type == "stock_split":
                await _apply_stock_split(db, event, company, now)
            # rights / delisting / news_shock: đánh dấu applied — sinh tin + điều
            # chỉnh giá là các bước sau (ngoài phạm vi hiện tại).
            event.applied_at = now
            applied += 1
        except Exception:
            logger.exception(
                "Corporate action %s (%s) failed for company %s",
                event.action_type,
                event.id,
                event.company_id,
            )

    if applied:
        await db.commit()
    return applied


async def create_event(
    db: AsyncSession,
    company_id: object,
    action_type: str,
    *,
    ex_date: datetime,
    config: dict | None = None,
    record_date: datetime | None = None,
) -> CorporateAction:
    """Tạo event (thường qua admin/seed). Đảm bảo idempotent theo mô tả."""
    record_datetime = record_date or ex_date
    event = CorporateAction(
        company_id=company_id,
        action_type=action_type,
        ex_date=ex_date,
        record_date=record_datetime,
        config=config or {},
        is_active=True,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
