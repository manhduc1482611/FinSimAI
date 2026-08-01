import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(max_length=255)
    username: str = Field(min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(None, max_length=200)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    username: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=255)
    password: str = Field(min_length=1)

    @model_validator(mode="after")
    def check_identifier(self):
        if not self.username and not self.email:
            raise ValueError("username hoặc email là bắt buộc")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WsTicketResponse(BaseModel):
    """Single-use ticket cho WebSocket handshake (thay JWT truyền qua query param)."""

    ticket: str
    ttl_seconds: float
    expires_at: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    display_name: str | None
    avatar_url: str | None
    role: str
    cash_balance: Decimal
    frozen_cash: Decimal
    risk_score: int
    cooldown_until: datetime | None
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str | None = Field(None, max_length=200)
    avatar_url: str | None = Field(None, max_length=500)
