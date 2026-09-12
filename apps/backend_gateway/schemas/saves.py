import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from schemas.news import NewsResponse
from schemas.social import SocialPostResponse


class ContentSaveToggleRequest(BaseModel):
    content_type: str = Field(pattern="^(news|social)$")
    content_id: uuid.UUID


class ContentSaveToggleResponse(BaseModel):
    saved: bool


class SavedContentItem(BaseModel):
    content_type: str
    content_id: uuid.UUID
    saved_at: datetime
    news: NewsResponse | None = None
    social: SocialPostResponse | None = None


class SavedContentListResponse(BaseModel):
    items: list[SavedContentItem]
    total: int
