"""Task cào tin tức RSS — chạy định kỳ qua ARQ.

- ``crawl_news``: fetch các nguồn RSS (mặc định danh sách đã kiểm chứng),
  parse, lọc trùng qua Redis, lưu bài MỚI vào danh sách ``news:latest``
  (giới hạn số bài gần nhất) để các task khác dùng làm bối cảnh.
- Chống trùng: ``SET news:seen:{url-hash} NX EX <ttl>`` — bài nào thêm được
  vào set mới được coi là mới.
- KHÔNG phụ thuộc Gemini → luôn chạy được dù chưa có API key.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from integrations.news_sources import (
    FeedConfig,
    NewsArticle,
    NewsSource,
    NewsSourceError,
    dedupe_articles,
    default_feed_config,
    fetch_source_with_retry,
)

logger = logging.getLogger(__name__)

SEEN_TTL_SECONDS = 30 * 24 * 3600  # 30 ngày
LATEST_KEY = "news:latest"
LATEST_MAX = 200
SEEN_PREFIX = "news:seen:"


async def crawl_news(
    ctx: dict[str, Any],
    *,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Cào mọi nguồn (hoặc nguồn chỉ định), lưu bài mới; trả về thống kê."""
    redis = ctx["redis"]
    config: FeedConfig = ctx.get("feed_config") or default_feed_config()

    sources = [source for source in config.sources if source.enabled]
    if source_ids:
        wanted = set(source_ids)
        sources = [source for source in sources if source.id in wanted]
    if not sources:
        return {"sources": [], "total": 0, "new": 0, "errors": 0, "error_details": []}

    semaphore = asyncio.Semaphore(config.max_concurrent)

    async def _fetch_one(source: NewsSource) -> tuple[str, list[NewsArticle], str | None]:
        async with semaphore:
            try:
                articles = await fetch_source_with_retry(
                    source,
                    retries=config.retries,
                    base_delay=config.base_delay,
                )
                return source.id, articles[: config.max_articles_per_source], None
            except NewsSourceError as exc:
                return source.id, [], str(exc)

    results = await asyncio.gather(*(_fetch_one(source) for source in sources))

    new_articles: list[NewsArticle] = []
    error_details: list[str] = []
    total = 0
    for source_id, articles, error in results:
        if error:
            error_details.append(error)
            continue
        total += len(articles)
        for article in articles:
            digest = hashlib.sha1(article.url.encode("utf-8")).hexdigest()
            added = await redis.set(
                f"{SEEN_PREFIX}{digest}", "1", nx=True, ex=SEEN_TTL_SECONDS
            )
            if added:
                new_articles.append(article)

    new_articles = dedupe_articles(new_articles)
    if new_articles:
        async with redis.pipeline() as pipe:
            for article in new_articles:
                pipe.rpush(LATEST_KEY, json.dumps(article.to_dict(), ensure_ascii=False))
            pipe.ltrim(LATEST_KEY, -LATEST_MAX, -1)
            await pipe.execute()

    logger.info(
        "crawl_news: %d nguồn, %d bài mới (tổng %d), %d lỗi",
        len(sources),
        len(new_articles),
        total,
        len(error_details),
    )
    return {
        "sources": [source.id for source in sources],
        "total": total,
        "new": len(new_articles),
        "errors": len(error_details),
        "error_details": error_details,
    }


async def latest_news(redis: Any, limit: int = 10) -> list[dict[str, Any]]:
    """Đọc các bài gần nhất (mới nhất trước) để dùng làm bối cảnh."""
    items = await redis.lrange(LATEST_KEY, -limit, -1)
    parsed: list[dict[str, Any]] = []
    for raw in items:
        try:
            parsed.append(json.loads(raw))
        except (TypeError, json.JSONDecodeError):
            continue
    parsed.reverse()
    return parsed
