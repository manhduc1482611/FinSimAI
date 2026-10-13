from decimal import Decimal

import pytest
from core.config import settings
from models.trade import Order
from services.trading_service import (
    _buy_freeze_price,
    _buy_max_fill_price,
    _is_marketable,
    _notify_fills,
    is_price_within_band,
    price_band_bounds,
)


@pytest.mark.asyncio
async def test_notify_fills_pushes_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    """match_orders sau commit phải đẩy các fill qua trade_notifier (event-driven)."""
    import realtime.trade_ws as trade_ws_module

    pushed: list[list[dict[str, object]]] = []

    class FakeNotifier:
        async def notify_transactions(self, transactions: list[dict[str, object]]) -> int:
            pushed.append(transactions)
            return len(transactions)

    monkeypatch.setattr(trade_ws_module, "trade_notifier", FakeNotifier())

    transactions = [{"user_id": 1, "side": "buy"}]
    await _notify_fills(transactions)

    assert pushed == [transactions]


@pytest.mark.asyncio
async def test_notify_fills_tolerates_notifier_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi lớp WebSocket/Redis KHÔNG làm hỏng giao dịch vừa commit — poll bù phát."""
    import realtime.trade_ws as trade_ws_module

    class BrokenNotifier:
        async def notify_transactions(self, transactions: list[dict[str, object]]) -> int:
            raise RuntimeError("redis down")

    monkeypatch.setattr(trade_ws_module, "trade_notifier", BrokenNotifier())

    await _notify_fills([{"user_id": 1}])  # không được raise


@pytest.mark.asyncio
async def test_notify_fills_skips_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    import realtime.trade_ws as trade_ws_module

    called = False

    class FakeNotifier:
        async def notify_transactions(self, transactions: list[dict[str, object]]) -> int:
            nonlocal called
            called = True
            return 0

    monkeypatch.setattr(trade_ws_module, "trade_notifier", FakeNotifier())

    await _notify_fills([])

    assert called is False


def _order(side: str, type_: str, price: Decimal | None) -> Order:
    return Order(side=side, type=type_, price=price)


def test_is_marketable_market_orders_always_cross() -> None:
    assert _is_marketable(_order("buy", "market", None), Decimal("42.10"))
    assert _is_marketable(_order("sell", "market", None), Decimal("42.10"))


def test_is_marketable_limit_buy_at_or_above_market() -> None:
    assert _is_marketable(_order("buy", "limit", Decimal("43.00")), Decimal("42.10"))
    assert _is_marketable(_order("buy", "limit", Decimal("42.10")), Decimal("42.10"))
    assert not _is_marketable(_order("buy", "limit", Decimal("41.00")), Decimal("42.10"))


def test_is_marketable_limit_sell_at_or_below_market() -> None:
    assert _is_marketable(_order("sell", "limit", Decimal("42.00")), Decimal("42.10"))
    assert _is_marketable(_order("sell", "limit", Decimal("42.10")), Decimal("42.10"))
    assert not _is_marketable(_order("sell", "limit", Decimal("43.00")), Decimal("42.10"))


def test_is_marketable_limit_without_price_never_crosses() -> None:
    assert not _is_marketable(_order("buy", "limit", None), Decimal("42.10"))
    assert not _is_marketable(_order("sell", "limit", None), Decimal("42.10"))


# ── Biên độ trần/sàn ±7% (P0 #5) ────────────────────────────────────────────
def test_price_band_bounds_plus_minus_seven_pct() -> None:
    lower, upper = price_band_bounds(Decimal("100.00"), Decimal("0.07"))
    assert lower == Decimal("93.00")
    assert upper == Decimal("107.00")


def test_price_band_bounds_round_half_up_to_cent() -> None:
    # 42.10 × 0.93 = 39.153 → 39.15; 42.10 × 1.07 = 45.047 → 45.05
    lower, upper = price_band_bounds(Decimal("42.10"), 0.07)
    assert lower == Decimal("39.15")
    assert upper == Decimal("45.05")


def test_is_price_within_band_inclusive_bounds() -> None:
    assert is_price_within_band(Decimal("93.00"), Decimal("100.00"), 0.07)
    assert is_price_within_band(Decimal("107.00"), Decimal("100.00"), 0.07)
    assert is_price_within_band(Decimal("100.00"), Decimal("100.00"), 0.07)
    assert not is_price_within_band(Decimal("92.99"), Decimal("100.00"), 0.07)
    assert not is_price_within_band(Decimal("107.01"), Decimal("100.00"), 0.07)


def test_is_price_within_band_fail_open_without_reference() -> None:
    # Chưa có giá tham chiếu hợp lệ → không đủ dữ liệu, bỏ qua (các check khác bảo vệ).
    assert is_price_within_band(Decimal("1000000"), Decimal("0"), 0.07)


# ── Đóng băng lệnh mua (P0 #4) ──────────────────────────────────────────────
def _buy(
    type_: str,
    price: Decimal | None,
    *,
    qty: Decimal = Decimal("100"),
    filled: Decimal = Decimal("0"),
    frozen: Decimal = Decimal("0"),
) -> Order:
    return Order(
        side="buy",
        type=type_,
        price=price,
        quantity=qty,
        filled_quantity=filled,
        frozen_cash=frozen,
    )


def test_buy_freeze_price_is_fee_inclusive_for_limit() -> None:
    # limit 100 × 100 cp × 1.0015 = 10_015.00 → 100.15/cp (đã gồm buffer phí).
    order = _buy("limit", Decimal("100"), qty=Decimal("100"), frozen=Decimal("10015.00"))
    assert _buy_freeze_price(order) == Decimal("100.15")


def test_buy_max_fill_price_limit_is_the_limit() -> None:
    order = _buy("limit", Decimal("100"), qty=Decimal("100"), frozen=Decimal("10015.00"))
    assert _buy_max_fill_price(order) == Decimal("100")


def test_buy_max_fill_price_market_excludes_fee_keeps_slippage_buffer() -> None:
    current = Decimal("100")
    slip = Decimal(str(settings.max_slippage_impact))
    fee = Decimal(str(settings.trading_fee_rate))
    qty = Decimal("100")
    frozen = qty * current * (Decimal("1") + slip) * (Decimal("1") + fee)
    order = _buy("market", None, qty=qty, frozen=frozen)
    assert _buy_max_fill_price(order) == current * (Decimal("1") + slip)


def test_buy_max_fill_price_zero_frozen_is_zero() -> None:
    assert _buy_max_fill_price(_buy("market", None, frozen=Decimal("0"))) == Decimal("0")
