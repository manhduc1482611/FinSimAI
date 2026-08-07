import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        Index("idx_news_company_simulated", "company_id", "simulated_at"),
        Index("idx_news_contest_company_simulated", "contest_id", "company_id", "simulated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="FinSim AI News", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="vĩ mô", nullable=False, index=True)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral", nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)

    contest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="news")
    social_posts = relationship("SocialPost", back_populates="news")
    contest = relationship("Contest", back_populates="news")
