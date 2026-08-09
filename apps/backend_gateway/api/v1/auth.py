from datetime import datetime, timedelta, timezone
from logging import getLogger
from uuid import UUID

from core.config import settings
from core.dependencies import get_current_user, get_db
from core.ratelimit import check_rate
from core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from jwt.exceptions import PyJWTError
from models.user import User
from realtime.auth import create_ws_ticket
from schemas.user import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WsTicketResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    existing = await db.execute(
        select(User).where(
            (User.email == body.email) | (User.username == body.username)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already exists",
        )

    user = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


_DUMMY_HASH = "$2b$12$oRZIijyiNHKS1aZ.BJMOvOge5Z.K8TRfasYgpSTF4qaovKvOpSnxe"


async def _rate_limit_or_429(
    request: Request,
    identifier: str,
    retry_after: str,
) -> None:
    """Kiểm tra giới hạn theo identifier VÀ theo IP; quá ngưỡng → 429."""
    keys = [f"login:identifier:{identifier}"]
    client_ip = request.client.host if request.client else "unknown"
    keys.append(f"login:ip:{client_ip}")

    allowed = True
    for key in keys:
        ok = await check_rate(
            key,
            max_attempts=settings.login_rate_limit_max,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
        if not ok:
            allowed = False
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Quá nhiều lần thử đăng nhập — thử lại sau ít phút",
            headers={"Retry-After": retry_after},
        )


def _issue_tokens(user_id: UUID) -> TokenResponse:
    access_token = create_access_token(
        data={"sub": str(user_id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user_id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_days=settings.refresh_token_expire_days,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    identifier = (body.email or body.username or "").strip().lower()
    await _rate_limit_or_429(
        request,
        identifier,
        retry_after=str(settings.login_rate_limit_window_seconds),
    )

    if body.email:
        stmt = select(User).where(User.email == body.email)
    elif body.username:
        stmt = select(User).where(User.username == body.username)
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email or username required",
        )

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        verify_password(body.password, _DUMMY_HASH)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return _issue_tokens(user.id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Xoay vòng refresh token → cặp access + refresh mới.

    Chỉ chấp nhận JWT có claim ``type=refresh``. Không cần user gửi token cũ
    khi hết hạn nữa — user chỉ phải đăng nhập lại sau khi refresh token hết hạn
    (mặc định 30 ngày) hoặc khi bị khoá.
    """
    try:
        payload = decode_access_token(
            body.refresh_token,
            settings.jwt_secret,
            [settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise PyJWTError("Not a refresh token")
        user_id = UUID(payload["sub"])
    except (PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị khoá",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_tokens(user.id)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def create_ws_ticket_endpoint(
    current_user: User = Depends(get_current_user),
) -> WsTicketResponse:
    """Cấp single-use ticket cho WebSocket handshake (tránh JWT nằm trong URL).

    JWT chỉ đi qua header ``Authorization: Bearer`` ở REST; WS mở socket bằng
    ``/ws/*?ticket=<ticket>``. Ticket ngẫu nhiên, TTL rất ngắn và chỉ dùng được
    1 lần — nếu lộ trong access log / APM trace cũng không thể "mượn" phiên.
    """
    ttl = settings.ws_ticket_ttl_seconds
    try:
        ticket = await create_ws_ticket(str(current_user.id))
    except Exception as e:
        # Redis không khả dụng (ngoài ``ws_local_mode``): trả 503 sạch thay vì để
        # 500 lọt qua ServerErrorMiddleware — response 500 không qua CORSMiddleware
        # nên trình duyệt báo nhầm "CORS blocked" thay vì lỗi thật.
        logger.warning("WS ticket issue failed (Redis unavailable?): %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Realtime service chưa sẵn sàng (Redis không khả dụng) — thử lại sau",
        ) from e
    now = datetime.now(timezone.utc)
    return WsTicketResponse(
        ticket=ticket,
        ttl_seconds=ttl,
        expires_at=(now + timedelta(seconds=ttl)).isoformat(),
    )
