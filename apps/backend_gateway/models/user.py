import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("cash_balance >= 0", name="chk_user_cash_balance"),
        CheckConstraint("frozen_cash >= 0", name="chk_user_frozen_cash"),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100", name="chk_user_risk_score"
        ),
        CheckConstraint(
            "cash_balance >= frozen_cash", name="chk_user_cash_solvency",
        ),
        Index(
            "uq_user_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_user_username_active",
            "username",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(
        ENUM("user", "admin", "bot", "host", name="user_role", create_type=False),
        default="user",
        nullable=False,
    )

    cash_balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("100000000.00"), nullable=False
    )
    frozen_cash: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    version_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    __mapper_args__ = {"version_id_col": version_id}

    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    hosted_contests = relationship(
        "Contest", back_populates="owner", foreign_keys="Contest.owner_id"
    )
    contest_memberships = relationship(
        "ContestMember", back_populates="member"
    )
    task_progress = relationship(
        "UserTaskProgress", back_populates="user", cascade="all, delete-orphan"
    )
    streak = relationship(
        "UserStreak", back_populates="user", cascade="all, delete-orphan", uselist=False
    )
