"""API quản trị rủi ro — trạng thái cooldown, kích hoạt phạt, gỡ phạt.

Đây là điểm nối cho hệ thống phát hiện bẫy tâm lý (Giai đoạn sau): engine phát
hiện vi phạm sẽ gọi ``POST /risk/penalties``; frontend CooldownOverlay dùng
``GET /risk/cooldown`` (đếm ngược) và ``POST /risk/cooldown/clear`` (gỡ khóa sau
khi hoàn thành bài tập phản tư với Mentor).
"""

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.user import User
from schemas.risk import CooldownStatus, PenaltyRequest, PenaltyResponse
from services import penalty_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/cooldown", response_model=CooldownStatus)
async def get_cooldown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await penalty_service.get_penalty_status(current_user.id, db)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return CooldownStatus.model_validate(result)


@router.post(
    "/penalties",
    response_model=PenaltyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_penalty(
    body: PenaltyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await penalty_service.apply_penalty(
        current_user.id,
        body.severity,
        db,
        trap_type=body.trap_type,
        description=body.description,
    )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("error", "Không thể áp dụng phạt"),
        )
    return PenaltyResponse.model_validate(result)


@router.post("/cooldown/clear", response_model=CooldownStatus)
async def clear_cooldown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await penalty_service.clear_cooldown(current_user.id, db)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return CooldownStatus.model_validate(result)
