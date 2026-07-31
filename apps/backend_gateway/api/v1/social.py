import uuid

from core.dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.social import SocialPost
from schemas.social import SocialPostListResponse, SocialPostResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/social", tags=["social"])


@router.get("", response_model=SocialPostListResponse)
async def list_social_posts(
    persona_type: str | None = Query(None),
    sentiment: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SocialPost)
    if persona_type:
        stmt = stmt.where(SocialPost.persona_type == persona_type)
    if sentiment:
        stmt = stmt.where(SocialPost.sentiment == sentiment)

    stmt = stmt.order_by(SocialPost.simulated_at.desc())
    items, total = await paginate(db, stmt, skip, limit)

    return SocialPostListResponse(items=items, total=total)


@router.get("/{post_id}", response_model=SocialPostResponse)
async def get_social_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(SocialPost, post_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social post not found")
    return entry
