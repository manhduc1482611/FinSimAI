import uuid
from datetime import datetime, timedelta, timezone
from decimal import ROUND_UP, Decimal

from clients.math_grpc_client import math_grpc_client
from models.trade import Order
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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
) -> dict:
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

    user = (
        await db.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one()

    user.risk_score = result["new_risk_score"]

    if result.get("cooldown_seconds", 0) > 0:
        user.cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=result["cooldown_seconds"]
        )

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
                cancel_qty = (needed / freeze_price).quantize(Decimal("1"), rounding=ROUND_UP)
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

    await db.commit()
    return result


async def clear_cooldown(user_id: uuid.UUID, db: AsyncSession) -> bool:
    now = datetime.now(timezone.utc)
    user_stmt = select(User).where(User.id == user_id).with_for_update()
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or not user.cooldown_until:
        return False
    if user.cooldown_until > now:
        return False
    user.cooldown_until = None
    await db.commit()
    return True
