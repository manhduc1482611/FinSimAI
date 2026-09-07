"""Golden-set eval suite cho Socratic Mentor (improvement_plan A2.4).

Mỗi case trong ``tests/golden/mentor_golden.yaml`` là một hội thoại chuẩn:
input (message + context) → kỳ vọng HÀNH VI (không phải câu chữ cố định):
- pass policy scanner,
- đúng schema SocraticReply (1–3 câu hỏi kết thúc "?"),
- focus thuộc tập chấp nhận,
- không chứa số dữ liệu ngoài context/message (grounding),
- luôn kèm disclaimer môi trường mô phỏng.

Suite ép chạy đường DETERMINISTIC (0 token) để CI ổn định; khi đổi prompt/
model/threshold chỉ cần chạy lại bộ này để phát hiện regression hành vi.

Chạy riêng: ``pytest apps/ai_engine -m golden``.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from agents.grounding import check_grounding
from agents.policy import scan_policy
from agents.socratic_mentor import MentorContext, SocraticMentorAgent
from integrations.gemini import GeminiClient, GeminiConfig

GOLDEN_FILE = Path(__file__).parent / "golden" / "mentor_golden.yaml"

pytestmark = pytest.mark.golden


def _load_cases() -> list[dict[str, Any]]:
    with GOLDEN_FILE.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise TypeError(f"Golden YAML hỏng: {GOLDEN_FILE}")
    return data["cases"]


CASES = _load_cases()
CASE_IDS = [case["id"] for case in CASES]


@pytest.fixture(scope="module")
def agent() -> SocraticMentorAgent:
    # Ép deterministic: key rỗng → gemini.available False bất kể .env máy dev.
    client = GeminiClient(config=GeminiConfig(gemini_api_key=""))
    assert client.available is False, (
        "Golden suite phải chạy deterministic — kiểm tra lại GeminiConfig."
    )
    return SocraticMentorAgent(gemini=client)


class TestGoldenSetIntegrity:
    def test_at_least_50_cases(self):
        assert len(CASES) >= 50, f"Golden set phải ≥50 case, hiện {len(CASES)}"

    def test_unique_ids(self):
        duplicates = {i for i in CASE_IDS if CASE_IDS.count(i) > 1}
        assert duplicates == set(), f"ID trùng lặp: {duplicates}"

    def test_every_case_has_expect_focus(self):
        for case in CASES:
            assert isinstance(case["expect"]["focus"], list), case["id"]
            assert case["expect"]["focus"], case["id"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
class TestGoldenBehavior:
    def _context(self, case: dict[str, Any]) -> MentorContext:
        payload = case.get("context") or {}
        return MentorContext(
            company=payload.get("company"),
            market_context=payload.get("market_context", ""),
            portfolio=payload.get("portfolio", ""),
        )

    def test_behavior_contract(self, agent: SocraticMentorAgent, case: dict[str, Any]):
        message: str = case["message"]
        ctx = self._context(case)
        expect = case["expect"]

        reply = agent.generate(message, ctx)

        # 1. Schema + cấu trúc.
        assert 1 <= len(reply.questions) <= 3, case["id"]
        for question in reply.questions:
            assert question.endswith("?"), f"{case['id']}: '{question}'"
            assert question.strip() == question, case["id"]
        assert len(reply.concepts) >= 1, case["id"]

        # 2. Chính sách tuyệt đối.
        violations = scan_policy(*reply.questions, reply.coaching_tip)
        assert violations == [], f"{case['id']}: {[v.kind for v in violations]}"

        # 3. Focus thuộc tập chấp nhận.
        assert reply.focus.value in expect["focus"], (
            f"{case['id']}: focus={reply.focus.value}, chấp nhận={expect['focus']}"
        )

        # 4. Grounding số liệu: mọi số trong reply phải có trong context+message
        #    (số cấu trúc ≤3 chữ số như '3 kịch bản', '1-5', '180 độ' tự do).
        grounding_source = f"{ctx.to_text()}\n{message}"
        reply_text = "\n".join([*reply.questions, reply.coaching_tip])
        ungrounded = check_grounding(reply_text, grounding_source)
        assert ungrounded == [], f"{case['id']}: số lạ {ungrounded}"

        # 5. Disclaimer luôn hiện diện.
        assert reply.disclaimer.startswith("Capia"), case["id"]
