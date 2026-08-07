import uuid

from core.dependencies import get_current_user_optional, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.news import News
from models.user import User
from schemas.news import NewsListResponse, NewsResponse
from services import task_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsListResponse)
async def list_news(
    category: str | None = Query(None),
    sentiment: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> NewsListResponse:
    stmt = select(News)
    if category:
        stmt = stmt.where(News.category == category)
    if sentiment:
        stmt = stmt.where(News.sentiment == sentiment)

    stmt = stmt.order_by(News.simulated_at.desc())
    items, total = await paginate(db, stmt, skip, limit)

    return NewsListResponse(
        items=[NewsResponse.model_validate(n) for n in items],
        total=total,
    )


@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> News:
    entry = await db.get(News, news_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="News not found")
    if current_user is not None:
        await task_service.record_event(db, current_user, "news_read")
    return entry
