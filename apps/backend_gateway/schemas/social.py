import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SocialPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_name: str
    author_avatar: str | None
    persona_type: str
    content: str
    sentiment: str
    is_trap: bool = False
    virality_score: float
    likes_count: int
    shares_count: int
    comments_count: int
    company_id: uuid.UUID | None
    news_id: uuid.UUID | None
    simulated_at: datetime
    created_at: datetime
    liked_by_me: bool = False


class SocialPostCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    company_symbol: str | None = Field(default=None, max_length=20)


class SocialPostListResponse(BaseModel):
    items: list[SocialPostResponse]
    total: int


class SocialCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    post_id: uuid.UUID
    author_name: str
    author_avatar: str | None
    content: str
    created_at: datetime


class SocialCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class SocialCommentListResponse(BaseModel):
    items: list[SocialCommentResponse]
    total: int


class SocialLikeResponse(BaseModel):
    liked: bool
    likes_count: int
