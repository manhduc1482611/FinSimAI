"""Gemini Fallback Service cho AI Mentor — dùng API Key khi question bank không trả lời được.

Khi deterministic question bank không khớp (ví dụ: khái niệm ngoài glossary, câu hỏi mở
về tài chính/thị trường không có keyword thiên kiến), hệ thống tự động gọi Gemini
bằng API key để trả lời theo phương pháp Socratic và định dạng chuẩn Capia.

Nguyên tắc TUYỆT ĐỐI:
1. Không đưa ra lời khuyên mua/bán cổ phiếu trực tiếp hay gián tiếp.
2. Không phán xét đúng/sai.
3. Luôn kết thúc bằng disclaimer của Capia.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.config import settings
from realtime.mentor_engine import _DISCLAIMER

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Bạn là "Socratic Mentor" của Capia — nền tảng mô phỏng thị trường chứng khoán tài chính cho người mới.

NHIỆM VỤ:
- Dùng phương pháp phản biện Socratic và giải thích giáo dục để người chơi hiểu bản chất vấn đề và tự rút ra kết luận.
- Mổ xẻ các khía cạnh: bản chất khái niệm tài chính, quy trình ra quyết định, quản trị rủi ro, kiểm chứng thông tin, tâm lý hành vi.

QUY TẮC TUYỆT ĐỐI (bất khả xâm phạm):
1. KHÔNG BAO GIỜ đưa ra lời khuyên MUA/BÁN trực tiếp hay gián tiếp (cấm tuyệt đối các từ: "nên mua", "nên bán", "hãy mua", "hãy bán", "múc", "thoát hàng", "giá mục tiêu", "khuyến nghị", "tín hiệu mua").
2. KHÔNG BAO GIỜ phán xét quyết định của người chơi là ĐÚNG hay SAI tuyệt đối.
3. KHÔNG BAO GIỜ xác nhận hay phủ nhận dự đoán giá (không nói "sắp tăng", "sẽ giảm").
4. Luôn giữ văn phong tiếng Việt tự nhiên, sư phạm, tôn trọng người học.
5. Luôn kèm theo tuyên bố miễn trừ trách nhiệm ở cuối.
"""


def _get_api_key() -> str:
    key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        try:
            from core.config import _find_project_root
            from dotenv import dotenv_values

            env_path = _find_project_root() / ".env"
            if env_path.exists():
                vals = dotenv_values(env_path)
                key = vals.get("GEMINI_API_KEY") or ""
        except Exception:
            pass
    return key.strip()


def _get_model_name() -> str:
    model = settings.gemini_model or os.environ.get("GEMINI_MODEL", "")
    if not model:
        try:
            from core.config import _find_project_root
            from dotenv import dotenv_values

            env_path = _find_project_root() / ".env"
            if env_path.exists():
                vals = dotenv_values(env_path)
                model = vals.get("GEMINI_MODEL") or ""
        except Exception:
            pass
    return (model or "gemini-3.5-flash-lite").strip()


