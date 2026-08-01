"""Test Socratic Mentor Agent — nguyên tắc tuyệt đối không Mua/Bán, không Đúng/Sai."""

import pytest
from pydantic import ValidationError

from agents.policy import PolicyViolationError, assert_policy, scan_policy
from agents.socratic_mentor import (
    MentorContext,
    SocraticFocus,
    SocraticMentorAgent,
    SocraticReply,
)
from integrations.gemini import GeminiClient, GeminiUnavailableError


@pytest.fixture(scope="module")
def agent() -> SocraticMentorAgent:
    return SocraticMentorAgent()


class TestGeminiAvailability:
    def test_unavailable_without_key(self):
        client = GeminiClient()
        assert client.available is False

    def test_generate_structured_raises_unavailable(self):
        client = GeminiClient()
        with pytest.raises(GeminiUnavailableError):
            client.generate_structured(
                SocraticReply,
                system_instruction="x",
                user_content="y",
            )


class TestPolicyScanner:
    def test_allows_pure_questions(self):
        violations = scan_policy(
            "Bạn có kế hoạch cắt lỗ chưa?",
            "Điều gì khiến bạn nghĩ giá sẽ tăng?",
        )
        assert violations == []

    def test_flags_direct_buy_advice(self):
        violations = scan_policy("Bạn nên mua cổ phiếu này ngay hôm nay.")
        assert any(v.kind == "advice" for v in violations)

    def test_flags_direct_sell_advice(self):
        violations = scan_policy("Hãy bán toàn bộ để bảo toàn vốn.")
        assert any(v.kind == "advice" for v in violations)

    def test_flags_right_wrong_judgment(self):
        violations = scan_policy("Quyết định này của bạn là đúng.")
        assert any(v.kind == "judgment" for v in violations)
        violations = scan_policy("Bạn sai rồi, không nên như vậy.")
        assert any(v.kind == "judgment" for v in violations)

    def test_exempts_question_mentioning_buy(self):
        # Mentor được phép NHẮC LẠI ý định mua/bán của người chơi trong câu hỏi.
        violations = scan_policy("Bạn định mua vì lý do gì?")
        assert violations == []

    def test_assert_policy_raises(self):
        with pytest.raises(PolicyViolationError):
            assert_policy("Bạn nên bán cổ phiếu này ngay.")
        assert_policy("Bạn đã xác định giới hạn chịu lỗ chưa?")


class TestSocraticReplySchema:
    def test_rejects_empty_questions(self):
        with pytest.raises(ValidationError):
            SocraticReply(
                focus=SocraticFocus.PROCESS,
                questions=[],
                coaching_tip="tip",
            )

    def test_rejects_more_than_3_questions(self):
        reply = SocraticReply(
            focus=SocraticFocus.PROCESS,
            questions=["q1", "q2", "q3", "q4"],
            coaching_tip="tip",
        )
        assert len(reply.questions) == 3

    def test_normalizes_missing_question_mark(self):
        reply = SocraticReply(
            focus=SocraticFocus.PROCESS,
            questions=["Bạn có kế hoạch chưa"],
            coaching_tip="tip",
        )
        assert reply.questions == ["Bạn có kế hoạch chưa?"]

    def test_rejects_advice_in_questions(self):
        with pytest.raises(PolicyViolationError):
            SocraticReply(
                focus=SocraticFocus.PROCESS,
                questions=["Bạn nên mua cổ phiếu này ngay."],
                coaching_tip="tip",
            )

    def test_rejects_advice_in_coaching_tip(self):
        with pytest.raises(PolicyViolationError):
            SocraticReply(
                focus=SocraticFocus.PROCESS,
                questions=["Bạn có kế hoạch chưa?"],
                coaching_tip="Nên cắt lỗ ngay lập tức.",
            )


class TestFallback:
    @pytest.mark.parametrize(
        "message,expected_focus",
        [
            ("Mã này tăng vùn vụt, không mua là bỏ lỡ!", SocraticFocus.FOMO),
            ("Cả group đều khuyên mua, tôi nghe theo thôi", SocraticFocus.HERDING),
            ("Tôi đang lỗ sâu, cứ chờ về bờ vậy", SocraticFocus.LOSS_AVERSION),
            ("Tôi chắc chắn không thể sai, đã nghiên cứu kỹ rồi", SocraticFocus.OVERCONFIDENCE),
            ("Giá từng đạt 100, giờ mới 40, quá rẻ", SocraticFocus.ANCHORING),
            ("Tôi chỉ thấy tin tốt, mọi phân tích đều ủng hộ", SocraticFocus.CONFIRMATION_BIAS),
            ("Nghe nói mai có tin, mua ngay bây giờ", SocraticFocus.NOISE_TRADING),
            ("Tôi đang phân vân giữa hai phương án", SocraticFocus.PROCESS),
        ],
    )
    def test_focus_detection(self, agent, message, expected_focus):
        reply = agent.generate(message)
        assert reply.focus == expected_focus

    def test_fallback_output_is_policy_safe(self, agent):
        reply = agent.generate("Không mua là bỏ lỡ cơ hội!", MentorContext(company="ACB"))
        # Mọi câu trả lời của fallback phải vượt qua chính sách (đã kiểm qua schema,
        # nhưng kiểm lại trực tiếp để chắc chắn).
        assert scan_policy(*reply.questions, reply.coaching_tip) == []
        for question in reply.questions:
            assert question.endswith("?")

    def test_fallback_deterministic(self, agent):
        message = "Tôi đang lỗ, chờ về bờ"
        first = agent.generate(message)
        second = agent.generate(message)
        assert first.questions == second.questions
        assert first.coaching_tip == second.coaching_tip

    def test_fallback_sets_disclaimer(self, agent):
        reply = agent.generate("test")
        assert reply.disclaimer.startswith("FinSimAI là môi trường mô phỏng")
