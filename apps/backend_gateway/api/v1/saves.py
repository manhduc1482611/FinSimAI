import uuid

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, Query
from models.news import News
from models.saves import ContentSave
from models.social import SocialPost
from models.user import User
from schemas.news import NewsResponse
from schemas.saves import (
    ContentSaveToggleRequest,
    ContentSaveToggleResponse,
    SavedContentItem,
    SavedContentListResponse,
)
from schemas.social import SocialPostResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/saves", tags=["saves"])


async def saved_content_ids(
    db: AsyncSession,
    user_id: uuid.UUID,
    content_type: str | None = None,
) -> set[uuid.UUID]:
    """Trả tập hợp content_id đã lưu của user (theo loại nếu có), dùng chung cho
    các endpoint list news/social để đánh dấu is_saved."""
    stmt = select(ContentSave.content_id).where(ContentSave.user_id == user_id)
    if content_type:
        stmt = stmt.where(ContentSave.content_type == content_type)
    result = await db.execute(stmt)
    return set(result.scalars().all())


@router.post("/toggle", response_model=ContentSaveToggleResponse)
async def toggle_save(
    body: ContentSaveToggleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContentSaveToggleResponse:
    stmt = select(ContentSave).where(
        ContentSave.user_id == user.id,
        ContentSave.content_type == body.content_type,
        ContentSave.content_id == body.content_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is None:
        db.add(
            ContentSave(
                user_id=user.id,
                content_type=body.content_type,
                content_id=body.content_id,
            )
        )
        await db.commit()
        return ContentSaveToggleResponse(saved=True)

    await db.execute(delete(ContentSave).where(ContentSave.id == existing.id))
    await db.commit()
    return ContentSaveToggleResponse(saved=False)


@router.get("", response_model=SavedContentListResponse)
async def list_saves(
    content_type: str | None = Query(None, pattern="^(news|social)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SavedContentListResponse:
    total_stmt = select(func.count()).select_from(ContentSave).where(
        ContentSave.user_id == user.id
    )
    if content_type:
        total_stmt = total_stmt.where(ContentSave.content_type == content_type)
    total = (await db.execute(total_stmt)).scalar_one()

    stmt = (
        select(ContentSave)
        .where(ContentSave.user_id == user.id)
        .order_by(ContentSave.created_at.desc())
    )
    if content_type:
        stmt = stmt.where(ContentSave.content_type == content_type)
    stmt = stmt.offset(skip).limit(limit)
    saves = (await db.execute(stmt)).scalars().all()

    news_ids = [s.content_id for s in saves if s.content_type == "news"]
    social_ids = [s.content_id for s in saves if s.content_type == "social"]

    news_map: dict[uuid.UUID, NewsResponse] = {}
    social_map: dict[uuid.UUID, SocialPostResponse] = {}
    if news_ids:
        news_rows = (
            await db.execute(select(News).where(News.id.in_(news_ids)))
        ).scalars().all()
        news_map = {n.id: NewsResponse.model_validate(n) for n in news_rows}
    if social_ids:
        social_rows = (
            await db.execute(select(SocialPost).where(SocialPost.id.in_(social_ids)))
        ).scalars().all()
        social_map = {p.id: SocialPostResponse.model_validate(p) for p in social_rows}

    items = []
    for s in saves:
        resp = SavedContentItem(
            content_type=s.content_type,
            content_id=s.content_id,
            saved_at=s.created_at,
        )
        if s.content_type == "news":
            resp.news = news_map.get(s.content_id)
        elif s.content_type == "social":
            resp.social = social_map.get(s.content_id)
        items.append(resp)

    return SavedContentListResponse(items=items, total=total)
