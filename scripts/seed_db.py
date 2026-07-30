import asyncio
import os
from pathlib import Path

import asyncpg
import yaml

SEEDS_DIR = Path(__file__).resolve().parent.parent / "packages" / "database" / "seeds"


def load_yaml(filename: str) -> dict:
    path = SEEDS_DIR / filename
    if not path.exists():
        print(f"[WARN] Seed file not found: {path}")
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


async def truncate_tables(conn: asyncpg.Connection) -> None:
    tables = [
        "user_scenarios",
        "trap_events",
        "social_posts",
        "news_companies",
        "news",
        "price_history",
        "transactions",
        "orders",
        "portfolios",
        "companies",
        "scenarios",
        "knowledge_base",
        "users",
    ]
    for table in tables:
        await conn.execute(f"TRUNCATE TABLE {table} CASCADE")
    print("[OK] Truncated all tables.")


async def seed_companies(conn: asyncpg.Connection, data: dict) -> None:
    rows = data.get("companies", [])
    if not rows:
        print("[SKIP] No companies to seed.")
        return
    for row in rows:
        await conn.execute(
            """
            INSERT INTO companies
                (symbol, name, description, sector, current_price, volatility,
                 shares_outstanding, health_score, pe_ratio, roe, net_margin, max_drawdown)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (symbol) DO UPDATE SET
                name              = EXCLUDED.name,
                description       = EXCLUDED.description,
                sector            = EXCLUDED.sector,
                current_price     = EXCLUDED.current_price,
                volatility        = EXCLUDED.volatility,
                shares_outstanding = EXCLUDED.shares_outstanding,
                health_score      = EXCLUDED.health_score,
                pe_ratio          = EXCLUDED.pe_ratio,
                roe               = EXCLUDED.roe,
                net_margin        = EXCLUDED.net_margin,
                max_drawdown      = EXCLUDED.max_drawdown
            """,
            row["symbol"],
            row["name"],
            row.get("description", ""),
            row["sector"],
            str(row["current_price"]),
            str(row.get("volatility", 0.01)),
            str(row.get("shares_outstanding", 10000000)),
            row.get("health_score", 70),
            row.get("pe_ratio"),
            row.get("roe"),
            row.get("net_margin"),
            row.get("max_drawdown"),
        )
    print(f"[OK] Seeded {len(rows)} companies.")


async def seed_knowledge_base(conn: asyncpg.Connection, data: dict) -> None:
    rows = data.get("knowledge_base", [])
    if not rows:
        print("[SKIP] No knowledge base entries to seed.")
        return
    for row in rows:
        await conn.execute(
            """
            INSERT INTO knowledge_base (keyword, concept, definition, category, difficulty, related_keywords)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (keyword) DO UPDATE SET
                concept          = EXCLUDED.concept,
                definition       = EXCLUDED.definition,
                category         = EXCLUDED.category,
                difficulty       = EXCLUDED.difficulty,
                related_keywords = EXCLUDED.related_keywords
            """,
            row["keyword"],
            row["concept"],
            row["definition"],
            row.get("category", "general"),
            row.get("difficulty", 1),
            row.get("related_keywords", []),
        )
    print(f"[OK] Seeded {len(rows)} knowledge base entries.")


async def seed_scenarios(conn: asyncpg.Connection, data: dict) -> None:
    rows = data.get("scenarios", [])
    if not rows:
        print("[SKIP] No scenarios to seed.")
        return
    for row in rows:
        await conn.execute(
            """
            INSERT INTO scenarios (name, description, scenario_type, difficulty, config)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT DO NOTHING
            """,
            row["name"],
            row["description"],
            row["scenario_type"],
            row.get("difficulty", 1),
            row.get("config", {}),
        )
    print(f"[OK] Seeded {len(rows)} scenarios.")


async def main() -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://finsim:finsim_secret@localhost:5432/finsimai",
    )

    print(f"[INFO] Connecting to: {database_url}")
    conn = await asyncpg.connect(database_url)

    try:
        companies_data = load_yaml("companies.yaml")
        knowledge_data = load_yaml("knowledge_base.yaml")
        scenarios_data = load_yaml("scenarios.yaml")

        await truncate_tables(conn)
        await seed_companies(conn, companies_data)
        await seed_knowledge_base(conn, knowledge_data)
        await seed_scenarios(conn, scenarios_data)

        print("\n[DONE] Database seeding completed successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
