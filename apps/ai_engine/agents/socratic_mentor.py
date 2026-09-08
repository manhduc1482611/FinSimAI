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
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator, model_validator

from agents.base import BaseAgent
from agents.grounding import assert_grounded
from agents.judge import JudgeVerdict, judge_enabled, judge_feedback_message, run_judge
from agents.policy import PolicyViolationError, normalize_text, scan_policy
from integrations.gemini import GeminiError

logger = logging.getLogger(__name__)

# Đường dẫn cơ sở tri thức khái niệm (docs v2.0, mục 3.2.1).
_KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge_base.yaml"

_concept_cache: dict[str, dict[str, Any]] | None = None


def _load_concept_bank() -> dict[str, dict[str, Any]]:
    """Nạp YAML knowledge base 1 lần; lỗi YAML → trả bank rỗng + log rõ."""
    global _concept_cache
    if _concept_cache is not None:
        return _concept_cache
    try:
        with _KB_PATH.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        concepts = raw["concepts"]
        _concept_cache = {k: v for k, v in concepts.items() if isinstance(k, str)}
    except Exception as exc:  # noqa: BLE001 - fallback rỗng, không chết agent
        logger.error("Không nạp được knowledge_base.yaml: %s", exc)
        _concept_cache = {}
    return _concept_cache


def lookup_concept(message: str) -> tuple[str, dict[str, Any]] | None:
    """Tìm khái niệm khớp với tin hỏi (đã chuẩn hoá bỏ dấu). Trả (id, entry)."""
    haystack = normalize_text(message or "")
    for key, entry in _load_concept_bank().items():
        keywords = entry.get("keywords") or []
        for kw in keywords:
            if kw and normalize_text(kw) in haystack:
                return key, entry
    return None


def nearest_concept(message: str) -> str | None:
    """Gợi ý khái niệm gần nhất dựa trên từ khoá — fallback 'không biết'."""
    haystack = normalize_text(message or "")
    best_key: str | None = None
    best_score = 0
    for key, entry in _load_concept_bank().items():
        score = sum(1 for kw in (entry.get("keywords") or []) if kw and normalize_text(kw) in haystack)
        if score > best_score:
            best_score, best_key = score, key
    return best_key if best_score > 0 else None


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


class ConceptReply(BaseModel):
    """Phản hồi Chế độ 1 — giải thích khái niệm (docs v2.0, mục 3.2.2)."""

    concept: str = Field(description="Tên khái niệm được hỏi")
    definition: str = Field(description="Định nghĩa ngắn gọn")
    explanation: str = Field(description="Giải thích dễ hiểu 2-4 câu")
    example: str = Field(description="Ví dụ số học trực quan")
    formula: str | None = Field(default=None, description="Công thức (nếu có)")
    interpretation: str = Field(description="Diễn giải — KHÔNG phán xét tốt/xấu")
    related: list[str] = Field(
        default_factory=list, min_length=0, description="1-3 khái niệm liên quan"
    )
    followup_question: str = Field(description="1 câu hỏi phản biện Socratic để nối tiếp")
    disclaimer: str = Field(default="", description="Cảnh báo môi trường mô phỏng")

    @model_validator(mode="after")
    def _enforce_policy(self) -> ConceptReply:
        violations = scan_policy(
            self.definition, self.explanation, self.example, self.interpretation
        )
        if violations:
            details = [f"[{v.kind}] {v.sentence}" for v in violations]
            raise PolicyViolationError(details)
        return self


