"""Test mô hình slippage & tick size VN (realism engine)."""

from decimal import Decimal

import pytest
from services.slippage import (
    compute_fill_price,
    round_to_tick,
    vn_tick_size,
)


# ── Tick size VN ───────────────────────────────────────────────────────────
def test_vn_tick_size_toy_prices() -> None:
    assert vn_tick_size(Decimal("42.10")) == Decimal("0.01")
    assert vn_tick_size(Decimal("999.99")) == Decimal("0.01")


def test_vn_tick_size_bands() -> None:
    assert vn_tick_size(Decimal("1000")) == Decimal("10")
    assert vn_tick_size(Decimal("10000")) == Decimal("50")
    assert vn_tick_size(Decimal("50000")) == Decimal("100")


def test_round_to_tick_rounds_to_nearest() -> None:
    assert round_to_tick(Decimal("42.137"), Decimal("0.01")) == Decimal("42.14")
    assert round_to_tick(Decimal("42.103"), Decimal("0.01")) == Decimal("42.10")


# ── Slippage ───────────────────────────────────────────────────────────────
def test_small_order_barely_slips() -> None:
    fill = compute_fill_price(
        side="buy",
        quantity=Decimal("100"),
        market_price=Decimal("42.10"),
        liquidity_depth=Decimal("500000"),
    )
    # Tham gia < 1% → trượt rất nhỏ, làm tròn theo tick.
    assert fill >= Decimal("42.10")
    assert fill < Decimal("42.20")


def test_buy_large_slips_up() -> None:
    fill = compute_fill_price(
        side="buy",
        quantity=Decimal("500000"),
        market_price=Decimal("42.10"),
        liquidity_depth=Decimal("500000"),
    )
    # Tham gia = 100% → trượt lên (impact cap 2%), làm tròn tick.
    assert fill >= Decimal("42.10")
    assert fill <= Decimal("43.00")


def test_sell_large_slips_down() -> None:
    fill = compute_fill_price(
        side="sell",
        quantity=Decimal("500000"),
        market_price=Decimal("42.10"),
        liquidity_depth=Decimal("500000"),
    )
    # Tham gia = 100% → trượt xuống (impact cap 2%), làm tròn tick.
    assert fill <= Decimal("42.10")
    assert fill >= Decimal("41.20")


def test_zero_depth_returns_market_price() -> None:
    assert compute_fill_price(
        side="buy",
        quantity=Decimal("1000"),
        market_price=Decimal("42.10"),
        liquidity_depth=Decimal("0"),
    ) == Decimal("42.10")


def test_fill_price_always_multiple_of_tick() -> None:
    for qty in (Decimal("1"), Decimal("1000"), Decimal("100000"), Decimal("500000")):
        for side in ("buy", "sell"):
            price = compute_fill_price(
                side=side,
                quantity=qty,
                market_price=Decimal("12345.00"),
                liquidity_depth=Decimal("500000"),
            )
            tick = vn_tick_size(Decimal("12345.00"))
            assert (price % tick) == 0 or abs((price % tick) - tick) < Decimal("0.0001")


def test_invalid_side_raises() -> None:
    with pytest.raises(ValueError):
        compute_fill_price(
            side="hold",  # type: ignore[arg-type]
            quantity=Decimal("10"),
            market_price=Decimal("42.10"),
            liquidity_depth=Decimal("500000"),
        )
