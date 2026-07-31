import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keyword: str
    concept: str
    definition: str
    category: str
    difficulty: int
    related_keywords: list[str] | None
    created_at: datetime


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeResponse]
    total: int


class KnowledgeMatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)


class KnowledgeMatchResponse(BaseModel):
    matches: list[KnowledgeResponse]
