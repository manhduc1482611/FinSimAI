"""Phạt & khóa giao dịch (Cooldown) theo điểm quản trị rủi ro.

Luồng tổng thể (Bước 5.1 — Cơ chế phạt Cooldown Overlay):

    Vi phạm (trap) → ``apply_penalty`` → risk_score tăng / trừ tiền /
    ``cooldown_until`` = now + cooldown_seconds.
    → Mọi lệnh giao dịch tiếp theo bị chặn với HTTP 423 (``enforce_cooldown``).
    → Hết thời gian cooldown, người dùng hoàn thành bài tập phản tư với Mentor
      (frontend), sau đó ``clear_cooldown`` gỡ khóa và đánh dấu trap đã resolved.

Nguyên tắc an toàn:
- Khóa cứng (423) chỉ đúng khi ``now < cooldown_until``; nếu đã hết hạn, mọi
  endpoint tự động gỡ khóa "lười biếng" (lazy-clear) để không bao giờ kẹt tài khoản.
- ``clear_cooldown`` KHÔNG thể rút ngắn thời gian phạt — chỉ gỡ khi đã hết hạn.
- ``apply_penalty`` ghi một ``TrapEvent`` để overlay hiển thị lý do + phục vụ
  analytics; khi gỡ phạt, trap chưa resolved sẽ được đánh dấu đã xử lý.
"""

import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal

from clients.math_grpc_client import math_grpc_client
from models.trade import Order
from models.trap import TrapEvent
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_reason(trap_type: str, severity: int, description: str | None) -> str:
    if description:
        return f"Vi phạm kỷ luật giao dịch — {trap_type}: {description}"
    return f"Vi phạm kỷ luật giao dịch — {trap_type} (mức độ {severity}/5)"


async def _penalty_reason(user_id: uuid.UUID, db: AsyncSession) -> str | None:
    """Lấy lý do phạt từ trap mới nhất chưa được xử lý (để hiển thị trên overlay)."""
    stmt = (
        select(TrapEvent)
        .where(TrapEvent.user_id == user_id, TrapEvent.resolved_at.is_(None))
        .order_by(TrapEvent.detected_at.desc())
        .limit(1)
    )
    event = (await db.execute(stmt)).scalar_one_or_none()
    if event is None:
        return "Điểm quản trị rủi ro tụt quá sâu"
    return _build_reason(event.type, event.severity, event.description)