async def generate_gemini_fallback(
    message: str,
    *,
    mode: str = "socratic",
    company: str = "",
) -> str | None:
    """Gọi Gemini API trả lời câu hỏi khi question bank deterministic không trả lời được.

    Trả về text hoàn chỉnh đã format hoặc None nếu thiếu key / lỗi mạng.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.debug("Không có GEMINI_API_KEY để gọi fallback")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_name = _get_model_name()

        if mode == "concept":
            user_instruction = (
                f"Người chơi đang hỏi về khái niệm hoặc thuật ngữ tài chính: \"{message}\"\n\n"
                "Hãy giải thích khái niệm này một cách dễ hiểu, có cấu trúc như sau:\n"
                "1. **Tên khái niệm** (in đậm)\n"
                "2. Định nghĩa ngắn gọn, súc tích (1-2 câu).\n"
                "3. Công thức tính (nếu có công thức chuẩn; nếu không có thì bỏ qua dòng này).\n"
                "4. Ý nghĩa và cách áp dụng trong đầu tư chứng khoán thực tế (2-3 câu).\n"
                "5. Một câu hỏi phản biện Socratic để người chơi tự suy ngẫm và liên hệ thực tế.\n\n"
                f"Cuối câu trả lời, hãy đính kèm chính xác dòng tuyên bố sau:\n{_DISCLAIMER}"
            )
        elif mode == "plan":
            user_instruction = (
                f"Người chơi muốn xây dựng hoặc tham khảo chiến lược đầu tư: \"{message}\"\n\n"
                "Hãy đề xuất khung chiến lược theo nguyên tắc Socratic:\n"
                "1. **Tên khung chiến lược phù hợp** (in đậm)\n"
                "2. Tiêu chí lựa chọn doanh nghiệp cốt lõi (2-3 gạch đầu dòng).\n"
                "3. Nguyên tắc phân bổ vốn và quản trị rủi ro / dừng lỗ.\n"
                "4. 2 câu hỏi phản biện để người chơi tự đánh giá xem khung này có hợp với mục tiêu, thời gian và khẩu vị rủi ro của mình không.\n\n"
                f"Cuối câu trả lời, hãy đính kèm chính xác dòng tuyên bố sau:\n{_DISCLAIMER}"
            )
        elif mode == "trade_now":
            context_extra = f" (Mã cổ phiếu đang xem xét: {company})" if company else ""
            user_instruction = (
                f"Người chơi đang cân nhắc một quyết định giao dịch: \"{message}\"{context_extra}\n\n"
                "Hãy phản biện quyết định này theo phương pháp Socratic:\n"
                "1. Đặt 2-3 câu hỏi phản biện sắc bén về: lý do vào lệnh, kế hoạch cắt lỗ, tỷ trọng vốn so với tổng danh mục.\n"
                "2. Bài tập thực hành (Coaching Tip): kiểm tra lại thông tin hoặc lập bảng kịch bản giá.\n\n"
                f"Cuối câu trả lời, hãy đính kèm chính xác dòng tuyên bố sau:\n{_DISCLAIMER}"
            )
        else:
            context_extra = f" (Mã cổ phiếu/Doanh nghiệp liên quan: {company})" if company else ""
            user_instruction = (
                f"Người chơi gửi câu hỏi hoặc tình huống: \"{message}\"{context_extra}\n\n"
                "Hãy phản hồi theo phương pháp Socratic:\n"
                "1. Đặt 2-3 câu hỏi phản biện sắc bén giúp người chơi nhìn nhận lại giả định, nguồn thông tin, "
                "mức độ rủi ro và quy trình ra quyết định của mình (mỗi câu hỏi kết thúc bằng '?').\n"
                "2. Một bài tập quy trình (Coaching Tip): bài tập thực hành tư duy cụ thể (ví dụ: viết ra các kịch bản, "
                "kiểm tra lại báo cáo tài chính,... theo định dạng 'Bài tập: ...').\n\n"
                f"Cuối câu trả lời, hãy đính kèm chính xác dòng tuyên bố sau:\n{_DISCLAIMER}"
            )

        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1024,
        )

        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=user_instruction,
                config=config,
            )
        except Exception as exc:
            # Nếu model được cấu hình bị 404 / deprecated, thử tự động fallback về gemini-3.5-flash-lite
            if model_name != "gemini-3.5-flash-lite":
                logger.warning(
                    "Gọi model %s thất bại, tự động thử lại với gemini-3.5-flash-lite: %s",
                    model_name,
                    exc,
                )
                response = await client.aio.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=user_instruction,
                    config=config,
                )
            else:
                raise

        reply_text = response.text.strip() if response and response.text else ""
        if not reply_text:
            return None

        # Đảm bảo có disclaimer ở cuối
        if _DISCLAIMER not in reply_text:
            reply_text = f"{reply_text}\n\n{_DISCLAIMER}"

        return reply_text

    except Exception as exc:
        logger.warning("Gemini mentor fallback call failed: %s", exc)
        return None
