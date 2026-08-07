"""Service cho cuộc thi (contests) — CRUD + pipeline tự sinh nội dung (§4.3).

Host chỉ chọn vài lựa chọn (template, lĩnh vực, số công ty, độ khó, auto_news,
auto_social); ``generate_content`` tự chọn/sinh công ty, gieo giá, tạo tin tức
và bài đăng social deterministic (0 token, không phụ thuộc AI) — đảm bảo contest
luôn có nội dung ngay khi kích hoạt.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from api.v1.pagination import paginate
from models.company import Company
from models.contest import Contest, ContestMember
from models.news import News
from models.social import SocialPost
from models.user import User
from schemas.contest import (
    ContestConfig,
    ContestContentMeta,
    ContestCreateRequest,
    ContestListResponse,
    ContestResponse,
    ContestUpdateRequest,
    build_config,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPANIES_SEED = REPO_ROOT / "packages" / "database" / "seeds" / "companies.yaml"

# Lĩnh vực (host chọn) → sector trong seed companies.yaml.
_INDUSTRY_SECTORS: dict[str, list[str]] = {
    "công nghệ": ["technology"],
    "công nghệ thông tin": ["technology"],
    "tài chính": ["financial"],
    "ngân hàng": ["financial"],
    "bảo hiểm": ["financial"],
    "y tế": ["healthcare"],
    "dược phẩm": ["healthcare"],
    "chăm sóc sức khỏe": ["healthcare"],
    "năng lượng": ["energy"],
    "điện": ["energy"],
    "tiêu dùng": ["consumer goods"],
    "bán lẻ": ["consumer goods"],
    "công nghiệp": ["industrial"],
    "xây dựng": ["industrial"],
    "logistics": ["industrial"],
    "truyền thông": ["communications"],
    "viễn thông": ["communications"],
}


def slugify(name: str) -> str:
    """Chuẩn hoá tên → slug ASCII viết thường, không dấu."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "contest"


async def unique_slug(db: AsyncSession, base: str) -> str:
    """Tạo slug chưa tồn tại — thêm hậu tố ``-2``, ``-3``... khi trùng."""
    candidate = base
    n = 2
    while True:
        exists = await db.execute(select(Contest).where(Contest.slug == candidate))
        if not exists.scalar_one_or_none():
            return candidate
        candidate = f"{base}-{n}"
        n += 1


# ────────────────────────────────────────────────────────────────────────────
# CRUD
# ────────────────────────────────────────────────────────────────────────────
async def get_contest(db: AsyncSession, slug: str) -> Contest | None:
    result = await db.execute(select(Contest).where(Contest.slug == slug))
    return result.scalar_one_or_none()


def is_owner_or_admin(contest: Contest, user: User) -> bool:
    return user.role == "admin" or (contest.owner_id is not None and contest.owner_id == user.id)


