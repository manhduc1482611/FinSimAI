"""Boot-time idempotent seeding cho Capia database.

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
from typing import Any

import yaml
from core.database import engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDS_DIR = REPO_ROOT / "packages" / "database" / "seeds"

_MACRO_CATEGORIES = ("thị trường", "vĩ mô")
_CATEGORIES = ("doanh nghiệp", "thị trường", "phân tích", "nhận định")


def _load_yaml(filename: str) -> dict[str, Any]:
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
                        (symbol, name, description, sector, contest_id, current_price, volatility,
                         shares_outstanding, health_score, pe_ratio, roe, net_margin, max_drawdown)
                    VALUES (:symbol, :name, :description, :sector, :contest_id,
                            :current_price, :volatility, :shares_outstanding, :health_score,
                            :pe_ratio, :roe, :net_margin, :max_drawdown)
                    ON CONFLICT (symbol) WHERE contest_id IS NULL DO NOTHING
                    """
                ),
                {
                    "symbol": row["symbol"],
                    "name": row["name"],
                    "description": row.get("description", ""),
                    "sector": row["sector"],
                    "contest_id": None,
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


async def _companies() -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT symbol, name, id::text FROM companies ORDER BY symbol")
        )
        return [{"symbol": s, "name": n, "id": i} for s, n, i in rows.all()]


