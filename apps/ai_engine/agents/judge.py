"""LLM-as-judge — lớp bảo vệ thứ 4 của Mentor (improvement_plan A2.2).

Sau khi agent sinh reply, gọi 1 request flash RẺ TIỀN (temp 0, output ngắn)
với vai trò JUDGE độc lập: "Reply này có vi phạm: khuyến nghị mua/bán, phán
xét đúng/sai, bịa số liệu không có trong ngữ cảnh?".

- Verdict ``violation=true`` → agent retry sinh reply ĐÚNG MỘT LẦN với feedback;
  vẫn lỗi → fallback deterministic (luôn an toàn).
- Judge lỗi (quota/mạng/parse) → bỏ qua lớp này (fail-open): các lớp 1/2/3/5
  (prompt policy, schema validator, scanner keyword, fallback) vẫn đứng.

Chi phí tăng ~30% token nhưng bảo đảm ranh giới giáo dục–tư vấn.
"""

from __future__ import annotations

import logging
import os

from pydantic import BaseModel, Field

from integrations.gemini import GeminiClient

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM_PROMPT = """Bạn là JUDGE kiểm tra nội dung độc lập của một Mentor tài chính giáo dục.

Reply được đánh giá có VI PHẠM nếu chứa BẤT KỲ điều nào sau đây:
1. Khuyến nghị mua/bán trực tiếp hay gián tiếp ("nên mua", "hãy bán", "cân nhắc mua",
   "kèo tốt", "giải ngân", "chốt lời", "vào lệnh"...). LƯU Ý: việc mentor NHẮC LẠI
   ý định của người chơi trong CÂU HỎI phản biện là HỢP LỆ ("Bạn định bán dựa trên gì?").
2. Phán xét quyết định của người chơi là đúng/sai/tốt/xấu/hợp lý hay không hợp lý.
3. Xác nhận hay phủ nhận dự đoán thị trường ("sẽ tăng", "sẽ giảm", giá mục tiêu).
4. Bịa dữ kiện, con số không tồn tại trong NGỮ CẢNH được cung cấp.

Trả về JSON: {"violation": bool, "reason": "lý do ngắn gọn khi violation=true"}"""


class JudgeVerdict(BaseModel):
    """Kết quả phán xét của lớp LLM-as-judge."""

    violation: bool = Field(description="True nếu reply vi phạm chính sách")
    reason: str = Field(default="", description="Lý do ngắn gọn khi vi phạm")


def judge_enabled() -> bool:
    """Bật/tắt qua env ``MENTOR_JUDGE_ENABLED`` (mặc định BẬT)."""
    return os.environ.get("MENTOR_JUDGE_ENABLED", "true").strip().lower() not in (
        "0",
        "false",
        "off",
    )


def run_judge(
    gemini: GeminiClient,
    *,
    reply_texts: list[str],
    source_content: str,
) -> JudgeVerdict | None:
    """Phán xét reply; trả None khi judge không chạy nổi (fail-open)."""
    if not gemini.available:
        return None
    reply_block = "\n".join(reply_texts)
    user_content = (
        f"NGỮ CẢNH hệ thống cung cấp cho Mentor:\n{source_content}\n\n"
        f"REPLY CẦN PHÁN XÉT:\n{reply_block}\n\n"
        "Chỉ trả về JSON khớp schema."
    )
    try:
        verdict = gemini.generate_structured(
            JudgeVerdict,
            system_instruction=_JUDGE_SYSTEM_PROMPT,
            user_content=user_content,
            temperature=0.0,
            max_output_tokens=256,
        )
    except Exception:  # judge lỗi không được làm sập mentor
        logger.warning("Mentor judge lỗi — bỏ qua lớp judge", exc_info=True)
        return None
    if not isinstance(verdict, JudgeVerdict):  # phòng hờ type
        return None
    return verdict


def judge_feedback_message(verdict: JudgeVerdict) -> str:
    """Feedback ghép vào prompt khi retry sau khi judge chặn."""
    reason = verdict.reason.strip() or "vi phạm chính sách mentor"
    return f"JUDGE từ chối reply trước vì: {reason}. Viết lại reply tuân thủ toàn bộ quy tắc."
