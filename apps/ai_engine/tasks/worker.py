"""Async Task Worker (ARQ + Redis) của AI Engine.

Dòng lệnh:
    python -m tasks.worker --check        # kiểm tra kết nối Redis rồi thoát
    python -m tasks.worker                # chạy worker nền (có cron định kỳ)
    python -m tasks.worker --burst        # xử lý hết việc đang chờ rồi thoát
    python -m tasks.worker --debug        # bật log mức DEBUG

Cron mặc định (cấu hình trong :class:`WorkerSettings.cron_jobs`):
- ``crawl_news``: mỗi 30 phút.
- ``generate_scenario_batch``: mỗi 4 giờ (0h, 4h, 8h, 12h, 16h, 20h + 5 phút).
- ``generate_social_posts``: mỗi 2 giờ.

Cấu hình qua biến môi trường:
- ``REDIS_URL`` — DSN Redis (mặc định ``redis://localhost:6379/0``).
- ``GEMINI_RATE_LIMIT_RPM`` / ``GEMINI_RATE_LIMIT_BURST`` /
  ``GEMINI_RATE_LIMIT_MAX_WAIT_SECONDS`` — ngưỡng rate limit Gemini.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import ClassVar

import arq
from arq.connections import RedisSettings

from integrations.gemini import GeminiClient
from integrations.news_sources import default_feed_config
from integrations.rate_limiter import RedisRateLimiter
from prompts.loader import PromptStore
from tasks.crawl_tasks import crawl_news
from tasks.scenario_tasks import generate_scenario_batch, generate_social_posts

logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    return RedisSettings.from_dsn(url)


def _rate_limiter(redis: Any) -> RedisRateLimiter:
    capacity = int(os.environ.get("GEMINI_RATE_LIMIT_BURST", "5"))
    rpm = float(os.environ.get("GEMINI_RATE_LIMIT_RPM", "15"))
    max_wait = float(os.environ.get("GEMINI_RATE_LIMIT_MAX_WAIT_SECONDS", "90"))
    return RedisRateLimiter(
        redis,
        name="gemini",
        capacity=capacity,
        refill_per_sec=rpm / 60.0,
        max_wait_seconds=max_wait,
    )


async def _startup(ctx: dict[str, Any]) -> None:
    ctx["store"] = PromptStore()
    ctx["gemini"] = GeminiClient()
    ctx["rate_limiter"] = _rate_limiter(ctx["redis"])
    ctx["feed_config"] = default_feed_config()
    logger.info(
        "Worker khởi động: Gemini available=%s, rate limit=%s",
        ctx["gemini"].available,
        ctx["rate_limiter"].name,
    )


class WorkerSettings:
    """Cấu hình worker cho :func:`arq.run_worker`."""

    functions: ClassVar[list] = [crawl_news, generate_scenario_batch, generate_social_posts]
    cron_jobs: ClassVar[list] = [
        arq.cron(crawl_news, minute={0, 30}, run_at_startup=False),
        arq.cron(
            generate_scenario_batch,
            hour={0, 4, 8, 12, 16, 20},
            minute=5,
        ),
        arq.cron(
            generate_social_posts,
            hour={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22},
            minute=10,
        ),
    ]
    redis_settings = _redis_settings()
    on_startup = _startup
    max_jobs = 5
    job_timeout = 600
    keep_result = 3600
    log_results = True
    retry_jobs = True


def _burst_settings() -> type[WorkerSettings]:
    """Settings cho chế độ ``--burst``.

    ARQ đọc cấu hình qua ``settings_cls.__dict__`` (không kế thừa), nên phải
    copy toàn bộ attribute public của :class:`WorkerSettings` để worker burst
    vẫn giữ được ``functions``, ``on_startup``, rate limit, ... Cron tắt để
    burst chỉ xử lý việc đang chờ rồi thoát.
    """
    attrs = {
        key: value
        for key, value in WorkerSettings.__dict__.items()
        if not key.startswith("__")
    }
    attrs.update({"burst": True, "cron_jobs": []})
    return type("BurstWorkerSettings", (WorkerSettings,), attrs)


async def _check_redis() -> None:
    settings = _redis_settings()
    pool = await arq.create_pool(settings)
    try:
        await pool.ping()
        info = await pool.info("server")
        version = info.get("redis_version", "?")
        host = settings.host
        port = settings.port
        logger.info("Redis OK — %s:%s (v%s)", host, port, version)
    finally:
        await pool.close(close_connection_pool=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FinSimAI Async Task Worker")
    parser.add_argument("--check", action="store_true", help="Kiểm tra kết nối Redis rồi thoát")
    parser.add_argument("--burst", action="store_true", help="Xử lý hết việc đang chờ rồi thoát")
    parser.add_argument("--debug", action="store_true", help="Bật log mức DEBUG")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.check:
        asyncio.run(_check_redis())
        return 0

    if args.burst:
        settings = _burst_settings()
    else:
        settings = WorkerSettings

    arq.run_worker(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
