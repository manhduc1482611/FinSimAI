"""Điểm kỷ luật (Discipline Score) — thưởng/quản trị HÀNH VI, không phải lợi nhuận.

Nguyên tắc cốt lõi (từ bản kế hoạch kinh doanh FinSimAI):
    - CỘNG điểm khi user thể hiện kỷ luật & quản trị rủi ro:
      check-in đều, giữ kỷ luật khi có bài học, hoàn thành phản tư sau cooldown.
    - TRỪ điểm khi user hành động theo cảm xúc / vi phạm giới hạn:
      vi phạm cooldown (FOMO/panic/pump-dump... ), tần suất giao dịch bất thường.
    - KHÔNG bao giờ thay đổi điểm theo lãi/lỗ (không thưởng profit ảo).

Điểm clamp 0–100, khởi điểm 90, mọi thay đổi ghi vào ``discipline_score_history``.
Các hàm ghi điểm đều cần user đã được lock (with_for_update) trước đó, và giao
việc commit cho caller.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from models.discipline import DisciplineScoreHistory
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

DISCIPLINE_START = 90
DISCIPLINE_MIN = 0
DISCIPLINE_MAX = 100

# Lý do — hằng số dùng chung để API/leaderboard tra cứu.
R_CHECKIN_DAILY = "daily_checkin"
R_REFLECTION = "mentor_reflection"
R_VIOLATION = "penalty_violation"
R_WIDE_LOSSES = "disciplined_loss_tolerance"
R_NO_STOP = "no_stop_loss"


@dataclass(frozen=True)
class DisciplineRule:
    """Quy tắc cộng/trừ điểm + min/max delta để chống thao túng hoặc spamming."""

    reason: str
    delta: int
    min: int = -100
    max: int = 100


RULES: dict[str, DisciplineRule] = {
    R_CHECKIN_DAILY: DisciplineRule(R_CHECKIN_DAILY, delta=1),
    R_REFLECTION: DisciplineRule(R_REFLECTION, delta=5),
    R_VIOLATION: DisciplineRule(R_VIOLATION, delta=-8, min=-8),
    R_NO_STOP: DisciplineRule(R_NO_STOP, delta=-3, min=-3),
}


def clamp(value: int) -> int:
    return max(DISCIPLINE_MIN, min(DISCIPLINE_MAX, value))


async def apply_discipline(
    db: AsyncSession,
    user: User,
    rule_key: str,
    context: dict[str, Any] | None = None,
) -> int:
    """Áp dụng một quy tắc điểm kỷ luật lên user (đã lock) và ghi history.

    Trả về ``score_delta`` đã áp dụng (sau clamp). Caller tự commit.
    """
    rule = RULES.get(rule_key)
    if rule is None:
        logger.warning("Discipline rule không tồn tại: %s", rule_key)
        return 0

    delta = max(rule.min, min(rule.max, rule.delta))
    before = user.discipline_score
    user.discipline_score = clamp(before + delta)
    applied = user.discipline_score - before

    db.add(
        DisciplineScoreHistory(
            user_id=user.id,
            score_delta=applied,
            reason=rule.reason,
            context=context,
        )
    )
    return applied


async def current_discipline(db: AsyncSession, user: User) -> dict[str, Any]:
    """Trả về thông tin điểm kỷ luật hiện tại của user."""
    return {
        "discipline_score": user.discipline_score,
        "discipline_start": DISCIPLINE_START,
        "discipline_max": DISCIPLINE_MAX,
    }
