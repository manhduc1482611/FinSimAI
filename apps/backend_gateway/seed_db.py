"""Boot-time idempotent seeding cho FinSimAI database.

Chạy trong lifespan của backend (bên trong mạng Render, cùng network với
Postgres) sau khi ``alembic upgrade head`` hoàn tất. Vì Render free-tier
chặn kết nối Postgres từ ngoài, đây là cách duy nhất nạp dữ liệu vào DB
production mà không cần shell.

Nguyên tắc an toàn:
- KHÔNG bao giờ TRUNCATE / xoá dữ liệu.
- Bảng tham chiếu (companies, knowledge_base, scenarios): upsert
  ``ON CONFLICT ... DO UPDATE/NOTHING`` → chạy lại bao nhiêu lần cũng được.
- Bảng nội dung (news, social_posts): chỉ ghi khi bảng ĐANG RỖNG.
- Lỗi seed chỉ ghi log, không làm crash quá trình khởi động.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from core.database import engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = REPO_ROOT / "packages" / "database" / "seeds"

_MACRO_CATEGORIES = ("thị trường", "vĩ mô")
_CATEGORIES = ("doanh nghiệp", "thị trường", "phân tích", "nhận định")


def _load_yaml(filename: str) -> dict:
    path = SEEDS_DIR / filename
    if not path.exists():
        logger.warning("Seed file not found: %s", path)
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


async def _table_count(table: str) -> int:
    async with engine.connect() as conn:
        row = await conn.execute(text(f"SELECT count(*) FROM {table}"))
        return int(row.scalar_one())


async def _seed_reference_rows() -> None:
    """Upsert companies, knowledge_base, scenarios từ YAML."""
    companies = _load_yaml("companies.yaml").get("companies", [])
    knowledge = _load_yaml("knowledge_base.yaml").get("knowledge_base", [])
    scenarios = _load_yaml("scenarios.yaml").get("scenarios", [])

    async with engine.begin() as conn:
        for row in companies:
            await conn.execute(
                text(
                    """
                    INSERT INTO companies
                        (symbol, name, description, sector, current_price, volatility,
                         shares_outstanding, health_score, pe_ratio, roe, net_margin, max_drawdown)
                    VALUES (:symbol, :name, :description, :sector, :current_price, :volatility,
                            :shares_outstanding, :health_score, :pe_ratio, :roe,
                            :net_margin, :max_drawdown)
                    ON CONFLICT (symbol) DO NOTHING
                    """
                ),
                {
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "sector": row["sector"],
                    "current_price": str(row["current_price"]),
                    "volatility": str(row.get("volatility", 0.01)),
                    "shares_outstanding": str(row.get("shares_outstanding", 10000000)),
                    "health_score": row.get("health_score", 70),
                    "pe_ratio": row.get("pe_ratio"),
                    "roe": row.get("roe"),
                    "net_margin": row.get("net_margin"),
                    "max_drawdown": row.get("max_drawdown"),
                },
            )
        for row in knowledge:
            await conn.execute(
                text(
                    """
                    INSERT INTO knowledge_base
                        (keyword, concept, definition, category, difficulty, related_keywords)
                    VALUES (:keyword, :concept, :definition, :category,
                            :difficulty, :related_keywords)
                    ON CONFLICT (keyword) DO UPDATE SET
                        concept = EXCLUDED.concept,
                        definition = EXCLUDED.definition,
                        category = EXCLUDED.category,
                        difficulty = EXCLUDED.difficulty
                    """
                ),
                {
                    "keyword": row["keyword"],
                    "concept": row["concept"],
                    "definition": row["definition"],
                    "category": row.get("category", "general"),
                    "difficulty": row.get("difficulty", 1),
                    "related_keywords": row.get("related_keywords", []),
                },
            )
        for row in scenarios:
            await conn.execute(
                text(
                    """
                    INSERT INTO scenarios (name, description, scenario_type, difficulty, config)
                    VALUES (:name, :description, :scenario_type, :difficulty,
                            CAST(:config AS jsonb))
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "name": row["name"],
                    "description": row["description"],
                    "scenario_type": row["scenario_type"],
                    "difficulty": row.get("difficulty", 1),
                    "config": json.dumps(row.get("config", {})),
                },
            )
    logger.info(
        "Seeded reference rows: %d companies, %d knowledge_base, %d scenarios",
        len(companies),
        len(knowledge),
        len(scenarios),
    )


async def _companies() -> list[dict]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT symbol, name, id::text FROM companies ORDER BY symbol")
        )
        return [{"symbol": s, "name": n, "id": i} for s, n, i in rows.all()]


