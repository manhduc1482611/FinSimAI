"""Socratic Mentor Agent — cố vấn phản biện theo phương pháp Socratic.

NGUYÊN TẮC TUYỆT ĐỐI (được bảo vệ bởi 5 lớp — improvement_plan A2):
1. Prompt hệ thống cấm tuyệt đối lời khuyên mua/bán và nhận xét đúng/sai.
2. Pydantic schema + :class:`SocraticReply` có ``model_validator`` quét chính sách
   (xem :mod:`agents.policy`) — bất kỳ output nào vi phạm đều bị loại ngay lập tức.
3. Scanner keyword tiếng Việt mở rộng, chịu được văn bản không dấu (A2.1).
4. **LLM-as-judge** độc lập chấm reply trước khi phát; vi phạm → retry 1 lần
   → vẫn lỗi thì fallback (A2.2).
5. Fallback DETERMINISTIC (0 token) luôn an toàn.

Bổ sung lớp chống hallucination số liệu (A2.3): mọi con số "dữ liệu" trong reply
phải tồn tại trong ngữ cảnh — xem :mod:`agents.grounding`.

Đầu ra: một object :class:`SocraticReply` hợp lệ — chỉ có câu hỏi phản biện.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from agents.base import BaseAgent
from agents.grounding import assert_grounded
from agents.judge import JudgeVerdict, judge_enabled, judge_feedback_message, run_judge
from agents.policy import PolicyViolationError, normalize_text, scan_policy
from integrations.gemini import GeminiError

logger = logging.getLogger(__name__)


class SocraticFocus(str, Enum):
    """Thiên kiến tâm lý mà lượt hỏi đang hướng tới."""

    FOMO = "fomo"
    HERDING = "herding"
    ANCHORING = "anchoring"
    LOSS_AVERSION = "loss_aversion"
    OVERCONFIDENCE = "overconfidence"
    CONFIRMATION_BIAS = "confirmation_bias"
    NOISE_TRADING = "noise_trading"
    PROCESS = "process"


class SocraticReply(BaseModel):
    """Phản hồi hợp lệ của Socratic Mentor — chỉ chứa câu hỏi phản biện."""

    focus: SocraticFocus = Field(description="Thiên kiến tâm lý đang được mổ xẻ")
    questions: list[str] = Field(
        min_length=1,
        max_length=3,
        description="1-3 câu hỏi phản biện, mỗi câu kết thúc bằng dấu ?",
    )
    coaching_tip: str = Field(
        min_length=1,
        description="Bài tập quy trình trung tính (không chứa hành động mua/bán)",
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="1-3 nhãn kiến thức tài chính liên quan (tiếng Việt)",
    )
    disclaimer: str = Field(default="", description="Cảnh báo môi trường mô phỏng")

    @field_validator("questions", mode="before")
    @classmethod
    def _normalize_questions(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise TypeError("questions phải là một mảng")
        raw: list[str] = []
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise TypeError("Mỗi câu hỏi phải là chuỗi")
            question = item.strip()
            if not question:
                continue
            raw.append(question)
            if not question.endswith("?"):
                question = f"{question}?"
            normalized.append(question)
        # Quét chính sách trên CHUỖI THÔ (trước khi thêm "?"): câu khẳng định
        # chứa lời khuyên mua/bán không được "núp" sau dấu "?" bị thêm vào.
        violations = scan_policy(*raw)
        if violations:
            details = [f"[{v.kind}] {v.sentence}" for v in violations]
            raise PolicyViolationError(details)
        return normalized[:3]

    @model_validator(mode="after")
    def _enforce_policy(self) -> SocraticReply:
        violations = scan_policy(*self.questions, self.coaching_tip)
        if violations:
            details = [f"[{v.kind}] {v.sentence}" for v in violations]
            raise PolicyViolationError(details)
        return self


@dataclass
class MentorContext:
    """Bối cảnh phiên do hệ thống cung cấp cho Mentor."""

    company: str | None = None
    market_context: str = ""
    portfolio: str = ""

    def to_text(self) -> str:
        parts: list[str] = []
        if self.company:
            parts.append(f"- Công ty đang thảo luận: {self.company}")
        if self.market_context:
            parts.append(f"- Bối cảnh thị trường: {self.market_context}")
        if self.portfolio:
            parts.append(f"- Danh mục người chơi: {self.portfolio}")
        return "\n".join(parts) if parts else "(trống)"


class SocraticMentorAgent(BaseAgent):
    """Agent phản biện Socratic — không bao giờ đưa lời khuyên mua/bán."""

    prompt_file = "mentor_prompts.yaml"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._disclaimer = self._require_prompt("fallback", "disclaimer")

    # ── API công khai ──────────────────────────────────────────────────────
    def generate(
        self,
        message: str,
        context: MentorContext | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> SocraticReply:
        """Phản hồi Socratic cho tin nhắn của người chơi (luôn trả về hợp lệ)."""
        ctx = context or MentorContext()
        try:
            return self._finalize(self.llm_reply(message, ctx, history))
        except GeminiError as exc:
            logger.warning("Socratic mentor dùng fallback deterministic: %s", exc)
            return self._finalize(self._fallback(message, ctx))

    def llm_reply(
        self,
        message: str,
        ctx: MentorContext | None = None,
        history: list[dict[str, Any]] | None = None,
        extra_rule: str = "",
    ) -> SocraticReply:
        """Sinh reply qua LLM với đầy đủ lớp bảo vệ; ném ``GeminiError`` nếu thất bại.

        Đường ống: render prompt → generate (validator grounding A2.3) → judge
        độc lập (A2.2) → vi phạm thì retry ĐÚNG MỘT LẦN với feedback → vẫn lỗi
        thì ném lỗi để caller rơi về fallback deterministic.
        ``extra_rule``: quy tắc bổ sung do caller/judge chèn vào prompt.
        """
        ctx = ctx or MentorContext()
        prompt = self._render_prompt(message, ctx, history, extra_rule)
        system_prompt = self._require_prompt("system_prompt")
        grounding_validator = self._grounding_validator(prompt)

        reply = self.gemini.generate_structured(
            SocraticReply,
            system_instruction=system_prompt,
            user_content=prompt,
            validator=grounding_validator,
        )

        verdict = self._judge(reply, prompt)
        if verdict is not None and verdict.violation:
            logger.warning("Mentor judge chặn reply (%s) — retry một lần", verdict.reason)
            feedback = judge_feedback_message(verdict)
            retried = self.gemini.generate_structured(
                SocraticReply,
                system_instruction=system_prompt,
                user_content=self._render_prompt(message, ctx, history, feedback),
                validator=grounding_validator,
            )
            second_verdict = self._judge(retried, prompt)
            if second_verdict is not None and second_verdict.violation:
                raise PolicyViolationError(
                    [f"JUDGE chặn lần 2: {second_verdict.reason or 'vi phạm chính sách'}"]
                )
            reply = retried
        return reply

    # ── Triển khai nội bộ ──────────────────────────────────────────────────
    def _render_prompt(
        self,
        message: str,
        ctx: MentorContext,
        history: list[dict[str, Any]] | None,
        extra_rule: str,
    ) -> str:
        return self.store.render_template(
            self.prompt_file,
            "user_prompt",
            context=ctx.to_text(),
            history=self._format_history(history),
            user_message=message,
            extra_rule=extra_rule,
        )
    @staticmethod
    def _grounding_validator(context_text: str):
        """Validator cho generate_structured: mọi số dữ liệu phải có trong ngữ cảnh."""

        def _validate(reply: SocraticReply) -> None:
            assert_grounded([*reply.questions, reply.coaching_tip], context_text)

        return _validate

    def _judge(self, reply: SocraticReply, prompt: str) -> JudgeVerdict | None:
        """Chạy LLM-as-judge; trả None khi tắt hoặc judge không chạy được."""
        if not judge_enabled():
            return None
        return run_judge(
            self.gemini,
            reply_texts=[*reply.questions, reply.coaching_tip],
            source_content=prompt,
        )

    def _finalize(self, reply: SocraticReply) -> SocraticReply:
        return reply.model_copy(update={"disclaimer": self._disclaimer})

    def _fallback(self, message: str, ctx: MentorContext) -> SocraticReply:
        combined = f"{message} {ctx.market_context} {ctx.portfolio}"
        focus = self._detect_focus(combined)
        bank = self._require_prompt("fallback", "question_bank", focus.value)
        company = ctx.company or ""

        questions = [self.store.render(q, company=company) for q in bank["questions"]]
        coaching_tip = self.store.render(bank["coaching_tip"], company=company)
        return SocraticReply(
            focus=focus,
            questions=questions,
            coaching_tip=coaching_tip,
            concepts=list(bank["concepts"]),
            disclaimer=self._disclaimer,
        )

    def _detect_focus(self, text: str) -> SocraticFocus:
        # Chuẩn hoá BỎ DẤU cả haystack lẫn keyword để bắt tin nhắn viết
        # không dấu ("tang vun vut") — nhất quán với scanner chính sách A2.1.
        haystack = normalize_text(text)
        detection = self._require_prompt("fallback", "detection")
        scores: dict[str, int] = {
            focus_key: sum(1 for keyword in keywords if normalize_text(keyword) in haystack)
            for focus_key, keywords in detection.items()
        }
        priority = self._require_prompt("fallback", "priority_order")
        best_key = max(priority, key=lambda key: (scores.get(key, 0), -priority.index(key)))
        if scores.get(best_key, 0) == 0:
            return SocraticFocus.PROCESS
        return SocraticFocus(best_key)

    @staticmethod
    def _format_history(history: list[dict[str, Any]] | None) -> str:
        if not history:
            return "(trống)"
        lines: list[str] = []
        for item in history[-6:]:
            role = item.get("role", "assistant")
            content = item.get("content", "")
            speaker = "Người chơi" if role == "user" else "Socratic Mentor"
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)
