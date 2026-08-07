import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company_portfolio"),
        CheckConstraint("quantity >= 0", name="chk_portfolio_quantity"),
        CheckConstraint("frozen_quantity >= 0", name="chk_portfolio_frozen_quantity"),
        CheckConstraint(
            "quantity >= frozen_quantity", name="chk_portfolio_qty_solvency",
        ),
        Index("idx_portfolios_user_contest", "user_id", "contest_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    contest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contests.id", ondelete="CASCADE"), nullable=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0000"), nullable=False
    )
    frozen_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0000"), nullable=False
    )
    average_buy_price: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    realized_pnl: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __mapper_args__ = {"version_id_col": version_id}

    user = relationship("User", back_populates="portfolios")
    company = relationship("Company", back_populates="portfolios")
    contest = relationship("Contest")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_user_status", "user_id", "status"),
        Index(
            "idx_orders_matching_buy",
            "company_id",
            text("price DESC NULLS LAST"),
            text("created_at ASC"),
            postgresql_where=text("side = 'buy' AND status IN ('pending', 'partially_filled')"),
        ),
        Index(
            "idx_orders_matching_sell",
            "company_id",
            text("price ASC NULLS LAST"),
            text("created_at ASC"),
            postgresql_where=text("side = 'sell' AND status IN ('pending', 'partially_filled')"),
        ),
        CheckConstraint("quantity > 0", name="chk_order_quantity"),
        CheckConstraint(
            "price IS NULL OR price > 0", name="chk_order_price"
        ),
        CheckConstraint(
            "side IN ('buy', 'sell')", name="chk_order_side"
        ),
        CheckConstraint(
            "type IN ('market', 'limit')", name="chk_order_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'filled', 'partially_filled', 'cancelled', 'rejected')",
            name="chk_order_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    type: Mapped[str] = mapped_column(String(10), default="limit", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0000"), nullable=False
    )
    frozen_cash: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    frozen_quantity: Mapped[Decimal] = mapped_column(
        Numeric(20, 4), default=Decimal("0.0000"), nullable=False
    )
    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __mapper_args__ = {"version_id_col": version_id}

    user = relationship("User", back_populates="orders")
    company = relationship("Company", back_populates="orders")
    transactions = relationship("Transaction", back_populates="order")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("idx_transactions_user_simulated", "user_id", "simulated_at"),
        Index("idx_transactions_company_simulated", "company_id", "simulated_at"),
        # Composite index cho poll watermark (leader trade notifier query mỗi 1-3s):
        # ORDER BY created_at ASC, id ASC + WHERE (created_at, id) > watermark.
        # Không có index này Postgres phải Seq Scan + Sort toàn bộ bảng mỗi nhịp.
        Index("idx_transactions_watermark", "created_at", "id"),
        CheckConstraint("quantity > 0", name="chk_transaction_quantity"),
        CheckConstraint("price >= 0", name="chk_transaction_price"),
        CheckConstraint("side IN ('buy', 'sell')", name="chk_transaction_side"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    simulated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order = relationship("Order", back_populates="transactions")
    user = relationship("User", back_populates="transactions")
    company = relationship("Company", back_populates="transactions")