def _news_rows(companies: list[dict]) -> list[dict]:
    """Sinh bộ tin tức mẫu (deterministic) gắn với công ty đã seed."""
    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    per_company_templates = [
        (
            "{name} công bố kết quả kinh doanh quý vượt kỳ vọng, "
            "cổ phiếu {symbol} tăng mạnh phiên sáng",
            "Báo cáo tài chính mới nhất của {name} vượt dự báo của giới phân tích, "
            "đẩy giá cổ phiếu {symbol} đi lên trong phiên giao dịch đầu ngày. "
            "Ban lãnh đạo cho biết sẽ tiếp tục đẩy mạnh mảng kinh doanh cốt lõi.",
            "positive",
            2.5,
        ),
        (
            "{name} đẩy nhanh kế hoạch mở rộng thị phần trong quý tới",
            "Ban điều hành {name} công bố chiến lược mở rộng mới, "
            "tập trung vào các thị trường tiềm năng. "
            "Nhiều nhà đầu tư kỳ vọng động thái này sẽ cải thiện doanh thu dài hạn.",
            "positive",
            1.8,
        ),
        (
            "Cổ đông {name} băn khoăn trước biến động ngắn hạn của cổ phiếu {symbol}",
            "Mặc dù nền tảng cơ bản ổn định, cổ phiếu {symbol} của {name} "
            "ghi nhận những phiên điều chỉnh, khiến một bộ phận cổ đông "
            "thận trọng trước xu hướng ngắn hạn.",
            "neutral",
            1.2,
        ),
        (
            "Áp lực cạnh tranh ngày càng lớn với {name}, chuyên gia đưa khuyến nghị thận trọng",
            "Sự xuất hiện của nhiều đối thủ mới cùng biên lợi nhuận bị thu hẹp "
            "khiến triển vọng {name} trở nên kém rõ ràng hơn. "
            "Các chuyên gia khuyến nghị theo dõi thêm trước khi ra quyết định.",
            "negative",
            2.2,
        ),
    ]

    for idx, company in enumerate(companies):
        if idx >= 12:
            break
        symbol = company["symbol"]
        name = company["name"]
        template = per_company_templates[idx % len(per_company_templates)]
        title_tpl, body, sentiment, impact = template
        hours_ago = (idx * 7) % 60
        rows.append(
            {
                "title": title_tpl.format(symbol=symbol, name=name),
                "summary": body[:120],
                "content": body,
                "sentiment": sentiment,
                "impact_score": impact,
                "source": "FinSimAI News",
                "category": _CATEGORIES[idx % len(_CATEGORIES)],
                "company_id": company["id"],
                "is_ai_generated": True,
                "simulated_at": now - timedelta(hours=hours_ago, minutes=idx),
            }
        )

    macro_templates = [
        (
            "Thị trường giao dịch tích cực nhờ dòng tiền luân chuyển",
            "Phiên giao dịch ghi nhận dòng tiền đổ vào các nhóm ngành chủ chốt, "
            "giúp chỉ số duy trì đà tăng. Thanh khoản cải thiện so với các phiên trước đó.",
            "positive",
            1.5,
        ),
        (
            "Mặt bằng lãi suất tiếp tục ổn định, hỗ trợ định giá cổ phiếu",
            "Lãi suất giữ ở mức ổn định giúp chi phí vốn doanh nghiệp không đổi, "
            "qua đó hỗ trợ mặt bằng định giá trên thị trường chứng khoán.",
            "neutral",
            1.0,
        ),
        (
            "Nhà đầu tư thận trọng chờ thêm tín hiệu vĩ mô rõ ràng",
            "Khối lượng giao dịch sụt giảm khi nhà đầu tư đứng ngoài quan sát, "
            "chờ thêm dữ liệu kinh tế trước khi giải ngân trở lại.",
            "negative",
            1.3,
        ),
    ]
    for idx, (title, body, sentiment, impact) in enumerate(macro_templates):
        rows.append(
            {
                "title": title,
                "summary": body[:120],
                "content": body,
                "sentiment": sentiment,
                "impact_score": impact,
                "source": "FinSimAI News",
                "category": "vĩ mô",
                "company_id": None,
                "is_ai_generated": True,
                "simulated_at": now - timedelta(hours=1, minutes=idx * 45),
            }
        )
    return rows


