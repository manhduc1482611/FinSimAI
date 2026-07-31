import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str
    description: str | None
    sector: str
    current_price: Decimal
    volatility: Decimal
    shares_outstanding: Decimal
    market_cap: Decimal | None
    health_score: int
    pe_ratio: Decimal | None
    roe: Decimal | None
    net_margin: Decimal | None


class CompanyListResponse(BaseModel):
    items: list[CompanyResponse]
    total: int
