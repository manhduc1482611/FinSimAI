import uuid

from core.dependencies import get_current_user_optional, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.news import News
from models.user import User
from realtime.simtime import sim_now
from schemas.news import NewsListResponse, NewsResponse
from services import task_service
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate
from api.v1.saves import saved_content_ids

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsListResponse)
async def list_news(
    category: str | None = Query(None),
    sentiment: str | None = Query(None),
    q: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> NewsListResponse:
    # As-of filter (chống look-ahead): nội dung sinh trước/lên lịch phát hành sau
    # chỉ xuất hiện khi simulated_at <= mốc hiện tại của thế giới mô phỏng.
    stmt = select(News).where(News.simulated_at <= sim_now())
    if category:
        stmt = stmt.where(News.category == category)
    if sentiment:
        stmt = stmt.where(News.sentiment == sentiment)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                News.title.ilike(pattern),
                News.summary.ilike(pattern),
                News.content.ilike(pattern),
            )
        )

    stmt = stmt.order_by(News.simulated_at.desc())
    items, total = await paginate(db, stmt, skip, limit)

    saved_ids = (
        await saved_content_ids(db, current_user.id, "news")
        if current_user is not None
        else set()
    )
    responses = []
    for n in items:
        item = NewsResponse.model_validate(n)
        item.is_saved = n.id in saved_ids
        responses.append(item)

    return NewsListResponse(items=responses, total=total)


@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> News:
    entry = await db.get(News, news_id)
    if not entry or entry.simulated_at > sim_now():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
    if current_user is not None:
        await task_service.record_event(db, current_user, "news_read")
    return entry
