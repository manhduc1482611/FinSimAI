"""Thanh toán bù trừ T+2 — giải phóng tiền bán về tài khoản khả dụng.

Khi một lệnh BÁN được khớp với thị trường (market maker) hoặc với user khác,
tiền ròng (revenue − phí − thuế) được ghi vào ``users.settling_cash`` kèm mốc
``transactions.settles_at = simulated_at + 2 ngày giao dịch MÔ PHỎNG``. "Ngày
giao dịch mô phỏng" tuân theo đồng hồ nén của hệ thống (1 phút thực = 1 ngày
ảo, tỉ lệ 1440) nên T+2 tương ứng **120 giây thực** chứ không phải 2 ngày thực
— nếu dùng ngày thực, user sẽ không bao giờ thấy tiền về trong một phiên.
Tiền này KHÔNG dùng được để đặt lệnh (tách khỏi cash_balance). Worker gọi
``release_due()`` mỗi nhịp (leader) để chuyển ``settling_cash`` → ``cash_balance``
cho mọi giao dịch đã đủ hạn, một cách **idempotent** (chỉ các dòng còn
``settles_at != NULL`` mới được xử lý; sau khi release đặt NULL để không trừ lại
lần nữa).

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
from realtime.simtime import real_seconds_for_sim_days
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def settlement_deadline(simulated_at: datetime) -> datetime:
    """Mốc giải phóng tiền: ``simulated_at`` + ``settlement_days`` NGÀY MÔ PHỎNG.

    ``simulated_at`` là đồng hồ thực UTC (timezone-aware); ``settlement_days``
    mặc định 2 theo `settings.settlement_days`. Số ngày đó là **ngày giao dịch
    mô phỏng**, quy đổi sang giây thực qua đồng hồ nén (1 ngày ảo = 60 giây
    thực với tỉ lệ 1440) — giao dịch khớp T0 → tiền về sau 2 ngày ảo (= 120
    giây thực). Nếu cộng 2 ngày THỰC, tiền sẽ không bao giờ về trong một phiên.
    """
    if simulated_at.tzinfo is None:
        simulated_at = simulated_at.replace(tzinfo=timezone.utc)
    real_seconds = real_seconds_for_sim_days(settings.settlement_days)
    return simulated_at + timedelta(seconds=real_seconds)


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
