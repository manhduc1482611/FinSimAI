"""Mentor session DB — bảng mentor_messages — migration 0008.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-22

Lưu hội thoại Socratic Mentor vào DB (improvement_plan A3.2): thay history
client-side 6 tin bằng nguồn chuẩn phía server — reload trang vẫn thấy hội
thoại cũ, LLM lấy 12 tin gần nhất từ DB, và mở đường cho cá nhân hóa + kiểm
toán chất lượng mentor (A4.2, A5.3).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mentor_messages",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("focus", sa.String(length=32), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "idx_mentor_messages_user_time",
        "mentor_messages",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_mentor_messages_session", "mentor_messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("idx_mentor_messages_session", table_name="mentor_messages")
    op.drop_index("idx_mentor_messages_user_time", table_name="mentor_messages")
    op.drop_table("mentor_messages")
