"""Pydantic schemas cho hệ thống Nhiệm vụ & Thưởng."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskCategory = Literal["onboarding", "learning", "daily", "streak", "contest"]
TaskResetFrequency = Literal["none", "daily"]


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: TaskCategory
    reward_amount: Decimal
    target_count: int
    reset_frequency: TaskResetFrequency


class TaskProgressResponse(BaseModel):
    """Tiến độ của user với 1 nhiệm vụ + trạng thái nhận thưởng."""

    task: TaskResponse
    progress_count: int
    target_count: int
    completed: bool
    claimable: bool = False
    completed_at: datetime | None = None


class TaskListResponse(BaseModel):
    streak_current: int
    streak_longest: int
    total_reward_earned: Decimal
    tasks: list[TaskProgressResponse]


class TaskEventRequest(BaseModel):
    """Sự kiện hành vi do frontend báo (mentor chat, hoàn thành kịch bản...)."""

    event: str = Field(max_length=50)


class TaskEventResponse(BaseModel):
    accepted: bool
    rewarded: bool


class CheckinResponse(BaseModel):
    already_checked_in: bool
    current_streak: int
    longest_streak: int
    reward_earned: Decimal


class TaskClaimResponse(BaseModel):
    task: TaskResponse
    progress_count: int
    target_count: int
    completed: bool
    reward_earned: Decimal


class TaskAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    category: TaskCategory
    reward_amount: Decimal
    target_count: int
    reset_frequency: TaskResetFrequency
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class TaskAdminListResponse(BaseModel):
    items: list[TaskAdminResponse]
    total: int


class TaskAdminCreateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: TaskCategory
    reward_amount: Decimal = Field(ge=Decimal("0"))
    target_count: int = Field(default=1, ge=1)
    reset_frequency: TaskResetFrequency = "none"
    is_active: bool = True
    sort_order: int = 0


class TaskAdminUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: TaskCategory | None = None
    reward_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    target_count: int | None = Field(default=None, ge=1)
    reset_frequency: TaskResetFrequency | None = None
    is_active: bool | None = None
    sort_order: int | None = None
