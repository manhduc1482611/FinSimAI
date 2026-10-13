"""Validation lệnh đặt (P0 #5).

Kiểm tra ``OrderRequest`` siết chặt đầu vào: scale giá (≤2 dp) và khối lượng
(≤4 dp) khớp cột DB, trần khối lượng, và yêu cầu giá với lệnh limit — tránh
Postgres làm tròn âm thầm giá trị đóng băng / thực nhận.
"""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from core.config import settings
from pydantic import ValidationError
from schemas.trade import OrderRequest

_MAX_QUANTITY = Decimal(str(settings.max_order_quantity))


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "company_id": str(uuid.uuid4()),
        "side": "buy",
        "type": "limit",
        "price": "42.10",
        "quantity": "100",
    }
    base.update(overrides)
    return base


def test_valid_limit_order() -> None:
    order = OrderRequest.model_validate(_payload())
    assert order.price == Decimal("42.10")
    assert order.quantity == Decimal("100")
    assert order.type == "limit"


def test_market_order_drops_price() -> None:
    order = OrderRequest.model_validate(
        _payload(type="market", price="999.00")
    )
    assert order.price is None


def test_limit_order_requires_price() -> None:
    with pytest.raises(ValidationError, match="price is required"):
        OrderRequest.model_validate(_payload(price=None))


def test_price_allows_two_decimals() -> None:
    order = OrderRequest.model_validate(_payload(price="42.99"))
    assert order.price == Decimal("42.99")


def test_price_rejects_sub_cent_precision() -> None:
    with pytest.raises(ValidationError, match="price tối đa 2"):
        OrderRequest.model_validate(_payload(price="42.999"))


def test_price_rejects_non_positive() -> None:
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(_payload(price="0"))


def test_quantity_allows_four_decimals() -> None:
    order = OrderRequest.model_validate(_payload(quantity="100.0001"))
    assert order.quantity == Decimal("100.0001")


def test_quantity_rejects_sub_unit_precision() -> None:
    with pytest.raises(ValidationError, match="quantity tối đa 4"):
        OrderRequest.model_validate(_payload(quantity="100.00001"))


def test_quantity_rejects_above_cap() -> None:
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(_payload(quantity=str(_MAX_QUANTITY + 1)))


def test_quantity_accepts_cap_exactly() -> None:
    order = OrderRequest.model_validate(_payload(quantity=str(_MAX_QUANTITY)))
    assert order.quantity == _MAX_QUANTITY


def test_quantity_rejects_zero() -> None:
    with pytest.raises(ValidationError):
        OrderRequest.model_validate(_payload(quantity="0"))
