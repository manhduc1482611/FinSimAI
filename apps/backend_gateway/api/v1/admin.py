"""Module quản trị — chỉ admin (``require_roles('admin')``).

Admin thấy toàn bộ users/contests/news/social-posts/companies của mọi contest,
cấp/thu hồi quyền host, khoá user, can thiệp status mọi contest (FR-2, FR-3).
"""

import uuid
from typing import Annotated, cast

from core.config import settings
from core.dependencies import get_db, require_roles
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from models.contest import Contest, ContestMember
from models.news import News
from models.social import SocialPost
from models.user import User
from schemas.admin import (
    AdminContestListResponse,
    AdminContestResponse,
    AdminContestStatusUpdate,
    AdminRoleUpdate,
    AdminStatusUpdate,
    AdminUserListResponse,
    AdminUserResponse,
)
from schemas.company import CompanyListResponse, CompanyResponse
from schemas.news import NewsListResponse, NewsResponse
from schemas.social import SocialPostListResponse, SocialPostResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],
)

AdminDep = Annotated[User, Depends(require_roles("admin"))]


def _escape_like(s: str) -> str:
    return s.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


# ────────────────────────────────────────────────────────────────────────────
# Users
# ────────────────────────────────────────────────────────────────────────────
@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    role: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> AdminUserListResponse:
    stmt = select(User).order_by(User.created_at.desc())
    if role:
        stmt = stmt.where(User.role == role)
    if search:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            (User.email.ilike(pattern))
            | (User.username.ilike(pattern))
            | (User.display_name.ilike(pattern))
        )
    items, total = await paginate(db, stmt, skip, limit)
    return AdminUserListResponse(
        items=[AdminUserResponse.model_validate(u) for u in items],
        total=total,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    body: AdminRoleUpdate,
    current_user: AdminDep,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> User:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự sửa role của chính mình",
        )
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if body.role == "admin" and target.email not in settings.admin_emails:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email không nằm trong ADMIN_EMAILS — không thể cấp role admin",
        )
    target.role = body.role
    await db.commit()
    await db.refresh(target)
    return target


@router.patch("/users/{user_id}/status", response_model=AdminUserResponse)
async def update_user_status(
    user_id: uuid.UUID,
    body: AdminStatusUpdate,
    current_user: AdminDep,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> User:
    if user_id == current_user.id and not body.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự khoá tài khoản của chính mình",
        )
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    target.is_active = body.is_active
    await db.commit()
    await db.refresh(target)
    return target


# ────────────────────────────────────────────────────────────────────────────
# Contests
# ────────────────────────────────────────────────────────────────────────────
@router.get("/contests", response_model=AdminContestListResponse)
async def list_all_contests(
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> AdminContestListResponse:
    stmt = select(Contest).order_by(Contest.created_at.desc())
    if status_filter:
        stmt = stmt.where(Contest.status == status_filter)
    contests, total = await paginate(db, stmt, skip, limit)

    ids = [c.id for c in contests]
    counts: dict[uuid.UUID, int] = {}
    if ids:
        rows = (
            await db.execute(
                select(ContestMember.contest_id, func.count())
                .where(ContestMember.contest_id.in_(ids))
                .group_by(ContestMember.contest_id)
            )
        ).all()
        counts = {cid: cnt for cid, cnt in rows}

    items: list[AdminContestResponse] = []
    for contest in contests:
        resp = AdminContestResponse.model_validate(contest)
        resp.member_count = counts.get(contest.id, 0)
        items.append(resp)
    return AdminContestListResponse(items=items, total=total)


@router.patch("/contests/{contest_id}/status", response_model=AdminContestResponse)
async def update_contest_status(
    contest_id: uuid.UUID,
    body: AdminContestStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> AdminContestResponse:
    contest = await db.get(Contest, contest_id)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")
    contest.status = body.status
    await db.commit()
    await db.refresh(contest)
    resp = AdminContestResponse.model_validate(contest)
    resp.member_count = await _contest_member_count(db, contest.id)
    return resp


async def _contest_member_count(db: AsyncSession, contest_id: uuid.UUID) -> int:
    row = await db.execute(
        select(func.count())
        .select_from(ContestMember)
        .where(ContestMember.contest_id == contest_id)
    )
    return int(row.scalar() or 0)


# ────────────────────────────────────────────────────────────────────────────
# Content (view toàn cục, FR-2) — không bị lọc theo contest trừ khi chỉ định
# ────────────────────────────────────────────────────────────────────────────
@router.get("/companies", response_model=CompanyListResponse)
async def list_all_companies(
    contest_id: Annotated[uuid.UUID | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> CompanyListResponse:
    stmt = select(Company).order_by(Company.symbol)
    if contest_id:
        stmt = stmt.where(Company.contest_id == contest_id)
    items, total = await paginate(db, stmt, skip, limit)
    return CompanyListResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/news", response_model=NewsListResponse)
async def list_all_news(
    contest_id: Annotated[uuid.UUID | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> NewsListResponse:
    stmt = select(News).order_by(News.simulated_at.desc())
    if contest_id:
        stmt = stmt.where(News.contest_id == contest_id)
    items, total = await paginate(db, stmt, skip, limit)
    return NewsListResponse(
        items=[NewsResponse.model_validate(n) for n in items],
        total=total,
    )


@router.get("/social-posts", response_model=SocialPostListResponse)
async def list_all_social_posts(
    contest_id: Annotated[uuid.UUID | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> SocialPostListResponse:
    stmt = select(SocialPost).order_by(SocialPost.simulated_at.desc())
    if contest_id:
        stmt = stmt.where(SocialPost.contest_id == contest_id)
    items, total = await paginate(db, stmt, skip, limit)
    return SocialPostListResponse(
        items=[SocialPostResponse.model_validate(s) for s in items],
        total=total,
    )
