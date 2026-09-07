"""Chính sách nội dung — lá chắn an toàn của Socratic Mentor.

Đảm bảo TUYỆT ĐỐI: không lời khuyên MUA/BÁN, không nhận xét ĐÚNG/SAI về quyết
định của người chơi.

Nguyên tắc quét:
- Cắt văn bản thành câu.
- Câu hỏi (kết thúc bằng "?" hoặc bắt đầu bằng từ để hỏi) được MIỄN TRỪ: việc
  mentor NHẮC LẠI ý định mua/bán của người chơi trong câu hỏi là hợp lệ.
- Câu khẳng định còn lại bị quét theo cụm từ "khuyến nghị mua/bán" và cụm từ
  "phán xét đúng/sai". Trúng bất kỳ cụm nào → vi phạm.

Lớp CHUẨN HOÁ (improvement_plan A2.1/A4.1): mỗi câu được hạ xuống dạng ASCII
không dấu (lowercase + NFD bỏ dấu tổ hợp + đ→d) trước khi so khớp, và toàn bộ
pattern cũng viết ở dạng không dấu — nhờ vậy "nên mua", "nen mua", "nến mua"
đều bị bắt như nhau. Các token dễ va chạm khi bỏ dấu ("xả"→"xa", "chốt"→"chot",
"kém"→"kem") chỉ được quét kèm TÂN NGỮ hoặc CHỦ NGỮ cảnh báo để hạn chế báo
nhầm với văn thuần giáo dục.

Đây là lá chắn HEURISTIC (không hoàn hảo). Vì vậy khi phát hiện vi phạm, Agent
sẽ retry có feedback; nếu hết retry vẫn vi phạm → rơi về fallback deterministic
vốn luôn an toàn.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from integrations.gemini import PolicyViolationError as _GeminiPolicyViolation

_QUESTION_SUFFIX = re.compile(r"[?؟]\s*$")
# Từ để hỏi — viết dạng không dấu vì so khớp trên bản chuẩn hoá.
# CHỈ giữ các mở đầu thực sự nghi vấn: "Bạn đã…", "Nếu…" cũng mở đầu câu
# khẳng định ("Bạn đã sai rồi.", "Nếu muốn thắng hãy mua ngay.") nên KHÔNG
# được miễn trừ — dấu "?" cuối câu là exemption chính.
_QUESTION_PREFIX = re.compile(
    r"^\s*(?:ban\s+co|anh\s+co|chi\s+co|em\s+co|co\s+phai|tai\s+sao|vi\s+sao|khi\s+nao|"
    r"o\s+dau|bao\s+gio|bao\s+nhieu|lam\s+sao|the\s+nao|nhu\s+the\s+nao|lieu|"
    r"ai\s+da|dieu\s+gi|cai\s+gi|hay\s+la|vay\s+thi)",
    re.IGNORECASE,
)

# ─── Khuyến nghị MUA/BÁN (câu khẳng định) ───────────────────────────────────
# Toàn bộ pattern viết ở dạng ĐÃ BỎ DẤU — so khớp với normalize_text(sentence).
_ADVICE_PATTERNS: list[re.Pattern[str]] = [
    # Động từ khuyến nghị trực tiếp: nên/hãy/có thể + hành động mua/bán.
    re.compile(
        r"\bnen\s+(?:mua|ban|nam\s+giu|chot\s+loi|cat\s+lo|vao\s+lenh|mo\s+lenh|"
        r"giu\s+lenh|gom|xa|danh)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhay\s+(?:mua|ban|chot\s+loi|cat\s+lo|vao\s+lenh|mo\s+lenh|gom|xa)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bco\s+the\s+(?:mua|ban|nam\s+giu|gom|xa)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:nen|hay|phai)\s+(?:dat|mo|giu|dong)\s+(?:lenh|vi\s+the)\b", re.IGNORECASE
    ),
    re.compile(r"\bkhuyen\s*nghi\b", re.IGNORECASE),
    re.compile(r"\bgia\s+muc\s*tieu\b", re.IGNORECASE),
    re.compile(r"\btin\s*hieu\s+(?:mua|ban)\b", re.IGNORECASE),
    re.compile(r"\b(?:chot\s+(?:loi|lo)|cat\s+lo)\s+(?:ngay|luon)\b", re.IGNORECASE),
    # Lách luật kiểu "mềm hoá": nên cân nhắc mua / cân nhắc bán / đáng để mua.
    re.compile(
        r"\b(?:nen|can)\s+can\s+nhac\s+(?:viec\s+)?(?:mua|ban|gom|xa|vao|ra)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcan\s+nhac\s+(?:mua|ban|gom|xa)\b", re.IGNORECASE),
    re.compile(r"\b(?:rat|thuc\s+su|kha|qua)\s+dang\s+(?:mua|ban|gom)\b", re.IGNORECASE),
    re.compile(r"\bdang\s+de\s+(?:mua|ban|gom)\b", re.IGNORECASE),
    re.compile(r"\bthoi\s*diem\s+(?:mua|ban|vao|gom)\b", re.IGNORECASE),
    re.compile(r"\bco\s*hoi\s+(?:de\s+)?(?:mua|ban|vao|gom)\b", re.IGNORECASE),
    # Tiền slang VN: kèo tốt, giải ngân, đánh vào, all-in, rót/bỏ vốn.
    re.compile(r"\bkeo\s+(?:tot|dep|hot|xinh)\b", re.IGNORECASE),
    re.compile(r"\bkeo\s+nay[^?!]*\b(?:tot|dep|hot)\b", re.IGNORECASE),
    re.compile(r"\bgiai\s+ngan\b", re.IGNORECASE),
    re.compile(
        r"\bdanh\s+vao\s+(?:co\s*phieu|con|ma|lenh|thi\s*truong|nganh)\b", re.IGNORECASE
    ),
    re.compile(r"\ball[\s-]*in\b", re.IGNORECASE),
    re.compile(r"\brot\s+von\b", re.IGNORECASE),
    re.compile(r"\b(?:bo|dut)\s+tien\s+(?:vao|cho)\b", re.IGNORECASE),
    re.compile(r"\btich\s*cuc\s+(?:mua|gom|ban)\b", re.IGNORECASE),
    # Gom/xả/chốt — chỉ quét kèm tân ngữ để tránh va chạm khi bỏ dấu
    # ("xả"→"xa" trùng "xa" = far; "chốt"→"chot" gần "chốt phương án").
    re.compile(
        r"\bgom\s+(?:vao|co\s*phieu|hang|chung|du\s*tron|ngay|luon|sach|duoc|them|full)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:nen|hay|can|bat\s*dau|tiep\s*tuc|dinh)\s+gom\b", re.IGNORECASE),
    re.compile(
        r"\bxa\s+(?:hang|co\s*phieu|bot|sach|ngay|luon|duoc|di|tha|het|nhe)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:nen|hay|can|bat\s*dau)\s+xa\b", re.IGNORECASE),
    re.compile(r"\bchot\s+(?:loi|lo|lenh|ngay|luon|duoc|lai|hom)\b", re.IGNORECASE),
    # Mệnh lệnh suồng sã: mua ngay/mua vô/mua đi, bán đi/bán tháo/vào lệnh.
    re.compile(r"\bmua\s+(?:ngay|luon|vo|vo\s*di|di|thoi|bay\s*gio)\b", re.IGNORECASE),
    re.compile(r"\bban\s+(?:ngay|luon|di|thao|het|bot|thoi|bay\s*gio)\b", re.IGNORECASE),
    re.compile(r"\b(?:vao|mo)\s+lenh\b", re.IGNORECASE),
]

# ─── Phán xét ĐÚNG/SAI về quyết định của người chơi (câu khẳng định) ────────
_JUDGMENT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:quyet\s+dinh|lua\s+chon)\b[^?!]*?\b(?:cua\s+ban\s+)?"
        r"(?:la\s+)?(?:mot\s+)?(?:dung|sai|hop\s*ly|khong\s*hop\s*ly|tot|xau|te|kem|"
        r"chinh\s*xac|lieu\s*linh|nguy\s*hiem|sai\s*lam)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:cach\s*lam|cach\s*choi|buoc\s*di|hanh\s*dong)\s*(?:nay|do|cua\s*ban)?\s*"
        r"la\s*(?:mot\s*)?(?:dung|sai|dung\s*dan|sai\s*lam)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bban\s+(?:da|se|dang)?\s*(?:hoan\s+toan\s+)?(?:dung|sai)\b", re.IGNORECASE),
    re.compile(r"\b(?:dung|sai)\s+roi\b", re.IGNORECASE),
    re.compile(
        r"\bdau\s*tu\s+(?:tot|xau|dung|sai|dung\s*dan|sai\s*lam)\b", re.IGNORECASE
    ),
    re.compile(
        r"\bnhan\s+dinh\s+(?:cua\s+ban\s+)?(?:la\s+)?(?:dung|sai|hop\s*ly|chinh\s*xac)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnhan\s+dinh[^?!]*\bchinh\s*xac\b", re.IGNORECASE),
    re.compile(
        r"\bdu\s*bao\s+(?:cua\s+ban\s+)?(?:la\s+)?(?:dung|sai|chinh\s*xac)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdong\s+y\s+voi\s+(?:quyet\s+dinh|lua\s+chon|cach|hanh\s*dong)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bban[^?!]*\bvi\s*pham\s+ky\s*luat\b", re.IGNORECASE),
]


def normalize_text(text: str) -> str:
    """Chuẩn hoá văn bản để so khớp: lowercase + bỏ dấu + đ→d.

    "Nên MUA" / "nen mua" / "NÊN MUA" đều trở thành ``nen mua`` — chặn được
    biến thể gõ không dấu hoặc lẫn hoa/thường của người dùng và của LLM.
    """
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    return stripped.replace("đ", "d")


class PolicyViolationError(_GeminiPolicyViolation):
    """Output hợp lệ về cấu trúc nhưng vi phạm chính sách (mua/bán, đúng/sai).

    Kế thừa :class:`integrations.gemini.PolicyViolationError` để vòng
    retry-feedback của ``generate_structured`` bắt được và cho LLM sửa lỗi.
    """

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        # Cha tự join danh sách thành message và giữ lại .violations.
        super().__init__(violations)


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
    return bool(_QUESTION_PREFIX.search(normalize_text(sentence)))


def scan_policy(*texts: str) -> list[PolicyViolation]:
    """Quét chính sách: trả về danh sách vi phạm (rỗng nếu sạch)."""
    violations: list[PolicyViolation] = []
    for text in texts:
        for sentence in _split_sentences(text):
            if _is_question(sentence):
                continue
            haystack = normalize_text(sentence)
            for pattern in _ADVICE_PATTERNS:
                if pattern.search(haystack):
                    violations.append(
                        PolicyViolation(sentence=sentence, kind="advice", pattern=pattern.pattern)
                    )
            for pattern in _JUDGMENT_PATTERNS:
                if pattern.search(haystack):
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
