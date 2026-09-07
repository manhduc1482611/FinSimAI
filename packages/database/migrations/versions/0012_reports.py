"""Báo cáo hằng ngày & hằng tuần — migration 0012.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-01

Bảng ``reports`` lưu digest hằng ngày (NAV đầu/cuối, P/L, phí thuế, sự kiện,
điểm kỷ luật) và báo cáo hằng tuần. Unique (user_id, kind, period) để không
tạo trùng báo cáo khi re-run.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.String(length=10), nullable=False),  # daily | weekly
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("user_id", "kind", "period", name="uq_reports_user_kind_period"),
    )
    op.create_index("idx_reports_user_period", "reports", ["user_id", sa.text("period DESC")])


def downgrade() -> None:
    op.drop_index("idx_reports_user_period", table_name="reports")
    op.drop_table("reports")
