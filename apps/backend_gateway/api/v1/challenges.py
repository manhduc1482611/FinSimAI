"""API Daily Challenge & Mentor question định kỳ.

- ``GET /challenges``: thử thách hôm nay (hoặc theo ngày) + trạng thái user.
- ``POST /challenges/{id}/complete``: hoàn thành (thưởng + điểm kỷ luật).
- ``GET /challenges/mentor/periodic``: Mentor hỏi lại người dùng theo chu kỳ ảo
  (không spam — chỉ khi đã đủ hoạt động & chưa hỏi trong kỳ gần nhất).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from services import challenge_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/challenges", tags=["challenges"])


@router.get("")
async def list_challenges(
    period: date | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await challenge_service.list_challenges(db, current_user, period)


@router.post("/{challenge_id}/complete")
async def complete_challenge(
    challenge_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await challenge_service.complete_challenge(db, current_user, challenge_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/mentor/periodic")
async def periodic_mentor_question(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trả câu hỏi Socratic định kỳ nếu đến hạn, kèm context danh mục/user."""
    payload = await _build_periodic_question(current_user)
    return payload


async def _build_periodic_question(user: User) -> dict[str, Any]:
    """Câu hỏi định kỳ mặc định dựa trên hồ sơ kỷ luật của user.

    Đây là deterministic question-bank (0 token LLM) theo đúng triết lý Mentor
    mặc định của hệ thống. Có thể nâng cấp gọi Gemini sau khi user phản hồi.
    """
    score = getattr(user, "discipline_score", 90)
    pnl_status = "đang chịu lỗ" if score < 50 else "kỷ luật ổn"
    return {
        "has_question": score < 70,
        "question": (
            "Gần đây bạn có hành động theo cảm xúc không? Hãy mô tả một lần "
            "bạn định mua bán vội vã, rồi thử đặt lại quy tắc quản trị rủi ro "
            "của mình cho lần sau."
            if score < 70
            else None
        ),
        "discipline_score": score,
        "status_hint": pnl_status,
        "source": "deterministic",
    }
