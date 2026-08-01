import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TrapEvent(Base):
    """Một lần vi phạm kỷ luật giao dịch được hệ thống phát hiện (bẫy tâm lý).

    Mỗi event ghi lại mức độ vi phạm, số điểm rủi ro bị trừ và thời điểm bị
    phát hiện. Khi cooldown được gỡ (sau bài tập phản tư với Mentor), event
    được đánh dấu ``resolved_at`` — dùng làm "lý do phạt" hiển thị trên
    CooldownOverlay và cho analytics sau này.
    """

    __tablename__ = "trap_events"
    __table_args__ = (
        Index("idx_trap_events_user", "user_id", "detected_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    social_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_posts.id", ondelete="SET NULL")
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    points_deducted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
