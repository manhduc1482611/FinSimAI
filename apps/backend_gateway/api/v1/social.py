import uuid
from datetime import datetime, timezone

from core.dependencies import get_current_user, get_current_user_optional, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from models.social import SocialComment, SocialLike, SocialPost
from models.user import User
from schemas.social import (
    SocialCommentCreate,
    SocialCommentListResponse,
    SocialCommentResponse,
    SocialLikeResponse,
    SocialPostCreate,
    SocialPostListResponse,
    SocialPostResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/social", tags=["social"])

# Ngữ liệu gợi ý tâm lý cho bài đăng của người dùng (mô phỏng heuristic đơn giản).
_POSITIVE_TOKENS = (
    "tăng", "tốt", "tích cực", "kỳ vọng", "triển vọng", "lãi", "chốt lời",
    "phát triển", "mạnh", "cơ hội", "tuyệt", "bùng nổ", "ấn tượng", "hiệu quả", "đạt",
)
_NEGATIVE_TOKENS = (
    "giảm", "xấu", "tiêu cực", "rủi ro", "lỗ", "cắt lỗ", "thua", "bán tháo",
    "điều chỉnh", "mất", "thất bại", "lo ngại", "nguy hiểm", "lừa đảo", "cảnh báo",
    "sụp", "rớt", "phá sản",
)


def _classify_sentiment(text: str) -> str:
    lower = text.lower()
    positive = sum(1 for token in _POSITIVE_TOKENS if token in lower)
    negative = sum(1 for token in _NEGATIVE_TOKENS if token in lower)
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def _post_to_response(post: SocialPost, liked_ids: set[uuid.UUID]) -> SocialPostResponse:
    response = SocialPostResponse.model_validate(post)
    response.liked_by_me = post.id in liked_ids
    return response


async def _liked_post_ids(
    db: AsyncSession,
    user: User | None,
    post_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    if user is None or not post_ids:
        return set()
    stmt = select(SocialLike.post_id).where(
        SocialLike.user_id == user.id,
        SocialLike.post_id.in_(post_ids),
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


@router.get("", response_model=SocialPostListResponse)
async def list_social_posts(
    persona_type: str | None = Query(None),
    sentiment: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SocialPost)
    if persona_type:
        stmt = stmt.where(SocialPost.persona_type == persona_type)
    if sentiment:
        stmt = stmt.where(SocialPost.sentiment == sentiment)

    stmt = stmt.order_by(SocialPost.simulated_at.desc())
    items, total = await paginate(db, stmt, skip, limit)

    liked_ids = await _liked_post_ids(db, user, [post.id for post in items])
    return SocialPostListResponse(
        items=[_post_to_response(post, liked_ids) for post in items],
        total=total,
    )


@router.get("/{post_id}", response_model=SocialPostResponse)
async def get_social_post(
    post_id: uuid.UUID,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(SocialPost, post_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social post not found")
    liked_ids = await _liked_post_ids(db, user, [post_id])
    return _post_to_response(entry, liked_ids)


@router.post("", response_model=SocialPostResponse, status_code=status.HTTP_201_CREATED)
async def create_social_post(
    body: SocialPostCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    company_id = None
    if body.company_symbol:
        company = (
            await db.execute(select(Company).where(Company.symbol == body.company_symbol))
        ).scalar_one_or_none()
        if company is not None:
            company_id = company.id

    post = SocialPost(
        author_name=user.display_name or user.username,
        author_avatar=user.avatar_url,
        persona_type="user",
        content=body.content,
        sentiment=_classify_sentiment(body.content),
        virality_score=1.0,
        likes_count=0,
        shares_count=0,
        comments_count=0,
        company_id=company_id,
        news_id=None,
        simulated_at=datetime.now(timezone.utc),
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _post_to_response(post, set())


@router.get("/{post_id}/comments", response_model=SocialCommentListResponse)
async def list_social_comments(
    post_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social post not found")

    stmt = (
        select(SocialComment)
        .where(SocialComment.post_id == post_id)
        .order_by(SocialComment.created_at.asc())
    )
    items, total = await paginate(db, stmt, skip, limit)
    return SocialCommentListResponse(items=items, total=total)


@router.post(
    "/{post_id}/comments",
    response_model=SocialCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_social_comment(
    post_id: uuid.UUID,
    body: SocialCommentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social post not found")

    comment = SocialComment(
        post_id=post_id,
        user_id=user.id,
        author_name=user.display_name or user.username,
        author_avatar=user.avatar_url,
        content=body.content,
    )
    post.comments_count += 1
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.post("/{post_id}/like", response_model=SocialLikeResponse)
async def toggle_social_like(
    post_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    post = await db.get(SocialPost, post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social post not found")

    stmt = select(SocialLike).where(
        SocialLike.post_id == post_id,
        SocialLike.user_id == user.id,
    )
    like = (await db.execute(stmt)).scalar_one_or_none()

    if like is None:
        db.add(SocialLike(post_id=post_id, user_id=user.id))
        post.likes_count += 1
        liked = True
    else:
        await db.delete(like)
        post.likes_count = max(0, post.likes_count - 1)
        liked = False

    await db.commit()
    await db.refresh(post)
    return SocialLikeResponse(liked=liked, likes_count=post.likes_count)
