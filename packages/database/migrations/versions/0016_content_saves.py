"""Lưu/Xem sau — bảng content_saves lưu bookmark tin tức + bài xã hội.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-11

Cho phép người dùng lưu bài tin hoặc bài xã hội vào danh sách "Đã lưu" (xem sau).
Schema content_saves chứa content_type ('news' | 'social') + content_id, unique
per user, mở rộng được cho các loại nội dung khác trong tương lai.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_saves",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content_type", sa.String(length=20), nullable=False),
        sa.Column("content_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_type", "content_id", name="uq_content_saves_user_type_id"),
    )
    op.create_index("idx_content_saves_user", "content_saves", ["user_id", "content_type"])


def downgrade() -> None:
    op.drop_index("idx_content_saves_user", table_name="content_saves")
    op.drop_table("content_saves")
