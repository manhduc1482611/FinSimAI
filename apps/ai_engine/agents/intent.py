"""IntentClassifier + MentorRouter — phân luồng "3 chế độ" cho Mentor.

docs/ai_mentor_3mode_plan.md v2.0, mục 2.1: trước khi sinh reply, router phân
định chế độ: concept / plan / trade_now / socratic.

Phân loại theo 3 lớp (ưu tiên độ tin cậy):
1. **Quy tắc cứng (deterministic, 0 token):** pattern từ khoá tiếng Việt BỎ DẤU.
   Đây là lớp mặc định & an toàn nhất — dùng hàm ``classify``.
2. **LLM (khi MENTOR_LLM_MODE=on):** nếu quy tắc cứng trả confidence thấp, gọi
   Gemini phân loại nhẹ (1 lần) trả ``{mode, confidence, reason}``.
3. **Fallback:** confidence thấp + LLM không khả dụng → ``socratic`` (an toàn nhất).

Ranh giới rủi ro quan trọng nhất là **plan vs câu hỏi mua/bán cụ thể**: câu
mua/bán cụ thể ('nên mua cổ X không') KHÔNG được rơi vào ``plan`` — nó quy về
``socratic`` phản biện. Mọi trường hợp mơ hồ → ``socratic``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from agents.base import BaseAgent
from agents.policy import normalize_text
from pydantic import BaseModel, Field

MentorMode = Literal["concept", "plan", "trade_now", "socratic"]


class _LLMIntent(BaseModel):
    mode: MentorMode = Field(description="Một trong: concept, plan, trade_now, socratic")
    confidence: float = Field(ge=0.0, le=1.0, description="Độ tin cậy 0-1")
    reason: str = Field(default="", description="Lý do ngắn gọn")


class MentorModeEnum(str, Enum):
    CONCEPT = "concept"
    PLAN = "plan"
    TRADE_NOW = "trade_now"
    SOCRATIC = "socratic"


@dataclass(frozen=True)
class IntentResult:
    """Kết quả phân loại ý định."""

    mode: MentorMode
    confidence: float
    reason: str
    selected_symbol: str | None = None


# Pattern khái niệm — từ khoá mở câu hỏi khái niệm (đã bỏ dấu).
_CONCEPT_QUERY_KEYWORDS = [
    "la gi",
    "nghia la",
    "giai thich",
    "khai niem",
    "dinh nghia",
    "la sao",
    "the nao",
    "nhu the nao",
    "yeu to gi",
    "def ",
    "dinh nghia ve",
]

# Pattern 'plan' — nhu cầu hướng đầu tư chiến lược (đã bỏ dấu).
_PLAN_KEYWORDS = [
    "huong dau tu",
    "chien luoc",
    "phan bo von",
    "ke hoach dau tu",
    "dau tu gi",
    "nen dau tu",
    "danh muc",
    "phai dau tu",
    "nen mua co phieu nao",
    "loi khuyen dau tu",
    "cach dau tu",
    "nen choi",
]

# Pattern 'trade_now' — ngữ cảnh giao dịch tức thời (đã bỏ dấu).
_TRADE_NOW_KEYWORDS = [
    "dang muon ban",
    "sap mua",
    "sap ban",
    "vua dat lenh",
    "dang dat lenh",
    "co nen chot",
    "co nen cat lo",
    "vua mua",
    "vua ban",
    "dang giu",
    "muon ra",
    "lenh cua toi",
    "toi moi mua",
    "toi moi ban",
    "dinh mua",
    "dinh ban",
    "co nen giu",
]

# Pattern nghi vấn đầu câu — để nhận diện câu hỏi (không phải câu khẳng định).
_QUESTION_PREFIX_HINT = [
    "co nen",
    "nen",
    "co the",
    "sap",
    "dang muon",
    "vua",
    "toi nen",
]


def _normalize(text: str) -> str:
    return normalize_text(text or "")


def _has_keyword(haystack: str, keywords: list[str]) -> bool:
    return any(kw and kw in haystack for kw in keywords)


class IntentClassifier:
    """Phân loại ý định bằng quy tắc cứng (deterministic, 0 token)."""

    def __init__(self) -> None:
        self._concept = _CONCEPT_QUERY_KEYWORDS
        self._plan = _PLAN_KEYWORDS
        self._trade = _TRADE_NOW_KEYWORDS

    def classify(
        self,
        message: str,
        *,
        selected_symbol: str | None = None,
        mode_hint: str | None = None,
    ) -> IntentResult:
        """Phân loại theo quy tắc cứng; không bao giờ có ngoại lệ."""
        text = _normalize(message or "")
        # Giả định: mode_hint do client gửi 'trade_now' khi trên Page Trade.
        # Quy tắc cứng vẫn phải KIỂM TRA — không tin client 100%.
        if mode_hint == "trade_now" and _has_keyword(text, _TRADE_NOW_KEYWORDS):
            return IntentResult("trade_now", 0.95, "client flag + keyword giao dịch tức thời", selected_symbol)
        if mode_hint == "plan" and _has_keyword(text, _PLAN_KEYWORDS):
            return IntentResult("plan", 0.95, "client flag + keyword chiến lược", selected_symbol)
        if _has_keyword(text, _CONCEPT_QUERY_KEYWORDS):
            return IntentResult("concept", 0.95, "câu hỏi khái niệm (là gì/nghĩa là/g.iải thích)", selected_symbol)
        if _has_keyword(text, _PLAN_KEYWORDS):
            # Phân biệt plan vs câu mua/bán cụ thể: nếu có từ khóa giao dịch
            # tức thời kèm theo → nghiêng về socratic phản biện.
            if _has_keyword(text, _TRADE_NOW_KEYWORDS):
                return IntentResult("socratic", 0.8, "mơ hồ giữa plan và trade_now → an toàn socratic", selected_symbol)
            return IntentResult("plan", 0.85, "nhu cầu hướng đầu tư chiến lược", selected_symbol)
        if _has_keyword(text, _TRADE_NOW_KEYWORDS):
            return IntentResult("trade_now", 0.85, "hành động giao dịch tức thời", selected_symbol)
        return IntentResult("socratic", 0.9, "mặc định an toàn — không khớp chế độ khác", selected_symbol)


class MentorRouter(BaseAgent):
    """Router cao nhất: chọn đúng agent theo ý định người chơi."""

    prompt_file = "mentor_prompts.yaml"

    def __init__(self, classifier: IntentClassifier | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._classifier = classifier or IntentClassifier()

    def classify(self, message: str, **kw: Any) -> IntentResult:
        return self._classifier.classify(message, **kw)

    # ── LLM lớp 2 (optional, khi MENTOR_LLM_MODE=on) ───────────────────────
    def llm_classify(self, message: str, **kw: Any) -> IntentResult | None:
        """LLM phân loại khi quy tắc cứng confidence thấp; trả None nếu không."""
        if not self.gemini.available:
            return None
        prompt = self._require_prompt("intent_llm", "user_prompt")
        rendered = self.store.render(prompt, user_message=message)
        try:
            reply = self.gemini.generate_structured(
                self._LLMIntent,
                system_instruction=self._require_prompt("intent_llm", "system_prompt"),
                user_content=rendered,
            )
        except Exception:  # noqa: BLE001 - thất bại LLM → fallback an toàn
            return None
        if reply.mode not in ("concept", "plan", "trade_now", "socratic"):
            return None
        return IntentResult(
            mode=reply.mode,
            confidence=reply.confidence,
            reason=reply.reason or "llm",
        )