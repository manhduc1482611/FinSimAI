import logging
import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from core.config import settings
from models.company import Company
from services.settlement_service import settlement_deadline
from services.slippage import compute_fill_price
from models.trade import Order, Portfolio, Transaction
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_CENT = Decimal("0.01")


def _trade_costs(side: str, quantity: Decimal, price: Decimal) -> tuple[Decimal, Decimal]:
    """Phí giao dịch + thuế của một lượt khớp.

    - Phí 0.15% giá trị khớp, áp cả MUA và BÁN.
    - Thuế chuyển nhượng 0.1% chỉ áp chiều BÁN.
    Trả về ``(fee, tax)`` đã làm tròn tới cent.
    """
    gross = quantity * price
    fee = (gross * Decimal(str(settings.trading_fee_rate))).quantize(_CENT, ROUND_HALF_UP)
    if side == "sell":
        tax = (gross * Decimal(str(settings.sell_tax_rate))).quantize(_CENT, ROUND_HALF_UP)
    else:
        tax = Decimal("0.00")
    return fee, tax


def _price_crosses(
    buy_price: Decimal | None,
    sell_price: Decimal | None,
) -> bool:
    if buy_price is None or sell_price is None:
        return True
    return buy_price >= sell_price


def _is_marketable(order: Order, market_price: Decimal) -> bool:
    """Lệnh đã khớp được ngay với giá thị trường (market maker).

    Market → luôn khớp. Limit → khớp khi giá thị trường vượt/ngang mức limit
    (mua: limit >= giá thị trường; bán: limit <= giá thị trường).
    """
    if order.type == "market":
        return True
    if order.price is None:
        return False
    if order.side == "buy":
        return order.price >= market_price
    return order.price <= market_price


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
) -> tuple[Decimal, Decimal]:
    """Ghi nhận lượt khớp MUA: trừ tiền (giá + phí), cập nhật portfolio.

    Trả về ``(fee, tax)`` để caller đóng dấu lên Transaction.
    """
    freeze_price = _buy_freeze_price(buy)
    actual_cost = fill_qty * fill_price
    fee, tax = _trade_costs("buy", fill_qty, fill_price)
    total_debit = actual_cost + fee

    remaining_before = buy.quantity - buy.filled_quantity
    if fill_qty >= remaining_before:
        unfreeze_amount = buy.frozen_cash
    else:
        unfreeze_amount = min(fill_qty * freeze_price, buy.frozen_cash)

    user.cash_balance += unfreeze_amount - total_debit
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
        # Giá vốn gồm cả phí mua — phản ánh đúng tổng chi phí sở hữu.
        total_cost = pf.quantity * pf.average_buy_price + total_debit
        pf.average_buy_price = total_cost / total_qty if total_qty > 0 else Decimal("0")
        pf.quantity = total_qty
    else:
        pf = Portfolio(
            user_id=buy.user_id,
            company_id=buy.company_id,
            quantity=fill_qty,
            average_buy_price=total_debit / fill_qty,
        )
        db.add(pf)

    return fee, tax


async def _apply_sell_fill(
    sell: Order,
    fill_qty: Decimal,
    fill_price: Decimal,
    user: User,
    db: AsyncSession,
) -> tuple[Decimal, Decimal]:
    """Ghi nhận lượt khớp BÁN: hoãn tiền ròng theo T+2, cập nhật portfolio.

    Tiền ròng (revenue − phí − thuế) được ghi vào ``settling_cash`` (chưa dùng
    được) thay vì ``cash_balance`` — mô phỏng thanh toán bù trừ T+2. Caller phải
    đóng dấu ``settles_at`` lên Transaction để worker giải phóng tiền sau này.

    Trả về ``(fee, tax)`` để caller đóng dấu lên Transaction.
    """
    revenue = fill_qty * fill_price
    fee, tax = _trade_costs("sell", fill_qty, fill_price)
    net_proceeds = revenue - fee - tax
    user.settling_cash += net_proceeds

    pf_stmt = (
        select(Portfolio)
        .where(Portfolio.user_id == sell.user_id, Portfolio.company_id == sell.company_id)
        .with_for_update()
    )
    pf = (await db.execute(pf_stmt)).scalar_one_or_none()
    if not pf:
        return fee, tax

    pf.frozen_quantity -= fill_qty
    pf.quantity -= fill_qty
    # Lãi/lỗ thực hiện tính trên dòng tiền ròng đã trừ chi phí giao dịch.
    pf.realized_pnl += net_proceeds - fill_qty * pf.average_buy_price
    return fee, tax


