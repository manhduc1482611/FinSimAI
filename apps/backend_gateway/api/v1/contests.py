"""Module cuộc thi — host tạo/quản lý contest, user browse/join, content scoped."""

from typing import Annotated, cast

from core.dependencies import get_current_user, get_current_user_optional, get_db, require_roles
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from models.contest import Contest
from models.news import News
from models.social import SocialPost
from models.user import User
from schemas.company import CompanyListResponse, CompanyResponse
from schemas.contest import (
    ContestCreateRequest,
    ContestJoinResponse,
    ContestListResponse,
    ContestResponse,
    ContestUpdateRequest,
)
from schemas.news import NewsListResponse, NewsResponse
from schemas.social import SocialPostListResponse, SocialPostResponse
from services import contest_service, task_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/contests", tags=["contests"])

Db = Annotated[AsyncSession, Depends(get_db)]
HostDep = Annotated[User, Depends(require_roles("host", "admin"))]


async def _get_contest_or_404(db: AsyncSession, slug: str) -> Contest:
    contest = await contest_service.get_contest(db, slug)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")
    return contest


async def _require_manager(contest: Contest, user: User) -> None:
    """Host sở hữu contest hoặc admin mới được quản lý contest này."""
    if not contest_service.is_owner_or_admin(contest, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền quản lý cuộc thi này",
        )


async def _require_scope(db: AsyncSession, user: User, slug: str) -> Contest:
    """Xác minh user có quyền xem content contest (owner/admin hoặc đã join)."""
    contest = await _get_contest_or_404(db, slug)
    is_manager = contest_service.is_owner_or_admin(contest, user)
    if contest.status != "active" and not is_manager:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")
    if not is_manager:
        member = await contest_service.get_membership(db, contest.id, user.id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn chưa tham gia cuộc thi này",
            )
    return contest


# ────────────────────────────────────────────────────────────────────────────
# CRUD + activate (host/admin)
# ────────────────────────────────────────────────────────────────────────────
@router.post("", response_model=ContestResponse, status_code=status.HTTP_201_CREATED)
async def create_contest(
    body: ContestCreateRequest,
    current_user: HostDep,
    db: Db,
) -> Contest:
    return await contest_service.create_contest(db, current_user, body)


@router.get("", response_model=ContestListResponse)
async def list_contests(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> ContestListResponse:
    return await contest_service.list_contests(db, current_user, skip, limit)


@router.get("/{slug}", response_model=ContestResponse)
async def get_contest_detail(
    slug: str,
    current_user: Annotated[User | None, Depends(get_current_user_optional)] = None,
    db: Db = cast(AsyncSession, None),
) -> Contest:
    contest = await _get_contest_or_404(db, slug)
    if contest.status != "active" and not (
        current_user and contest_service.is_owner_or_admin(contest, current_user)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")
    return contest


@router.patch("/{slug}", response_model=ContestResponse)
async def update_contest(
    slug: str,
    body: ContestUpdateRequest,
    current_user: HostDep,
    db: Db,
) -> Contest:
    contest = await _get_contest_or_404(db, slug)
    await _require_manager(contest, current_user)
    return await contest_service.update_contest(db, contest, body)


@router.delete("/{slug}", response_model=ContestResponse)
async def delete_contest(
    slug: str,
    current_user: HostDep,
    db: Db,
) -> Contest:
    """Xoá mềm contest (status='ended'), chỉ host sở hữu."""
    contest = await _get_contest_or_404(db, slug)
    if contest.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền quản lý cuộc thi này",
        )
    return await contest_service.soft_delete_contest(db, contest)


@router.post("/{slug}/activate", response_model=ContestResponse)
async def activate_contest(
    slug: str,
    current_user: HostDep,
    db: Db,
) -> Contest:
    """Chạy pipeline tự sinh nội dung rồi chuyển contest sang ``active`` (FR-4)."""
    contest = await _get_contest_or_404(db, slug)
    await _require_manager(contest, current_user)
    return await contest_service.activate_contest(db, contest)


@router.post("/{slug}/join", response_model=ContestJoinResponse)
async def join_contest(
    slug: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Db,
) -> ContestJoinResponse:
    contest = await _get_contest_or_404(db, slug)
    if contest.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cuộc thi chưa mở — không thể tham gia",
        )
    if current_user.role in ("admin", "host") and contest_service.is_owner_or_admin(
        contest, current_user
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Host/Admin không cần tham gia cuộc thi của mình",
        )
    await contest_service.join_contest(db, current_user, contest)
    await task_service.record_event(db, current_user, "contest_joined")
    return ContestJoinResponse(joined=True, contest_id=contest.id)


# ────────────────────────────────────────────────────────────────────────────
# Content scoped theo contest — user đã join hoặc host/admin (FR-5)
# ────────────────────────────────────────────────────────────────────────────
@router.get("/{slug}/companies", response_model=CompanyListResponse)
async def list_contest_companies(
    slug: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> CompanyListResponse:
    contest = await _require_scope(db, current_user, slug)
    stmt = (
        select(Company)
        .where(Company.contest_id == contest.id, Company.is_active.is_(True))
        .order_by(Company.symbol)
    )
    items, total = await paginate(db, stmt, skip, limit)
    return CompanyListResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/{slug}/news", response_model=NewsListResponse)
async def list_contest_news(
    slug: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> NewsListResponse:
    contest = await _require_scope(db, current_user, slug)
    stmt = (
        select(News)
        .where(News.contest_id == contest.id)
        .order_by(News.simulated_at.desc())
    )
    items, total = await paginate(db, stmt, skip, limit)
    return NewsListResponse(
        items=[NewsResponse.model_validate(n) for n in items],
        total=total,
    )


@router.get("/{slug}/social-posts", response_model=SocialPostListResponse)
async def list_contest_social_posts(
    slug: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> SocialPostListResponse:
    contest = await _require_scope(db, current_user, slug)
    stmt = (
        select(SocialPost)
        .where(SocialPost.contest_id == contest.id)
        .order_by(SocialPost.simulated_at.desc())
    )
    items, total = await paginate(db, stmt, skip, limit)
    return SocialPostListResponse(
        items=[SocialPostResponse.model_validate(s) for s in items],
        total=total,
    )
