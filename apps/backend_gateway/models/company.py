import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("current_price >= 0", name="chk_company_current_price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    current_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    volatility: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=Decimal("0.0100"), nullable=False
    )
    shares_outstanding: Mapped[Decimal] = mapped_column(
        Numeric(20, 0), default=Decimal("10000000"), nullable=False
    )
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    health_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    pe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    roe: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    net_margin: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    portfolios = relationship("Portfolio", back_populates="company")
    orders = relationship("Order", back_populates="company")
    transactions = relationship("Transaction", back_populates="company")
    news = relationship("News", back_populates="company")
    social_posts = relationship("SocialPost", back_populates="company")
