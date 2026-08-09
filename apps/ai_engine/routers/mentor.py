"""Mentor API — endpoint HTTP cho Socratic Mentor (ai-engine-api).

Gemini chỉ được gọi khi có ``GEMINI_API_KEY`` VÀ giành được token rate limit
(token bucket phân tán qua Redis, cấu hình ``GEMINI_RATE_LIMIT_RPM/BURST/...``).
Thiếu key / hết token / Redis lỗi / mạng lỗi → phản hồi deterministic question-bank
(0 token). Kết quả LUÔN là JSON hợp lệ kèm trường ``source`` = "llm" | "deterministic"
để phía tiêu thụ biết mình nhận phản hồi từ nguồn nào.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

import redis.asyncio as redis_ai
from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from agents.socratic_mentor import MentorContext, SocraticMentorAgent, SocraticReply
from integrations.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["mentor"])


class MentorContextPayload(BaseModel):
    company: str | None = None
    market_context: str = ""
    portfolio: str = ""


class MentorRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    session_id: str = ""
    context: MentorContextPayload | None = None
    history: list[dict[str, Any]] | None = None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message không được trống")
        return stripped


class MentorResponse(SocraticReply):
    source: Literal["llm", "deterministic"]


_agent: SocraticMentorAgent | None = None
_redis_client: Any | None = None


def _get_agent() -> SocraticMentorAgent:
    """Agent dùng chung (nạp prompt YAML 1 lần)."""
    global _agent
    if _agent is None:
        _agent = SocraticMentorAgent()
    return _agent


def _get_redis() -> Any:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis_ai.from_url(url)  # type: ignore[no-untyped-call]
    return _redis_client


def _get_limiter() -> RedisRateLimiter:
    redis = _get_redis()
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


def _to_context(payload: MentorContextPayload | None) -> MentorContext:
    if payload is None:
        return MentorContext()
    return MentorContext(
        company=payload.company,
        market_context=payload.market_context,
        portfolio=payload.portfolio,
    )


@router.post("/mentor", response_model=MentorResponse)
async def mentor(payload: MentorRequest) -> MentorResponse:
    """Phản hồi Socratic cho tin nhắn; ưu tiên deterministic (0 token)."""
    agent = _get_agent()
    ctx = _to_context(payload.context)

    if agent.gemini.available:
        try:
            await _get_limiter().acquire()
            prompt = agent.store.render_template(
                agent.prompt_file,
                "user_prompt",
                context=ctx.to_text(),
                history=agent._format_history(payload.history),
                user_message=payload.message,
            )
            reply = agent.gemini.generate_structured(
                SocraticReply,
                system_instruction=agent._require_prompt("system_prompt"),
                user_content=prompt,
            )
            return MentorResponse(**reply.model_dump(), source="llm")
        except Exception as exc:  # noqa: BLE001 - quota/mạng → deterministic
            logger.warning("Mentor LLM thất bại, dùng deterministic: %s", exc)

    reply = agent._fallback(payload.message, ctx)
    return MentorResponse(**reply.model_dump(), source="deterministic")
