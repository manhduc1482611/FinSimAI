import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class SocialPost(Base):
    __tablename__ = "social_posts"
    __table_args__ = (
        Index("idx_social_company_simulated", "company_id", "simulated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    author_avatar: Mapped[str | None] = mapped_column(String(500))
    persona_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral", nullable=False)

    virality_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shares_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    news_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news.id", ondelete="SET NULL"), nullable=True
    )

    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="social_posts")
    news = relationship("News", back_populates="social_posts")
