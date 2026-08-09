"""HTTP client tới AI Engine cho Mentor (tuỳ chọn, giới hạn lượt Gemini).

Chỉ được gọi khi ``MENTOR_LLM_MODE=on``. Mọi lỗi (ai_engine down, timeout,
quota rate limit ở phía ai_engine) → trả ``None`` để HybridMentorStream rơi về
deterministic question-bank (0 token) — người chơi không bao giờ mất phản hồi.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from core.config import settings

logger = logging.getLogger(__name__)


class MentorClient:
    """HTTP client tới ai-engine-api (web service) cho Socratic Mentor."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.ai_engine_url.rstrip("/"),
                timeout=httpx.Timeout(
                    connect=2.0,
                    read=settings.ai_engine_timeout_seconds,
                    write=10.0,
                    pool=2.0,
                ),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("AI engine mentor client closed")

    async def ask(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        """Gọi Mentor của ai_engine; trả phản hồi, hoặc ``None`` khi thất bại."""
        payload: dict[str, Any] = {
            "user_id": user_id,
            "message": message,
            "session_id": session_id,
        }
        if history:
            payload["history"] = history
        try:
            client = await self._ensure_client()
            resp = await client.post(
                "/api/v1/mentor",
                json=payload,
                timeout=settings.ai_engine_timeout_seconds,
            )
            resp.raise_for_status()
            return dict(resp.json())
        except Exception:  # noqa: BLE001 - fail-closed: rơi về deterministic
            logger.warning("ai_engine mentor call failed — dùng deterministic", exc_info=True)
            return None


mentor_client = MentorClient()