def _news_rows(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sinh bộ tin tức mẫu (deterministic) gắn với công ty đã seed."""
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    per_company_templates = [
        (
            "{name} công bố kết quả kinh doanh quý vượt kỳ vọng, "
            "cổ phiếu {symbol} tăng mạnh phiên sáng",
            "Báo cáo tài chính mới nhất của {name} vượt dự báo của giới phân tích, "
            "đẩy giá cổ phiếu {symbol} đi lên trong phiên giao dịch đầu ngày. "
            "Ban lãnh đạo cho biết sẽ tiếp tục đẩy mạnh mảng kinh doanh cốt lõi.\n\n"
            "Theo báo cáo, doanh thu quý tăng trưởng hai chữ số so với cùng kỳ nhờ "
            "mở rộng kênh phân phối và tối ưu biên gộp. Biên lợi nhuận ròng cải thiện "
            "đáng kể sau khi doanh nghiệp kiểm soát chi phí vận hành.\n\n"
            "Giới phân tích nâng ước tính giá mục tiêu cho {symbol} sau kết quả vượt "
            "trội, đồng thời lưu ý rủi ro từ biến động tỷ giá và chu kỳ hàng tồn kho. "
            "Nhà đầu tư dự kiến sẽ đón thêm thông tin chi tiết tại buổi họp cổ đông tới.",
            "positive",
            2.5,
        ),
        (
            "{name} đẩy nhanh kế hoạch mở rộng thị phần trong quý tới",
            "Ban điều hành {name} công bố chiến lược mở rộng mới, "
            "tập trung vào các thị trường tiềm năng. "
            "Nhiều nhà đầu tư kỳ vọng động thái này sẽ cải thiện doanh thu dài hạn.\n\n"
            "Kế hoạch bao gồm mở thêm điểm bán, tăng độ phủ sản phẩm và đầu tư vào "
            "chuyển đổi số. Lãnh đạo công ty nhấn mạnh việc thận trọng trong chi tiêu "
            "để bảo đảm dòng tiền ổn định.\n\n"
            "Cổ phiếu {symbol} phản ứng tích cực trong ngắn hạn. Tuy nhiên các chuyên "
            "gia khuyến nghị theo dõi tiến độ thực thi kế hoạch trước khi đưa ra nhận "
            "định dài hạn về mức tăng trưởng.",
            "positive",
            1.8,
        ),
        (
            "Cổ đông {name} băn khoăn trước biến động ngắn hạn của cổ phiếu {symbol}",
            "Mặc dù nền tảng cơ bản ổn định, cổ phiếu {symbol} của {name} "
            "ghi nhận những phiên điều chỉnh, khiến một bộ phận cổ đông "
            "thận trọng trước xu hướng ngắn hạn.\n\n"
            "Khối lượng giao dịch tăng trong các phiên giảm điểm cho thấy áp lực "
            "chốt lời sau nhịp tăng trước đó. Nhà đầu tư nội bộ chưa ghi nhận giao "
            "dịch bất thường của cổ đông lớn.\n\n"
            "Ban lãnh đạo khẳng định hoạt động kinh doanh vẫn diễn ra bình thường và "
            "kỳ vọng thị trường sẽ sớm ổn định khi các thông tin cụ thể được công bố.",
            "neutral",
            1.2,
        ),
        (
            "Áp lực cạnh tranh ngày càng lớn với {name}, chuyên gia đưa khuyến nghị thận trọng",
            "Sự xuất hiện của nhiều đối thủ mới cùng biên lợi nhuận bị thu hẹp "
            "khiến triển vọng {name} trở nên kém rõ ràng hơn. "
            "Các chuyên gia khuyến nghị theo dõi thêm trước khi ra quyết định.\n\n"
            "Thị phần của doanh nghiệp đang chịu sức ép từ các sản phẩm thay thế và "
            "chính sách giá cạnh tranh của đối thủ. Chi phí nguyên vật liệu tăng cũng "
            "ăn mòn biên lợi nhuận quý gần nhất.\n\n"
            "Nhiều quỹ đầu tư hạ tỷ trọng nắm giữ {symbol} trong danh mục. Cổ phiếu "
            "có thể tiếp tục chịu áp lực cho tới khi doanh nghiệp cho thấy dấu hiệu "
            "cải thiện rõ rệt về hiệu quả hoạt động.",
            "negative",
            2.2,
        ),
    ]

    for idx, company in enumerate(companies[:40]):
        symbol = company["symbol"]
        name = company["name"]
        template = per_company_templates[idx % len(per_company_templates)]
        title_tpl, body, sentiment, impact = template
        full_body = body.format(symbol=symbol, name=name)
        hours_ago = (idx * 7) % 90
        rows.append(
            {
                "title": title_tpl.format(symbol=symbol, name=name),
                "summary": full_body.split("\n\n")[0][:160],
                "content": full_body,
                "sentiment": sentiment,
                "impact_score": impact,
                "source": "Capia News",
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
            "giúp chỉ số duy trì đà tăng. Thanh khoản cải thiện so với các phiên trước đó.\n\n"
            "Nhóm ngân hàng và bất động sản dẫn dắt đà hồi phục nhờ kỳ vọng tín dụng "
            "tăng tốc cuối năm. Khối ngoại quay lại mua ròng trên cả hai sàn.\n\n"
            "Giới phân tích cho rằng xu hướng tích lũy vẫn còn nguyên khi định giá "
            "nhiều cổ phiếu đang về vùng hấp dẫn so với trung bình lịch sử.",
            "positive",
            1.5,
        ),
        (
            "Mặt bằng lãi suất tiếp tục ổn định, hỗ trợ định giá cổ phiếu",
            "Lãi suất giữ ở mức ổn định giúp chi phí vốn doanh nghiệp không đổi, "
            "qua đó hỗ trợ mặt bằng định giá trên thị trường chứng khoán.\n\n"
            "Ngân hàng nhà nước phát đi thông điệp điều hành linh hoạt, tránh gây sốc "
            "lên thị trường tiền tệ. Lãi suất huy động vẫn ở vùng thấp tạo điều kiện "
            "cho dòng tiền dư thừa tìm đến kênh đầu tư.\n\n"
            "Các doanh nghiệp vay vốn mới được hưởng mức lãi suất cạnh tranh, giúp "
            "giảm áp lực lên chi phí tài chính trong kỳ báo cáo sắp tới.",
            "neutral",
            1.0,
        ),
        (
            "Nhà đầu tư thận trọng chờ thêm tín hiệu vĩ mô rõ ràng",
            "Khối lượng giao dịch sụt giảm khi nhà đầu tư đứng ngoài quan sát, "
            "chờ thêm dữ liệu kinh tế trước khi giải ngân trở lại.\n\n"
            "Diễn biến thị trường toàn cầu chưa rõ nét khiến dòng vốn tổ chức chờ "
            "đợi. Các phiên tăng giảm đan xen làm gia tăng sự phân vân của nhà đầu tư.\n\n"
            "Nhiều khuyến nghị cho rằng nên ưu tiên quản trị rủi ro, duy trì tỷ trọng "
            "tiền mặt hợp lý cho tới khi xu hướng chủ đạo được xác nhận.",
            "negative",
            1.3,
        ),
        (
            "Chu kỳ nguyên vật liệu biến động khiến chi phí sản xuất tăng",
            "Giá nguyên vật liệu đầu vào tăng mạnh trong những tuần gần đây, gây áp "
            "lực lên biên lợi nhuận của các doanh nghiệp sản xuất.\n\n"
            "Các doanh nghiệp lớn đang tái đàm phán hợp đồng cung cấp dài hạn nhằm "
            "hạ nhiệt tác động ngắn hạn. Một số đơn vị tính phương án tăng giá bán."
            "\n\nChuyên gia đánh giá mức độ ảnh hưởng phụ thuộc vào tỷ trọng chi phí "
            "nguyên liệu trong cơ cấu giá thành của từng ngành.",
            "negative",
            2.0,
        ),
        (
            "Ngành bán lẻ ghi nhận tín hiệu phục hồi tiêu dùng tích cực",
            "Sức mua nội địa cải thiện khi lạm phát hạ nhiệt và thu nhập người lao "
            "động phục hồi, mở ra triển vọng tích cực cho nhóm bán lẻ.\n\n"
            "Doanh thu bán lẻ hàng hóa tăng so với cùng kỳ ở nhiều nhóm mặt hàng như "
            "điện tử, thời trang và hàng tiêu dùng thiết yếu.\n\n"
            "Các chuỗi bán lẻ chủ động mở rộng cửa hàng và triển khai khuyến mãi để "
            "gia tăng thị phần trong mùa cao điểm tiêu dùng sắp tới.",
            "positive",
            1.7,
        ),
        (
            "Tỷ giá giằng co, doanh nghiệp xuất khẩu được hưởng lợi một phần",
            "Tỷ giá trung tâm được điều chỉnh linh hoạt theo biến động thị trường "
            "quốc tế, tạo thuận lợi tương đối cho khối doanh nghiệp xuất khẩu.\n\n"
            "Tuy nhiên các doanh nghiệp nhập khẩu nguyên liệu gặp áp lực chi phí cao "
            "hơn. Cân đối thu chi ngoại tệ vẫn được duy trì ổn định.\n\n"
            "Ngân hàng trung ương khẳng định sẽ can thiệp khi cần để tránh biến động "
            "quá mức gây tổn hại cho nền kinh tế.",
            "neutral",
            1.4,
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
                "source": "Capia News",
                "category": "vĩ mô",
                "company_id": None,
                "is_ai_generated": True,
                "simulated_at": now - timedelta(hours=1, minutes=idx * 45),
            }
        )
    return rows


def _social_rows(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
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


async def _seed_sample_contest() -> None:
    """Nếu chưa có contest nào, tạo 1 contest mẫu bằng chính pipeline §4.3."""
    count = await _table_count("contests")
    if count > 0:
        logger.info("contests table already has %d rows — skip sample contest.", count)
        return

    from core.database import async_session_factory
    from models.contest import Contest
    from schemas.contest import ContestCreateRequest, build_config
    from services import contest_service

    async with async_session_factory() as db:
        request = ContestCreateRequest(
            name="Thị trường chính ảo",
            slug="thi-truong-chinh-ao",
            description=(
                "Cuộc thi mẫu do hệ thống tự tạo khi chưa có contest nào, "
                "minh hoạ generator nội dung deterministic hoạt động."
            ),
            template="classic",
            difficulty="normal",
        )
        contest = Contest(
            slug=request.slug,
            name=request.name,
            description=request.description,
            status="draft",
            config=build_config(request).model_dump(mode="json"),
            owner_id=None,
        )
        db.add(contest)
        await db.commit()
        await db.refresh(contest)
        await contest_service.generate_content(db, contest)
        logger.info("Seeded sample contest '%s' via generator pipeline.", contest.name)


_TASKS = [
    # ── A. Định hướng (onboarding) ──────────────────────────────────────────
    ("profile_complete", "Hoàn thiện hồ sơ cá nhân",
     "Cập nhật đầy đủ thông tin hồ sơ để bắt đầu hành trình đầu tư.",
     "onboarding", "500000", 1, "none", True, 100),
    ("first_trade", "Đặt lệnh giao dịch đầu tiên",
     "Đặt thành công lệnh mua hoặc bán đầu tiên của bạn.",
     "onboarding", "200000", 1, "none", True, 110),
    ("first_knowledge_read", "Đọc bài kiến thức đầu tiên",
     "Khám phá kho kiến thức chứng khoán của Capia.",
     "onboarding", "100000", 1, "none", True, 120),
    ("first_news_read", "Đọc tin tức đầu tiên",
     "Cập nhật tin tức thị trường mới nhất trong ngày.",
     "onboarding", "100000", 1, "none", True, 130),
    ("first_company_view", "Xem hồ sơ công ty đầu tiên",
     "Tìm hiểu thông tin một doanh nghiệp niêm yết.",
     "onboarding", "100000", 1, "none", True, 140),
    ("first_mentor_chat", "Trò chuyện Mentor lần đầu",
     "Đặt câu hỏi đầu tiên cho Mentor AI của bạn.",
     "onboarding", "200000", 1, "none", True, 150),
    ("scenario_1_done", "Hoàn thành kịch bản đầu tiên",
     "Vượt qua kịch bản mô phỏng đầu tiên trong chế độ luyện tập.",
     "onboarding", "300000", 1, "none", True, 160),
    ("onboarding_complete", "Hoàn tất định hướng",
     "Hoàn thành TẤT CẢ nhiệm vụ định hướng để nhận thưởng lớn.",
     "onboarding", "1000000", 1, "none", True, 190),
    # ── B. Học tập (learning) ───────────────────────────────────────────────
    ("read_5_knowledge", "Đọc 5 bài kiến thức",
     "Tích lũy 5 bài kiến thức đã đọc (cộng dồn).",
     "learning", "300000", 5, "none", True, 200),
    ("read_10_knowledge", "Đọc 10 bài kiến thức",
     "Tích lũy 10 bài kiến thức đã đọc (cộng dồn).",
     "learning", "500000", 10, "none", True, 210),
    ("read_10_news", "Đọc 10 tin tức",
     "Cập nhật 10 tin tức thị trường (cộng dồn).",
     "learning", "400000", 10, "none", True, 220),
    ("analyze_3_companies", "Phân tích 3 công ty",
     "Xem hồ sơ chi tiết của 3 doanh nghiệp (cộng dồn).",
     "learning", "300000", 3, "none", True, 230),
    ("mentor_3_chats", "Trò chuyện Mentor 3 lần",
     "Trao đổi 3 lượt với Mentor AI (cộng dồn).",
     "learning", "400000", 3, "none", True, 240),
    # ── C. Hằng ngày (daily) ────────────────────────────────────────────────
    ("daily_checkin", "Điểm danh hằng ngày",
     "Đăng nhập và điểm danh mỗi ngày để giữ chuỗi ngày liên tiếp.",
     "daily", "50000", 1, "daily", True, 300),
    ("daily_trade_1", "Giao dịch trong ngày",
     "Đặt ít nhất 1 lệnh giao dịch trong ngày hôm nay.",
     "daily", "100000", 1, "daily", True, 310),
    ("daily_read_3_knowledge", "Đọc 3 bài kiến thức trong ngày",
     "Đọc 3 bài kiến thức trong ngày hôm nay.",
     "daily", "100000", 3, "daily", True, 320),
    ("daily_read_2_news", "Đọc 2 tin tức trong ngày",
     "Đọc 2 tin tức trong ngày hôm nay.",
     "daily", "100000", 2, "daily", True, 330),
    ("daily_mentor_1", "Trò chuyện Mentor trong ngày",
     "Trò chuyện với Mentor ít nhất 1 lần trong ngày.",
     "daily", "100000", 1, "daily", True, 340),
    ("daily_all_4", "Hoàn thành 4/5 nhiệm vụ hằng ngày",
     "Hoàn thành 4 trong 5 nhiệm vụ hằng ngày để nhận thưởng lớn.",
     "daily", "500000", 1, "daily", True, 390),
    # ── D. Chuỗi ngày (streak) ──────────────────────────────────────────────
    ("streak_3", "Chuỗi 3 ngày liên tiếp",
     "Duy trì chuỗi điểm danh 3 ngày liên tiếp.",
     "streak", "200000", 3, "none", True, 400),
    ("streak_7", "Chuỗi 7 ngày liên tiếp",
     "Duy trì chuỗi điểm danh 7 ngày liên tiếp.",
     "streak", "500000", 7, "none", True, 410),
    ("streak_30", "Chuỗi 30 ngày liên tiếp",
     "Duy trì chuỗi điểm danh 30 ngày liên tiếp.",
     "streak", "2000000", 30, "none", True, 420),
    # ── E. Cuộc thi (contest) ───────────────────────────────────────────────
    ("contest_join_1", "Tham gia cuộc thi đầu tiên",
     "Gia nhập một cuộc thi đầu tư ảo để cạnh tranh thứ hạng.",
     "contest", "200000", 1, "none", True, 500),
    ("contest_top10", "Lọt top 10 cuộc thi",
     "Đứng trong top 10 bảng xếp hạng một cuộc thi — nhận thưởng thủ công.",
     "contest", "2000000", 1, "none", True, 510),
]


async def _seed_tasks() -> None:
    """Upsert nhiệm vụ theo ``code`` — idempotent, chạy lại không nhân đôi."""
    async with engine.begin() as conn:
        for row in _TASKS:
            await conn.execute(
                text(
                    """
                    INSERT INTO tasks
                        (code, name, description, category, reward_amount,
                         target_count, reset_frequency, is_active, sort_order)
                    VALUES (:code, :name, :description, :category, :reward_amount,
                            :target_count, :reset_frequency, :is_active, :sort_order)
                    ON CONFLICT (code) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        reward_amount = EXCLUDED.reward_amount,
                        target_count = EXCLUDED.target_count,
                        reset_frequency = EXCLUDED.reset_frequency,
                        is_active = EXCLUDED.is_active,
                        sort_order = EXCLUDED.sort_order
                    """
                ),
                {
                    "code": row[0],
                    "name": row[1],
                    "description": row[2],
                    "category": row[3],
                    "reward_amount": row[4],
                    "target_count": row[5],
                    "reset_frequency": row[6],
                    "is_active": row[7],
                    "sort_order": row[8],
                },
            )
    logger.info("Seeded %d task definitions.", len(_TASKS))


async def seed_if_empty() -> None:
    """Entry point — chạy sau migrations. Fail-soft: lỗi chỉ log, không crash boot."""
    try:
        await _seed_reference_rows()
        await _seed_content_rows()
        await _seed_sample_contest()
        await _seed_tasks()
        logger.info("Database seeding finished.")
    except Exception as e:  # noqa: BLE001
        logger.error("Database seeding failed (non-fatal): %s", e, exc_info=True)
