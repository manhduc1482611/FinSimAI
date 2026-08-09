import secrets
import uuid as uuid_lib
from collections.abc import AsyncGenerator, Awaitable, Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError
from models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import async_session_factory
from core.security import decode_access_token


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await _resolve_user(credentials, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn hoặc không hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Xác thực nếu có token, trả None khi không có — dùng cho endpoint công khai."""
    if credentials is None:
        return None
    return await _resolve_user(credentials, db)


def require_internal_api_key(
    api_key: str = Header(default="", alias="X-Internal-Api-Key"),
) -> str:
    """Endpoint nội bộ chỉ dành cho service khác (AI Engine) — không phải user.

    Key so sánh bằng ``secrets.compare_digest`` (chống timing attack). Khi
    ``INTERNAL_API_KEY`` chưa cấu hình, endpoint bị khoá vĩnh viễn (403) —
    fail-closed, tránh lộ endpoint trong lúc cấu hình dang dở.
    """
    expected = settings.internal_api_key
    if not expected or not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing internal API key",
        )
    return api_key


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """Factory trả về dependency yêu cầu user thuộc một trong các role.

    Role ``admin`` còn bị ràng buộc bởi ``ADMIN_EMAILS`` (defense in depth):
    một user chỉ được coi là admin khi email nằm trong ``settings.admin_emails``,
    kể cả khi cột role trong DB bị set thủ công.
    """

    async def _dependency(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện thao tác này",
            )
        if user.role == "admin" and user.email not in settings.admin_emails:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản admin không nằm trong danh sách cho phép",
            )
        return user

    return _dependency


async def _resolve_user(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> User | None:
    if credentials is None:
        return None
    token = credentials.credentials
    try:
        payload = decode_access_token(
            token, settings.jwt_secret, [settings.jwt_algorithm]
        )
        user_id_raw: str | None = payload.get("sub")
        if user_id_raw is None:
            return None
        user_id = uuid_lib.UUID(user_id_raw)
    except (PyJWTError, ValueError):
        return None

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None
    return user
