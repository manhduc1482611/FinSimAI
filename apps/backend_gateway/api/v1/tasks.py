"""Module Nhiệm vụ & Thưởng — user xem/điểm danh/báo sự kiện/nhận thưởng, admin CRUD."""

import uuid
from typing import Annotated, cast

from core.dependencies import get_current_user, get_db, require_roles
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.task import Task
from models.user import User
from schemas.task import (
    CheckinResponse,
    TaskAdminCreateRequest,
    TaskAdminListResponse,
    TaskAdminResponse,
    TaskAdminUpdateRequest,
    TaskClaimResponse,
    TaskEventRequest,
    TaskEventResponse,
    TaskListResponse,
)
from services import task_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/tasks", tags=["tasks"])

admin_router = APIRouter(
    prefix="/admin/tasks",
    tags=["admin"],
    dependencies=[Depends(require_roles("admin"))],
)

Db = Annotated[AsyncSession, Depends(get_db)]
AdminDep = Annotated[User, Depends(require_roles("admin"))]


def _task_error(exc: task_service.TaskServiceError) -> HTTPException:
    if isinstance(exc, task_service.TaskNotClaimableError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ────────────────────────────────────────────────────────────────────────────
# User endpoints
# ────────────────────────────────────────────────────────────────────────────
@router.get("", response_model=TaskListResponse)
async def list_tasks(
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> dict[str, object]:
    return await task_service.list_tasks(db, current_user)


@router.post("/checkin", response_model=CheckinResponse)
async def checkin(
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> dict[str, object]:
    return await task_service.checkin(db, current_user)


@router.post("/events", response_model=TaskEventResponse)
async def report_event(
    body: TaskEventRequest,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> TaskEventResponse:
    try:
        accepted, rewarded = await task_service.report_event(db, current_user, body.event)
    except task_service.TaskServiceError as exc:
        raise _task_error(exc) from exc
    return TaskEventResponse(accepted=accepted, rewarded=rewarded)


@router.post("/{task_id}/claim", response_model=TaskClaimResponse)
async def claim_task(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)] = cast(User, None),
    db: Db = cast(AsyncSession, None),
) -> dict[str, object]:
    try:
        return await task_service.claim_task(db, current_user, task_id)
    except task_service.TaskServiceError as exc:
        raise _task_error(exc) from exc


# ────────────────────────────────────────────────────────────────────────────
# Admin CRUD
# ────────────────────────────────────────────────────────────────────────────
@admin_router.get("", response_model=TaskAdminListResponse)
async def list_all_tasks(
    category: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> TaskAdminListResponse:
    stmt = select(Task).order_by(Task.sort_order, Task.code)
    if category:
        stmt = stmt.where(Task.category == category)
    if is_active is not None:
        stmt = stmt.where(Task.is_active.is_(is_active))
    items, total = await paginate(db, stmt, skip, limit)
    return TaskAdminListResponse(
        items=[TaskAdminResponse.model_validate(t) for t in items],
        total=total,
    )


@admin_router.post("", response_model=TaskAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskAdminCreateRequest,
    current_user: AdminDep,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> Task:
    existing = await db.execute(select(Task).where(Task.code == body.code))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task code đã tồn tại",
        )
    task = Task(**body.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@admin_router.patch("/{task_id}", response_model=TaskAdminResponse)
async def update_task(
    task_id: uuid.UUID,
    body: TaskAdminUpdateRequest,
    current_user: AdminDep,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> Task:
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


@admin_router.delete("/{task_id}", response_model=TaskAdminResponse)
async def delete_task(
    task_id: uuid.UUID,
    current_user: AdminDep,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> Task:
    task = await db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.is_active = False
    await db.commit()
    await db.refresh(task)
    return task
