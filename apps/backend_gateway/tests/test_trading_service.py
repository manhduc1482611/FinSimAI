from decimal import Decimal

import pytest
from models.trade import Order
from services.trading_service import _is_marketable, _notify_fills


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
