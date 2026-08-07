"""Pydantic schemas cho cuộc thi (contests) — config + template + request/response.

Template hardcode tại đây (quyết định đã chốt — KHÔNG tạo bảng contest_templates).
Host chỉ chọn vài lựa chọn (template, lĩnh vực, số công ty, độ khó, auto_news,
auto_social); phần còn lại (rules, content) do hệ thống tự điền khi kích hoạt.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TemplateId = Literal["classic", "tech_news", "fast_paced", "micro"]
Difficulty = Literal["easy", "normal", "hard"]
ContestStatus = Literal["draft", "active", "ended"]


class ContestTheme(BaseModel):
    """Tuỳ chọn thẩm mỹ cho trang web thu nhỏ của contest."""

    primary_color: str = "#0ea5e9"
    logo_url: str | None = None


class ContestRules(BaseModel):
    """Quy tắc giao dịch của contest — resolved từ template + difficulty."""

    start_cash: Decimal = Field(default=Decimal("100000000"), ge=Decimal("0"))
    cooldown_seconds: int = Field(default=30, ge=0, le=3600)
    allow_short: bool = False
    volatility_multiplier: float = Field(default=1.0, ge=0.2, le=3.0)
    trading_duration_days: int | None = Field(default=None, ge=1, le=365)


class ContestContentMeta(BaseModel):
    """Hồ sơ nội dung đã được hệ thống tự sinh (§4.3) — idempotency guard."""

    generated: bool = False
    generated_at: datetime | None = None
    company_count: int = 0
    news_count: int = 0
    social_count: int = 0
    symbols: list[str] = Field(default_factory=list)


class ContestConfig(BaseModel):
    """Toàn bộ config lưu trong cột JSONB ``contests.config``.

    Host chỉ điền phần đầu (template/theme/industry/company_count/difficulty/
    auto_news/auto_social); ``rules`` được resolve từ template + difficulty khi
    tạo, ``content`` do pipeline ``activate`` tự điền.
    """

    template: TemplateId = "classic"
    theme: ContestTheme = Field(default_factory=ContestTheme)
    industry: str = "tổng hợp"
    company_count: int = Field(default=8, ge=3, le=20)
    difficulty: Difficulty = "normal"
    auto_news: bool = True
    auto_social: bool = True
    rules: ContestRules = Field(default_factory=ContestRules)
    content: ContestContentMeta = Field(default_factory=ContestContentMeta)


class ContestTemplate(BaseModel):
    """Khuôn (template) — hardcode, host chỉ chọn id."""

    id: TemplateId
    label: str
    description: str
    default_company_count: int
    default_industry: str
    default_rules: ContestRules
    news_emphasis: bool


# ────────────────────────────────────────────────────────────────────────────
# Template có sẵn (quyết định đã chốt — không bảng contest_templates)
# ────────────────────────────────────────────────────────────────────────────
TEMPLATES: dict[str, ContestTemplate] = {
    "classic": ContestTemplate(
        id="classic",
        label="Cổ điển",
        description="Mặc định, giống thị trường chính.",
        default_company_count=8,
        default_industry="tổng hợp",
        default_rules=ContestRules(
            start_cash=Decimal("100000000"),
            cooldown_seconds=30,
            allow_short=False,
            volatility_multiplier=1.0,
            trading_duration_days=None,
        ),
        news_emphasis=False,
    ),
    "tech_news": ContestTemplate(
        id="tech_news",
        label="Công nghệ & Tin tức",
        description="Trọng tâm tin tức và bài viết về lĩnh vực đã chọn.",
        default_company_count=6,
        default_industry="công nghệ",
        default_rules=ContestRules(
            start_cash=Decimal("200000000"),
            cooldown_seconds=15,
            allow_short=False,
            volatility_multiplier=1.2,
            trading_duration_days=30,
        ),
        news_emphasis=True,
    ),
    "fast_paced": ContestTemplate(
        id="fast_paced",
        label="Biến động mạnh",
        description="Giá biến động mạnh, cooldown ngắn — dành cho nhà giao dịch nhanh.",
        default_company_count=10,
        default_industry="tổng hợp",
        default_rules=ContestRules(
            start_cash=Decimal("500000000"),
            cooldown_seconds=5,
            allow_short=True,
            volatility_multiplier=1.6,
            trading_duration_days=14,
        ),
        news_emphasis=False,
    ),
    "micro": ContestTemplate(
        id="micro",
        label="Thu nhỏ",
        description="Cuộc thi nhỏ gọn, ít công ty, diễn ra nhanh.",
        default_company_count=4,
        default_industry="tổng hợp",
        default_rules=ContestRules(
            start_cash=Decimal("50000000"),
            cooldown_seconds=5,
            allow_short=False,
            volatility_multiplier=1.0,
            trading_duration_days=7,
        ),
        news_emphasis=False,
    ),
}

# Mức độ khó chỉnh các biến của template.
_DIFFICULTY_MODS: dict[str, dict[str, float]] = {
    "easy": {"volatility": 0.7, "start_cash": 1.5, "cooldown": 2.0},
    "normal": {"volatility": 1.0, "start_cash": 1.0, "cooldown": 1.0},
    "hard": {"volatility": 1.4, "start_cash": 0.5, "cooldown": 0.5},
}


def resolve_rules(template: ContestTemplate, difficulty: Difficulty) -> ContestRules:
    """Resolve quy tắc giao dịch từ template + độ khó."""
    mod = _DIFFICULTY_MODS[difficulty]
    base = template.default_rules
    start_cash = (base.start_cash * Decimal(str(mod["start_cash"]))).quantize(
        Decimal("0.01")
    )
    cooldown = max(1, int(base.cooldown_seconds * mod["cooldown"]))
    volatility = round(base.volatility_multiplier * mod["volatility"], 2)
    return ContestRules(
        start_cash=start_cash,
        cooldown_seconds=cooldown,
        allow_short=base.allow_short,
        volatility_multiplier=volatility,
        trading_duration_days=base.trading_duration_days,
    )


# ────────────────────────────────────────────────────────────────────────────
# Request / Response
# ────────────────────────────────────────────────────────────────────────────
class ContestCreateRequest(BaseModel):
    """Vài lựa chọn của host khi tạo contest (FR-4) — hệ thống lo phần còn lại."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=3, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=60,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=2000)
    template: TemplateId = "classic"
    industry: str = Field(default="tổng hợp", max_length=100)
    company_count: int | None = Field(default=None, ge=3, le=20)
    difficulty: Difficulty = "normal"
    auto_news: bool = True
    auto_social: bool = True
    theme: ContestTheme = Field(default_factory=ContestTheme)


class ContestUpdateRequest(BaseModel):
    """Cập nhật contest — mọi trường tuỳ chọn."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=3, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=60,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=2000)
    template: TemplateId | None = None
    industry: str | None = Field(default=None, max_length=100)
    company_count: int | None = Field(default=None, ge=3, le=20)
    difficulty: Difficulty | None = None
    auto_news: bool | None = None
    auto_social: bool | None = None
    theme: ContestTheme | None = None


class ContestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    status: str
    config: ContestConfig
    owner_id: uuid.UUID | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0


class ContestListResponse(BaseModel):
    items: list[ContestResponse]
    total: int


class ContestJoinResponse(BaseModel):
    joined: bool
    contest_id: uuid.UUID


def build_config(request: ContestCreateRequest) -> ContestConfig:
    """Dựng config hoàn chỉnh từ vài lựa chọn của host."""
    template = TEMPLATES[request.template]
    rules = resolve_rules(template, request.difficulty)
    return ContestConfig(
        template=request.template,
        theme=request.theme,
        industry=request.industry or template.default_industry,
        company_count=request.company_count or template.default_company_count,
        difficulty=request.difficulty,
        auto_news=request.auto_news,
        auto_social=request.auto_social,
        rules=rules,
    )
