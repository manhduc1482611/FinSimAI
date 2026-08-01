"""Chính sách nội dung — lá chắn an toàn của Socratic Mentor.

Đảm bảo TUYỆT ĐỐI: không lời khuyên MUA/BÁN, không nhận xét ĐÚNG/SAI về quyết
định của người chơi.

Nguyên tắc quét:
- Cắt văn bản thành câu.
- Câu hỏi (kết thúc bằng "?" hoặc bắt đầu bằng từ để hỏi) được MIỄN TRỪ: việc
  mentor NHẮC LẠI ý định mua/bán của người chơi trong câu hỏi là hợp lệ.
- Câu khẳng định còn lại bị quét theo cụm từ "khuyến nghị mua/bán" và cụm từ
  "phán xét đúng/sai". Trúng bất kỳ cụm nào → vi phạm.

Đây là lá chắn HEURISTIC (không hoàn hảo). Vì vậy khi phát hiện vi phạm, Agent
sẽ retry có feedback; nếu hết retry vẫn vi phạm → rơi về fallback deterministic
vốn luôn an toàn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from integrations.gemini import GeminiError

_QUESTION_SUFFIX = re.compile(r"[?؟]\s*$")
_QUESTION_PREFIX = re.compile(
    r"^\s*(?:bạn\s+có|anh\s+có|chị\s+có|em\s+có|có\s+phải|tại\s+sao|vì\s+sao|khi\s+nào|"
    r"ở\s+đâu|bao\s+giờ|bao\s+nhiêu|làm\s+sao|thế\s+nào|như\s+thế\s+nào|liệu|"
    r"ai\s+đã|điều\s+gì|cái\s+gì|nếu\s+...|hay\s+là|vậy\s+thì|bạn\s+đã)",
    re.IGNORECASE,
)

# Khuyến nghị MUA/BÁN trực tiếp (câu khẳng định)
_ADVICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bnên\s+(?:mua|bán|nắm\s+giữ|chốt\s+lời|cắt\s+lỗ|vào\s+lệnh|mở\s+lệnh|giữ\s+lệnh|xả)\b", re.IGNORECASE),
    re.compile(r"\bhãy\s+(?:mua|bán|chốt\s+lời|cắt\s+lỗ|vào\s+lệnh|mở\s+lệnh)\b", re.IGNORECASE),
    re.compile(r"\bcó\s+thể\s+(?:mua|bán|nắm\s+giữ)\b", re.IGNORECASE),
    re.compile(r"\b(?:nên|hãy|phải)\s+(?:đặt|mở|giữ|đóng)\s+(?:lệnh|vị\s+thế)\b", re.IGNORECASE),
    re.compile(r"\bkhuyến\s*nghị\b", re.IGNORECASE),
    re.compile(r"\bgiá\s+mục\s+tiêu\b", re.IGNORECASE),
    re.compile(r"\btín\s+hiệu\s+(?:mua|bán)\b", re.IGNORECASE),
    re.compile(r"\bchốt\s+lời\s+(?:ngay|luôn)\b", re.IGNORECASE),
    re.compile(r"\bcắt\s+lỗ\s+(?:ngay|luôn)\b", re.IGNORECASE),
]

# Phán xét ĐÚNG/SAI về quyết định của người chơi (câu khẳng định)
_JUDGMENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:quyết\s+định|lựa\s+chọn)\b[^?!]*?\b(?:của\s+bạn\s+)?"
        r"(?:là\s+)?(?:một\s+)?(?:đúng|sai|hợp\s*lý|không\s+hợp\s*lý|tốt|xấu)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bbạn\s+(?:đã|sẽ|đang)?\s*(?:hoàn\s+toàn\s+)?(?:đúng|sai)\b", re.IGNORECASE),
    re.compile(r"\b(?:đúng|sai)\s+rồi\b", re.IGNORECASE),
    re.compile(r"\bđầu\s+tư\s+(?:tốt|xấu|đúng|sai|đúng\s+đắn)\b", re.IGNORECASE),
    re.compile(r"\bnhận\s+định\s+(?:của\s+bạn\s+)?(?:là\s+)?(?:đúng|sai|hợp\s*lý)\b", re.IGNORECASE),
    re.compile(r"\bdự\s+đoán\s+(?:của\s+bạn\s+)?(?:là\s+)?(?:đúng|sai)\b", re.IGNORECASE),
]


class PolicyViolationError(GeminiError):
    """Output hợp lệ về cấu trúc nhưng vi phạm chính sách (mua/bán, đúng/sai)."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations) or "Vi phạm chính sách nội dung")


@dataclass(frozen=True)
class PolicyViolation:
    sentence: str
    kind: str
    pattern: str


def _split_sentences(text: str) -> list[str]:
    """Tách văn bản thành câu theo dấu câu kết thúc câu."""
    text = text.strip()
    if not text:
        return []
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _is_question(sentence: str) -> bool:
    if _QUESTION_SUFFIX.search(sentence):
        return True
    return bool(_QUESTION_PREFIX.search(sentence))


def scan_policy(*texts: str) -> list[PolicyViolation]:
    """Quét chính sách: trả về danh sách vi phạm (rỗng nếu sạch)."""
    violations: list[PolicyViolation] = []
    for text in texts:
        for sentence in _split_sentences(text):
            if _is_question(sentence):
                continue
            for pattern in _ADVICE_PATTERNS:
                if pattern.search(sentence):
                    violations.append(
                        PolicyViolation(sentence=sentence, kind="advice", pattern=pattern.pattern)
                    )
            for pattern in _JUDGMENT_PATTERNS:
                if pattern.search(sentence):
                    violations.append(
                        PolicyViolation(sentence=sentence, kind="judgment", pattern=pattern.pattern)
                    )
    return violations


def assert_policy(*texts: str) -> None:
    """Ném :class:`PolicyViolationError` nếu bất kỳ đoạn nào vi phạm chính sách."""
    violations = scan_policy(*texts)
    if violations:
        details = [f"[{v.kind}] {v.sentence}" for v in violations]
        raise PolicyViolationError(details)
