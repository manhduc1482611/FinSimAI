-- FinSimAI Database Schema (Production Ready v3)
-- Target: PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─── ENUMs ────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM ('user', 'admin', 'bot');
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('market', 'limit');
CREATE TYPE order_status AS ENUM ('pending', 'filled', 'partially_filled', 'cancelled', 'rejected');
CREATE TYPE sentiment AS ENUM ('positive', 'negative', 'neutral');
CREATE TYPE trap_type AS ENUM ('fomo', 'panic', 'pump_dump', 'fake_news', 'whale_trap');
CREATE TYPE persona_type AS ENUM ('ta_fa_kol', 'profit_flex', 'loss_flex', 'dump_group', 'pro_trader', 'f0_newbie', 'macro_guru', 'insider', 'memes', 'scam_alert');
CREATE TYPE scenario_status AS ENUM ('pending', 'active', 'completed', 'failed');

-- ─── Users ────────────────────────────────────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    username        VARCHAR(100) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(200),
    avatar_url      VARCHAR(500),
    role            user_role NOT NULL DEFAULT 'user',

    -- Tài chính & Kỷ luật
    cash_balance    NUMERIC(20, 2) NOT NULL DEFAULT 100000000.00 CHECK (cash_balance >= 0),
    frozen_cash     NUMERIC(20, 2) NOT NULL DEFAULT 0.00 CHECK (frozen_cash >= 0),
    risk_score      INTEGER NOT NULL DEFAULT 0 CHECK (risk_score >= 0 AND risk_score <= 100),
    cooldown_until  TIMESTAMPTZ,

    is_active       BOOLEAN NOT NULL DEFAULT true,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_username ON users (username);

-- ─── Companies ────────────────────────────────────────────
CREATE TABLE companies (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol             VARCHAR(20) NOT NULL UNIQUE,
    name               VARCHAR(255) NOT NULL,
    description        TEXT,
    sector             VARCHAR(100) NOT NULL,

    -- Chỉ số thị trường real-time
    current_price      NUMERIC(20, 2) NOT NULL DEFAULT 0 CHECK (current_price >= 0),
    volatility         NUMERIC(5, 4) NOT NULL DEFAULT 0.0100,
    shares_outstanding NUMERIC(20, 0) NOT NULL DEFAULT 10000000,
    market_cap         NUMERIC(20, 2) GENERATED ALWAYS AS (current_price * shares_outstanding) STORED,

    -- Báo cáo tài chính & Health Score
    health_score       INTEGER NOT NULL DEFAULT 70 CHECK (health_score >= 0 AND health_score <= 100),
    pe_ratio           NUMERIC(10, 2),
    roe                NUMERIC(5, 2),
    net_margin         NUMERIC(5, 2),
    max_drawdown       NUMERIC(5, 2),

    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_companies_symbol ON companies (symbol);
CREATE INDEX idx_companies_sector ON companies (sector);

-- ─── Price History (OHLCV / Biểu đồ nến) ──────────────────
CREATE TABLE price_history (
    id            BIGSERIAL PRIMARY KEY,
    company_id    UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    time_frame    VARCHAR(10) NOT NULL DEFAULT '1m',
    open_price    NUMERIC(20, 2) NOT NULL,
    high_price    NUMERIC(20, 2) NOT NULL,
    low_price     NUMERIC(20, 2) NOT NULL,
    close_price   NUMERIC(20, 2) NOT NULL,
    volume        NUMERIC(20, 4) NOT NULL DEFAULT 0,
    simulated_at  TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uk_price_history_candle UNIQUE (company_id, time_frame, simulated_at)
);

CREATE INDEX idx_price_history_lookup ON price_history (company_id, time_frame, simulated_at DESC);

-- ─── Portfolios ───────────────────────────────────────────
CREATE TABLE portfolios (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    company_id        UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    quantity          NUMERIC(20, 4) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    frozen_quantity   NUMERIC(20, 4) NOT NULL DEFAULT 0 CHECK (frozen_quantity >= 0),
    average_buy_price NUMERIC(20, 2) NOT NULL DEFAULT 0,
    realized_pnl      NUMERIC(20, 2) NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, company_id)
);

CREATE INDEX idx_portfolios_user_id ON portfolios (user_id);

-- ─── Orders ───────────────────────────────────────────────
CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    side            order_side NOT NULL,
    type            order_type NOT NULL DEFAULT 'limit',
    status          order_status NOT NULL DEFAULT 'pending',
    price           NUMERIC(20, 2) CHECK (price > 0),            -- NULL cho Market Order
    quantity        NUMERIC(20, 4) NOT NULL CHECK (quantity > 0),
    filled_quantity NUMERIC(20, 4) NOT NULL DEFAULT 0 CHECK (filled_quantity >= 0),
    frozen_cash     NUMERIC(20, 2) NOT NULL DEFAULT 0 CHECK (frozen_cash >= 0),
    frozen_quantity NUMERIC(20, 4) NOT NULL DEFAULT 0 CHECK (frozen_quantity >= 0),
    simulated_at    TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_orders_limit_price CHECK (type = 'market' OR price IS NOT NULL)
);

