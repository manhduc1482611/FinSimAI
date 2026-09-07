"""Grounding số liệu — lớp chống hallucination thứ 4.5 (improvement_plan A2.3).

Nguyên tắc: mọi con số "dữ liệu" (giá, %, khối lượng...) xuất hiện trong reply
của Mentor PHẢI tồn tại trong ngữ cảnh được hệ thống/người chơi cung cấp.
LLM không được tự tính toán hay bịa số.

Chính sách so khớp (cân bằng giữa chống bịa và không giết câu hỏi Socratic):

- **Được phép tự do**: số nguyên THUẦN ≤ 3 chữ số (≤999) — dùng để liệt kê
  ("3 kịch bản", "2 nguồn tin"), ngày/tháng, thang điểm ("1-5"), thành ngữ
  ("quay ngoắt 180 độ"). Đây là số CẤU TRÚC của câu chữ. Số có dấu ngăn cách
  hoặc thập phân (92.500, 12,5) và số nguyên ≥4 chữ số luôn được coi là DỮ LIỆU.
- **Phải có trong ngữ cảnh**: mọi số dữ liệu còn lại. So khớp theo CHUỖI CHỮ SỐ
  bỏ dấu ngăn cách nên ``92.500`` trong reply khớp với ``92500`` trong ngữ cảnh
  và ngược lại.

Vi phạm được báo dưới dạng :class:`PolicyViolationError` (quy tắc 4 của prompt
hệ thống: "KHÔNG bịa dữ kiện, con số") để tận dụng vòng retry-feedback sẵn có
của :meth:`GeminiClient.generate_structured`.
"""

from __future__ import annotations

import re

from agents.policy import PolicyViolationError
from integrations.gemini import GeminiError  # noqa: F401 - tái xuất cho caller

# Số nguyên/có phân cách: 3, 12.5, 92.500, 1,5, 2026
_NUMBER_TOKEN = re.compile(r"\d+(?:[.,]\d+)*")
_SEPARATORS = str.maketrans("", "", ".,")
# Ngưỡng số cấu trúc: số nguyên thuần ≤ 3 chữ số (liệt kê/ngày/thành ngữ).
_STRUCTURAL_MAX_DIGITS = 3


class GroundingError(PolicyViolationError):
    """Reply chứa con số dữ liệu KHÔNG có trong ngữ cảnh (bịa số)."""


def extract_numbers(text: str) -> list[str]:
    """Trích các token số (giữ nguyên dạng viết)."""
    return [m.group(0) for m in _NUMBER_TOKEN.finditer(text)]


def _canon(token: str) -> str:
    """Chuỗi chữ số chuẩn: bỏ chấm/phẩy ngăn cách — '92.500' → '92500'."""
    return token.translate(_SEPARATORS)


def _is_structural(token: str) -> bool:
    canon = _canon(token)
    # Số nguyên thuần ≤3 chữ số: có dấu ngăn cách/thập phân thì luôn là dữ liệu.
    return token == canon and len(canon) <= _STRUCTURAL_MAX_DIGITS


def check_grounding(text: str, context: str) -> list[str]:
    """Trả về danh sách số trong ``text`` KHÔNG tìm thấy trong ``context``."""
    context_numbers = {_canon(t) for t in extract_numbers(context)}
    ungrounded: list[str] = []
    for token in extract_numbers(text):
        if _canon(token) in context_numbers:
            continue
        if _is_structural(token):
            continue
        ungrounded.append(token)
    return ungrounded


def assert_grounded(texts: tuple[str, ...] | list[str], context: str) -> None:
    """Ném :class:`GroundingError` nếu bất kỳ đoạn nào chứa số lạ.

    ``texts`` là các phần của reply cần kiểm (questions, coaching_tip...);
    ``context`` là toàn bộ nguồn hợp lệ: ngữ cảnh hệ thống + lịch sử + tin nhắn
    người chơi (quote lại số người chơi cung cấp là hợp lệ).
    """
    violations: list[str] = []
    for text in texts:
        for token in check_grounding(text, context):
            violations.append(f"'{token}' không có trong ngữ cảnh")
    if violations:
        raise GroundingError(violations)
