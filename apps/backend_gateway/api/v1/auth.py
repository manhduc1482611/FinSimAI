from datetime import datetime, timedelta, timezone

from core.config import settings
from core.dependencies import get_current_user, get_db
from core.security import create_access_token, hash_password, verify_password
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from schemas.user import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WsTicketResponse,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from websockets.auth import create_ws_ticket

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
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


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
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

    token = create_access_token(
        data={"sub": str(user.id)},
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
    )
    return TokenResponse(access_token=token)


@router.post("/ws-ticket", response_model=WsTicketResponse)
async def create_ws_ticket_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Cấp single-use ticket cho WebSocket handshake (tránh JWT nằm trong URL).

    JWT chỉ đi qua header ``Authorization: Bearer`` ở REST; WS mở socket bằng
    ``/ws/*?ticket=<ticket>``. Ticket ngẫu nhiên, TTL rất ngắn và chỉ dùng được
    1 lần — nếu lộ trong access log / APM trace cũng không thể "mượn" phiên.
    """
    ttl = settings.ws_ticket_ttl_seconds
    ticket = await create_ws_ticket(str(current_user.id))
    now = datetime.now(timezone.utc)
    return WsTicketResponse(
        ticket=ticket,
        ttl_seconds=ttl,
        expires_at=(now + timedelta(seconds=ttl)).isoformat(),
    )
