import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str | None
    content: str
    source: str
    category: str
    sentiment: str
    impact_score: float
    company_id: uuid.UUID | None
    is_ai_generated: bool
    simulated_at: datetime
    created_at: datetime


class NewsListResponse(BaseModel):
    items: list[NewsResponse]
    total: int
