import logging
import uuid
from decimal import Decimal
from typing import Any

from models.company import Company
from models.trade import Order, Portfolio, Transaction
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _price_crosses(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
) -> bool:
    if buy_price is None or sell_price is None:
        return True
    return buy_price >= sell_price


async def _peek_best_buy(
    company_id: uuid.UUID,
    db: AsyncSession,
    skip_ids: set[uuid.UUID] | None = None,
) -> Order | None:
    stmt = (
        select(Order)
        .where(
            Order.company_id == company_id,
            Order.side == "buy",
            Order.status.in_(["pending", "partially_filled"]),
            Order.quantity > Order.filled_quantity,
        )
        .order_by(Order.price.desc().nullsfirst(), Order.created_at.asc())
        .limit(1)
    )
    if skip_ids:
        stmt = stmt.where(Order.id.notin_(skip_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _peek_best_sell(
    company_id: uuid.UUID,
    db: AsyncSession,
    skip_ids: set[uuid.UUID] | None = None,
) -> Order | None:
    stmt = (
        select(Order)
        .where(
            Order.company_id == company_id,
            Order.side == "sell",
            Order.status.in_(["pending", "partially_filled"]),
            Order.quantity > Order.filled_quantity,
        )
        .order_by(Order.price.asc().nullsfirst(), Order.created_at.asc())
        .limit(1)
    )
    if skip_ids:
        stmt = stmt.where(Order.id.notin_(skip_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _lock_users_sorted(
    id1: uuid.UUID,
    id2: uuid.UUID,
    db: AsyncSession,
) -> tuple[User, User]:
    if id1 == id2:
        user = (
            await db.execute(select(User).where(User.id == id1).with_for_update())
        ).scalar_one()
        return user, user
    first_id, second_id = (id1, id2) if id1 < id2 else (id2, id1)
    first = (
        await db.execute(select(User).where(User.id == first_id).with_for_update())
    ).scalar_one()
    second = (
        await db.execute(select(User).where(User.id == second_id).with_for_update())
    ).scalar_one()
    return (first, second) if first_id == id1 else (second, first)


async def _lock_orders_sorted(
    buy_id: uuid.UUID,
    sell_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[Order | None, Order | None]:
    first_id, second_id = (buy_id, sell_id) if buy_id < sell_id else (sell_id, buy_id)
    o1 = (
        await db.execute(select(Order).where(Order.id == first_id).with_for_update())
    ).scalar_one_or_none()
    o2 = (
        await db.execute(select(Order).where(Order.id == second_id).with_for_update())
    ).scalar_one_or_none()
    if first_id == buy_id:
        return o1, o2
    return o2, o1


def _buy_freeze_price(buy: Order) -> Decimal:
    if buy.type == "limit" and buy.price:
        return buy.price
    remaining_qty = buy.quantity - buy.filled_quantity
    if remaining_qty > 0 and buy.frozen_cash > Decimal("0"):
        return buy.frozen_cash / remaining_qty
    return buy.price if buy.price else Decimal("0")


async def _apply_buy_fill(
    buy: Order,
    fill_qty: Decimal,
    fill_price: Decimal,
    current_price: Decimal,
    user: User,
    db: AsyncSession,
) -> None:
    freeze_price = _buy_freeze_price(buy)
    actual_cost = fill_qty * fill_price

    remaining_before = buy.quantity - buy.filled_quantity
    if fill_qty >= remaining_before:
        unfreeze_amount = buy.frozen_cash
    else:
        unfreeze_amount = min(fill_qty * freeze_price, buy.frozen_cash)

    user.cash_balance += unfreeze_amount - actual_cost
    user.frozen_cash -= unfreeze_amount
    buy.frozen_cash -= unfreeze_amount

    pf_stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == buy.user_id, Portfolio.company_id == buy.company_id)
        .with_for_update()
    )
    pf = (await db.execute(pf_stmt)).scalar_one_or_none()

    if pf:
        total_qty = pf.quantity + fill_qty
        total_cost = pf.quantity * pf.average_buy_price + actual_cost
        pf.average_buy_price = total_cost / total_qty if total_qty > 0 else Decimal("0")
        pf.quantity = total_qty
    else:
        pf = Portfolio(
            user_id=buy.user_id,
            company_id=buy.company_id,
            quantity=fill_qty,
            average_buy_price=fill_price,
        )
        db.add(pf)


async def _apply_sell_fill(
    sell: Order,
    fill_qty: Decimal,
    fill_price: Decimal,
    user: User,
    db: AsyncSession,
) -> None:
    revenue = fill_qty * fill_price
    user.cash_balance += revenue

    pf_stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == sell.user_id, Portfolio.company_id == sell.company_id)
        .with_for_update()
    )
    pf = (await db.execute(pf_stmt)).scalar_one_or_none()
    if not pf:
        return

    pf.frozen_quantity -= fill_qty
    pf.quantity -= fill_qty
    pf.realized_pnl += revenue - fill_qty * pf.average_buy_price


async def match_orders(
    company_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    company = await db.get(Company, company_id)
    if not company:
        return []

    simulated_at = company.updated_at
    market_price = company.current_price

    transactions: list[dict[str, Any]] = []
    skip_buy_ids: set[uuid.UUID] = set()
    skip_sell_ids: set[uuid.UUID] = set()

    while True:
        buy = await _peek_best_buy(company_id, db, skip_buy_ids)
        sell = await _peek_best_sell(company_id, db, skip_sell_ids)

        if not buy or not sell:
            break

        buy_price = buy.price if buy.type == "limit" else None
        sell_price = sell.price if sell.type == "limit" else None

        if not _price_crosses(buy_price, sell_price):
            break

        if buy.user_id == sell.user_id:
            buyer, seller = await _lock_users_sorted(buy.user_id, sell.user_id, db)

            locked_buy, locked_sell = await _lock_orders_sorted(buy.id, sell.id, db)
            if (
                not locked_buy
                or not locked_sell
                or locked_buy.status not in ("pending", "partially_filled")
                or locked_sell.status not in ("pending", "partially_filled")
            ):
                skip_buy_ids.add(buy.id)
                skip_sell_ids.add(sell.id)
                await db.rollback()
                continue

            buyer.cash_balance += locked_buy.frozen_cash
            buyer.frozen_cash -= locked_buy.frozen_cash
            locked_buy.frozen_cash = Decimal("0")
            locked_buy.status = "cancelled"

            pf_stmt = (
                select(Portfolio)
                .where(
                    Portfolio.user_id == locked_sell.user_id,
                    Portfolio.company_id == locked_sell.company_id,
                )
                .with_for_update()
            )
            pf = (await db.execute(pf_stmt)).scalar_one_or_none()
            if pf:
                pf.frozen_quantity -= locked_sell.quantity - locked_sell.filled_quantity
            locked_sell.status = "cancelled"
            skip_buy_ids.add(buy.id)
            skip_sell_ids.add(sell.id)
            await db.commit()
            continue

        buyer, seller = await _lock_users_sorted(buy.user_id, sell.user_id, db)

        locked_buy, locked_sell = await _lock_orders_sorted(buy.id, sell.id, db)
        if (
            not locked_buy
            or not locked_sell
            or locked_buy.status not in ("pending", "partially_filled")
            or locked_sell.status not in ("pending", "partially_filled")
        ):
            if buy:
                skip_buy_ids.add(buy.id)
            if sell:
                skip_sell_ids.add(sell.id)
            await db.rollback()
            continue

        buy_price = locked_buy.price if locked_buy.type == "limit" else None
        sell_price = locked_sell.price if locked_sell.type == "limit" else None
        if not _price_crosses(buy_price, sell_price):
            skip_buy_ids.add(buy.id)
            skip_sell_ids.add(sell.id)
            await db.rollback()
            continue

        buy_remain = locked_buy.quantity - locked_buy.filled_quantity
        sell_remain = locked_sell.quantity - locked_sell.filled_quantity
        fill_qty = min(buy_remain, sell_remain)

        if locked_buy.type == "limit" and locked_sell.type == "limit":
            fill_price = buy_price if locked_buy.created_at < locked_sell.created_at else sell_price
        elif locked_buy.type == "market":
            fill_price = sell_price
        else:
            fill_price = buy_price

        if fill_price is None:
            fill_price = market_price

        tx = Transaction(
            order_id=locked_buy.id,
            user_id=locked_buy.user_id,
            company_id=company_id,
            side="buy",
            quantity=fill_qty,
            price=fill_price,
            simulated_at=simulated_at,
        )
        db.add(tx)

        sell_tx = Transaction(
            order_id=locked_sell.id,
            user_id=locked_sell.user_id,
            company_id=company_id,
            side="sell",
            quantity=fill_qty,
            price=fill_price,
            simulated_at=simulated_at,
        )
        db.add(sell_tx)

        await _apply_buy_fill(locked_buy, fill_qty, fill_price, market_price, buyer, db)
        await _apply_sell_fill(locked_sell, fill_qty, fill_price, seller, db)

        locked_buy.filled_quantity += fill_qty
        locked_sell.filled_quantity += fill_qty

        if locked_buy.filled_quantity >= locked_buy.quantity:
            locked_buy.status = "filled"
        else:
            locked_buy.status = "partially_filled"

        if locked_sell.filled_quantity >= locked_sell.quantity:
            locked_sell.status = "filled"
        else:
            locked_sell.status = "partially_filled"

        sell_order_id = locked_sell.id
        sell_user_id = locked_sell.user_id
        fill = {
            "order_id": locked_buy.id,
            "user_id": locked_buy.user_id,
            "company_id": company_id,
            "side": "buy",
            "quantity": fill_qty,
            "price": fill_price,
            "simulated_at": simulated_at,
        }
        sell_fill = {
            "order_id": sell_order_id,
            "user_id": sell_user_id,
            "company_id": company_id,
            "side": "sell",
            "quantity": fill_qty,
            "price": fill_price,
            "simulated_at": simulated_at,
        }
        await db.commit()

        # id/created_at là server_default (gen_random_uuid / now()) — chỉ có sau
        # commit; refresh để lấy cho event-push. transaction_id + created_at giúp
        # TradeNotifier claim (SETNX) + watermark, tránh poll catch-up đẩy trùng.
        await db.refresh(tx)
        await db.refresh(sell_tx)
        fill["transaction_id"] = tx.id
        fill["created_at"] = tx.created_at
        sell_fill["transaction_id"] = sell_tx.id
        sell_fill["created_at"] = sell_tx.created_at
        transactions.append(fill)
        transactions.append(sell_fill)

    await _notify_fills(transactions)
    return transactions


async def _notify_fills(transactions: list[dict[str, Any]]) -> None:
    """Đẩy khớp lệnh real-time qua TradeNotifier sau khi commit (best-effort).

    Import muộn tránh vòng dependency services → websockets ở module-level. Nếu
    lớp WebSocket/Redis hỏng, không làm hỏng giao dịch vừa commit — poll catch-up
    của leader sẽ bù phát (claim-first + watermark đã chống đẩy trùng).
    """
    if not transactions:
        return
    try:
        from realtime.trade_ws import trade_notifier

        await trade_notifier.notify_transactions(transactions)
    except Exception:
        logger.exception(
            "Trade fill push failed — poll catch-up will cover %d fill(s)",
            len(transactions),
        )
