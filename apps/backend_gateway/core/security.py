from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(
    data: dict[str, Any],
    secret: str,
    algorithm: str,
    expires_minutes: int,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def create_refresh_token(
    data: dict[str, Any],
    secret: str,
    algorithm: str,
    expires_days: int,
) -> str:
    """Refresh token: thời hạn dài hơn access token, mang claim ``type=refresh``.

    Endpoint ``/auth/refresh`` chỉ chấp nhận token loại này — access token (thiếu
    claim ``type`` hoặc ``type=access``) không bao giờ dùng để xoay vòng được.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def decode_access_token(token: str, secret: str, algorithms: list[str]) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=algorithms)
