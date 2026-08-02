"""Initial schema v3 — FinSimAI Production-Ready Data Model

Revision ID: 0001
Revises:
Create Date: 2026-07-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgcrypto không có sẵn trên Windows native build — tạo hàm thay thế
    op.execute("""
        CREATE OR REPLACE FUNCTION gen_random_uuid() RETURNS UUID AS $$
        DECLARE hex TEXT;
        BEGIN
            hex := md5(random()::text || clock_timestamp()::text);
            RETURN (
                substr(hex, 1, 8) || '-' ||
                substr(hex, 9, 4) || '-' ||
                substr(hex, 13, 4) || '-' ||
                substr(hex, 17, 4) || '-' ||
                substr(hex, 21, 12)
            )::uuid;
        END;
        $$ LANGUAGE plpgsql;
    """)
    # pg_trgm: bật nếu server hỗ trợ. Build không có extension (VD Windows native)
    # sẽ bỏ qua các index trigram thay vì fail — giữ migration chạy được mọi nơi.
    pg_trgm_available = op.get_bind().execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'")
    ).first() is not None
    if pg_trgm_available:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


    # ─── Enums ──────────────────────────────────────────────
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin', 'bot')")
    op.execute("CREATE TYPE order_side AS ENUM ('buy', 'sell')")
    op.execute("CREATE TYPE order_type AS ENUM ('market', 'limit')")
    op.execute("CREATE TYPE order_status AS ENUM ('pending', 'filled', 'partially_filled', 'cancelled', 'rejected')")
    op.execute("CREATE TYPE sentiment AS ENUM ('positive', 'negative', 'neutral')")
    op.execute("CREATE TYPE trap_type AS ENUM ('fomo', 'panic', 'pump_dump', 'fake_news', 'whale_trap')")
    op.execute("""CREATE TYPE persona_type AS ENUM (
        'ta_fa_kol', 'profit_flex', 'loss_flex', 'dump_group',
        'pro_trader', 'f0_newbie', 'macro_guru', 'insider', 'memes', 'scam_alert'
    )""")
    op.execute("CREATE TYPE scenario_status AS ENUM ('pending', 'active', 'completed', 'failed')")

    # ─── Users ──────────────────────────────────────────────
    op.create_table("users",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("role", postgresql.ENUM("user", "admin", "bot", name="user_role", create_type=False), server_default=sa.text("'user'"), nullable=False),
        sa.Column("cash_balance", sa.Numeric(20, 2), server_default=sa.text("100000000.00"), nullable=False),
        sa.Column("frozen_cash", sa.Numeric(20, 2), server_default=sa.text("0.00"), nullable=False),
        sa.Column("risk_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_username", "users", ["username"])

    # ─── Companies ──────────────────────────────────────────
    op.create_table("companies",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("current_price", sa.Numeric(20, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("volatility", sa.Numeric(5, 4), server_default=sa.text("0.0100"), nullable=False),
        sa.Column("shares_outstanding", sa.Numeric(20, 0), server_default=sa.text("10000000"), nullable=False),
        sa.Column("market_cap", sa.Numeric(20, 2), sa.Computed("current_price * shares_outstanding", persisted=True), nullable=False),
        sa.Column("health_score", sa.Integer(), server_default=sa.text("70"), nullable=False),
        sa.Column("pe_ratio", sa.Numeric(10, 2), nullable=True),
        sa.Column("roe", sa.Numeric(5, 2), nullable=True),
        sa.Column("net_margin", sa.Numeric(5, 2), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("idx_companies_symbol", "companies", ["symbol"])
    op.create_index("idx_companies_sector", "companies", ["sector"])

    # ─── Price History ──────────────────────────────────────
    op.create_table("price_history",
        sa.Column("id", sa.BigInteger(), sa.Sequence("price_history_id_seq"), autoincrement=True, nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.Column("time_frame", sa.String(10), server_default=sa.text("'1m'"), nullable=False),
        sa.Column("open_price", sa.Numeric(20, 2), nullable=False),
        sa.Column("high_price", sa.Numeric(20, 2), nullable=False),
        sa.Column("low_price", sa.Numeric(20, 2), nullable=False),
        sa.Column("close_price", sa.Numeric(20, 2), nullable=False),
        sa.Column("volume", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "time_frame", "simulated_at", name="uk_price_history_candle"),
    )
    op.create_index("idx_price_history_lookup", "price_history", ["company_id", "time_frame", sa.text("simulated_at DESC")])

    # ─── Portfolios ─────────────────────────────────────────
    op.create_table("portfolios",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("frozen_quantity", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("average_buy_price", sa.Numeric(20, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(20, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_portfolios_user_id", "portfolios", ["user_id"])

    # ─── Orders ─────────────────────────────────────────────
    op.create_table("orders",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.Column("side", postgresql.ENUM("buy", "sell", name="order_side", create_type=False), nullable=False),
        sa.Column("type", postgresql.ENUM("market", "limit", name="order_type", create_type=False), server_default=sa.text("'limit'"), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "filled", "partially_filled", "cancelled", "rejected", name="order_status", create_type=False), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("price", sa.Numeric(20, 2), nullable=True),  # NULL cho Market Order
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("frozen_cash", sa.Numeric(20, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("frozen_quantity", sa.Numeric(20, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("type = 'market' OR price IS NOT NULL", name="chk_orders_limit_price"),
    )
    op.create_index("idx_orders_user", "orders", ["user_id", "status"])
    op.create_index("idx_orders_matching", "orders", ["company_id", "side", "status", sa.text("price DESC"), sa.text("simulated_at ASC")])

    # ─── Transactions ───────────────────────────────────────
    op.create_table("transactions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", postgresql.UUID(), nullable=True),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.Column("side", postgresql.ENUM("buy", "sell", name="order_side", create_type=False), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 4), nullable=False),
        sa.Column("price", sa.Numeric(20, 2), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 2), sa.Computed("quantity * price", persisted=True), nullable=False),
        sa.Column("fee", sa.Numeric(20, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_transactions_user", "transactions", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_transactions_company", "transactions", ["company_id"])

    # ─── News ───────────────────────────────────────────────
    op.create_table("news",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sentiment", postgresql.ENUM("positive", "negative", "neutral", name="sentiment", create_type=False), server_default=sa.text("'neutral'"), nullable=False),
        sa.Column("impact_score", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_news_simulated_at", "news", ["simulated_at"], postgresql_using="btree")
    if pg_trgm_available:
        op.execute("CREATE INDEX idx_news_title_trgm ON news USING gin (title gin_trgm_ops)")
        op.execute("CREATE INDEX idx_news_content_trgm ON news USING gin (content gin_trgm_ops)")

    op.create_table("news_companies",
        sa.Column("news_id", postgresql.UUID(), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["news_id"], ["news.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("news_id", "company_id"),
    )
    op.create_index("idx_news_companies_company", "news_companies", ["company_id"])

    # ─── Social Posts ───────────────────────────────────────
    op.create_table("social_posts",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=True),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("persona", postgresql.ENUM("ta_fa_kol", "profit_flex", "loss_flex", "dump_group", "pro_trader", "f0_newbie", "macro_guru", "insider", "memes", "scam_alert", name="persona_type", create_type=False), server_default=sa.text("'f0_newbie'"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("virality_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("sentiment", postgresql.ENUM("positive", "negative", "neutral", name="sentiment", create_type=False), server_default=sa.text("'neutral'"), nullable=False),
        sa.Column("is_trap", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("trap_type", postgresql.ENUM("fomo", "panic", "pump_dump", "fake_news", "whale_trap", name="trap_type", create_type=False), nullable=True),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_social_posts_company", "social_posts", ["company_id", sa.text("simulated_at DESC")])
    op.create_index("idx_social_posts_virality", "social_posts", ["virality_score"], postgresql_using="btree")

    # ─── Trap Events ────────────────────────────────────────
    op.create_table("trap_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("company_id", postgresql.UUID(), nullable=True),
        sa.Column("social_post_id", postgresql.UUID(), nullable=True),
        sa.Column("type", postgresql.ENUM("fomo", "panic", "pump_dump", "fake_news", "whale_trap", name="trap_type", create_type=False), nullable=False),
        sa.Column("severity", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("points_deducted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("simulated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["social_post_id"], ["social_posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trap_events_user", "trap_events", ["user_id", sa.text("detected_at DESC")])

    # ─── Knowledge Base ─────────────────────────────────────
    op.create_table("knowledge_base",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("concept", sa.String(500), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100), server_default=sa.text("'general'"), nullable=False),
        sa.Column("difficulty", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("related_keywords", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("keyword"),
    )
    if pg_trgm_available:
        op.execute("CREATE INDEX idx_kb_keyword_trgm ON knowledge_base USING gin (keyword gin_trgm_ops)")
    op.execute("CREATE INDEX idx_kb_related_keywords ON knowledge_base USING gin (related_keywords)")

    # ─── Scenarios ──────────────────────────────────────────
    op.create_table("scenarios",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("difficulty", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("CREATE INDEX idx_scenarios_config ON scenarios USING gin (config)")
    op.create_index("idx_scenarios_type", "scenarios", ["scenario_type"])

    # ─── User Scenarios ─────────────────────────────────────
    op.create_table("user_scenarios",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(), nullable=False),
        sa.Column("scenario_id", postgresql.UUID(), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "active", "completed", "failed", name="scenario_status", create_type=False), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("config_override", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "scenario_id"),
    )
    op.create_index("idx_user_scenarios_user", "user_scenarios", ["user_id"])
    op.create_index("idx_user_scenarios_status", "user_scenarios", ["status"])

    # ─── Triggers ───────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("users", "companies", "portfolios", "orders"):
        op.execute(f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")


def downgrade() -> None:
    for table in ("orders", "portfolios", "companies", "users"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    op.drop_table("user_scenarios")
    op.drop_table("scenarios")
    op.drop_table("knowledge_base")
    op.drop_table("trap_events")
    op.drop_table("social_posts")
    op.drop_table("news_companies")
    op.drop_table("news")
    op.drop_table("transactions")
    op.drop_table("orders")
    op.drop_table("portfolios")
    op.drop_table("price_history")
    op.drop_table("companies")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS scenario_status")
    op.execute("DROP TYPE IF EXISTS persona_type")
    op.execute("DROP TYPE IF EXISTS trap_type")
    op.execute("DROP TYPE IF EXISTS sentiment")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS order_type")
    op.execute("DROP TYPE IF EXISTS order_side")
    op.execute("DROP TYPE IF EXISTS user_role")
