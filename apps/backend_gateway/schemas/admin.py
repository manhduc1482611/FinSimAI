"""Pydantic schemas cho các endpoint quản trị (chỉ admin)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from schemas.contest import ContestConfig

UserRole = Literal["user", "host", "admin"]
ContestStatus = Literal["draft", "active", "ended"]


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    display_name: str | None
    role: str
    is_active: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int


class AdminRoleUpdate(BaseModel):
    role: UserRole


class AdminStatusUpdate(BaseModel):
    is_active: bool


class AdminContestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    status: str
    config: ContestConfig
    owner_id: uuid.UUID | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    member_count: int = 0


class AdminContestListResponse(BaseModel):
    items: list[AdminContestResponse]
    total: int


class AdminContestStatusUpdate(BaseModel):
    status: ContestStatus
