"""Align schema with SQLAlchemy models — fix drift (missing columns).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-02

Các bảng được tạo từ 0001 nhưng model đã tiến hoá thêm cột mà chưa có migration
nào bổ sung — khi backend query/insert theo model sẽ gặp UndefinedColumnError
(VD: ``column news.category does not exist``). Migration này đưa schema khớp model:

- ``users`` / ``portfolios`` / ``orders``: thêm ``version_id`` (SQLAlchemy versioning).
- ``news``: thêm ``category``, ``company_id`` (FK companies), ``is_ai_generated``.
- ``social_posts``: đổi ``persona`` → ``persona_type`` (VARCHAR), thêm
  ``author_avatar``, ``news_id`` (FK news), ``likes_count``, ``shares_count``,
  ``comments_count``.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Optimistic concurrency version columns ─────────────
    op.add_column("users", sa.Column("version_id", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("portfolios", sa.Column("version_id", sa.Integer(), server_default=sa.text("1"), nullable=False))
    op.add_column("orders", sa.Column("version_id", sa.Integer(), server_default=sa.text("1"), nullable=False))

    # ─── News: category / company_id / is_ai_generated ──────
    op.add_column("news", sa.Column("category", sa.String(length=100), server_default=sa.text("'v\u0129 m\u00f4'"), nullable=False))
    op.add_column("news", sa.Column("company_id", postgresql.UUID(), nullable=True))
    op.add_column("news", sa.Column("is_ai_generated", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.create_foreign_key(
        "fk_news_company", "news", "companies",
        ["company_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_news_category", "news", ["category"])
    op.create_index("idx_news_company_simulated", "news", ["company_id", "simulated_at"])
    # model dùng Float (impact_score 5.0 / 2.5) — DB cũ là Integer
    op.alter_column(
        "news", "impact_score",
        type_=sa.Float(),
        existing_type=sa.Integer(),
        existing_server_default=sa.text("1"),
        postgresql_using="impact_score::double precision",
    )

    # ─── Social posts: persona → persona_type + counters ────
    op.alter_column("social_posts", "persona", new_column_name="persona_type")
    op.alter_column(
        "social_posts",
        "persona_type",
        type_=sa.String(length=50),
        postgresql_using="persona_type::text",
        existing_type=postgresql.ENUM(
            "ta_fa_kol", "profit_flex", "loss_flex", "dump_group",
            "pro_trader", "f0_newbie", "macro_guru", "insider", "memes", "scam_alert",
            name="persona_type",
        ),
    )
    op.add_column("social_posts", sa.Column("author_avatar", sa.String(length=500), nullable=True))
    op.add_column("social_posts", sa.Column("news_id", postgresql.UUID(), nullable=True))
    op.add_column("social_posts", sa.Column("likes_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("social_posts", sa.Column("shares_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("social_posts", sa.Column("comments_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.create_foreign_key(
        "fk_social_posts_news", "social_posts", "news",
        ["news_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("idx_social_posts_persona_type", "social_posts", ["persona_type"])
    # model dùng Float (virality_score 1.0) — DB cũ là Integer
    op.alter_column(
        "social_posts", "virality_score",
        type_=sa.Float(),
        existing_type=sa.Integer(),
        existing_server_default=sa.text("0"),
        postgresql_using="virality_score::double precision",
    )


def downgrade() -> None:
    op.drop_index("idx_social_posts_persona_type", table_name="social_posts")
    op.drop_constraint("fk_social_posts_news", "social_posts", type_="foreignkey")
    op.alter_column(
        "social_posts", "virality_score",
        type_=sa.Integer(),
        existing_type=sa.Float(),
        postgresql_using="virality_score::integer",
    )
    op.drop_column("social_posts", "comments_count")
    op.drop_column("social_posts", "shares_count")
    op.drop_column("social_posts", "likes_count")
    op.drop_column("social_posts", "news_id")
    op.drop_column("social_posts", "author_avatar")
    op.alter_column(
        "social_posts",
        "persona_type",
        type_=postgresql.ENUM(
            "ta_fa_kol", "profit_flex", "loss_flex", "dump_group",
            "pro_trader", "f0_newbie", "macro_guru", "insider", "memes", "scam_alert",
            name="persona_type",
        ),
        postgresql_using="persona_type::persona_type",
    )
    op.alter_column("social_posts", "persona_type", new_column_name="persona")

    op.drop_index("idx_news_company_simulated", table_name="news")
    op.drop_index("idx_news_category", table_name="news")
    op.drop_constraint("fk_news_company", "news", type_="foreignkey")
    op.alter_column(
        "news", "impact_score",
        type_=sa.Integer(),
        existing_type=sa.Float(),
        postgresql_using="impact_score::integer",
    )
    op.drop_column("news", "is_ai_generated")
    op.drop_column("news", "company_id")
    op.drop_column("news", "category")

    op.drop_column("orders", "version_id")
    op.drop_column("portfolios", "version_id")
    op.drop_column("users", "version_id")
