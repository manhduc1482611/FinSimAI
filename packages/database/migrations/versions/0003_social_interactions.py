"""Mạng xã hội tương tác — bảng like & bình luận cho bài đăng.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01

Lý do: trang Xã hội nâng cấp theo kiểu Facebook — cần lưu like theo người dùng
(social_likes, unique per user+post) và bình luận (social_comments). Số lượng
like/comment vẫn duy trì dạng counter trên social_posts để giữ hợp đồng cũ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_likes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["social_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_social_likes_post_user"),
    )
    op.create_table(
        "social_comments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("author_name", sa.String(length=100), nullable=False),
        sa.Column("author_avatar", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["social_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_social_comments_post_created",
        "social_comments",
        ["post_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_social_comments_post_created", table_name="social_comments")
    op.drop_table("social_comments")
    op.drop_table("social_likes")