async def get_penalty_status(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Trả về trạng thái cooldown của user (KHÔNG gây lỗi khi không bị phạt).

    Cooldown đã hết hạn sẽ được gỡ "lười biếng" (lazy-clear) trước khi trả về.
    """
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        return {"success": False, "error": "User not found"}

    now = _utcnow()
    risk_score = user.risk_score
    cooldown_until = user.cooldown_until

    if cooldown_until is not None and cooldown_until <= now:
        await clear_cooldown(user_id, db)
        cooldown_until = None

    locked = cooldown_until is not None

    remaining_seconds = 0
    if cooldown_until is not None:
        remaining_seconds = max(0, math.ceil((cooldown_until - now).total_seconds()))

    reason = await _penalty_reason(user_id, db) if locked else None

    return {
        "success": True,
        "locked": locked,
        "cooldown_until": cooldown_until,
        "remaining_seconds": remaining_seconds,
        "risk_score": risk_score,
        "reason": reason,
    }


async def enforce_cooldown(user_id: uuid.UUID, db: AsyncSession) -> dict | None:
    """Gate cho mọi thao tác giao dịch.

    Trả về dict trạng thái cooldown khi đang bị khóa (→ API trả HTTP 423),
    hoặc ``None`` khi được phép giao dịch (cooldown rỗng / đã hết hạn).
    """
    status = await get_penalty_status(user_id, db)
    if status.get("success") and status["locked"]:
        return status
    return None


def _buy_freeze_price(buy: Order) -> Decimal:
    if buy.type == "limit" and buy.price:
        return buy.price
    remaining_qty = buy.quantity - buy.filled_quantity
    if remaining_qty > 0 and buy.frozen_cash > Decimal("0"):
        return buy.frozen_cash / remaining_qty
    return buy.price if buy.price else Decimal("0")


async def apply_penalty(
    user_id: uuid.UUID,
    trap_severity: int,
    db: AsyncSession,
    *,
    trap_type: str = "discipline_violation",
    description: str | None = None,
) -> dict:
    """Áp dụng phạt từ một lần vi phạm: tăng risk_score, trừ tiền, đặt cooldown.

    - Gọi math engine để tính ``new_risk_score`` / ``cooldown_seconds``.
    - Nếu trừ điểm vượt quá số dư tiền mặt, hủy dần lệnh mua đang chờ (giải
      phóng tiền đóng băng) để thu hồi phần thiếu; không đủ thì rollback.
    - Ghi một ``TrapEvent`` làm bằng chứng vi phạm.
    """
    user_stmt = select(User.risk_score).where(User.id == user_id)
    user_data = (await db.execute(user_stmt)).first()
    if not user_data:
        return {"success": False, "error": "User not found"}

    result = await math_grpc_client.check_penalty_status(
        risk_score=user_data.risk_score,
        trap_severity=trap_severity,
    )
    if not result.get("success"):
        return result

    deduction = Decimal(str(result.get("points_deducted", 0)))
    cooldown_until: datetime | None = None

    user = (
        await db.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one()

    user.risk_score = result["new_risk_score"]

    if result.get("cooldown_seconds", 0) > 0:
        cooldown_until = _utcnow() + timedelta(seconds=result["cooldown_seconds"])
        user.cooldown_until = cooldown_until

    if deduction > 0 and user.cash_balance < deduction:
        shortfall = deduction - user.cash_balance
        recovered = Decimal("0")

        stmt = (
            select(Order)
            .where(
                Order.user_id == user_id,
                Order.side == "buy",
                Order.status.in_(["pending", "partially_filled"]),
                Order.quantity > Order.filled_quantity,
            )
            .with_for_update()
            .order_by(Order.created_at.asc())
        )
        pending_orders = (await db.execute(stmt)).scalars().all()

        for order in pending_orders:
            remaining_qty = order.quantity - order.filled_quantity
            if remaining_qty <= Decimal("0"):
                continue

            freeze_price = _buy_freeze_price(order)
            if freeze_price <= Decimal("0"):
                continue

            needed = shortfall - recovered
            order_frozen = min(remaining_qty * freeze_price, order.frozen_cash)
            if order_frozen <= Decimal("0"):
                continue

            if order_frozen <= needed:
                cancel_all = True
            else:
                cancel_qty = (needed / freeze_price).quantize(
                    Decimal("1"), rounding=ROUND_UP
                )
                unfreeze_amt = cancel_qty * freeze_price
                cancel_all = cancel_qty >= remaining_qty or unfreeze_amt > order.frozen_cash

            if cancel_all:
                recovered += order_frozen
                user.cash_balance += order_frozen
                user.frozen_cash -= order_frozen
                order.frozen_cash = Decimal("0")
                order.status = "cancelled"
            else:
                recovered += unfreeze_amt
                user.cash_balance += unfreeze_amt
                user.frozen_cash -= unfreeze_amt
                order.frozen_cash -= unfreeze_amt
                order.quantity -= cancel_qty

            if recovered >= shortfall:
                break

        if recovered < shortfall:
            await db.rollback()
            return {
                "success": False,
                "error": "Insufficient funds: cancelled all pending orders but still short",
            }

    if deduction > 0:
        user.cash_balance -= deduction

    db.add(
        TrapEvent(
            user_id=user_id,
            type=trap_type,
            severity=trap_severity,
            description=description,
            points_deducted=int(deduction),
            detected_at=_utcnow(),
            simulated_at=_utcnow(),
        )
    )

    await db.commit()
    return {
        **result,
        "cooldown_until": cooldown_until,
        "reason": _build_reason(trap_type, trap_severity, description),
    }


async def clear_cooldown(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Gỡ khóa giao dịch — chỉ khi cooldown đã hết hạn (không thể rút ngắn).

    Đồng thời đánh dấu các lần vi phạm chưa xử lý là đã resolved
    (hoàn thành bài tập phản tư với Mentor).
    """
    now = _utcnow()
    user = (
        await db.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one_or_none()

    if not user:
        return {"success": False, "error": "User not found"}
    if not user.cooldown_until:
        return {
            "success": True,
            "cleared": False,
            "locked": False,
            "cooldown_until": None,
            "remaining_seconds": 0,
            "risk_score": user.risk_score,
            "reason": None,
        }
    if user.cooldown_until > now:
        return {
            "success": True,
            "cleared": False,
            "locked": True,
            "cooldown_until": user.cooldown_until,
            "remaining_seconds": math.ceil((user.cooldown_until - now).total_seconds()),
            "risk_score": user.risk_score,
            "reason": await _penalty_reason(user_id, db),
        }

    user.cooldown_until = None

    events = (
        await db.execute(
            select(TrapEvent)
            .where(TrapEvent.user_id == user_id, TrapEvent.resolved_at.is_(None))
            .with_for_update()
        )
    ).scalars().all()
    for event in events:
        event.resolved_at = now

    await db.commit()
    return {
        "success": True,
        "cleared": True,
        "locked": False,
        "cooldown_until": None,
        "remaining_seconds": 0,
        "risk_score": user.risk_score,
        "reason": None,
    }
