"""Contests & roles — nền tảng đa cuộc thi.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-03

Thêm role ``host`` vào enum ``user_role``, tạo bảng ``contests`` /
``contest_members``, và gắn scope contest vào nội dung
(``companies`` / ``news`` / ``social_posts`` / ``portfolios``).

Nguyên tắc: ``contest_id`` NULL = "thị trường chính" (dữ liệu hiện có),
không cần backfill. Symbol của company: bỏ unique toàn cục → partial unique
index ``(contest_id, symbol) WHERE contest_id IS NOT NULL`` + ``(symbol)
WHERE contest_id IS NULL`` để 2 contest dùng chung symbol được nhưng dữ liệu
thị trường chính vẫn bảo toàn ràng buộc cũ.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Role 'host' ────────────────────────────────────────────
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'host'")

    # ─── contests ───────────────────────────────────────────────
    op.create_table(
        "contests",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20),
            server_default=sa.text("'draft'"), nullable=False,
        ),
        sa.Column(
            "config", postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(),
            server_default=sa.text("true"), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index("idx_contests_slug", "contests", ["slug"], unique=True)
    op.create_index("idx_contests_owner_status", "contests", ["owner_id", "status"])

    # ─── contest_members ────────────────────────────────────────
    op.create_table(
        "contest_members",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "contest_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contests.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_contest_members_contest_user"),
    )
    op.create_index("idx_contest_members_user", "contest_members", ["user_id"])

    # ─── contest_id trên nội dung ───────────────────────────────
    for table in ("companies", "news", "social_posts", "portfolios"):
        op.add_column(
            table, sa.Column("contest_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            f"fk_{table}_contest", table, "contests",
            ["contest_id"], ["id"], ondelete="CASCADE",
        )

    op.create_index(
        "idx_news_contest_company_simulated",
        "news", ["contest_id", "company_id", "simulated_at"],
    )
    op.create_index("idx_social_posts_contest", "social_posts", ["contest_id"])
    op.create_index("idx_portfolios_user_contest", "portfolios", ["user_id", "contest_id"])

    # ─── Symbol: unique toàn cục → partial theo contest ─────────
    # An toàn: kiểm tra không có symbol trùng trước khi bỏ ràng buộc cũ.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM companies GROUP BY symbol HAVING count(*) > 1) THEN
                RAISE EXCEPTION 'Duplicate symbols in companies — cannot drop global unique';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint("companies_symbol_key", "companies", type_="unique")
    op.create_index(
        "uq_companies_contest_symbol", "companies", ["contest_id", "symbol"],
        unique=True, postgresql_where=sa.text("contest_id IS NOT NULL"),
    )
    op.create_index(
        "uq_companies_symbol_main", "companies", ["symbol"],
        unique=True, postgresql_where=sa.text("contest_id IS NULL"),
    )


def downgrade() -> None:
    # ─── Hoàn tác symbol ────────────────────────────────────────
    op.drop_index("uq_companies_symbol_main", table_name="companies")
    op.drop_index("uq_companies_contest_symbol", table_name="companies")
    op.create_unique_constraint("companies_symbol_key", "companies", ["symbol"])

    op.drop_index("idx_portfolios_user_contest", table_name="portfolios")
    op.drop_index("idx_social_posts_contest", table_name="social_posts")
    op.drop_index("idx_news_contest_company_simulated", table_name="news")
    for table in ("portfolios", "social_posts", "news", "companies"):
        op.drop_constraint(f"fk_{table}_contest", table, type_="foreignkey")
        op.drop_column(table, "contest_id")

    op.drop_index("idx_contest_members_user", table_name="contest_members")
    op.drop_table("contest_members")
    op.drop_index("idx_contests_owner_status", table_name="contests")
    op.drop_index("idx_contests_slug", table_name="contests")
    op.drop_table("contests")

    # PG13+ mới có ALTER TYPE ... DROP VALUE; một số build (vd MinGW-w64) không
    # hỗ trợ ở mức parser. Bọc SAVEPOINT để lỗi không làm hỏng transaction —
    # giá trị 'host' còn lại trong enum là vô hại (downgrade vẫn hoàn tất).
    op.execute("SAVEPOINT enum_drop")
    try:
        op.execute("ALTER TYPE user_role DROP VALUE IF EXISTS 'host'")
        op.execute("RELEASE SAVEPOINT enum_drop")
    except Exception:
        op.execute("ROLLBACK TO SAVEPOINT enum_drop")
