"""Deterministic Socratic Mentor Engine — 0 token Gemini.

Port tầng fallback của ``SocraticMentorAgent`` (ai_engine) sang gateway để
WebSocket mentor luôn trả phản hồi Socratic chuẩn mà KHÔNG tốn một lượt Gemini
nào. Question-bank dùng chung nội dung với ``ai_engine/prompts/mentor_prompts.yaml``:

- 8 nhóm thiên kiến tâm lý (FOMO, bầy đàn, loss aversion, ...).
- Phát hiện focus bằng keyword scoring theo ``priority_order``.
- Câu hỏi phản biện + bài tập quy trình + disclaimer, không chứa lời khuyên mua/bán.

Nguyên tắc tuyệt đối: KHÔNG đưa lời khuyên mua/bán, KHÔNG phán xét đúng/sai —
chỉ đặt câu hỏi phản biện. Dữ liệu là hằng số (không có đầu vào AI), nên không
cần quét chính sách runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Thứ tự ưu tiên khi nhiều focus cùng có điểm: giống ai_engine mentor_prompts.yaml.
_PRIORITY_ORDER = [
    "fomo",
    "herding",
    "loss_aversion",
    "overconfidence",
    "anchoring",
    "confirmation_bias",
    "noise_trading",
    "process",
]

# Keyword phát hiện thiên kiến tâm lý (đồng bộ với ai_engine).
_DETECTION: dict[str, list[str]] = {
    "fomo": [
        "fomo",
        "bỏ lỡ",
        "bùng nổ",
        "to the moon",
        "lên không ngừng",
        "tăng vùn vụt",
        "đu theo",
        "ai cũng mua",
        "sóng mới",
        "kẻo hết",
        "sốt",
    ],
    "herding": [
        "nghe theo",
        "cả group",
        "cả room",
        "ai cũng khuyên",
        "admin khuyến nghị",
        "mọi người đều",
        "đám đông",
        "cả hội",
    ],
    "loss_aversion": [
        "đang lỗ",
        "thua lỗ",
        "lỗ sâu",
        "chờ về bờ",
        "gỡ vốn",
        "không nỡ bán",
        "cắt lỗ thì tiếc",
    ],
    "overconfidence": [
        "chắc chắn",
        "chắc thắng",
        "không thể sai",
        "nghiên cứu kỹ rồi",
        "tự tin tuyệt đối",
        "bao giờ cũng đúng",
    ],
    "anchoring": [
        "giá cũ",
        "từng đạt",
        "so với hôm qua",
        "tham chiếu",
        "về mốc",
        "hồi giá cao hơn",
    ],
    "confirmation_bias": [
        "chỉ thấy tin tốt",
        "tìm đủ lý do",
        "ủng hộ quyết định",
        "phớt lờ tin xấu",
        "phân tích đều ủng hộ",
    ],
    "noise_trading": [
        "tin đồn",
        "nghe nói",
        "insider",
        "mai có tin",
        "bí mật",
        "mua ngay bây giờ",
    ],
}

# Question-bank mỗi focus: câu hỏi phản biện + bài tập quy trình + nhãn kiến thức.
_QUESTION_BANK: dict[str, dict[str, Any]] = {
    "fomo": {
        "questions": [
            "Điều gì khiến bạn tin rằng nhịp tăng này sẽ còn tiếp tục, "
            "thay vì chỉ là cơn sóng ngắn hạn?",
            "Nếu tất cả những người đang hào hứng mua trên mạng xã hội đều sai, "
            "bạn sẽ phát hiện ra điều đó bằng cách nào?",
            "Bạn đã chuẩn bị kịch bản xử lý khi giá đi ngược kỳ vọng "
            "ngay sau khi bạn quyết định chưa?",
        ],
        "coaching_tip": (
            "Viết ra 3 kịch bản có thể xảy ra (tăng mạnh, đi ngang, giảm mạnh) kèm "
            "phản ứng của bạn với từng kịch bản, rồi đối chiếu xem kịch bản nào bạn "
            "chưa chuẩn bị."
        ),
    },
    "herding": {
        "questions": [
            "Quyết định của bạn dựa trên phân tích của chính bạn, "
            "hay dựa trên việc nhiều người khác cùng làm giống vậy?",
            "Nếu cộng đồng mạng hôm nay quay ngoắt 180 độ, "
            "bạn sẽ giữ nguyên lập trường hay lật theo họ?",
            "Bạn có thể chỉ ra một điểm yếu trong nhận định phổ biến "
            "mà mọi người đang tin không?",
        ],
        "coaching_tip": (
            "Ghi lại nguồn gốc từng thông tin bạn đang dựa vào: bài báo nào, "
            "bài viết mạng xã hội nào, con số nào. Sau đó đánh dấu xem nguồn nào "
            "là dữ liệu, nguồn nào chỉ là ý kiến của đám đông."
        ),
    },
    "loss_aversion": {
        "questions": [
            "Nếu bạn đang đứng ở vị trí người ngoài nhìn vào danh mục này, "
            "bạn sẽ khuyên người chủ nó xử lý thế nào?",
            "Việc chờ đợi để gỡ vốn có làm quyết định của bạn khách quan hơn không, "
            "hay chỉ khiến bạn đeo đuổi một con số trong quá khứ?",
            "Chi phí cơ hội của việc giữ một vị thế đang lỗ là gì?",
        ],
        "coaching_tip": (
            "Tách hai câu hỏi riêng biệt: (1) giữ hay thoát khỏi vị thế hiện tại, "
            "và (2) mức giá nào bạn từng trả. Viết câu trả lời cho câu (1) "
            "mà không nhắc đến câu (2)."
        ),
    },
    "overconfidence": {
        "questions": [
            "Điều gì có thể khiến nhận định của bạn sai, "
            "dù bạn đã tự tin vào nó?",
            "Bạn có từng đúng mà không phải vì phân tích của mình không?",
            "Nếu buộc phải đặt cược rằng mình sai, bạn sẽ đặt cược vào kịch bản nào "
            "và với xác suất bao nhiêu?",
        ],
        "coaching_tip": (
            "Liệt kê 3 lý do khiến quyết định của bạn có thể thất bại. Nếu không "
            "tìm ra nổi 3 lý do, hãy tự hỏi mình đang thiếu thông tin gì."
        ),
    },
    "anchoring": {
        "questions": [
            "Mức giá bạn đang so sánh được lấy từ đâu, và nó có còn phản ánh "
            "giá trị hiện tại của doanh nghiệp không?",
            "Nếu bạn chưa từng biết mức giá cũ, "
            "bạn sẽ định giá cổ phiếu này như thế nào?",
            "Con số bạn đang bám víu có thay đổi bất kỳ yếu tố cơ bản nào "
            "của công ty không?",
        ],
        "coaching_tip": (
            "Viết ra giá trị bạn ước tính cho cổ phiếu dựa trên báo cáo tài chính "
            "hiện tại, KHÔNG nhìn vào bất kỳ mức giá lịch sử nào. So sánh hai con số "
            "sau khi đã viết xong."
        ),
    },
    "confirmation_bias": {
        "questions": [
            "Bạn đã chủ động tìm kiếm thông tin PHẢN BÁC quyết định của mình, "
            "hay chỉ gom nhặt những gì ủng hộ nó?",
            "Nếu cùng một bài báo mang dấu hiệu tiêu cực, "
            "bạn sẽ đọc kỹ đến đâu?",
            "Lần gần nhất bạn thay đổi quan điểm vì một bằng chứng mới là khi nào?",
        ],
        "coaching_tip": (
            "Tìm 2 nguồn tin trái chiều về cùng một chủ đề và tóm tắt lập luận "
            "của cả hai bên trước khi quyết định."
        ),
    },
    "noise_trading": {
        "questions": [
            "Thông tin bạn vừa nghe có kiểm chứng được từ báo cáo tài chính "
            "hoặc tin tức chính thức không?",
            "Nếu tin đồn đó không bao giờ thành sự thật, "
            "quyết định của bạn dựa trên cái gì?",
            "Bạn có phân biệt được đâu là tín hiệu có giá trị, "
            "đâu chỉ là tiếng ồn của thị trường không?",
        ],
        "coaching_tip": (
            "Với mỗi thông tin bạn định hành động, ghi nguồn gốc và mức độ tin cậy "
            "(1-5). Chỉ xem xét hành động khi nguồn tin đạt độ tin cậy cao "
            "và có thể kiểm chứng."
        ),
    },
    "process": {
        "questions": [
            "Trước khi hành động, bạn đã xác định giới hạn chịu lỗ và mục tiêu "
            "của quyết định này chưa?",
            "Thông tin bạn đang dựa vào đến từ đâu, và độ tin cậy của nó "
            "được kiểm chứng bằng cách nào?",
            "Nếu quyết định này thất bại, hậu quả lớn nhất là gì "
            "và bạn có kế hoạch xử lý không?",
        ],
        "coaching_tip": (
            "Viết ra câu trả lời cho 3 câu hỏi: tôi hành động vì lý do gì, "
            "nguồn thông tin đó đáng tin cậy ở mức nào, và tôi sẽ làm gì "
            "nếu mọi thứ ngược lại với kỳ vọng."
        ),
    },
}

_DISCLAIMER = (
    "FinSimAI là môi trường mô phỏng. Tôi không đưa ra lời khuyên mua bán — "
    "tôi chỉ giúp bạn phản biện quyết định của chính mình."
)


class SocraticFocus(str, Enum):
    """Thiên kiến tâm lý mà lượt hỏi đang hướng tới."""

    FOMO = "fomo"
    HERDING = "herding"
    LOSS_AVERSION = "loss_aversion"
    OVERCONFIDENCE = "overconfidence"
    ANCHORING = "anchoring"
    CONFIRMATION_BIAS = "confirmation_bias"
    NOISE_TRADING = "noise_trading"
    PROCESS = "process"


@dataclass(frozen=True)
class SocraticReply:
    """Phản hồi Socratic deterministic — chỉ chứa câu hỏi phản biện."""

    focus: SocraticFocus
    questions: tuple[str, ...]
    coaching_tip: str
    disclaimer: str = _DISCLAIMER


def detect_focus(text: str) -> SocraticFocus:
    """Phát hiện thiên kiến tâm lý theo keyword scoring + priority order."""
    haystack = text.lower()
    scores = {
        focus: sum(1 for keyword in keywords if keyword in haystack)
        for focus, keywords in _DETECTION.items()
    }
    best_key = max(
        _PRIORITY_ORDER,
        key=lambda key: (scores.get(key, 0), -_PRIORITY_ORDER.index(key)),
    )
    if scores.get(best_key, 0) == 0:
        return SocraticFocus.PROCESS
    return SocraticFocus(best_key)


def _render(template: str, *, company: str) -> str:
    if company:
        return template.replace("{{company}}", company)
    return template


def socratic_reply(message: str, company: str = "") -> SocraticReply:
    """Soạn phản hồi Socratic deterministic cho tin nhắn (0 token Gemini)."""
    focus = detect_focus(message or "")
    bank = _QUESTION_BANK[focus.value]
    questions = tuple(
        _render(q, company=company) for q in bank["questions"]
    )
    coaching_tip = _render(bank["coaching_tip"], company=company)
    return SocraticReply(
        focus=focus,
        questions=questions,
        coaching_tip=coaching_tip,
    )


def reply_to_text(reply: SocraticReply) -> str:
    """Chuyển phản hồi có cấu trúc thành văn bản để stream chunk."""
    lines = [*reply.questions, "", f"Bài tập: {reply.coaching_tip}", "", reply.disclaimer]
    return "\n".join(lines)
