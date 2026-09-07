"""Lưu trữ hội thoại Socratic Mentor — improvement_plan A3.2.

Mỗi lượt hỏi/đáp của Mentor được ghi vào ``mentor_messages`` thay vì chỉ giữ
history phía client (trước đây mất khi reload, không kiểm toán được). Lợi ích:

- **Continuity**: reload trang vẫn thấy hội thoại cũ (REST ``GET /mentor/history``).
- **LLM history**: 12 tin gần nhất lấy từ DB gửi cho Gemini thay vì client tự gửi.
- **Cá nhân hóa + kiểm toán** (A4.2, A5.3): dữ liệu nền để chọn focus và audit
  chất lượng mentor theo tuần.

``role`` là "user" | "mentor". ``prompt_version`` ghi nguồn nội dung
(deterministic question-bank hoặc phiên bản prompt YAML của LLM) để truy vết
chất lượng theo phiên bản — improvement_plan A3.4.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

_MENTOR_ROLES = ("user", "mentor")


class MentorMessage(Base):
    __tablename__ = "mentor_messages"
    __table_args__ = (
        Index(
            "idx_mentor_messages_user_time",
            "user_id",
            text("created_at DESC"),
        ),
        Index("idx_mentor_messages_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Focus Socratic của lượt trả lời (NULL với tin nhắn user).
    focus: Mapped[str | None] = mapped_column(String(32))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __init__(self, **kwargs: object) -> None:
        role = kwargs.get("role")
        if role not in _MENTOR_ROLES:
            raise ValueError(f"role phải là một trong {_MENTOR_ROLES}, nhận {role!r}")
        super().__init__(**kwargs)