async def _fill_against_market(
    order: Order,
    *,
    market_price: Decimal,
    simulated_at: datetime,
    db: AsyncSession,
    liquidity_depth: Decimal,
    remaining_liquidity: Decimal,
) -> dict[str, Any] | None:
    """Fill một lệnh "marketable" với giá thị trường mô phỏng (market maker).

    Thị trường đóng vai đối ứng: lệnh market, hoặc lệnh limit đã lệch giá
    (mua: limit >= giá thị trường; bán: limit <= giá thị trường), được fill tại
    ``market_price`` trừ đi làn trượt giá (slippage) theo độ sâu thanh khoản —
    một người dùng đơn lẻ vẫn giao dịch được mà không cần chờ đối ứng thật.

    Khối lượng khớp KHÔNG vượt quá ``remaining_liquidity`` (giới hạn thanh khoản
    còn lại của công ty trong nhịp này); phần dư để ``partially_filled`` và khớp
    tiếp ở nhịp sau. Lock theo thứ tự order → user để không deadlock với route
    ``create_order`` / ``cancel_order``.
    """
    locked = (
        await db.execute(select(Order).where(Order.id == order.id).with_for_update())
    ).scalar_one_or_none()
    if (
        locked is None
        or locked.status not in ("pending", "partially_filled")
        or locked.quantity <= locked.filled_quantity
        or remaining_liquidity <= 0
    ):
        return None

    user = (
        await db.execute(select(User).where(User.id == locked.user_id).with_for_update())
    ).scalar_one()

    fill_qty = min(locked.quantity - locked.filled_quantity, remaining_liquidity)

    if locked.side == "buy":
        fill_price = compute_fill_price(
            side="buy",
            quantity=fill_qty,
            market_price=market_price,
            liquidity_depth=liquidity_depth,
            impact_factor=Decimal(str(settings.slippage_impact_factor)),
        )
        # Mua trượt lên — không vượt quá limit của chính lệnh (chống fill với giá
        # "ăn qua" mức limit khiến lệnh bị xoá bất hợp lý).
        if locked.type == "limit" and locked.price is not None:
            fill_price = min(fill_price, locked.price)
    else:
        fill_price = compute_fill_price(
            side="sell",
            quantity=fill_qty,
            market_price=market_price,
            liquidity_depth=liquidity_depth,
            impact_factor=Decimal(str(settings.slippage_impact_factor)),
        )
        if locked.type == "limit" and locked.price is not None:
            fill_price = max(fill_price, locked.price)

    if locked.side == "buy":
        fee, tax = await _apply_buy_fill(locked, fill_qty, fill_price, market_price, user, db)
    else:
        fee, tax = await _apply_sell_fill(locked, fill_qty, fill_price, user, db)

    tx = Transaction(
        order_id=locked.id,
        user_id=locked.user_id,
        company_id=locked.company_id,
        side=locked.side,
        quantity=fill_qty,
        price=fill_price,
        fee=fee,
        tax=tax,
        simulated_at=simulated_at,
        settles_at=(
            settlement_deadline(simulated_at) if locked.side == "sell" else None
        ),
    )
    db.add(tx)

    locked.filled_quantity += fill_qty
    if locked.filled_quantity >= locked.quantity:
        locked.status = "filled"
    else:
        locked.status = "partially_filled"

    await db.commit()
    await db.refresh(tx)

    fill: dict[str, Any] = {
        "order_id": locked.id,
        "user_id": locked.user_id,
        "company_id": locked.company_id,
        "side": locked.side,
        "quantity": fill_qty,
        "price": fill_price,
        "fee": tx.fee,
        "tax": tx.tax,
        "simulated_at": simulated_at,
    }
    fill["transaction_id"] = tx.id
    fill["created_at"] = tx.created_at
    return fill


