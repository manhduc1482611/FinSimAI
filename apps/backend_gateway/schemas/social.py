import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SocialPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_name: str
    author_avatar: str | None
    persona_type: str
    content: str
    sentiment: str
    virality_score: float
    likes_count: int
    shares_count: int
    comments_count: int
    company_id: uuid.UUID | None
    news_id: uuid.UUID | None
    simulated_at: datetime
    created_at: datetime


class SocialPostListResponse(BaseModel):
    items: list[SocialPostResponse]
    total: int
