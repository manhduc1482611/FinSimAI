"""Tests cho endpoint POST /api/v1/mentor (ai-engine-api).

Trọng tâm: ưu tiên deterministic (0 token); Gemini chỉ dùng khi có key + rate
limit; mọi lỗi quota/mạng → tự rơi về deterministic.
"""

from typing import Any

import httpx
import pytest

from agents.policy import scan_policy
from agents.socratic_mentor import SocraticFocus, SocraticReply
from integrations.rate_limiter import RateLimitExceeded
from main_ai import app


class FakeGemini:
    available = True
    # Tương thích với GeminiClient.mentor_model / fast_model (model routing).
    mentor_model = "fake-pro"
    fast_model = "fake-flash"

    def __init__(self, reply: SocraticReply) -> None:
        self.reply = reply

    def generate_structured(
        self,
        model_type: Any,
        *,
        system_instruction: str,
        user_content: str,
        validator: Any = None,
        **kwargs: Any,
    ) -> SocraticReply:
        if validator is not None:
            validator(self.reply)
        return self.reply


class FakeLimiter:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def acquire(self) -> None:
        if self.error is not None:
            raise self.error


async def _post(payload: dict[str, Any]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/mentor", json=payload)


async def test_mentor_api_deterministic_without_key() -> None:
    """Không có GEMINI_API_KEY (conftest) → phản hồi deterministic, 0 token."""
    resp = await _post(
        {
            "user_id": "u1",
            "message": "Mọi người đều bảo ACB sắp sốt, tôi sợ bỏ lỡ",
            "session_id": "s1",
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "deterministic"
    assert data["focus"] in {f.value for f in SocraticFocus}
    assert data["questions"]
    for question in data["questions"]:
        assert question.endswith("?")
    assert data["disclaimer"]
    # Nguyên tắc tuyệt đối: không lời khuyên mua/bán, không phán xét đúng/sai.
    joined = " ".join([*data["questions"], data["coaching_tip"]])
    assert scan_policy(joined) == []


async def test_mentor_api_llm_path_used_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Có key + rate limiter cho phép → dùng Gemini, source = llm."""
    import routers.mentor as mentor_router

    reply = SocraticReply(
        focus=SocraticFocus.PROCESS,
        questions=["Bạn đã xác định giới hạn chịu lỗ trước khi quyết định chưa?"],
        coaching_tip="Viết ra 3 kịch bản có thể xảy ra.",
    )
    agent = mentor_router._get_agent()
    monkeypatch.setattr(mentor_router, "_get_agent", lambda: agent)
    agent.gemini = FakeGemini(reply)  # type: ignore[assignment]
    monkeypatch.setattr(mentor_router, "_get_limiter_pro", lambda: FakeLimiter())

    resp = await _post({"user_id": "u1", "message": "Tôi muốn kiểm tra quy trình của mình"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "llm"
    assert data["questions"] == reply.questions


async def test_mentor_api_falls_back_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hết token rate limit → KHÔNG gọi Gemini, dùng deterministic."""
    import routers.mentor as mentor_router

    calls: list[str] = []

    class CountingGemini(FakeGemini):
        def generate_structured(self, model_type: Any, **kwargs: Any) -> SocraticReply:
            calls.append("llm")
            return super().generate_structured(model_type, **kwargs)

    agent = mentor_router._get_agent()
    monkeypatch.setattr(mentor_router, "_get_agent", lambda: agent)
    agent.gemini = CountingGemini(  # type: ignore[assignment]
        SocraticReply(
            focus=SocraticFocus.PROCESS,
            questions=["Câu hỏi test?"],
            coaching_tip="Bài tập test.",
        )
    )
    monkeypatch.setattr(
        mentor_router,
        "_get_limiter_pro",
        lambda: FakeLimiter(error=RateLimitExceeded("gemini", 10)),
    )

    resp = await _post({"user_id": "u1", "message": "Tôi muốn mua cổ phiếu"})
    assert resp.status_code == 200
    assert resp.json()["source"] == "deterministic"
    assert calls == []


async def test_mentor_api_rejects_empty_message() -> None:
    resp = await _post({"user_id": "u1", "message": "   "})
    assert resp.status_code == 422


async def test_mentor_api_rejects_overlong_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    resp = await _post({"user_id": "u1", "message": "x" * 2001})
    assert resp.status_code == 422


# ─── Auth nội bộ (shared secret): route mentor đốt quota Gemini ─────────────
async def _post_with_headers(
    payload: dict[str, Any], headers: dict[str, str]
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/mentor", json=payload, headers=headers)


async def test_mentor_api_requires_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    resp = await _post({"user_id": "u1", "message": "Tôi muốn kiểm tra quy trình"})
    assert resp.status_code == 403


async def test_mentor_api_accepts_correct_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    resp = await _post_with_headers(
        {"user_id": "u1", "message": "Tôi muốn kiểm tra quy trình"},
        {"X-Internal-Api-Key": "s3cret-internal"},
    )
    assert resp.status_code == 200


async def test_mentor_api_rejects_wrong_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    resp = await _post_with_headers(
        {"user_id": "u1", "message": "Tôi muốn kiểm tra quy trình"},
        {"X-Internal-Api-Key": "wrong"},
    )
    assert resp.status_code == 403


async def test_mentor_api_production_without_key_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    resp = await _post({"user_id": "u1", "message": "Tôi muốn kiểm tra quy trình"})
    assert resp.status_code == 503