class StrategyReply(BaseModel):
    """Phản hồi Chế độ 2 — khung chiến lược (docs v2.0, mục 4.2).

    Nội dung framework được KHÓA CỨNG trong bank (mentor_prompts.yaml); LLM chỉ
    chọn framework enum + điền tham số trong khoảng hợp lệ — không tự soạn câu chữ.
    """

    framework_name: str = Field(description="Tên khung chiến lược")
    objective: str = Field(description="Mục tiêu của khung")
    criteria: list[str] = Field(min_length=1, description="2-4 tiêu chí định lượng")
    allocation_rule: str = Field(description="Quy tắc phân bổ vốn (không nêu mã)")
    risk_rule: str = Field(description="Quy tắc quản trị rủi ro (không nêu mã)")
    how_to_trade: list[str] = Field(min_length=1, description="Các bước thực hiện KHÔNG nêu mã")
    questions: list[str] = Field(min_length=1, description="1-3 câu hỏi phản biện")
    disclaimer: str = Field(default="", description="Cảnh báo môi trường mô phỏng")

    @model_validator(mode="after")
    def _enforce_policy(self) -> StrategyReply:
        # Whitelist W1-W4 áp dụng cho mode plan (docs v2.0, mục 2.2): nội dung
        # khung lấy từ bank đã duyệt, không nêu mã/giá cụ thể.
        violations = scan_policy(
            *self.criteria,
            self.allocation_rule,
            self.risk_rule,
            *self.how_to_trade,
            allow_whitelist=True,
        )
        if violations:
            details = [f"[{v.kind}] {v.sentence}" for v in violations]
            raise PolicyViolationError(details)
        return self


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

    # ── Chế độ 1: Concept ──────────────────────────────────────────────────
    def generate_concept(
        self, message: str, context: MentorContext | None = None
    ) -> ConceptReply:
        """Trả ConceptReply từ deterministic glossary; LLM path nếu không khớp."""
        result = lookup_concept(message)
        if result is not None:
            key, entry = result
            return self._concept_from_bank(key, entry)
        # Không khớp glossary → LLM mở rộng nếu khả dụng, không thì fallback.
        ctx = context or MentorContext()
        if self.gemini.available:
            try:
                return self.llm_concept(message, ctx)
            except Exception as exc:  # noqa: BLE001 - mọi lỗi → fallback an toàn
                logger.warning("Concept LLM thất bại — fallback: %s", exc)
        suggestion = nearest_concept(message)
        return self._concept_unknown(message, suggestion)

    def llm_concept(self, message: str, ctx: MentorContext) -> ConceptReply:
        """Sinh ConceptReply qua LLM (5 lớp bảo vệ + grounding bắt buộc)."""
        prompt = self._render_prompt(message, ctx, None, "")
        system_prompt = self._require_prompt("concept_system_prompt")
        grounding_validator = self._grounding_validator(prompt)
        reply = self.gemini.generate_structured(
            ConceptReply,
            system_instruction=system_prompt,
            user_content=prompt,
            validator=grounding_validator,
        )
        return reply.model_copy(update={"disclaimer": self._disclaimer})

    def _concept_from_bank(self, key: str, entry: dict[str, Any]) -> ConceptReply:
        return ConceptReply(
            concept=entry["name"],
            definition=entry["definition"],
            explanation=entry["explanation"],
            example=entry["example"],
            formula=entry.get("formula"),
            interpretation=entry["interpretation"],
            related=entry.get("related") or [],
            followup_question="Bạn có thử áp dụng khái niệm này vào một tình huống cụ thể của mình không? Hãy mô tả để cùng phản biện.",
            disclaimer=self._disclaimer,
        )

    def _concept_unknown(self, message: str, suggestion: str | None) -> ConceptReply:
        tip = f" Bạn có thể hỏi thêm về '{suggestion}'." if suggestion else ""
        return ConceptReply(
            concept="(không xác định)",
            definition="Tôi chưa có khái niệm này trong cơ sở tri thức.",
            explanation=f"{tip} Thay vì đoán, tôi mời bạn cho biết ngữ cảnh bạn đang gặp để cùng suy nghĩ theo phương pháp phản biện.",
            example="",
            formula=None,
            interpretation="",
            related=[],
            followup_question="Hãy mô tả tình huống hoặc câu hỏi cụ thể của bạn, tôi giúp bạn nhìn nhận vấn đề theo khía cạnh khác.",
            disclaimer=self._disclaimer,
        )

    # ── Chế độ 2: Strategy (khóa cứng) ─────────────────────────────────────

    # ── Interior: chọn framework bank deterministic ─────────────────────────
    def _strategy_from_bank(self, framework_id: str) -> StrategyReply:
        bank = self._require_prompt("strategy_bank")
        entry = bank["frameworks"][framework_id]
        return StrategyReply(
            framework_name=entry["name"],
            objective=entry["objective"],
            criteria=list(entry["criteria"]),
            allocation_rule=entry["allocation_rule"],
            risk_rule=entry["risk_rule"],
            how_to_trade=list(entry["how_to_trade"]),
            questions=entry.get("questions") or ["Bạn đã xác định khả năng chịu rủi ro của mình đến đâu chưa?"],
            disclaimer=self._disclaimer,
        )

    def _match_framework(self, message: str, ctx: MentorContext) -> str:
        """Chọn framework theo từ khoá + profile (deterministic, 0 token)."""
        text = normalize_text(f"{message} {ctx.portfolio} {ctx.market_context}")
        # Ưu tiên explicit profile trước.
        if "an toan" in text or "roi ro thap" in text or "thu nhap" in text:
            return "income"
        if "tang truong" in text or "nhanh" in text or "lai suat cao" in text:
            return "growth"
        if "danh muc" in text or "phan theo doi" in text:
            return "index"
        if "can slim" in text or "trend" in text:
            return "growth"
        return "index"  # safe default

    def generate_strategy(
        self, message: str, context: MentorContext | None = None
    ) -> StrategyReply:
        """Trả StrategyReply từ framework bank (deterministic default).

        Khóa cứng: nội dung khung luôn lấy từ bank đã duyệt; LLM (nếu on) chỉ
        chọn framework + sinh 1-3 câu hỏi phản biện; output không khớp bank →
        quay về deterministic.
        """
        ctx = context or MentorContext()
        framework_id = self._match_framework(message, ctx)
        base = self._strategy_from_bank(framework_id)
        # LLM path: chỉ cho phép thay đổi questions (câu hỏi phản biện) và
        # framework_name phải nằm trong bank. Nếu output lệch bank → giữ base.
        if self.gemini.available:
            try:
                llm_reply = self.llm_strategy(message, ctx)
            except Exception as exc:  # noqa: BLE001 - lỗi LLM → base an toàn
                logger.warning("Strategy LLM thất bại — dùng bank: %s", exc)
                llm_reply = None
            if llm_reply is not None and self._matches_bank(llm_reply):
                base = base.model_copy(
                    update={
                        "framework_name": llm_reply.framework_name,
                        "questions": llm_reply.questions,
                    }
                )
        return base

    def llm_strategy(self, message: str, ctx: MentorContext) -> StrategyReply | None:
        """LLM CHỈ chọn framework trong bank + sinh câu hỏi phản biện."""
        prompt = self._render_prompt(message, ctx, None, "")
        system_prompt = self._require_prompt("strategy_system_prompt")
        validator = self._strategy_validator()
        try:
            return self.gemini.generate_structured(
                StrategyReply,
                system_instruction=system_prompt,
                user_content=prompt,
                validator=validator,
            )
        except Exception as exc:  # noqa: BLE001 - validate lách → None → base
            logger.warning("Strategy LLM không hợp lệ: %s", exc)
            return None

    def _matches_bank(self, reply: StrategyReply) -> bool:
        """Bảng matrix khóa cứng: nội dung khung phải thuộc bank đã duyệt."""
        bank = self._require_prompt("strategy_bank")
        names = [f["name"] for f in bank["frameworks"].values()]
        if reply.framework_name not in names:
            return False
        return True

    def _strategy_validator(self):
        def _validate(reply: StrategyReply) -> None:
            if not self._matches_bank(reply):
                raise PolicyViolationError(
                    ["StrategyReply framework_name không thuộc bank đã duyệt"]
                )
        return _validate

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