def _social_rows(companies: list[dict]) -> list[dict]:
    """Sinh bộ bài đăng mạng xã hội mẫu (deterministic)."""
    now = datetime.now(timezone.utc)
    personas = [
        ("F0 mới tập tành đầu tư", "f0_newbie", 0.3),
        ("Nhà đầu tư cá nhân giàu kinh nghiệm", "pro_trader", 0.7),
        ("Chuyên gia phân tích kỹ thuật", "ta_fa_kol", 0.9),
        ("Tin đồn từ cộng đồng", "rumor_birds", 0.5),
        ("Cò mồi cảm xúc", "meme_entertain", 0.4),
    ]
    templates = [
        (
            "Mình mới mua thêm {symbol} hôm nay, thấy tiềm năng dài hạn rõ ràng! "
            "Ai cùng quan điểm không?",
            0.8,
            "positive",
            False,
        ),
        (
            "Nhìn đồ thị {symbol} mà phát hoảng, ngắn hạn chưa nên ôm. "
            "Kiên nhẫn chờ điểm vào tốt hơn.",
            0.6,
            "negative",
            False,
        ),
        (
            "Có ai để ý {symbol} của {name} không? "
            "Thanh khoản hôm nay tăng bất thường, cẩn thận nhé.",
            0.9,
            "negative",
            True,
        ),
        (
            "{name} về cơ bản vẫn tốt, mình giữ quan điểm tích lũy dần {symbol} mỗi tuần.",
            0.5,
            "positive",
            False,
        ),
        (
            "Tôi nghĩ giá {symbol} sẽ sideway vài tuần tới "
            "trước khi có tín hiệu rõ ràng. Cá nhân đứng ngoài.",
            0.4,
            "neutral",
            False,
        ),
    ]

    rows: list[dict] = []
    for idx, company in enumerate(companies[:14]):
        symbol = company["symbol"]
        name = company["name"]
        author_name, persona_type, virality = personas[idx % len(personas)]
        body_tpl, v_boost, sentiment, is_trap = templates[idx % len(templates)]
        likes = int(20 + ((idx * 37) % 300))
        shares = int(3 + ((idx * 13) % 40))
        rows.append(
            {
                "author_name": author_name,
                "author_avatar": f"https://api.dicebear.com/7.x/thumbs/png?seed={symbol}-{idx}",
                "persona_type": persona_type,
                "content": body_tpl.format(symbol=symbol, name=name),
                "virality_score": round(virality + v_boost, 2),
                "sentiment": sentiment,
                "is_trap": is_trap,
                "company_id": company["id"],
                "likes_count": likes,
                "shares_count": shares,
                "comments_count": int(likes * 0.05),
                "simulated_at": now - timedelta(hours=idx % 40, minutes=(idx * 17) % 60),
            }
        )
    return rows


async def _seed_content_rows() -> None:
    """Ghi news + social_posts chỉ khi bảng đang rỗng."""
    companies = await _companies()
    if not companies:
        logger.warning("No companies seeded — skipping sample news/social content.")
        return

    news_count = await _table_count("news")
    if news_count == 0:
        news_rows = _news_rows(companies)
        async with engine.begin() as conn:
            for row in news_rows:
                await conn.execute(
                    text(
                        """
                        INSERT INTO news
                            (title, summary, content, sentiment, impact_score, source,
                             category, company_id, is_ai_generated, simulated_at)
                        VALUES (:title, :summary, :content, :sentiment, :impact_score, :source,
                                :category, :company_id, :is_ai_generated, :simulated_at)
                        """
                    ),
                    {
                        "title": row["title"],
                        "summary": row["summary"],
                        "content": row["content"],
                        "sentiment": row["sentiment"],
                        "impact_score": row["impact_score"],
                        "source": row["source"],
                        "category": row["category"],
                        "company_id": row["company_id"],
                        "is_ai_generated": row["is_ai_generated"],
                        "simulated_at": row["simulated_at"],
                    },
                )
        logger.info("Seeded %d sample news rows.", len(news_rows))
    else:
        logger.info("news table already has %d rows — skip sample seeding.", news_count)

    social_count = await _table_count("social_posts")
    if social_count == 0:
        social_rows = _social_rows(companies)
        async with engine.begin() as conn:
            for row in social_rows:
                await conn.execute(
                    text(
                        """
                        INSERT INTO social_posts
                            (author_name, author_avatar, persona_type, content, virality_score,
                             sentiment, is_trap, company_id, likes_count, shares_count,
                             comments_count, simulated_at)
                        VALUES (:author_name, :author_avatar, :persona_type, :content,
                                :virality_score,
                                :sentiment, :is_trap, :company_id, :likes_count, :shares_count,
                                :comments_count, :simulated_at)
                        """
                    ),
                    {
                        "author_name": row["author_name"],
                        "author_avatar": row["author_avatar"],
                        "persona_type": row["persona_type"],
                        "content": row["content"],
                        "virality_score": row["virality_score"],
                        "sentiment": row["sentiment"],
                        "is_trap": row["is_trap"],
                        "company_id": row["company_id"],
                        "likes_count": row["likes_count"],
                        "shares_count": row["shares_count"],
                        "comments_count": row["comments_count"],
                        "simulated_at": row["simulated_at"],
                    },
                )
        logger.info("Seeded %d sample social_posts rows.", len(social_rows))
    else:
        logger.info("social_posts table already has %d rows — skip sample seeding.", social_count)


async def seed_if_empty() -> None:
    """Entry point — chạy sau migrations. Fail-soft: lỗi chỉ log, không crash boot."""
    try:
        await _seed_reference_rows()
        await _seed_content_rows()
        logger.info("Database seeding finished.")
    except Exception as e:  # noqa: BLE001
        logger.error("Database seeding failed (non-fatal): %s", e, exc_info=True)
