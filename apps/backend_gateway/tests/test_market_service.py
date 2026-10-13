import uuid
from decimal import Decimal

import pytest


def test_day_reference_stable_within_day_resets_next_day() -> None:
    from services import market_service

    market_service._DAY_REFERENCE.clear()
    cid = uuid.uuid4()
    day = 1_000

    first = market_service._reference_price(cid, day, Decimal("50.00"))
    assert first == Decimal("50.00")
    # Giá đổi trong CÙNG ngày → vẫn trả mốc đã chốt (biên không trôi).
    again = market_service._reference_price(cid, day, Decimal("55.00"))
    assert again == Decimal("50.00")
    # Sang ngày mô phỏng mới → chốt mốc mới theo giá hiện tại.
    next_day = market_service._reference_price(cid, day + 1, Decimal("55.00"))
    assert next_day == Decimal("55.00")

    market_service._DAY_REFERENCE.clear()


@pytest.mark.asyncio
async def test_fetch_price_values_forwards_reference_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import market_service

    captured: dict[str, object] = {}

    class FakeClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"prices": [kwargs["current_price"], 42.00], "success": True}

    monkeypatch.setattr(market_service, "math_client", FakeClient())

    await market_service._fetch_price_values(
        42.10, 0.019, 1.0 / 252, 7, reference_price=40.0
    )
    assert captured["reference_price"] == 40.0


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

    # Truyền seed cố định: fallback GBM dùng random.Random() không seed sẽ ngẫu
    # nhiên — có ~8% lần ra giá tròn về 42.10 và làm test "flaky" (đỏ giả).
    price = await market_service._fetch_price_values(42.10, 0.019, 1.0 / 252, 7)

    assert price is not None
    assert price != Decimal("42.10")
