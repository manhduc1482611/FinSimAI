from datetime import datetime

from pydantic import BaseModel, Field


class PenaltyRequest(BaseModel):
    """Kích hoạt một lần phạt (do hệ thống phát hiện bẫy / demo).

    ``severity`` từ 1 (nhẹ) đến 5 (rất nặng) — math engine quyết định mức
    tăng risk_score, tiền bị trừ và thời gian cooldown tương ứng.
    """

    trap_type: str = Field(default="discipline_violation", max_length=50)
    severity: int = Field(ge=1, le=5)
    description: str | None = Field(default=None, max_length=500)


class CooldownStatus(BaseModel):
    """Trạng thái khóa giao dịch hiện tại của user (dữ liệu cho CooldownOverlay)."""

    locked: bool
    cooldown_until: datetime | None = None
    remaining_seconds: int = 0
    risk_score: int = 0
    reason: str | None = None


class PenaltyResponse(BaseModel):
    """Kết quả áp dụng một lần phạt (sau khi đã commit xuống DB)."""

    new_risk_score: int
    risk_score_delta: int
    points_deducted: int
    cooldown_seconds: float
    cooldown_until: datetime | None = None
    reason: str | None = None
