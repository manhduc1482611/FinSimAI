"""API Bảng xếp hạng — NAV (toàn cầu / theo contest) và Điểm kỷ luật.

Công khai (không bắt buộc token): bất kỳ ai cũng xem được bảng. Khi có token
hợp lệ, response kèm thêm ``my_rank`` (hạng của user hiện tại).
"""

from __future__ import annotations

from uuid import UUID

from core.dependencies import get_current_user_optional, get_db
from fastapi import APIRouter, Depends, Query
from models.user import User
from services import leaderboard_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
async def get_leaderboard(
    kind: str = Query("nav", pattern="^(nav|discipline)$"),
    contest_id: UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user is None:
        return await leaderboard_service.get_rankings(
            db, kind=kind, contest_id=contest_id, limit=limit
        )
    return await leaderboard_service.get_rankings_for_user(
        db,
        current_user.id,
        kind=kind,
        contest_id=contest_id,
        limit=limit,
    )
