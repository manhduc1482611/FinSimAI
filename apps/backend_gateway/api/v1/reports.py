"""API Báo cáo — Daily Digest & Weekly Report cho user hiện tại.

- ``GET /reports?kind=daily&period=YYYY-MM-DD``: digest của ngày (tạo/lấy).
- ``GET /reports?kind=daily`` (không period): lấy danh sách đã lưu gần đây.
"""

from __future__ import annotations

from datetime import date

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, Query
from models.user import User
from services import report_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def get_reports(
    kind: str = Query("daily", pattern="^(daily|weekly)$"),
    period: date | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if kind == "daily" and period is not None:
        payload = await report_service.build_daily_digest_persisted(
            db, current_user, period
        )
        return {"kind": kind, "period": period.isoformat(), "payload": payload}

    reports = await report_service.get_reports(
        db, current_user.id, kind, limit=limit
    )
    return {"kind": kind, "items": reports}