async def get_membership(
    db: AsyncSession, contest_id: uuid.UUID, user_id: uuid.UUID
) -> ContestMember | None:
    result = await db.execute(
        select(ContestMember).where(
            ContestMember.contest_id == contest_id,
            ContestMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_contest(
    db: AsyncSession, owner: User, body: ContestCreateRequest
) -> Contest:
    """Dựng contest draft từ vài lựa chọn của host (chưa generate nội dung)."""
    contest = Contest(
        slug=body.slug or slugify(body.name),
        name=body.name,
        description=body.description,
        status="draft",
        config=build_config(body).model_dump(mode="json"),
        owner_id=owner.id,
    )
    contest.slug = await unique_slug(db, contest.slug)
    db.add(contest)
    await db.commit()
    await db.refresh(contest)
    return contest


async def update_contest(
    db: AsyncSession, contest: Contest, body: ContestUpdateRequest
) -> Contest:
    if body.name is not None:
        contest.name = body.name
    if body.slug is not None and body.slug != contest.slug:
        contest.slug = await unique_slug(db, body.slug)
    if body.description is not None:
        contest.description = body.description

    config = ContestConfig.model_validate(contest.config)
    if body.template is not None:
        config.template = body.template
    if body.industry is not None:
        config.industry = body.industry
    if body.company_count is not None:
        config.company_count = body.company_count
    if body.difficulty is not None:
        config.difficulty = body.difficulty
    if body.auto_news is not None:
        config.auto_news = body.auto_news
    if body.auto_social is not None:
        config.auto_social = body.auto_social
    if body.theme is not None:
        config.theme = body.theme

    if not config.content.generated:
        contest.config = config.model_dump(mode="json")

    await db.commit()
    await db.refresh(contest)
    return contest


async def soft_delete_contest(db: AsyncSession, contest: Contest) -> Contest:
    """Xoá mềm — chỉ chuyển ``status='ended'``, không hard-delete."""
    contest.status = "ended"
    await db.commit()
    await db.refresh(contest)
    return contest


async def list_contests(
    db: AsyncSession, user: User, skip: int, limit: int
) -> ContestListResponse:
    if user.role == "admin":
        stmt = select(Contest)
    elif user.role == "host":
        stmt = select(Contest).where(
            (Contest.status == "active") | (Contest.owner_id == user.id)
        )
    else:
        stmt = select(Contest).where(Contest.status == "active")
    stmt = stmt.order_by(Contest.created_at.desc())
    items, total = await paginate(db, stmt, skip, limit)

    ids = [c.id for c in items]
    counts: dict[uuid.UUID, int] = {}
    if ids:
        rows = (
            await db.execute(
                select(ContestMember.contest_id, func.count())
                .where(ContestMember.contest_id.in_(ids))
                .group_by(ContestMember.contest_id)
            )
        ).all()
        counts = {cid: cnt for cid, cnt in rows}

    responses: list[ContestResponse] = []
    for contest in items:
        resp = ContestResponse.model_validate(contest)
        resp.member_count = counts.get(contest.id, 0)
        responses.append(resp)
    return ContestListResponse(items=responses, total=total)


async def join_contest(
    db: AsyncSession, user: User, contest: Contest
) -> ContestMember:
    existing = await get_membership(db, contest.id, user.id)
    if existing:
        return existing
    member = ContestMember(contest_id=contest.id, user_id=user.id)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


# ────────────────────────────────────────────────────────────────────────────
# Pipeline tự sinh (§4.3) — idempotent
# ────────────────────────────────────────────────────────────────────────────
async def activate_contest(db: AsyncSession, contest: Contest) -> Contest:
    """Kích hoạt contest — chạy pipeline tự sinh rồi chuyển ``active``.

    Idempotent: nếu đã generate content rồi thì bỏ qua, không nhân đôi dữ liệu.
    """
    config = ContestConfig.model_validate(contest.config)
    if config.content.generated:
        return contest
    return await generate_content(db, contest)


def _load_company_templates() -> list[dict[str, Any]]:
    if not COMPANIES_SEED.exists():
        return []
    with open(COMPANIES_SEED, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return list(data.get("companies", []))


def _match_company_templates(
    templates: list[dict[str, Any]], industry: str
) -> list[dict[str, Any]]:
    """Lọc template công ty theo lĩnh vực host chọn; 'tổng hợp' → tất cả."""
    key = (industry or "").strip().lower()
    if not key or key in ("tổng hợp", "general", "tất cả"):
        return templates
    sectors = _INDUSTRY_SECTORS.get(key, [])
    if sectors:
        matched = [c for c in templates if c["sector"].lower() in sectors]
        if matched:
            return matched
    return [c for c in templates if key in c["sector"].lower()]


def _sector_label(industry: str) -> str:
    """Sector mặc định cho công ty tự sinh (SCEN_) theo lĩnh vực."""
    key = (industry or "").strip().lower()
    for aliases in _INDUSTRY_SECTORS.values():
        if key in aliases:
            return aliases[0].title()
    return "General"


def _ensure_company_count(
    templates: list[dict[str, Any]], count: int, sector_label: str
) -> list[dict[str, Any]]:
    """Bổ sung công ty tự sinh (prefix SCEN_) nếu seed không đủ."""
    result = list(templates)
    idx = 1
    while len(result) < count:
        result.append(
            {
                "symbol": f"SCEN{idx:03d}",
                "name": f"Scenario Corp {idx}",
                "description": f"Tự sinh theo lĩnh vực {sector_label}.",
                "sector": sector_label,
                "current_price": 100.0,
                "volatility": 0.03,
                "shares_outstanding": 100000000,
                "health_score": 70,
                "pe_ratio": None,
                "roe": None,
                "net_margin": None,
                "max_drawdown": None,
            }
        )
        idx += 1
    return result[:count]


def _opt_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _news_rows_for_contest(
    companies: list[Company], industry: str, news_emphasis: bool
) -> list[dict[str, Any]]:
    """Sinh tin deterministic cho contest (1–2 tin/công ty + 1 tin vĩ mô)."""
    now = datetime.now(timezone.utc)
    per_company = [
        (
            "{name} công bố kết quả kinh doanh quý vượt kỳ vọng, "
            "cổ phiếu {symbol} tăng mạnh phiên sáng",
            "Báo cáo tài chính mới nhất của {name} vượt dự báo của giới phân tích, "
            "đẩy giá cổ phiếu {symbol} đi lên. Ban lãnh đạo cho biết sẽ tiếp tục "
            "đẩy mạnh mảng kinh doanh cốt lõi.",
            "positive",
            2.5,
        ),
        (
            "{name} đẩy nhanh kế hoạch mở rộng thị phần trong quý tới",
            "Ban điều hành {name} công bố chiến lược mở rộng mới tập trung vào các "
            "thị trường tiềm năng. Nhiều nhà đầu tư kỳ vọng động thái này cải thiện "
            "doanh thu dài hạn.",
            "positive",
            1.8,
        ),
        (
            "Cổ đông {name} băn khoăn trước biến động ngắn hạn của cổ phiếu {symbol}",
            "Mặc dù nền tảng cơ bản ổn định, cổ phiếu {symbol} của {name} ghi nhận "
            "những phiên điều chỉnh khiến một bộ phận cổ đông thận trọng trước xu "
            "hướng ngắn hạn.",
            "neutral",
            1.2,
        ),
        (
            "Áp lực cạnh tranh ngày càng lớn với {name}, chuyên gia đưa khuyến nghị thận trọng",
            "Sự xuất hiện của nhiều đối thủ mới cùng biên lợi nhuận bị thu hẹp khiến "
            "triển vọng {name} kém rõ ràng hơn. Các chuyên gia khuyến nghị theo dõi "
            "thêm trước khi ra quyết định.",
            "negative",
            2.2,
        ),
    ]
    repeat = 2 if news_emphasis else 1
    rows: list[dict[str, Any]] = []
    idx = 0
    for company in companies:
        for _ in range(repeat):
            title_tpl, body, sentiment, impact = per_company[idx % len(per_company)]
            hours_ago = (idx * 5) % 48
            rows.append(
                {
                    "title": title_tpl.format(symbol=company.symbol, name=company.name),
                    "summary": body[:120],
                    "content": body,
                    "sentiment": sentiment,
                    "impact_score": impact,
                    "category": "doanh nghiệp",
                    "company_id": company.id,
                    "simulated_at": now - timedelta(hours=hours_ago, minutes=idx),
                }
            )
            idx += 1

    label = industry or "mô phỏng"
    rows.append(
        {
            "title": f"Thị trường {label} giao dịch tích cực nhờ dòng tiền luân chuyển",
            "summary": "Phiên giao dịch ghi nhận dòng tiền đổ vào các nhóm ngành "
            "chủ chốt, giúp chỉ số duy trì đà tăng.",
            "content": f"Trong bối cảnh lĩnh vực {label} được quan tâm, dòng tiền "
            "luân chuyển mạnh mẽ khiến thanh khoản cải thiện so với các phiên trước.",
            "sentiment": "positive",
            "impact_score": 1.5,
            "category": "vĩ mô",
            "company_id": None,
            "simulated_at": now - timedelta(minutes=5),
        }
    )
    return rows


def _social_rows_for_contest(companies: list[Company]) -> list[dict[str, Any]]:
    """Sinh bài đăng MXH deterministic cho contest."""
    now = datetime.now(timezone.utc)
    personas = [
        ("F0 mới tập tành đầu tư", "f0_newbie", 0.3),
        ("Nhà đầu tư cá nhân giàu kinh nghiệm", "pro_trader", 0.7),
        ("Chuyên gia phân tích kỹ thuật", "ta_fa_kol", 0.9),
        ("Tin đồn từ cộng đồng", "rumor_birds", 0.5),
    ]
    templates = [
        (
            "Mình mới mua thêm {symbol} hôm nay, thấy tiềm năng dài hạn rõ ràng! "
            "Ai cùng quan điểm không?",
            0.8,
            "positive",
        ),
        (
            "Nhìn đồ thị {symbol} mà phát hoảng, ngắn hạn chưa nên ôm. "
            "Kiên nhẫn chờ điểm vào tốt hơn.",
            0.6,
            "negative",
        ),
        (
            "Có ai để ý {symbol} của {name} không? "
            "Thanh khoản hôm nay tăng bất thường, cẩn thận nhé.",
            0.9,
            "negative",
        ),
        (
            "{name} về cơ bản vẫn tốt, mình giữ quan điểm tích lũy dần {symbol} mỗi tuần.",
            0.5,
            "positive",
        ),
    ]
    rows: list[dict[str, Any]] = []
    for idx, company in enumerate(companies):
        author_name, persona_type, virality = personas[idx % len(personas)]
        body_tpl, v_boost, sentiment = templates[idx % len(templates)]
        likes = int(20 + ((idx * 37) % 300))
        rows.append(
            {
                "author_name": author_name,
                "author_avatar": (
                    "https://api.dicebear.com/7.x/thumbs/png?"
                    f"seed={company.symbol}-{idx}"
                ),
                "persona_type": persona_type,
                "content": body_tpl.format(symbol=company.symbol, name=company.name),
                "virality_score": round(virality + v_boost, 2),
                "sentiment": sentiment,
                "company_id": company.id,
                "likes_count": likes,
                "shares_count": int(3 + ((idx * 13) % 40)),
                "comments_count": int(likes * 0.05),
                "simulated_at": now - timedelta(hours=idx % 40, minutes=(idx * 17) % 60),
            }
        )
    return rows


async def generate_content(db: AsyncSession, contest: Contest) -> Contest:
    """Pipeline tự sinh §4.3: công ty → giá → tin → social → config content."""
    config = ContestConfig.model_validate(contest.config)
    if config.content.generated:
        return contest

    templates = _load_company_templates()
    matched = _match_company_templates(templates, config.industry)
    sector_label = _sector_label(config.industry)
    picked = _ensure_company_count(matched, config.company_count, sector_label)

    vol_mult = Decimal(str(config.rules.volatility_multiplier))
    companies: list[Company] = []
    for tpl in picked:
        price = Decimal(str(tpl["current_price"]))
        shares = Decimal(str(tpl["shares_outstanding"]))
        volatility = (Decimal(str(tpl["volatility"])) * vol_mult).quantize(
            Decimal("0.0001")
        )
        company = Company(
            contest_id=contest.id,
            symbol=tpl["symbol"],
            name=tpl["name"],
            description=tpl.get("description"),
            sector=tpl["sector"],
            current_price=price,
            volatility=volatility,
            shares_outstanding=shares,
            health_score=tpl.get("health_score", 70),
            pe_ratio=_opt_decimal(tpl.get("pe_ratio")),
            roe=_opt_decimal(tpl.get("roe")),
            net_margin=_opt_decimal(tpl.get("net_margin")),
            max_drawdown=_opt_decimal(tpl.get("max_drawdown")),
        )
        db.add(company)
        companies.append(company)
    await db.flush()

    news_count = 0
    if config.auto_news:
        news_rows = _news_rows_for_contest(
            companies, config.industry, config.template == "tech_news"
        )
        for row in news_rows:
            db.add(
                News(
                    contest_id=contest.id,
                    company_id=row["company_id"],
                    title=row["title"],
                    summary=row["summary"],
                    content=row["content"],
                    source="FinSimAI Contest",
                    category=row["category"],
                    sentiment=row["sentiment"],
                    impact_score=row["impact_score"],
                    is_ai_generated=True,
                    simulated_at=row["simulated_at"],
                )
            )
        news_count = len(news_rows)

    social_count = 0
    if config.auto_social:
        social_rows = _social_rows_for_contest(companies)
        for row in social_rows:
            db.add(
                SocialPost(
                    contest_id=contest.id,
                    company_id=row["company_id"],
                    author_name=row["author_name"],
                    author_avatar=row["author_avatar"],
                    persona_type=row["persona_type"],
                    content=row["content"],
                    sentiment=row["sentiment"],
                    virality_score=row["virality_score"],
                    likes_count=row["likes_count"],
                    shares_count=row["shares_count"],
                    comments_count=row["comments_count"],
                    simulated_at=row["simulated_at"],
                )
            )
        social_count = len(social_rows)

    now = datetime.now(timezone.utc)
    config.content = ContestContentMeta(
        generated=True,
        generated_at=now,
        company_count=len(companies),
        news_count=news_count,
        social_count=social_count,
        symbols=[c.symbol for c in companies],
    )
    contest.config = config.model_dump(mode="json")
    contest.status = "active"
    contest.starts_at = now
    if config.rules.trading_duration_days:
        contest.ends_at = now + timedelta(days=config.rules.trading_duration_days)
    await db.commit()
    await db.refresh(contest)
    return contest
