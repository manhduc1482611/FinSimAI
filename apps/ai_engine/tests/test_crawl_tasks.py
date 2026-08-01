"""Test task cào RSS: fetch giả lập, lọc trùng qua Redis, lưu news:latest."""

from datetime import UTC, datetime

import fakeredis.aioredis
import pytest

from integrations.news_sources import FeedConfig, NewsArticle, NewsSource
from tasks.crawl_tasks import crawl_news, latest_news

SOURCE = NewsSource(id="src1", name="Nguồn 1", url="https://example.com/rss")

SAMPLE_ARTICLES = [
    NewsArticle(
        source_id="src1",
        source_name="Nguồn 1",
        title="Tin A",
        url="https://example.com/a",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
        summary="Tóm tắt A",
    ),
    NewsArticle(
        source_id="src1",
        source_name="Nguồn 1",
        title="Tin B",
        url="https://example.com/b",
        published_at=datetime(2025, 1, 2, tzinfo=UTC),
        summary="Tóm tắt B",
    ),
]


@pytest.fixture
def ctx(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis()
    context = {"redis": redis, "feed_config": FeedConfig(sources=(SOURCE,))}
    return context


async def _inject_fetcher(ctx, articles, *, error=False):
    async def fake_fetch(source, *, retries, base_delay):
        if error:
            from integrations.news_sources import NewsSourceError

            raise NewsSourceError("lỗi giả lập")
        return articles

    import tasks.crawl_tasks as module

    module.fetch_source_with_retry = fake_fetch
    return ctx


async def test_crawl_stores_new_articles(ctx):
    await _inject_fetcher(ctx, SAMPLE_ARTICLES)
    result = await crawl_news(ctx)
    assert result["total"] == 2
    assert result["new"] == 2
    assert result["errors"] == 0

    latest = await latest_news(ctx["redis"], limit=10)
    assert [item["title"] for item in latest] == ["Tin B", "Tin A"]


async def test_crawl_does_not_duplicate_on_second_run(ctx):
    await _inject_fetcher(ctx, SAMPLE_ARTICLES)
    first = await crawl_news(ctx)
    second = await crawl_news(ctx)
    assert first["new"] == 2
    assert second["new"] == 0
    latest = await latest_news(ctx["redis"], limit=10)
    assert len(latest) == 2


async def test_crawl_reports_errors(ctx):
    await _inject_fetcher(ctx, [], error=True)
    result = await crawl_news(ctx)
    assert result["errors"] == 1
    assert result["new"] == 0
    assert any("lỗi giả lập" in detail for detail in result["error_details"])


async def test_crawl_source_filter(ctx):
    await _inject_fetcher(ctx, SAMPLE_ARTICLES)
    result = await crawl_news(ctx, source_ids=["khong_ton_tai"])
    assert result["sources"] == []
    assert result["new"] == 0
