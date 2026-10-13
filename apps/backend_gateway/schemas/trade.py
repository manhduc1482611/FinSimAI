import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from core.config import settings
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_OrderSide = Literal["buy", "sell"]
_OrderType = Literal["market", "limit"]
_OrderStatus = Literal["pending", "filled", "partially_filled", "cancelled", "rejected"]

# Số chữ số thập phân tối đa khớp cột DB: giá Numeric(20,2), khối lượng Numeric(20,4).
# Vượt ngưỡng sẽ bị Postgres làm tròn âm thầm (sai lệch giá trị đóng băng/thực nhận).
_PRICE_MAX_DECIMALS = 2
_QUANTITY_MAX_DECIMALS = 4
# Trần khối lượng một lệnh — đồng bộ settings.max_order_quantity.
_MAX_ORDER_QUANTITY = Decimal(str(settings.max_order_quantity))


def _decimal_places(value: Decimal) -> int:
    """Số chữ số phần thập phân của ``Decimal`` (0 nếu là số nguyên/special)."""
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        return 0
    return max(-exponent, 0)


class OrderRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_id: uuid.UUID
    side: _OrderSide
    type: _OrderType = "limit"
    price: Decimal | None = Field(None, gt=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"), le=_MAX_ORDER_QUANTITY)

    @field_validator("price")
    @classmethod
    def check_price_precision(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and _decimal_places(v) > _PRICE_MAX_DECIMALS:
            raise ValueError(f"price tối đa {_PRICE_MAX_DECIMALS} chữ số thập phân")
        return v

    @field_validator("quantity")
    @classmethod
    def check_quantity_precision(cls, v: Decimal) -> Decimal:
        if _decimal_places(v) > _QUANTITY_MAX_DECIMALS:
            raise ValueError(f"quantity tối đa {_QUANTITY_MAX_DECIMALS} chữ số thập phân")
        return v

    @model_validator(mode="after")
    def check_price(self) -> Self:
        if self.type == "limit" and self.price is None:
            raise ValueError("price is required when type='limit'")
        if self.type == "market" and self.price is not None:
            self.price = None
        return self


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    side: _OrderSide
    type: _OrderType
    status: _OrderStatus
    price: Decimal | None
    quantity: Decimal
    filled_quantity: Decimal
    created_at: datetime


class PortfolioResponse(BaseModel):
    company_id: uuid.UUID
    symbol: str
    company_name: str
    quantity: Decimal
    average_buy_price: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal


class PortfolioListResponse(BaseModel):
    items: list[PortfolioResponse]
    total_cash: Decimal
    total_nav: Decimal
