"""Tests cho deterministic Socratic Mentor Engine + Hybrid stream (gateway).

Trọng tâm: Mentor chạy deterministic question-bank (0 token Gemini) làm chính;
Gemini chỉ được dùng khi bật MENTOR_LLM_MODE=on + AI_ENGINE_URL; mọi lỗi → tự
rơi về deterministic.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from core.config import settings
from realtime.mentor_engine import (
    SocraticFocus,
    detect_focus,
    reply_to_text,
    socratic_reply,
)
from realtime.mentor_ws import DeterministicMentorStream, HybridMentorStream

_FORBIDDEN_ADVICE = ("nên mua", "hãy mua", "nên bán", "hãy bán", "chốt lời ngay", "cắt lỗ ngay")


async def _collect(stream: AsyncIterator[str]) -> str:
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return "".join(chunks)


class FakeMentorClient:
    def __init__(self, reply: dict[str, Any] | None = None) -> None:
        self.reply = reply
        self.calls = 0

    async def ask(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls += 1
        return self.reply


def test_detect_focus_fomo() -> None:
    assert detect_focus("sợ bỏ lỡ cơn sốt ACB") == SocraticFocus.FOMO


def test_detect_focus_herding() -> None:
    assert detect_focus("mọi người đều mua") == SocraticFocus.HERDING


def test_detect_focus_unknown_is_process() -> None:
    assert detect_focus("xin chào") == SocraticFocus.PROCESS


def test_socratic_reply_structure() -> None:
    reply = socratic_reply("tôi sợ bỏ lỡ cơn sóng mới")
    assert reply.focus == SocraticFocus.FOMO
    assert len(reply.questions) == 3
    for question in reply.questions:
        assert question.endswith("?")
    assert reply.disclaimer
    assert reply.coaching_tip


def test_socratic_reply_never_gives_advice() -> None:
    reply = socratic_reply("Tôi muốn mua ACB ngay bây giờ kẻo hết")
    joined = " ".join([*reply.questions, reply.coaching_tip]).lower()
    for phrase in _FORBIDDEN_ADVICE:
        assert phrase not in joined


def test_reply_to_text_includes_all_parts() -> None:
    reply = socratic_reply("chào")
    text = reply_to_text(reply)
    assert reply.questions[0] in text
    assert "Bài tập:" in text
    assert reply.disclaimer in text


@pytest.mark.asyncio
async def test_deterministic_stream_chunks_full_reply() -> None:
    expected = reply_to_text(socratic_reply("hello"))
    stream = DeterministicMentorStream()
    got = await _collect(stream.stream(user_id="1", message="hello", session_id="s"))
    assert got == expected


@pytest.mark.asyncio
async def test_hybrid_default_is_deterministic() -> None:
    # Mặc định MENTOR_LLM_MODE=off, AI_ENGINE_URL="" → 0 token Gemini.
    client = FakeMentorClient()
    stream = HybridMentorStream(client=client)
    assert stream.llm_enabled is False
    got = await _collect(stream.stream(user_id="1", message="hello", session_id="s"))
    assert got == reply_to_text(socratic_reply("hello"))
    assert client.calls == 0


@pytest.mark.asyncio
async def test_hybrid_requires_url_even_in_llm_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mentor_llm_mode", "on")
    monkeypatch.setattr(settings, "ai_engine_url", "")
    stream = HybridMentorStream(client=FakeMentorClient())
    assert stream.llm_enabled is False


@pytest.mark.asyncio
async def test_hybrid_uses_llm_reply_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mentor_llm_mode", "on")
    monkeypatch.setattr(settings, "ai_engine_url", "http://ai-engine:8000")
    reply = {
        "questions": ["Câu hỏi A?"],
        "coaching_tip": "Bài tập B",
        "disclaimer": "Cảnh báo C",
    }
    client = FakeMentorClient(reply=reply)
    stream = HybridMentorStream(client=client)
    assert stream.llm_enabled is True

    got = await _collect(stream.stream(user_id="1", message="hello", session_id="s"))
    assert got == "Câu hỏi A?\n\nBài tập: Bài tập B\n\nCảnh báo C"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_hybrid_falls_back_when_client_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mentor_llm_mode", "on")
    monkeypatch.setattr(settings, "ai_engine_url", "http://ai-engine:8000")
    client = FakeMentorClient(reply=None)
    stream = HybridMentorStream(client=client)

    got = await _collect(stream.stream(user_id="1", message="hello", session_id="s"))
    assert got == reply_to_text(socratic_reply("hello"))
    assert client.calls == 1