CREATE INDEX idx_orders_user ON orders (user_id, status);
CREATE INDEX idx_orders_matching ON orders (company_id, side, status, price DESC, simulated_at ASC);

-- ─── Transactions ─────────────────────────────────────────
CREATE TABLE transactions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id      UUID REFERENCES orders(id) ON DELETE SET NULL,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    company_id    UUID NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    side          order_side NOT NULL,
    quantity      NUMERIC(20, 4) NOT NULL CHECK (quantity > 0),
    price         NUMERIC(20, 2) NOT NULL CHECK (price >= 0),
    total_value   NUMERIC(20, 2) GENERATED ALWAYS AS (quantity * price) STORED,
    fee           NUMERIC(20, 2) NOT NULL DEFAULT 0 CHECK (fee >= 0),
    simulated_at  TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_user ON transactions (user_id, created_at DESC);
CREATE INDEX idx_transactions_company ON transactions (company_id);

-- ─── News ─────────────────────────────────────────────────
CREATE TABLE news (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title         VARCHAR(500) NOT NULL,
    summary       TEXT,
    content       TEXT NOT NULL,
    sentiment     sentiment NOT NULL DEFAULT 'neutral',
    impact_score  INTEGER NOT NULL DEFAULT 1 CHECK (impact_score BETWEEN 1 AND 10),
    source        VARCHAR(200),
    simulated_at  TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE news_companies (
    news_id     UUID NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    company_id  UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    PRIMARY KEY (news_id, company_id)
);

CREATE INDEX idx_news_simulated_at ON news (simulated_at DESC);
CREATE INDEX idx_news_title_trgm ON news USING gin (title gin_trgm_ops);
CREATE INDEX idx_news_content_trgm ON news USING gin (content gin_trgm_ops);
CREATE INDEX idx_news_companies_company ON news_companies (company_id);

-- ─── Social Posts ─────────────────────────────────────────
CREATE TABLE social_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id      UUID REFERENCES companies(id) ON DELETE SET NULL,
    author_name     VARCHAR(200) NOT NULL,
    persona         persona_type NOT NULL DEFAULT 'f0_newbie',
    content         TEXT NOT NULL,
    virality_score  INTEGER NOT NULL DEFAULT 0 CHECK (virality_score BETWEEN 0 AND 100),
    sentiment       sentiment NOT NULL DEFAULT 'neutral',
    is_trap         BOOLEAN NOT NULL DEFAULT false,
    trap_type       trap_type,
    simulated_at    TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_social_posts_company ON social_posts (company_id, simulated_at DESC);
CREATE INDEX idx_social_posts_virality ON social_posts (virality_score DESC);

-- ─── Trap Events ──────────────────────────────────────────
CREATE TABLE trap_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_id      UUID REFERENCES companies(id) ON DELETE SET NULL,
    social_post_id  UUID REFERENCES social_posts(id) ON DELETE SET NULL,
    type            trap_type NOT NULL,
    severity        INTEGER NOT NULL DEFAULT 1 CHECK (severity BETWEEN 1 AND 5),
    description     TEXT,
    points_deducted INTEGER NOT NULL DEFAULT 0 CHECK (points_deducted >= 0),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    simulated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_trap_events_user ON trap_events (user_id, detected_at DESC);

-- ─── Knowledge Base ───────────────────────────────────────
CREATE TABLE knowledge_base (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword          VARCHAR(200) NOT NULL UNIQUE,
    concept          VARCHAR(500) NOT NULL,
    definition       TEXT NOT NULL,
    category         VARCHAR(100) NOT NULL DEFAULT 'general',
    difficulty       INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    related_keywords TEXT[],
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kb_keyword_trgm ON knowledge_base USING gin (keyword gin_trgm_ops);
CREATE INDEX idx_kb_related_keywords ON knowledge_base USING gin (related_keywords);

-- ─── Scenarios ────────────────────────────────────────────
CREATE TABLE scenarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(300) NOT NULL,
    description     TEXT NOT NULL,
    scenario_type   VARCHAR(50) NOT NULL,
    difficulty      INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    config          JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_scenarios_config ON scenarios USING gin (config);
CREATE INDEX idx_scenarios_type ON scenarios (scenario_type);

-- ─── User Scenarios ───────────────────────────────────────
CREATE TABLE user_scenarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id     UUID NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    status          scenario_status NOT NULL DEFAULT 'pending',
    progress        INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    score           INTEGER DEFAULT 0,
    config_override JSONB,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, scenario_id)
);

CREATE INDEX idx_user_scenarios_user ON user_scenarios (user_id);
CREATE INDEX idx_user_scenarios_status ON user_scenarios (status);

-- ─── Triggers ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at     BEFORE UPDATE ON users     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_companies_updated_at BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_portfolios_updated_at BEFORE UPDATE ON portfolios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_orders_updated_at    BEFORE UPDATE ON orders    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
