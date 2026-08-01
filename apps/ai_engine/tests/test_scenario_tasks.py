"""Test task sinh nội dung: fallback deterministic scenario + social 10 personas."""

import fakeredis.aioredis
import pytest

from integrations.gemini import GeminiClient
from integrations.rate_limiter import RedisRateLimiter
from prompts.loader import PromptStore
from tasks.scenario_tasks import (
    SCENARIO_PROMPT_FILE,
    SOCIAL_PROMPT_FILE,
    SocialPost,
    generate_scenario_batch,
    generate_social_posts,
)

CATEGORIES = {
    "macro_domestic",
    "macro_international",
    "industry",
    "company",
    "market_report",
}
SENTIMENTS = {"positive", "negative", "neutral"}


@pytest.fixture
def ctx():
    redis = fakeredis.aioredis.FakeRedis()
    return {
        "redis": redis,
        "store": PromptStore(),
        "gemini": GeminiClient(),
        "rate_limiter": RedisRateLimiter(redis, max_wait_seconds=0.1),
    }


class TestScenarioFallback:
    async def test_generates_count_articles(self, ctx):
        result = await generate_scenario_batch(ctx, count=5)
        assert len(result) == 5

    async def test_articles_are_valid(self, ctx):
        result = await generate_scenario_batch(ctx, count=5)
        for item in result:
            assert item["category"] in CATEGORIES
            assert item["sentiment"] in SENTIMENTS
            assert 1 <= item["impact_score"] <= 10
            assert item["is_fictional"] is True
            assert "[AI Generated]" in item["content"]
            assert item["title"].strip()
            assert item["summary"].strip()

    async def test_company_article_references_fake_company(self, ctx):
        companies = ctx["store"].require(SCENARIO_PROMPT_FILE, "fallback", "companies")
        names = {company["name"] for company in companies}
        result = await generate_scenario_batch(ctx, count=5)
        company_articles = [item for item in result if item["category"] == "company"]
        assert company_articles
        for item in company_articles:
            assert set(item["affected_companies"]) & names, "Bài company phải nhắc công ty giả lập"

    async def test_no_leftover_tokens(self, ctx):
        result = await generate_scenario_batch(ctx, count=5)
        for item in result:
            for field in ("title", "summary", "content"):
                assert ctx["store"].leftover_tokens(item[field]) == []

    async def test_deterministic(self, ctx):
        first = await generate_scenario_batch(ctx, count=5)
        second = await generate_scenario_batch(ctx, count=5)
        assert first == second


class TestSocialFallback:
    async def test_generates_all_10_personas(self, ctx):
        result = await generate_social_posts(ctx)
        assert len(result) == 10
        personas = ctx["store"].require(SOCIAL_PROMPT_FILE, "personas")
        assert {post["persona_id"] for post in result} == set(personas)

    async def test_posts_respect_persona(self, ctx):
        personas = ctx["store"].require(SOCIAL_PROMPT_FILE, "personas")
        result = await generate_social_posts(ctx)
        for post in result:
            persona = personas[post["persona_id"]]
            assert post["content"].strip()
            assert post["sentiment"] in persona["sentiment_range"]
            assert 1 <= post["virality_score"] <= 10
            assert post["has_deception"] == bool(persona.get("red_flags"))

    async def test_subset_personas(self, ctx):
        result = await generate_social_posts(ctx, persona_ids=["kol_ta_fa", "rumor_birds"])
        assert {post["persona_id"] for post in result} == {"kol_ta_fa", "rumor_birds"}

    async def test_deterministic(self, ctx):
        first = await generate_social_posts(ctx)
        second = await generate_social_posts(ctx)
        assert [post["content"] for post in first] == [post["content"] for post in second]
        assert [post["sentiment"] for post in first] == [post["sentiment"] for post in second]

    async def test_schema_valid(self, ctx):
        result = await generate_social_posts(ctx, persona_ids=["meme_entertain"])
        post = SocialPost.model_validate(result[0])
        assert post.persona_id == "meme_entertain"
