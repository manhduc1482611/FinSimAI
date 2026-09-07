"""Daily Challenge & periodic mentor questions — migration 0013.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-01

- ``daily_challenges``: thử thách hằng ngày (kỹ năng / kỷ luật) kèm thưởng.
- ``user_daily_challenges``: trạng thái hoàn thành của mỗi user (unique
  user+challenge để thưởng đúng 1 lần).
Mentor periodic question tận dụng luồng mentor_messages hiện có (không thêm
bảng riêng); endpoint trả câu hỏi khi đến hạn dựa trên lịch ảo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_challenges",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("challenge_date", sa.Date(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "target", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "reward_amount", sa.Numeric(precision=20, scale=2),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("challenge_date", "code", name="uq_daily_challenges_date_code"),
    )
    op.create_table(
        "user_daily_challenges",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "challenge_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("daily_challenges.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "reward_earned", sa.Numeric(precision=20, scale=2),
            server_default=sa.text("0"), nullable=False,
        ),
        sa.UniqueConstraint("user_id", "challenge_id", name="uq_user_daily_challenges"),
    )


def downgrade() -> None:
    op.drop_table("user_daily_challenges")
    op.drop_table("daily_challenges")
