import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class DisciplineScoreHistory(Base):
    __tablename__ = "discipline_score_history"
    __table_args__ = {"comment": "Log mọi biến động Điểm kỷ luật (audit trail)"}

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    score_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="discipline_history")
