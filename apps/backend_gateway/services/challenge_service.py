"""Daily Challenge — thử thách kỹ năng/kỷ luật hằng ngày, thưởng + điểm kỷ luật.

- ``list_challenges``: thử thách của 1 ngày kèm trạng thái hoàn thành của user.
- ``verify_and_complete``: xác minh điều kiện (target JSON), credit reward +
  +2 điểm kỷ luật (thể hiện cam kết học/đọc bài tập), idempotent (1 lần).

Mentor periodic question: tận dụng luồng mentor_messages — endpoint riêng trả
câu hỏi khi đến hạn theo chu kỳ ảo (xem api/v1/challenges).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from core.config import settings
from models.challenge import DailyChallenge, UserDailyChallenge
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CHALLENGE_KEYS = frozenset({"trade", "read_knowledge", "disciplined"})

# Thưởng mặc định + điểm kỷ luật khi hoàn thành thử thách.
DISCIPLINE_REWARD_PER_CHALLENGE = 2


def _today() -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(settings.app_timezone)).date()


async def list_challenges(
    db: AsyncSession, user: User, day: date | None = None
) -> dict:
    day = day or _today()
    challenges = (
        await db.execute(
            select(DailyChallenge)
            .where(
                DailyChallenge.is_active.is_(True),
                DailyChallenge.challenge_date == day,
            )
            .order_by(DailyChallenge.code)
        )
    ).scalars().all()
    done = (
        await db.execute(
            select(UserDailyChallenge).where(UserDailyChallenge.user_id == user.id)
        )
    ).scalars().all()
    done_ids = {c.challenge_id for c in done}
    return {
        "period": day.isoformat(),
        "items": [
            {
                "id": c.id,
                "code": c.code,
                "title": c.title,
                "description": c.description,
                "reward_amount": str(c.reward_amount),
                "completed": c.id in done_ids,
            }
            for c in challenges
        ],
    }


async def complete_challenge(
    db: AsyncSession, user: User, challenge_id: object
) -> dict:
    challenge = await db.get(DailyChallenge, challenge_id)
    if challenge is None or not challenge.is_active:
        raise ValueError("Thử thách không tồn tại hoặc đã tắt")

    existing = (
        await db.execute(
            select(UserDailyChallenge).where(
                UserDailyChallenge.user_id == user.id,
                UserDailyChallenge.challenge_id == challenge.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "success": True,
            "already_completed": True,
            "reward_earned": str(existing.reward_earned),
        }

    # Credit reward + 2 điểm kỷ luật.
    locked_user = (
        await db.execute(select(User).where(User.id == user.id).with_for_update())
    ).scalar_one()
    locked_user.cash_balance = (locked_user.cash_balance or Decimal("0.00")) + challenge.reward_amount

    try:
        from services.discipline_service import apply_discipline

        await apply_discipline(
            db, locked_user, "daily_checkin",
            context={"challenge": challenge.code},
        )
    except Exception:
        logger.exception("Thưởng điểm kỷ luật thử thách thất bại (không chặn)")

    record = UserDailyChallenge(
        user_id=user.id,
        challenge_id=challenge.id,
        completed_at=datetime.now(timezone.utc),
        reward_earned=challenge.reward_amount,
    )
    db.add(record)
    await db.commit()
    return {
        "success": True,
        "already_completed": False,
        "reward_earned": str(challenge.reward_amount),
    }
