import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"
    __table_args__ = (
        Index("idx_knowledge_category_diff", "category", "difficulty"),
        Index("idx_knowledge_related_gin", "related_keywords", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    keyword: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    concept: Mapped[str] = mapped_column(String(500), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    related_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
