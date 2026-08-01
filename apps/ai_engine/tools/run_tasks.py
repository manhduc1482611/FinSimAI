"""CLI thao tác task queue ARQ — độc lập với worker đang chạy.

Dòng lệnh (từ thư mục ``apps/ai_engine`` hoặc dùng đường dẫn đầy đủ):
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py redis-info
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py crawl --wait
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py scenario --count 5 --wait
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py social --wait
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py latest-news --limit 5
    .venv\\Scripts\\python apps/ai_engine/tools/run_tasks.py result <job_id>

- ``--wait``: đợi kết quả job (worker phải đang chạy) rồi in ra.
- ``--sync``: chạy task TRỰC TIẾP trong tiến trình này (không cần worker),
  hữu ích để kiểm thử nhanh; cần Redis để lưu trạng thái.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arq

from integrations.news_sources import default_feed_config


def _redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def _redis_settings() -> arq.connections.RedisSettings:
    return arq.connections.RedisSettings.from_dsn(_redis_url())


async def _redis_info() -> None:
    pool = await arq.create_pool(_redis_settings())
    try:
        await pool.ping()
        info = await pool.info("server")
        key_count = await pool.dbsize()
        print(f"Redis OK — v{info.get('redis_version', '?')}, {key_count} keys")
    finally:
        await pool.close(close_connection_pool=True)


async def _enqueue_and_wait(
    function: str,
    *,
    wait: bool,
    **kwargs: Any,
) -> None:
    pool = await arq.create_pool(_redis_settings())
    try:
        job = await pool.enqueue_job(function, **kwargs)
        print(f"Đã đưa job {function} vào queue — job_id={job.job_id}")
        if wait:
            result = await job.result(timeout=180)
            print(f"── KẾT QUẢ {function} ──")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await pool.close(close_connection_pool=True)


async def _latest_news(limit: int) -> None:
    pool = await arq.create_pool(_redis_settings())
    try:
        from tasks.crawl_tasks import latest_news

        items = await latest_news(pool, limit=limit)
        print(f"Có {len(items)} bài gần nhất:")
        for item in items:
            print(f"- [{item['source_name']}] {item['title']} ({item['published_at']})")
    finally:
        await pool.close(close_connection_pool=True)


async def _result(job_id: str) -> None:
    pool = await arq.create_pool(_redis_settings())
    try:
        job = arq.jobs.Job(job_id, pool)
        result = await job.result(timeout=1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except TimeoutError:
        print("Job chưa có kết quả (đang chờ trong queue hoặc bị bỏ).")
    finally:
        await pool.close(close_connection_pool=True)


async def _sync_direct(function: str, **kwargs: Any) -> None:
    """Chạy task trực tiếp (không qua worker) — cần Redis cho trạng thái."""
    from integrations.gemini import GeminiClient
    from integrations.rate_limiter import RedisRateLimiter
    from prompts.loader import PromptStore
    from tasks.crawl_tasks import crawl_news
    from tasks.scenario_tasks import generate_scenario_batch, generate_social_posts

    tasks = {
        "crawl_news": crawl_news,
        "generate_scenario_batch": generate_scenario_batch,
        "generate_social_posts": generate_social_posts,
    }
    func = tasks[function]
    pool = await arq.create_pool(_redis_settings())
    try:
        ctx: dict[str, Any] = {
            "redis": pool,
            "store": PromptStore(),
            "gemini": GeminiClient(),
            "rate_limiter": RedisRateLimiter(pool),
            "feed_config": default_feed_config(),
        }
        result = await func(ctx, **kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await pool.close(close_connection_pool=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FinSimAI Task Queue CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("redis-info", help="Kiểm tra kết nối Redis")

    p = sub.add_parser("crawl", help="Cào tin RSS")
    p.add_argument("--sources", default=None, help="Danh sách source_id cách dấu phẩy")
    p.add_argument("--wait", action="store_true", help="Đợi kết quả job")
    p.add_argument("--sync", action="store_true", help="Chạy trực tiếp (không cần worker)")

    p = sub.add_parser("scenario", help="Sinh bài báo giả lập")
    p.add_argument("--count", type=int, default=5)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--sync", action="store_true")

    p = sub.add_parser("social", help="Sinh bài MXH cho personas")
    p.add_argument("--personas", default=None, help="Danh sách persona_id cách dấu phẩy")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--sync", action="store_true")

    p = sub.add_parser("latest-news", help="Đọc bài tin gần nhất")
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("result", help="Xem kết quả job theo job_id")
    p.add_argument("job_id")

    args = parser.parse_args(argv)

    if args.command == "redis-info":
        asyncio.run(_redis_info())
        return 0
    if args.command == "latest-news":
        asyncio.run(_latest_news(args.limit))
        return 0
    if args.command == "result":
        asyncio.run(_result(args.job_id))
        return 0

    if args.command == "crawl":
        sources = args.sources.split(",") if args.sources else None
        if args.sync:
            asyncio.run(_sync_direct("crawl_news", source_ids=sources))
        else:
            asyncio.run(_enqueue_and_wait("crawl_news", wait=args.wait, source_ids=sources))
        return 0
    if args.command == "scenario":
        if args.sync:
            asyncio.run(_sync_direct("generate_scenario_batch", count=args.count))
        else:
            asyncio.run(_enqueue_and_wait("generate_scenario_batch", wait=args.wait, count=args.count))
        return 0
    if args.command == "social":
        personas = args.personas.split(",") if args.personas else None
        if args.sync:
            asyncio.run(_sync_direct("generate_social_posts", persona_ids=personas))
        else:
            asyncio.run(_enqueue_and_wait("generate_social_posts", wait=args.wait, persona_ids=personas))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
