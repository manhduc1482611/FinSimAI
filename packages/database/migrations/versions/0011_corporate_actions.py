"""Sự kiện doanh nghiệp (Corporate Actions) — migration 0011.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-01

Bảng ``corporate_actions`` mô phỏng các sự kiện doanh nghiệp theo lịch ảo:
cổ tức tiền mặt (cash_dividend), chia tách cổ phiếu (stock_split), phát hành
quyền (rights), hủy niêm yết (delisting) và sốc tin tức (news_shock).

Nguyên tắc chống look-ahead: event chỉ được hiện thực hoá khi ``simulated_at``
của đồng hồ mô phỏng đã đạt ``ex_date`` (+ ``look_ahead_guard``). Generator
trong ``MarketSim.tick`` duyệt các sự kiện đủ hạn và áp dụng idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "corporate_actions",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "action_type", sa.String(length=24), nullable=False,
        ),  # cash_dividend | stock_split | rights | delisting | news_shock
        sa.Column("ex_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False,
        ),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "idx_corporate_actions_company",
        "corporate_actions",
        ["company_id", sa.text("ex_date DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_corporate_actions_company", table_name="corporate_actions")
    op.drop_table("corporate_actions")
