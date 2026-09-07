"""Test grounding số liệu (improvement_plan A2.3).

Mọi con số "dữ liệu" trong reply phải tồn tại trong ngữ cảnh; LLM không được
tự tính/bịa số. Số nguyên thuần ≤3 chữ số (liệt kê, ngày, thang điểm, thành ngữ
như "180 độ") là cấu trúc câu chữ, được phép tự do.
"""

from typing import ClassVar

import pytest

from agents.grounding import (
    GroundingError,
    assert_grounded,
    check_grounding,
    extract_numbers,
)


class TestExtractNumbers:
    def test_extracts_integers_and_decimals(self):
        text = "Giá 92.500 đồng, lãi 12,5%, khối lượng 1500000"
        assert extract_numbers(text) == ["92.500", "12,5", "1500000"]

    def test_empty_when_no_number(self):
        assert extract_numbers("Không có con số nào cả.") == []


class TestCheckGrounding:
    def test_invented_price_flagged(self):
        violations = check_grounding(
            "VCB đang ở 92.500 đấy.", "Danh mục: ACB 1000 cổ."
        )
        assert violations == ["92.500"]

    def test_number_present_in_context_passes(self):
        context = "Giá tham chiếu hệ thống ghi nhận: 92500"
        assert check_grounding("Giá đang ở mức 92.500?", context) == []

    def test_separator_equivalence_both_ways(self):
        # Ngữ cảnh viết có dấu chấm ngăn cách, reply viết liền (và ngược lại).
        assert check_grounding("Giá đang ở 92.500 đấy", "Tham chiếu hệ thống: 92500") == []
        assert check_grounding("Khối lượng 1500000", "KLGD: 1.500.000") == []
        # Số thập phân phải khớp đúng giá trị (bỏ dấu ngăn cách).
        assert check_grounding("Tăng 12,5% trong phiên", "Biến động: +12,5%") == []

    def test_decimal_mismatch_flagged(self):
        # 1.5 triệu ≠ 1500000 — số thập phân là dữ liệu, không được tự do.
        violations = check_grounding("Khối lượng 1.5 triệu", "KLGD: 1500000")
        assert violations == ["1.5"]

    def test_small_enumeration_numbers_pass(self):
        # Số liệt kê/thang điểm/ngày là cấu trúc câu chữ, không phải dữ liệu.
        assert check_grounding("Bạn đã viết ra 3 kịch bản chưa?", "") == []
        assert check_grounding("Đánh giá độ tin cậy nguồn tin từ 1-5?", "") == []
        assert check_grounding("Ngày 15 tháng 6 có gì bất thường?", "") == []
        assert check_grounding("Nếu đám đông quay ngoắt 180 độ thì sao?", "") == []

    def test_three_digit_data_number_without_context_passes_but_four_digit_flagged(self):
        # Biên: 3 chữ số = cấu trúc, 4 chữ số trở lên = dữ liệu phải grounding.
        assert check_grounding("Khoảng 500 người cùng mua", "") == []
        violations = check_grounding("Giá về mức 2500 thì sao?", "")
        assert violations == ["2500"]

    def test_invented_percentage_flagged(self):
        violations = check_grounding(
            "Lợi suất kỳ vọng khoảng 18,7% thì sao?",
            "Bối cảnh thị trường: VN-Index đi ngang.",
        )
        assert violations == ["18,7"]

    def test_multiple_violations_collected(self):
        violations = check_grounding("Giá 25000 và KL 30000 nhé", "")
        assert sorted(violations) == ["25000", "30000"]

    def test_user_provided_number_is_valid_context(self):
        # Quote lại số người chơi cung cấp trong tin nhắn là hợp lệ.
        context = 'TIN NHẮN CỦA NGƯỜI CHƠI:\n"Tôi mua VCB ở giá 88000"'
        assert check_grounding("Bạn mua VCB ở 88.000 dựa trên căn cứ nào?", context) == []


class TestAssertGrounded:
    def test_raises_with_details(self):
        with pytest.raises(GroundingError) as exc_info:
            assert_grounded(("Giá về 12345 thì sao?",), context="")
        assert "12345" in str(exc_info.value)

    def test_passes_clean_texts(self):
        assert_grounded(("Bạn có kế hoạch thoát lệnh chưa?", "3 kịch bản"), context="")


def test_grounding_validator_wired_into_agent():
    """Agent sinh validator chặn reply chứa số lạ so với prompt."""
    from agents.socratic_mentor import SocraticMentorAgent

    agent = SocraticMentorAgent()
    prompt = "NGỮ CẢNH PHIÊN:\nGiá tham chiếu 92500\nTIN NHẮN: tôi vừa mua"
    validator = agent._grounding_validator(prompt)

    class _ReplyLike:
        questions: ClassVar[list[str]] = ["Giá về 99999 thì sao?"]
        coaching_tip: ClassVar[str] = "Viết ra 3 kịch bản."

    import pytest as _pytest

    from agents.policy import PolicyViolationError

    with _pytest.raises(PolicyViolationError):
        validator(_ReplyLike())
