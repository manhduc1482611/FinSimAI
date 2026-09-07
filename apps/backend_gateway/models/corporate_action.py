import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base

# Kiểu sự kiện doanh nghiệp (trùng enum logic bên service).
ACTION_CASH_DIVIDEND = "cash_dividend"
ACTION_STOCK_SPLIT = "stock_split"
ACTION_RIGHTS = "rights"
ACTION_DELISTING = "delisting"
ACTION_NEWS_SHOCK = "news_shock"


class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    __table_args__ = {"comment": "Sự kiện doanh nghiệp theo lịch mô phỏng"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(24), nullable=False)
    ex_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("Company", back_populates="corporate_actions")
