import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

_OrderSide = Literal["buy", "sell"]
_OrderType = Literal["market", "limit"]
_OrderStatus = Literal["pending", "filled", "partially_filled", "cancelled", "rejected"]


class OrderRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_id: uuid.UUID
    side: _OrderSide
    type: _OrderType = "limit"
    price: Decimal | None = Field(None, gt=Decimal("0"))
    quantity: Decimal = Field(gt=Decimal("0"))

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
