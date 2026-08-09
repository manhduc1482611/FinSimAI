"""Đồng bộ nội dung AI sinh ra lên Backend Gateway để persist vào Postgres.

- Gateway expose ``POST /api/v1/ai/content`` (bảo vệ bằng ``X-Internal-Api-Key``).
- Service này chỉ gửi khi cấu hình đủ ``BACKEND_GATEWAY_URL`` +
  ``INTERNAL_API_KEY`` (cùng key với gateway, đặt qua env). Thiếu cấu hình →
  no-op, không làm hỏng cron.
- Mọi lỗi (gateway down, timeout, 4xx/5xx) chỉ log cảnh báo — worker vẫn coi
  task là thành công; cron sau sẽ gửi bù (gateway dedupe theo title/content).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CONTENT_SYNC_TIMEOUT_SECONDS = 5.0


def _sync_config() -> tuple[str, str] | None:
    url = os.environ.get("BACKEND_GATEWAY_URL", "").strip().rstrip("/")
    key = os.environ.get("INTERNAL_API_KEY", "").strip()
    if not url or not key:
        return None
    return url, key


async def sync_content(
    articles: list[dict[str, Any]] | None = None,
    social_posts: list[dict[str, Any]] | None = None,
) -> None:
    """Gửi batch nội dung mới nhất lên gateway. No-op khi chưa cấu hình."""
    config = _sync_config()
    if config is None:
        return
    articles = articles or []
    social_posts = social_posts or []
    if not articles and not social_posts:
        return

    url, key = config
    payload = {"articles": articles, "social_posts": social_posts}
    try:
        async with httpx.AsyncClient(timeout=CONTENT_SYNC_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{url}/api/v1/ai/content",
                json=payload,
                headers={"X-Internal-Api-Key": key},
            )
            resp.raise_for_status()
        logger.info(
            "Content sync OK: %d articles, %d social posts",
            len(articles),
            len(social_posts),
        )
    except Exception as exc:  # noqa: BLE001 - best-effort, không crash cron
        logger.warning(
            "Content sync failed (gateway %s): %s — sẽ gửi lại ở cron sau",
            url,
            exc,
        )