async def match_orders(
    company_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    company = await db.get(Company, company_id)
    if not company:
        return []

    simulated_at = company.updated_at
    market_price = company.current_price
    # Giới hạn thanh khoản: tổng khối lượng khớp của 1 công ty trong 1 nhịp
    # không vượt quá liquidity_depth (ngưỡng tác động thị trường). Giảm dần
    # qua từng lượt khớp (user↔user + market maker) trong cùng một tick.
    liquidity_depth = company.liquidity_depth
    remaining_liquidity = liquidity_depth

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
        fill_qty = min(buy_remain, sell_remain, remaining_liquidity)

        if locked_buy.type == "limit" and locked_sell.type == "limit":
            fill_price = buy_price if locked_buy.created_at < locked_sell.created_at else sell_price
        elif locked_buy.type == "market":
            fill_price = sell_price
        else:
            fill_price = buy_price

        if fill_price is None:
            fill_price = market_price

        buy_fee, buy_tax = await _apply_buy_fill(
            locked_buy, fill_qty, fill_price, market_price, buyer, db
        )
        sell_fee, sell_tax = await _apply_sell_fill(locked_sell, fill_qty, fill_price, seller, db)

        tx = Transaction(
            order_id=locked_buy.id,
            user_id=locked_buy.user_id,
            company_id=company_id,
            side="buy",
            quantity=fill_qty,
            price=fill_price,
            fee=buy_fee,
            tax=buy_tax,
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
            fee=sell_fee,
            tax=sell_tax,
            simulated_at=simulated_at,
            settles_at=settlement_deadline(simulated_at),
        )
        db.add(sell_tx)

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
            "fee": tx.fee,
            "tax": tx.tax,
            "simulated_at": simulated_at,
        }
        sell_fill = {
            "order_id": sell_order_id,
            "user_id": sell_user_id,
            "company_id": company_id,
            "side": "sell",
            "quantity": fill_qty,
            "price": fill_price,
            "fee": sell_tx.fee,
            "tax": sell_tx.tax,
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
        remaining_liquidity = max(remaining_liquidity - fill_qty, Decimal("0"))

        if remaining_liquidity <= 0:
            # Hết thanh khoản nhịp này — dừng khớp tiếp.
            break

    # ── Market-maker pass ──────────────────────────────────────────────
    # Sau khi khớp user ↔ user, các lệnh "marketable" còn sót (market / limit đã
    # lệch giá so với current_price) được fill ngay với giá thị trường (kèm
    # slippage). Đây là mảnh ghép khiến 1 người dùng đơn lẻ đặt lệnh vẫn khớp
    # được — trước đây lệnh treo pending mãi vì thiếu đối ứng trong sổ lệnh.
    while remaining_liquidity > 0:
        buy = await _peek_best_buy(company_id, db, skip_buy_ids)
        sell = await _peek_best_sell(company_id, db, skip_sell_ids)

        if buy is not None and _is_marketable(buy, market_price):
            mm_fill = await _fill_against_market(
                buy,
                market_price=market_price,
                simulated_at=simulated_at,
                db=db,
                liquidity_depth=liquidity_depth,
                remaining_liquidity=remaining_liquidity,
            )
            skip_buy_ids.add(buy.id)
            if mm_fill is not None:
                transactions.append(mm_fill)
                remaining_liquidity = max(
                    remaining_liquidity - Decimal(str(mm_fill["quantity"])),
                    Decimal("0"),
                )
                continue
            continue

        if sell is not None and _is_marketable(sell, market_price):
            mm_fill = await _fill_against_market(
                sell,
                market_price=market_price,
                simulated_at=simulated_at,
                db=db,
                liquidity_depth=liquidity_depth,
                remaining_liquidity=remaining_liquidity,
            )
            skip_sell_ids.add(sell.id)
            if mm_fill is not None:
                transactions.append(mm_fill)
                remaining_liquidity = max(
                    remaining_liquidity - Decimal(str(mm_fill["quantity"])),
                    Decimal("0"),
                )
                continue
            continue

        break

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


async def cancel_order(
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Order:
    """Huỷ lệnh còn treo (pending / partially_filled) và hoàn tiền/CP đã đóng băng.

    - Mua: trả lại ``frozen_cash`` còn lại cho ``cash_balance``.
    - Bán: trả lại phần cổ phiếu chưa khớp về ``frozen_quantity`` của portfolio.
    Lock order → user theo cùng thứ tự với ``_fill_against_market`` để không
    deadlock khi leader đang khớp lệnh trong cùng chu kỳ tick.
    """
    locked = (
        await db.execute(
            select(Order)
            .where(Order.id == order_id, Order.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked is None:
        raise LookupError("Order not found")
    if locked.status not in ("pending", "partially_filled"):
        raise ValueError("Order already finalised")

    if locked.side == "buy":
        user = (
            await db.execute(select(User).where(User.id == locked.user_id).with_for_update())
        ).scalar_one()
        user.cash_balance += locked.frozen_cash
        user.frozen_cash -= locked.frozen_cash
        locked.frozen_cash = Decimal("0.00")
    else:
        pf_stmt = (
            select(Portfolio)
            .where(
                Portfolio.user_id == locked.user_id,
                Portfolio.company_id == locked.company_id,
            )
            .with_for_update()
        )
        pf = (await db.execute(pf_stmt)).scalar_one_or_none()
        if pf:
            pf.frozen_quantity -= locked.quantity - locked.filled_quantity
        locked.frozen_quantity = Decimal("0.0000")

    locked.status = "cancelled"
    await db.commit()
    await db.refresh(locked)

    try:
        from realtime.trade_ws import trade_notifier

        await trade_notifier.notify_order_update(
            {
                "order_id": locked.id,
                "user_id": locked.user_id,
                "company_id": locked.company_id,
                "symbol": None,
                "status": locked.status,
                "side": locked.side,
                "quantity": locked.quantity,
                "filled_quantity": locked.filled_quantity,
                "simulated_at": locked.simulated_at,
            }
        )
    except Exception:
        logger.exception("Order cancel notify failed for %s", locked.id)

    return locked
