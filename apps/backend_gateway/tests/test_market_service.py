from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_fetch_price_values_uses_last_element(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Math Engine trả path `[giá_cũ, giá_mới]` — phải lấy phần tử CUỐI."""
    from services import market_service

    calls: list[dict[str, object]] = []

    class FakeClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            calls.append(kwargs)
            return {"prices": [kwargs["current_price"], 42.36], "success": True}

    monkeypatch.setattr(market_service, "math_client", FakeClient())

    price = await market_service._fetch_price_values(42.10, 0.019, 1.0 / 252, None)

    assert price == Decimal("42.36")


@pytest.mark.asyncio
async def test_fetch_price_values_falls_back_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Math Engine lỗi → GBM fallback nội bộ, KHÔNG ghi giá cũ."""
    from services import market_service

    class BrokenClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            return {"success": False, "prices": []}

    monkeypatch.setattr(market_service, "math_client", BrokenClient())

    price = await market_service._fetch_price_values(42.10, 0.019, 1.0 / 252, None)

    assert price is not None
    assert price != Decimal("42.10")
