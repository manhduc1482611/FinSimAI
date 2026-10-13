"""Hardening cấu hình — fail-fast khi production dùng JWT secret yếu.

Bối cảnh: ``JWT_SECRET`` mặc định ``dev-secret-change-me`` + ``render.yaml`` để
``sync: false``. Nếu quên điền biến, người biết giá trị mặc định ký được token
hợp lệ cho bất kỳ user. ``Settings`` từ chối khởi động ở production trong trường
hợp đó (xem ``_validate_production_secrets``).
"""

import pytest
from core.config import DEFAULT_JWT_SECRET, MIN_JWT_SECRET_LENGTH, Settings
from pydantic import ValidationError

STRONG_SECRET = "s" * MIN_JWT_SECRET_LENGTH


def test_production_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret=DEFAULT_JWT_SECRET)


def test_production_rejects_short_jwt_secret() -> None:
    short = "x" * (MIN_JWT_SECRET_LENGTH - 1)
    with pytest.raises(ValidationError):
        Settings(environment="production", jwt_secret=short)


def test_production_accepts_strong_jwt_secret() -> None:
    s = Settings(environment="production", jwt_secret=STRONG_SECRET)
    assert s.jwt_secret == STRONG_SECRET


def test_production_environment_is_case_insensitive() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="Production", jwt_secret=DEFAULT_JWT_SECRET)


def test_development_allows_default_jwt_secret() -> None:
    """Dev/test không bị chặn — chỉ production mới fail-fast."""
    s = Settings(environment="development", jwt_secret=DEFAULT_JWT_SECRET)
    assert s.jwt_secret == DEFAULT_JWT_SECRET
