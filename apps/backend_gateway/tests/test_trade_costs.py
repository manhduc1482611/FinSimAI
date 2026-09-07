"""Test phí giao dịch (0.15%) + thuế bán hàng (0.1%) — realism engine B1."""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from models.trade import Order, Portfolio
from services.trading_service import _apply_buy_fill, _apply_sell_fill, _trade_costs


class _FakeDB:
    def __init__(self, portfolio: Portfolio | None) -> None:
        self._portfolio = portfolio
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, stmt: object) -> SimpleNamespace:
        return SimpleNamespace(scalar_one_or_none=lambda: self._portfolio)


def _user(cash: str = "1000000.00", frozen: str = "0.00", settling: str = "0.00") -> SimpleNamespace:
    return SimpleNamespace(
        cash_balance=Decimal(cash),
        frozen_cash=Decimal(frozen),
        settling_cash=Decimal(settling),
    )


# ── Công thức phí/thuế ──────────────────────────────────────────────────────
def test_buy_costs_fee_only_no_tax() -> None:
    fee, tax = _trade_costs("buy", Decimal("100"), Decimal("50"))
    # gross = 5_000 → phí 0.15% = 7.50; mua không chịu thuế.
    assert fee == Decimal("7.50")
    assert tax == Decimal("0.00")


def test_sell_costs_fee_and_tax() -> None:
    fee, tax = _trade_costs("sell", Decimal("100"), Decimal("50"))
    assert fee == Decimal("7.50")
    # thuế 0.1% × 5_000 = 5.00
    assert tax == Decimal("5.00")


def test_costs_round_half_up_to_cent() -> None:
    # gross = 33.33 → fee = 0.049995 → làm tròn 0.05
    fee, tax = _trade_costs("buy", Decimal("1"), Decimal("33.33"))
    assert fee == Decimal("0.05")
    assert tax == Decimal("0.00")


# ── Dòng tiền khi khớp ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_buy_fill_debits_cost_plus_fee_and_sets_avg_price_with_fee() -> None:
    order = Order(
        side="buy", type="market", quantity=Decimal("100"),
        filled_quantity=Decimal("0"), frozen_cash=Decimal("5000.00"),
    )
    user = _user(cash="1000000.00", frozen="5000.00")
    db = _FakeDB(portfolio=None)

    fee, tax = await _apply_buy_fill(
        order, Decimal("100"), Decimal("50"), Decimal("50"), user, db
    )

    assert (fee, tax) == (Decimal("7.50"), Decimal("0.00"))
    # Hoàn frozen 5000, trừ tổng 5007.50 → cash giảm đúng 7.50 so với ban đầu,
    # frozen về 0.
    assert user.cash_balance == Decimal("999992.50")
    assert user.frozen_cash == Decimal("0.00")
    assert order.frozen_cash == Decimal("0.00")


@pytest.mark.asyncio
async def test_buy_fill_average_price_includes_fee() -> None:
    order = Order(
        side="buy", type="market", quantity=Decimal("100"),
        filled_quantity=Decimal("0"), frozen_cash=Decimal("5000.00"),
    )
    user = _user()
    db = _FakeDB(portfolio=None)

    await _apply_buy_fill(order, Decimal("100"), Decimal("50"), Decimal("50"), user, db)

    assert len(db.added) == 1
    pf = db.added[0]
    # Giá vốn = (5000 + 7.50) / 100 = 50.075 — gồm cả phí mua.
    assert pf.average_buy_price == Decimal("5007.50") / Decimal("100")
    assert pf.quantity == Decimal("100")


@pytest.mark.asyncio
async def test_sell_fill_credits_settling_cash_net_of_fee_and_tax() -> None:
    """T+2: tiền bán về settling_cash (chưa dùng được), không vào cash_balance."""
    pf = Portfolio(
        quantity=Decimal("100"), frozen_quantity=Decimal("100"),
        average_buy_price=Decimal("40.00"), realized_pnl=Decimal("0.00"),
    )
    order = Order(side="sell", type="market", quantity=Decimal("100"))
    user = _user(cash="0.00")

    fee, tax = await _apply_sell_fill(order, Decimal("100"), Decimal("50"), user, _FakeDB(pf))

    assert (fee, tax) == (Decimal("7.50"), Decimal("5.00"))
    # Ròng về tay = 5000 − 7.50 − 5.00 = 4987.50 → đang CHỜ thanh toán (settling).
    assert user.settling_cash == Decimal("4987.50")
    assert user.cash_balance == Decimal("0.00")
    assert pf.quantity == Decimal("0")
    assert pf.frozen_quantity == Decimal("0")
    # Realized PnL ròng = 4987.50 − 4000 = 987.50 (đã trừ chi phí giao dịch).
    assert pf.realized_pnl == Decimal("987.50")


@pytest.mark.asyncio
async def test_sell_fill_without_portfolio_still_credits_settling_cash() -> None:
    """Portfolio thiếu (dữ liệu lệch) không được mất tiền của user."""
    order = Order(side="sell", type="market", quantity=Decimal("10"))
    user = _user(cash="0.00")

    await _apply_sell_fill(order, Decimal("10"), Decimal("50"), user, _FakeDB(None))

    expected_net = Decimal("500") - Decimal("0.75") - Decimal("0.50")
    assert user.settling_cash == expected_net
    assert user.cash_balance == Decimal("0.00")
