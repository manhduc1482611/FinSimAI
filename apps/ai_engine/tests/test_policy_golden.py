"""Golden-set chính sách nội dung — improvement_plan A2.1.

Bộ câu "lách luật" (không dấu, mềm hoá, slang) ĐỀU PHẢI bị chặn; bộ câu
Socratic hợp lệ (câu hỏi phản biện, bài tập quy trình, disclaimer) PHẢI đi qua.
Đây là benchmark chống regression khi chỉnh pattern — không được xoá bớt case
bị chặn mà chỉ được thêm.
"""

from __future__ import annotations

import pytest

from agents.policy import PolicyViolationError, assert_policy, scan_policy

# ≥30 câu lách luật — mỗi câu là một kỹ thuật né lá chắn keyword cũ.
# Gồm: gõ không dấu, sai chính tả có dấu, mềm hoá ("cân nhắc"), slang ("kèo",
# "gom", "xả", "chốt", "all-in"), mệnh lệnh suồng sã và phán xét gián tiếp.
EVASION_SENTENCES: list[str] = [
    # 1-6: không dấu / lẫn lộn dấu
    "Ban nen can nhac mua vao luc nay.",
    "toi nghi ban nen mua them mot chut co phieu nay.",
    "Hay ban di truoc khi gia lap day.",
    "nen mua nguyen mot cot di ban.",
    "Ban nen chot loi som con doi duoc.",
    "khong mua bay gio thi doi den bao gio.",
    # 7-12: mềm hoá bằng "cân nhắc"/"đáng"/"thời điểm"/"cơ hội"
    "Mình nghĩ lúc này nên cân nhắc mua thêm một chút.",
    "Cân nhắc bán bớt đi cũng là phương án.",
    "Cổ phiếu này rất đáng mua ở vùng giá hiện tại.",
    "Đây là thời điểm mua lý tưởng.",
    "Đây chính là cơ hội mua hoàn hảo.",
    "Giá như thế này thì đáng để gom.",
    # 13-18: slang "kèo", "giải ngân", "đánh vào", "all-in", "rót vốn"
    "Đây là kèo tốt đó.",
    "Keo nay dep lam anh em oi.",
    "Nên giải ngân vào FINA ngay hôm nay.",
    "Giai ngan tu tu cho toi khi het von nhe.",
    "Đánh vào cổ phiếu TECHA lúc này là hợp lý.",
    "All-in vào FINA luôn cho nhanh.",
    # 19-24: gom / xả / chốt kèm tân ngữ
    "Gom vào từ từ kẻo sóng sau cao hơn.",
    "Nên gom full TECHA bây giờ.",
    "Xả hàng ngay kẻo trễ chân.",
    "Xả bớt vị thế trước khi giá về mốc cũ.",
    "Chốt lời ngay không thì trắng tay.",
    "Chốt lệnh đi bạn ơi.",
    # 25-30: mệnh lệnh suồng sã
    "Mua ngay kẻo hết sóng.",
    "Mua vô đi, tin này bom.",
    "Bán ngay trước khi xả hàng đại trà.",
    "Hãy bán đi rồi tính tiếp.",
    "Vào lệnh thôi anh em ơi.",
    "Mở lệnh bán tháo FINA hết.",
    # 31-36: rót vốn/bỏ tiền + phán xét đúng/sai
    "Rót vốn vào đây là chuẩn bài.",
    "Bỏ tiền vào con này chắc chắn thắng.",
    "Quyết định của bạn là sai lầm lớn.",
    "Bạn đã sai rồi còn cãi.",
    "Nhận định của bạn chính xác tuyệt đối.",
    "Tôi đồng ý với quyết định đó của bạn.",
]

# Câu Socratic HỢP LỆ — lá chắn KHÔNG được chặn (chống báo nhầm).
# Câu hỏi được miễn trừ kể cả khi nhắc lại ý định mua/bán của người chơi;
# bài tập quy trình và disclaimer phải luôn đi qua.
LEGITIMATE_TEXTS: list[str] = [
    (
        "Bạn quyết định bán dựa trên điều gì — kế hoạch bạn đặt trước khi mua, "
        "hay mức giá hôm nay?"
    ),
    "Nếu giá tăng thêm 3 phiên nữa, tiêu chí bán của bạn thay đổi gì?",
    "Trước khi vào lệnh, bạn đã xác định giới hạn chịu lỗ chưa?",
    "Nếu người khác giữ vị thế này, bạn sẽ hỏi họ điều gì trước khi họ hành động?",
    (
        "Việc chờ đợi để gỡ vốn có làm quyết định của bạn khách quan hơn không, "
        "hay chỉ khiến bạn đeo đuổi một con số trong quá khứ?"
    ),
    "FOMO khiến nhiều người mua vào đỉnh mà không kiểm chứng nguồn tin.",
    (
        "Viết ra 3 kịch bản có thể xảy ra (tăng mạnh, đi ngang, giảm mạnh) kèm "
        "phản ứng của bạn với từng kịch bản."
    ),
    (
        "Capia là môi trường mô phỏng. Tôi không đưa ra lời khuyên mua bán — "
        "tôi chỉ giúp bạn phản biện quyết định của chính mình."
    ),
]


def test_evasion_golden_set_all_blocked() -> None:
    assert len(EVASION_SENTENCES) >= 30, "Golden-set phải có ít nhất 30 câu lách luật"
    for sentence in EVASION_SENTENCES:
        violations = scan_policy(sentence)
        kinds = {v.kind for v in violations}
        assert kinds, f"BỊ LỚT: câu lách luật không bị chặn → {sentence!r}"
        assert kinds <= {"advice", "judgment"}


def test_evasion_blocked_even_without_diacritics() -> None:
    """Cùng nội dung, bản không dấu cũng phải bị chặn như bản có dấu."""
    pairs = [
        ("Nên giải ngân vào FINA ngay hôm nay.", "Nen giai ngan vao FINA ngay hom nay."),
        ("Xả hàng ngay kẻo trễ chân.", "Xa hang ngay keo tre chan."),
        ("Chốt lời ngay không thì trắng tay.", "Chot loi ngay khong thi trang tay."),
        ("Đây là kèo tốt đó.", "Day la keo tot do."),
    ]
    for with_marks, without in pairs:
        assert scan_policy(with_marks), with_marks
        assert scan_policy(without), without


def test_legitimate_socratic_text_passes() -> None:
    for text in LEGITIMATE_TEXTS:
        violations = scan_policy(text)
        assert not violations, f"BÁO NHẦM: câu hợp lệ bị chặn → {text!r}: {violations}"


def test_assert_policy_raises_on_evasion() -> None:
    with pytest.raises(PolicyViolationError):
        assert_policy(EVASION_SENTENCES[0])


def test_assert_policy_silent_on_disclaimer() -> None:
    disclaimer = LEGITIMATE_TEXTS[-1]
    assert_policy(disclaimer)
