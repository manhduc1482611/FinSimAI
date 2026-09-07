"""Test đường ống llm_reply của SocraticMentorAgent: grounding validator +
LLM-as-judge với retry đúng một lần (improvement_plan A2.2, A2.3)."""

from typing import Any

import pytest

from agents import socratic_mentor as mentor_module
from agents.policy import PolicyViolationError
from agents.socratic_mentor import (
    MentorContext,
    SocraticFocus,
    SocraticMentorAgent,
    SocraticReply,
)
from integrations.gemini import GeminiError


class FakeGemini:
    """Client giả: trả lần lượt các reply dựng sẵn; gọi validator như client thật."""

    def __init__(self, replies: list[Any], error: GeminiError | None = None):
        self.replies = list(replies)
        self.error = error
        self.calls: list[str] = []
        self.available = True

    def generate_structured(self, model_type, *, user_content, validator=None, **_):
        self.calls.append(user_content)
        if self.replies:
            item = self.replies.pop(0)
            if isinstance(item, Exception):
                raise item
            if validator is not None:
                validator(item)
            return item
        raise self.error or PolicyViolationError(["hết reply dựng sẵn"])


def _reply(questions: list[str], tip: str = "Viết ra 3 kịch bản.") -> SocraticReply:
    return SocraticReply(
        focus=SocraticFocus.PROCESS,
        questions=questions,
        coaching_tip=tip,
    )


@pytest.fixture()
def judge_off(monkeypatch):
    monkeypatch.setattr(mentor_module, "judge_enabled", lambda: False)


class TestLlmReply:
    def test_happy_path_returns_reply(self, monkeypatch, judge_off):
        good = _reply(["Bạn dựa vào căn cứ nào?"])
        fake = FakeGemini([good])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]

        result = agent.llm_reply("Tôi định mua VCB", MentorContext(company="VCB"))

        assert result.questions == good.questions
        assert len(fake.calls) == 1

    def test_prompt_has_no_leftover_tokens(self, monkeypatch, judge_off):
        from prompts.loader import PromptStore

        seen: dict[str, str] = {}

        class SpyGemini(FakeGemini):
            def generate_structured(self, model_type, *, user_content, validator=None, **kw):
                seen["prompt"] = user_content
                return super().generate_structured(
                    model_type, user_content=user_content, validator=validator, **kw
                )

        agent = SocraticMentorAgent(gemini=SpyGemini([_reply(["q?"])]))  # type: ignore[arg-type]
        agent.llm_reply("Tôi định mua", None, [{"role": "user", "content": "chào"}])

        assert PromptStore.leftover_tokens(seen["prompt"]) == []

    def test_judge_block_then_pass(self, monkeypatch):
        monkeypatch.setenv("MENTOR_JUDGE_ENABLED", "true")
        bad = _reply(["Quyết định này là đúng đắn chứ?"])
        good = _reply(["Bạn xác nhận quyết định đó dựa trên dữ liệu nào?"])
        fake = FakeGemini([bad, good])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]

        verdicts = iter(
            [
                mentor_module.JudgeVerdict(violation=True, reason="phán xét đúng/sai"),
                mentor_module.JudgeVerdict(violation=False),
            ]
        )
        monkeypatch.setattr(
            mentor_module, "run_judge", lambda *a, **k: next(verdicts)
        )

        result = agent.llm_reply("tôi bán hết rồi", MentorContext())

        assert result.questions == good.questions
        assert len(fake.calls) == 2
        # Lần 2 phải chứa feedback từ judge.
        assert "JUDGE" in fake.calls[1]

    def test_judge_block_twice_raises_policy_error(self, monkeypatch):
        monkeypatch.setenv("MENTOR_JUDGE_ENABLED", "true")
        bad = _reply(["Quyết định này là đúng đắn chứ?"])
        fake = FakeGemini([bad, bad])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]

        verdict = mentor_module.JudgeVerdict(violation=True, reason="khuyên mua")
        monkeypatch.setattr(mentor_module, "run_judge", lambda *a, **k: verdict)

        with pytest.raises(PolicyViolationError):
            agent.llm_reply("tôi bán hết rồi", MentorContext())

    def test_judge_disabled_skips_layer(self, monkeypatch, judge_off):
        bad = _reply(["Quyết định này là đúng đắn chứ?"])
        fake = FakeGemini([bad])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]
        called = []
        monkeypatch.setattr(mentor_module, "run_judge", lambda *a, **k: called.append(1))

        result = agent.llm_reply("tôi bán hết rồi", MentorContext())

        assert result.questions == bad.questions
        assert called == []

    def test_grounding_violation_propagates(self, monkeypatch, judge_off):
        # Reply bịa giá không có trong ngữ cảnh → validator chặn ngay.
        invented = _reply(["Giá về 123456 thì sao?"])
        fake = FakeGemini([invented])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]

        with pytest.raises(PolicyViolationError):
            agent.llm_reply("nhận định đi", MentorContext())


class TestGenerateFallback:
    def test_generate_falls_back_when_llm_blocked(self, monkeypatch):
        bad = _reply(["Quyết định này là đúng đắn chứ?"])
        fake = FakeGemini([bad, bad])
        agent = SocraticMentorAgent(gemini=fake)  # type: ignore[arg-type]

        def _always_violate(*args: Any, **kwargs: Any):
            return mentor_module.JudgeVerdict(violation=True, reason="phán xét")

        monkeypatch.setattr(mentor_module, "run_judge", _always_violate)

        reply = agent.generate("tôi vừa bán hết", MentorContext(company="ACB"))

        assert reply.disclaimer.startswith("Capia là môi trường mô phỏng")
        assert reply.questions  # fallback question-bank luôn có câu hỏi

    def test_generate_falls_back_on_gemini_error(self, judge_off):
        unavailable = GeminiUnavailableLike()
        agent = SocraticMentorAgent(gemini=unavailable)  # type: ignore[arg-type]

        reply = agent.generate("test")

        assert reply.questions


class GeminiUnavailableLike:
    available = False

    def generate_structured(self, *args: Any, **kwargs: Any):
        raise GeminiError("no key")
