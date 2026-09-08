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

from agents.intent import IntentClassifier, IntentResult
from agents.socratic_mentor import (
    ConceptReply,
    MentorContext,
    SocraticMentorAgent,
    SocraticReply,
    StrategyReply,
)
from integrations.rate_limiter import RedisRateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["mentor"])


class MentorContextPayload(BaseModel):
    company: str | None = None
    market_context: str = ""
    portfolio: str = ""
    risk_profile: str | None = None
    investment_horizon: str | None = None
    experience: str | None = None
    capital_scale: str | None = None


class TradeSnapshotPayload(BaseModel):
    """Snapshot do gateway gửi — dữ liệu SERVER (không tin client)."""

    selected_symbol: str | None = None
    cash_balance: float | None = None
    total_nav: float | None = None
    holdings: list[dict[str, Any]] = []
    open_orders: list[dict[str, Any]] = []
    current_price: float | None = None
    risk_flags: list[str] = []


class MentorRequest(BaseModel):
    user_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    session_id: str = ""
    context: MentorContextPayload | None = None
    history: list[dict[str, Any]] | None = None
    mode: Literal["concept", "plan", "trade_now", "socratic"] = "socratic"
    selected_symbol: str | None = None
    trade_snapshot: TradeSnapshotPayload | None = None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message không được trống")
        return stripped


class MentorResponse(SocraticReply):
    source: Literal["llm", "deterministic"]


class ConceptResponse(ConceptReply):
    source: Literal["llm", "deterministic"]


class StrategyResponse(StrategyReply):
    source: Literal["llm", "deterministic"]


_agent: SocraticMentorAgent | None = None
_redis_client: Any | None = None
_classifier: IntentClassifier | None = None


def _get_agent() -> SocraticMentorAgent:
    """Agent dùng chung (nạp prompt YAML 1 lần)."""
    global _agent
    if _agent is None:
        _agent = SocraticMentorAgent()
    return _agent


def _get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


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
            reply = agent.llm_reply(payload.message, ctx, payload.history)
            return MentorResponse(**reply.model_dump(), source="llm")
        except Exception as exc:  # noqa: BLE001 - quota/mạng/judge → deterministic
            logger.warning("Mentor LLM thất bại, dùng deterministic: %s", exc)

    reply = agent._fallback(payload.message, ctx)
    return MentorResponse(**reply.model_dump(), source="deterministic")


@router.post("/mentor/concept", response_model=ConceptResponse)
async def mentor_concept(payload: MentorRequest) -> ConceptResponse:
    """Chế độ 1: giải thích khái niệm — glossary deterministic, LLM mở rộng."""
    agent = _get_agent()
    ctx = _to_context(payload.context)
    reply: ConceptReply
    source: Literal["llm", "deterministic"] = "deterministic"
    if agent.gemini.available:
        try:
            await _get_limiter().acquire()
            reply = agent.llm_concept(payload.message, ctx)
            source = "llm"
        except Exception as exc:  # noqa: BLE001 - fallback deterministic
            logger.warning("Concept LLM thất bại, dùng glossary: %s", exc)
            reply = agent.generate_concept(payload.message, ctx)
    else:
        reply = agent.generate_concept(payload.message, ctx)
    return ConceptResponse(**reply.model_dump(), source=source)


@router.post("/mentor/strategy", response_model=StrategyResponse)
async def mentor_strategy(payload: MentorRequest) -> StrategyResponse:
    """Chế độ 2: khung chiến lược — khóa cứng framework bank (docs v2.0, mục 4.2)."""
    agent = _get_agent()
    ctx = _to_context(payload.context)
    reply: StrategyReply
    source: Literal["llm", "deterministic"] = "deterministic"
    if agent.gemini.available:
        try:
            await _get_limiter().acquire()
            llm = agent.llm_strategy(payload.message, ctx)
        except Exception as exc:  # noqa: BLE001 - fallback deterministic
            logger.warning("Strategy LLM thất bại, dùng bank: %s", exc)
            llm = None
        if llm is not None and agent._matches_bank(llm):
            reply = llm
            source = "llm"
        else:
            reply = agent.generate_strategy(payload.message, ctx)
    else:
        reply = agent.generate_strategy(payload.message, ctx)
    return StrategyResponse(**reply.model_dump(), source=source)
