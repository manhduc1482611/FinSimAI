from dataclasses import dataclass


@dataclass
class Holding:
    quantity: float
    average_buy_price: float
    current_price: float


@dataclass
class TradeResult:
    new_quantity: float
    new_avg_price: float
    realized_pnl_delta: float
    fee: float


def calc_nav(cash_balance: float, holdings: list[Holding]) -> float:
    return cash_balance + sum(h.quantity * h.current_price for h in holdings)


def calc_unrealized_pnl(holdings: list[Holding]) -> float:
    return sum(h.quantity * (h.current_price - h.average_buy_price) for h in holdings)


def apply_buy(
    current_quantity: float,
    current_avg_price: float,
    buy_quantity: float,
    buy_price: float,
    fee: float = 0.0,
) -> TradeResult:
    if buy_quantity <= 0 or buy_price <= 0:
        raise ValueError("buy_quantity and buy_price must be positive")

    total_asset_value = current_quantity * current_avg_price + buy_quantity * buy_price
    new_qty = current_quantity + buy_quantity
    new_avg = total_asset_value / new_qty if new_qty > 0 else 0.0

    return TradeResult(
        new_quantity=new_qty,
        new_avg_price=new_avg,
        realized_pnl_delta=-fee,
        fee=fee,
    )


def apply_sell(
    current_quantity: float,
    current_avg_price: float,
    sell_quantity: float,
    sell_price: float,
    fee: float = 0.0,
) -> TradeResult:
    if sell_quantity <= 0 or sell_price <= 0:
        raise ValueError("sell_quantity and sell_price must be positive")
    if sell_quantity > current_quantity:
        raise ValueError("cannot sell more than current quantity")

    realized = sell_quantity * (sell_price - current_avg_price) - fee
    new_qty = current_quantity - sell_quantity
    new_avg = current_avg_price if new_qty > 0 else 0.0

    return TradeResult(
        new_quantity=new_qty,
        new_avg_price=new_avg,
        realized_pnl_delta=realized,
        fee=fee,
    )
