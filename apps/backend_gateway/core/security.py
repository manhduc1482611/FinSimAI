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
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret, algorithm=algorithm)


def decode_access_token(token: str, secret: str, algorithms: list[str]) -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=algorithms)
