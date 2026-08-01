"""Task sinh nội dung giả lập — chạy qua ARQ.

- ``generate_scenario_batch``: sinh N bài báo giả lập cho thế giới mô phỏng.
- ``generate_social_posts``: sinh bài đăng MXH cho 10 Persona ngầm.

Cả hai:
- Ưu tiên gọi Gemini (qua :class:`integrations.gemini.GeminiClient`) có ép
  JSON schema, NHƯNG luôn đi qua rate limiter Redis để không vượt RPM.
- Khi Gemini chưa có key / hết token / trả output sai → FALLBACK DETERMINISTIC
  (0 token) từ template YAML, đảm bảo luôn trả về kết quả hợp lệ.
"""

from __future__ import annotations

import asyncio
import logging
import random
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from integrations.gemini import GeminiError, GeminiUnavailableError
from prompts.loader import PromptStore

logger = logging.getLogger(__name__)

SCENARIO_PROMPT_FILE = "scenario_prompts.yaml"
SOCIAL_PROMPT_FILE = "social_prompts.yaml"


class ArticleCategory(str, Enum):
    """Loại bài báo giả lập."""

    MACRO_DOMESTIC = "macro_domestic"
    MACRO_INTERNATIONAL = "macro_international"
    INDUSTRY = "industry"
    COMPANY = "company"
    MARKET_REPORT = "market_report"


class SentimentLabel(str, Enum):
    """Hướng ảnh hưởng của nội dung tới thị trường."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ScenarioArticle(BaseModel):
    """Một bài báo giả lập — schema khớp cả prompt lẫn fallback YAML."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    content: str = Field(min_length=1)
    category: ArticleCategory
    sentiment: SentimentLabel
    impact_score: int = Field(ge=1, le=10)
    affected_industries: list[str] = Field(default_factory=list)
    affected_companies: list[str] = Field(default_factory=list)
    knowledge_tags: list[str] = Field(default_factory=list)
    is_fictional: bool = True


class SocialPost(BaseModel):
    """Một bài đăng MXH giả lập của một persona."""

    persona_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    sentiment: SentimentLabel
    virality_score: int = Field(ge=1, le=10)
    tags: list[str] = Field(default_factory=list)
    has_deception: bool = False
    deception_note: str = ""


# ────────────────────────────────────────────────────────────────────────────
# Scenario batch
# ────────────────────────────────────────────────────────────────────────────
async def generate_scenario_batch(
    ctx: dict[str, Any],
    *,
    count: int = 5,
    macro_context: str | None = None,
) -> list[dict[str, Any]]:
    """Sinh ``count`` bài báo giả lập (mặc định 5, tối đa 10)."""
    count = max(1, min(int(count), 10))
    store: PromptStore = ctx["store"]
    redis = ctx["redis"]

    companies = store.require(SCENARIO_PROMPT_FILE, "fallback", "companies")
    templates = store.require(SCENARIO_PROMPT_FILE, "fallback", "article_templates")
    categories = list(templates.keys())
    macro = macro_context or await _build_macro_context(redis)
    company_lines = "\n".join(
        f"- {company['name']} ({company['ticker']}) — ngành {company['industry']}"
        for company in companies
    )

    articles: list[ScenarioArticle] = []
    for index in range(count):
        category = categories[index % len(categories)]
        try:
            if ctx["gemini"].available:
                article = await _gemini_scenario(
                    ctx, category, macro, company_lines
                )
            else:
                raise GeminiUnavailableError("Chưa có GEMINI_API_KEY")
        except GeminiError as exc:
            logger.warning(
                "Scenario fallback deterministic (%s): %s", category, exc
            )
            article = _fallback_scenario(
                store, templates, category, companies, macro, index
            )
        articles.append(article)

    logger.info("generate_scenario_batch: đã sinh %d bài", len(articles))
    return [article.model_dump(mode="json") for article in articles]


async def _gemini_scenario(
    ctx: dict[str, Any],
    category: str,
    macro: str,
    companies_text: str,
) -> ScenarioArticle:
    """Gọi Gemini (có rate limit) sinh MỘT bài đúng category."""
    store: PromptStore = ctx["store"]
    await ctx["rate_limiter"].acquire()
    prompt = store.render_template(
        SCENARIO_PROMPT_FILE,
        "user_prompt",
        macro_context=macro,
        real_news="(không có nguồn tin tham khảo phù hợp)",
        companies=companies_text,
        instructions=f"Viết ĐÚNG MỘT bài thuộc category: {category}.",
        article_count=1,
    )
    article = await asyncio.to_thread(
        ctx["gemini"].generate_structured,
        ScenarioArticle,
        system_instruction=store.require(SCENARIO_PROMPT_FILE, "system_prompt"),
        user_content=prompt,
    )
    if article.category != category:
        article = article.model_copy(update={"category": category})
    return article


