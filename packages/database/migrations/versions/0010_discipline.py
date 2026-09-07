"""Điểm kỷ luật (Discipline Score) — migration 0010.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-01

Thêm hệ thống điểm kỷ luật tách biệt khỏi ``risk_score`` (điểm quản trị rủi ro
dùng cho mentor):
- ``users.discipline_score``: điểm hiện tại, clamp 0–100, khởi điểm 90.
- ``discipline_score_history``: log mọi thay đổi (delta + lý do) để audit.

Triết lý: thưởng KỶ LUẬT / quản trị rủi ro, KHÔNG thưởng lợi nhuận ảo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "discipline_score",
            sa.Integer(),
            server_default="90",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "chk_user_discipline_score",
        "users",
        "discipline_score >= 0 AND discipline_score <= 100",
    )
    op.create_table(
        "discipline_score_history",
        sa.Column(
            "id", sa.Integer(), sa.Identity(), primary_key=True,
        ),
        sa.Column(
            "user_id", sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("score_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("context", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "idx_discipline_history_user",
        "discipline_score_history",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_discipline_history_user", table_name="discipline_score_history")
    op.drop_table("discipline_score_history")
    op.drop_constraint("chk_user_discipline_score", "users", type_="check")
    op.drop_column("users", "discipline_score")
