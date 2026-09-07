"""Mentor REST API của gateway — lịch sử hội thoại (improvement_plan A3.2).

Trước đây history chỉ nằm phía client (mất khi reload). Giờ ``mentor_messages``
trong DB là nguồn chuẩn: client gọi ``GET /mentor/history`` khi mở panel để
thấy lại hội thoại cũ; LLM cũng lấy 12 tin gần nhất từ cùng nguồn.
"""

from __future__ import annotations

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.mentor import MentorMessage
from models.user import User
from services.mentor_history import to_api_dicts
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.get("/history")
async def get_mentor_history(
    session_id: str | None = Query(None, description="Lọc theo 1 phiên cụ thể"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Tin nhắn mentor gần nhất của user (cũ → mới) để phục hồi hội thoại."""
    conditions = [MentorMessage.user_id == current_user.id]
    if session_id:
        conditions.append(MentorMessage.session_id == session_id)

    total_stmt = select(func.count()).select_from(MentorMessage).where(*conditions)
    total = (await db.execute(total_stmt)).scalar() or 0

    stmt = (
        select(MentorMessage)
        .where(*conditions)
        .order_by(MentorMessage.created_at.desc(), MentorMessage.id.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()

    return {"items": to_api_dicts(rows), "total": total}


@router.get("/history/{session_id}")
async def get_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Toàn bộ tin nhắn của một phiên (cũ → mới); chặn đọc phiên người khác."""
    stmt = (
        select(MentorMessage)
        .where(MentorMessage.user_id == current_user.id, MentorMessage.session_id == session_id)
        .order_by(MentorMessage.created_at.asc(), MentorMessage.id.asc())
        .limit(500)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return {"items": to_api_dicts(rows), "total": len(rows)}