def _fallback_scenario(
    store: PromptStore,
    templates: dict[str, Any],
    category: str,
    companies: list[dict[str, Any]],
    macro: str,
    index: int,
) -> ScenarioArticle:
    """Sinh bài từ template YAML (0 token), deterministic theo chỉ số."""
    company = companies[index % len(companies)]
    template = templates[category]
    rendered = store.render_value(
        template,
        company=company["name"],
        ticker=company["ticker"],
        industry=company["industry"],
        context=macro,
    )
    return ScenarioArticle(**rendered)


async def _build_macro_context(redis: Any) -> str:
    """Dựng bối cảnh vĩ mô từ tin cào được gần nhất."""
    from tasks.crawl_tasks import latest_news

    articles = await latest_news(redis, limit=5)
    if not articles:
        return (
            "Thị trường mô phỏng đang trong giai đoạn biến động bình thường; "
            "không có sự kiện nổi bật gần nhất."
        )
    lines = [f"- {article['title']}" for article in articles]
    return "Sự kiện thị trường gần nhất:\n" + "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────
# Social posts
# ────────────────────────────────────────────────────────────────────────────
async def generate_social_posts(
    ctx: dict[str, Any],
    *,
    persona_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Sinh bài đăng cho 10 Persona (hoặc subset được chỉ định)."""
    store: PromptStore = ctx["store"]
    personas = store.require(SOCIAL_PROMPT_FILE, "personas")
    fallback_templates = store.require(SOCIAL_PROMPT_FILE, "fallback", "templates")

    ids = list(personas.keys()) if not persona_ids else [
        pid for pid in persona_ids if pid in personas
    ]
    if not ids:
        return []

    companies = store.require(SCENARIO_PROMPT_FILE, "fallback", "companies")
    company = companies[0]
    macro = await _build_macro_context(ctx["redis"])
    company_text = f"{company['name']} ({company['ticker']}) — ngành {company['industry']}"

    posts: list[SocialPost] = []
    for persona_id in ids:
        persona = personas[persona_id]
        try:
            if ctx["gemini"].available:
                post = await _gemini_social(ctx, persona, company_text, macro)
            else:
                raise GeminiUnavailableError("Chưa có GEMINI_API_KEY")
        except GeminiError as exc:
            logger.warning(
                "Social fallback deterministic (%s): %s", persona_id, exc
            )
            post = _fallback_social(store, persona, fallback_templates, company, macro)
        posts.append(post)

    logger.info("generate_social_posts: đã sinh %d bài cho %d persona", len(posts), len(ids))
    return [post.model_dump(mode="json") for post in posts]


async def _gemini_social(
    ctx: dict[str, Any],
    persona: dict[str, Any],
    company_text: str,
    macro: str,
) -> SocialPost:
    """Gọi Gemini (có rate limit) sinh bài đăng cho một persona."""
    store: PromptStore = ctx["store"]
    await ctx["rate_limiter"].acquire()
    persona_description = "\n".join(
        f"- {key}: {value}"
        for key, value in persona.items()
        if key not in {"example_topics"}
    )
    prompt = store.render_template(
        SOCIAL_PROMPT_FILE,
        "user_prompt",
        persona_description=persona_description,
        market_context=macro,
        companies=company_text,
        instructions="Viết đúng giọng của persona, không thêm công ty ngoài danh sách.",
    )
    post = await asyncio.to_thread(
        ctx["gemini"].generate_structured,
        SocialPost,
        system_instruction=store.require(SOCIAL_PROMPT_FILE, "system_prompt"),
        user_content=prompt,
    )
    if post.persona_id != persona["id"]:
        post = post.model_copy(update={"persona_id": persona["id"]})
    allowed = persona.get("sentiment_range") or ["neutral"]
    if post.sentiment not in allowed:
        post = post.model_copy(update={"sentiment": allowed[0]})
    return post


def _fallback_social(
    store: PromptStore,
    persona: dict[str, Any],
    templates: dict[str, list[str]],
    company: dict[str, Any],
    macro: str,
) -> SocialPost:
    """Sinh bài từ template YAML (0 token), deterministic theo persona id."""
    persona_id = persona["id"]
    candidates = templates.get(persona_id) or []
    rng = random.Random(persona_id)
    template = (
        candidates[rng.randrange(len(candidates))]
        if candidates
        else "(persona chưa có mẫu fallback)"
    )
    content = store.render(
        template,
        ticker=company["ticker"],
        company=company["name"],
        market_context=macro,
    )
    sentiment = persona["sentiment_range"][
        rng.randrange(len(persona["sentiment_range"]))
    ]
    virality = min(10, int(persona.get("emotional_strength", 3)) + 2)
    red_flags = persona.get("red_flags") or []
    return SocialPost(
        persona_id=persona_id,
        content=content,
        sentiment=sentiment,
        virality_score=virality,
        tags=list(persona.get("example_topics", []))[:3],
        has_deception=bool(red_flags),
        deception_note=(
            "Mẫu fallback chứa dấu hiệu nhiễu theo mô tả persona" if red_flags else ""
        ),
    )
