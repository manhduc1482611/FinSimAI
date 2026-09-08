"""Metadata versioned ghi vào ``mentor_messages.metadata_json`` cho mục đích audit.

Khi regulator yêu cầu xem lại "vì sao Mentor đưa ra câu hỏi X", cần biết chính
xác: chế độ nào, prompt phiên bản nào, model nào, focus nào, snapshot danh mục
đã dùng ra sao, và các lớp bảo vệ nào đã kích hoạt. JSON thuần tuỳ tiện rất khó
audit — nên `metadata_json` tuân thủ schema versioned này (docs/ai_mentor_3mode_plan.md
v2.0, mục 2.2).

Khi thay đổi cấu trúc: bump ``SCHEMA_VERSION``, giữ backward-compatible bằng cách
decode cũ → mới (xem :func:`decode_metadata`). Decode lỗi version → báo rõ, không
im lặng bỏ qua.
"""

from __future__ import annotations

import logging
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

MentorMode = Literal["concept", "plan", "trade_now", "socratic"]


class TradeSnapshotMetadata(BaseModel):
    """Tóm lược danh mục đã dùng khi sinh reply (KHÔNG lưu token nhạy cảm)."""

    model_config = ConfigDict(extra="forbid")

    symbol: str | None = None
    total_nav: float | None = None
    cash_balance: float | None = None
    holdings: int = 0
    open_orders: int = 0
    allocation_pct: float | None = None
    pnl_pct: float | None = None


class MentorMetadata(BaseModel):
    """Schema versioned cho ``mentor_messages.metadata_json``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    mode: MentorMode = "socratic"
    prompt_version: str = "qbank-3.1.0"
    model: str | None = None  # "gemini-2.5-flash" hoặc "deterministic"
    focus: str | None = None
    trade_snapshot: TradeSnapshotMetadata | None = None
    used_layers: list[str] = []


def to_metadata_dict(**kwargs: object) -> dict:
    """Tạo dict tuân thủ schema (dùng để lưu thẳng vào JSONB)."""
    try:
        meta = MentorMetadata(**kwargs)
        return meta.model_dump()
    except Exception:
        logger.warning("Metadata không hợp lệ — ghi metadata rỗng", exc_info=True)
        return {"schema_version": SCHEMA_VERSION, "mode": "socratic"}


def decode_metadata(raw: dict | None) -> MentorMetadata:
    """Giải mã metadata_json từ DB; decode lỗi version → log rõ, trả default.

    Không im lặng bỏ qua: khi decode thất bại do version cũ/không hợp lệ, ghi
    cảnh báo để audit tool phát hiện, không bị che giấu.
    """
    if not raw:
        return MentorMetadata()
    try:
        version = int(raw.get("schema_version", SCHEMA_VERSION))
        if version > SCHEMA_VERSION:
            logger.error(
                "metadata_json có schema_version mới hơn code (%s > %s) — cần nâng cấp dịch vụ",
                version,
                SCHEMA_VERSION,
            )
            raise ValueError(f"unsupported schema_version: {version}")
        return MentorMetadata.model_validate(raw)
    except Exception:
        logger.warning("decode_metadata thất bại — trả metadata default", exc_info=True)
        return MentorMetadata()
