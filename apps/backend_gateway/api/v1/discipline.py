"""API Điểm kỷ luật — điểm hiện tại + lịch sử (audit).

Discipline Score thưởng hành vi kỷ luật (check-in đều, phản tư sau cooldown)
và trừ khi vi phạm — KHÔNG phụ thuộc lãi/lỗ. Frontend dùng để hiển thị badge,
mở khoá thử thách và giữ người dùng quay lại đều đặn.
"""

from __future__ import annotations

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.discipline import DisciplineScoreHistory
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/discipline", tags=["discipline"])


@router.get("/me")
async def get_my_discipline(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    history_stmt = (
        select(DisciplineScoreHistory)
        .where(DisciplineScoreHistory.user_id == current_user.id)
        .order_by(DisciplineScoreHistory.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(history_stmt)).scalars().all()

    return {
        "discipline_score": current_user.discipline_score,
        "history": [
            {
                "delta": h.score_delta,
                "reason": h.reason,
                "context": h.context,
                "created_at": h.created_at,
            }
            for h in rows
        ],
    }
