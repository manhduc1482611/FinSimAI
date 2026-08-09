"""Schema cho endpoint nội bộ nhận nội dung AI sinh ra (news + social posts).

Chỉ AI Engine dùng (xác thực qua ``X-Internal-Api-Key``). Dữ liệu được
normalise về đúng dạng model của gateway: symbol → ``company_id``, category
tiếng Anh của ai_engine → category tiếng Việt hiển thị, ``has_deception`` →
``is_trap``.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AiNewsItem(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=2000)
    content: str = Field(min_length=1)
    category: str = Field(default="vĩ mô", max_length=100)
    sentiment: str = Field(default="neutral", max_length=20)
    impact_score: float = Field(default=5.0, ge=1.0, le=10.0)
    source: str = Field(default="FinSim AI News", max_length=100)
    company_symbol: str | None = Field(default=None, max_length=20)
    simulated_at: datetime | None = None


class AiSocialPostItem(BaseModel):
    author_name: str = Field(min_length=1, max_length=100)
    author_avatar: str | None = Field(default=None, max_length=500)
    persona_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)
    sentiment: str = Field(default="neutral", max_length=20)
    virality_score: float = Field(default=1.0, ge=1.0, le=10.0)
    company_symbol: str | None = Field(default=None, max_length=20)
    has_deception: bool = False
    simulated_at: datetime | None = None


class AiContentBatch(BaseModel):
    articles: list[AiNewsItem] = Field(default_factory=list)
    social_posts: list[AiSocialPostItem] = Field(default_factory=list)


class AiContentSyncResponse(BaseModel):
    inserted_news: int
    inserted_social_posts: int
    skipped_news: int
    skipped_social_posts: int
