"""Thanh toán bù trừ T+2 — giải phóng tiền bán về tài khoản khả dụng.

Khi một lệnh BÁN được khớp với thị trường (market maker) hoặc với user khác,
tiền ròng (revenue − phí − thuế) được ghi vào ``users.settling_cash`` kèm mốc
``transactions.settles_at = simulated_at + settlement_days``. Tiền này KHÔNG
dùng được để đặt lệnh (tách khỏi cash_balance). Worker gọi ``release_due()``
mỗi nhịp (leader) để chuyển ``settling_cash`` → ``cash_balance`` cho mọi giao
dịch đã đủ hạn, một cách **idempotent** (chỉ các dòng còn ``settles_at != NULL``
mới được xử lý; sau khi release đặt NULL để không trừ lại lần nữa).

Bất biến được giữ suốt quá trình:
    cash_balance >= frozen_cash
    cash_balance + settling_cash >= frozen_cash
Bán fill chỉ làm tăng settling_cash (không chạm cash_balance); release chỉ
chuyển settling_cash → cash_balance. Do đó không lệnh mua nào lấy được tiền
chưa về.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from core.config import settings
from models.trade import Transaction
from models.user import User
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def settlement_deadline(simulated_at: datetime) -> datetime:
    """Mốc giải phóng tiền: ``simulated_at`` + ``settlement_days`` ngày thực.

    ``simulated_at`` là đồng hồ thực (timezone-aware); ``settlement_days`` mặc
    định 2 theo `settings.settlement_days`. Giao dịch khớp T0 → tiền về T+2.
    """
    if simulated_at.tzinfo is None:
        simulated_at = simulated_at.replace(tzinfo=timezone.utc)
    return simulated_at + timedelta(days=settings.settlement_days)


async def _unfreeze_buy_orders_if_possible(db: AsyncSession, user: User) -> None:
    """Không dùng — giữ để tương lai scale; hiện mua đóng băng ngay khi đặt."""
    return None


async def release_due(db: AsyncSession) -> int:
    """Chuyển settling_cash → cash_balance cho mọi giao dịch bán đã đủ hạn.

    Trả về số giao dịch được giải phóng. Idempotent: chỉ xử lý dòng còn
    ``settles_at != NULL`` và ``settles_at <= now()``; sau đó set NULL.
    """
    now = _now_utc()
    tx_stmt = (
        select(Transaction)
        .where(
            Transaction.settles_at.is_not(None),
            Transaction.settles_at <= now,
            Transaction.side == "sell",
        )
        .order_by(Transaction.id)
    )
    due = (await db.execute(tx_stmt)).scalars().all()
    if not due:
        return 0

    # Gộp theo user để cập nhật settling_cash 1 lần mỗi user (tránh lock cạnh tranh).
    by_user: dict[object, Decimal] = {}
    for tx in due:
        # net_proceeds = quantity * price − fee − tax (đã lưu khi fill).
        proceeds = tx.quantity * tx.price - tx.fee - tx.tax
        by_user[tx.user_id] = by_user.get(tx.user_id, Decimal("0.00")) + Decimal(
            str(proceeds)
        )

    for user_id, amount in by_user.items():
        user_stmt = select(User).where(User.id == user_id).with_for_update()
        user = (await db.execute(user_stmt)).scalar_one()
        # Cận dưới 0 để tránh âm do rounding.
        release = min(amount, user.settling_cash)
        user.settling_cash -= release
        user.cash_balance += release

    # Đánh dấu đã release → idempotent (không chạm lại 2 lần).
    for tx in due:
        tx.settles_at = None

    await db.commit()
    logger.info("Released T+2 settlement for %d sale transaction(s)", len(due))
    return len(due)
