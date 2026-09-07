"""Lịch sử hội thoại Mentor — persistence + nguồn history cho LLM (A3.2).

- ``save_exchange``: ghi cặp tin user + mentor sau một lượt stream hoàn tất.
- ``recent_history``: N tin gần nhất dạng ``[{role, content}]`` để gửi Gemini
  (12 tin — improvement_plan A3.2).
- ``list_messages``: toàn bộ row (REST GET /mentor/history cho client reload).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from models.mentor import MentorMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Số tin tối đa gửi vào prompt LLM (mỗi tin 1 dòng, giữ context gọn).
LLM_HISTORY_LIMIT = 12


async def save_exchange(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | str,
    session_id: str,
    user_message: str,
    mentor_reply: str,
    focus: str | None = None,
    prompt_version: str | None = None,
) -> None:
    """Ghi 1 lượt hỏi-đáp (2 row). Lỗi DB chỉ log — không làm hỏng phiên chat."""
    try:
        db.add_all(
            [
                MentorMessage(
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=user_message,
                    prompt_version=prompt_version,
                ),
                MentorMessage(
                    user_id=user_id,
                    session_id=session_id,
                    role="mentor",
                    content=mentor_reply,
                    focus=focus,
                    prompt_version=prompt_version,
                ),
            ]
        )
        await db.commit()
    except Exception:
        logger.exception("Không lưu được lịch sử mentor (session=%s)", session_id)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001 - session có thể đã chết theo commit
            logger.debug("Rollback session mentor history cũng thất bại", exc_info=True)


async def recent_messages(
    db: AsyncSession, user_id: uuid.UUID | str, limit: int = LLM_HISTORY_LIMIT
) -> list[MentorMessage]:
    """Tin nhắn gần nhất theo thời gian tăng dần (cũ → mới)."""
    stmt = (
        select(MentorMessage)
        .where(MentorMessage.user_id == user_id)
        .order_by(MentorMessage.created_at.desc(), MentorMessage.id.desc())
        .limit(max(limit, 0))
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()
    return rows


def to_llm_history(rows: list[MentorMessage]) -> list[dict[str, str]]:
    """Chuyển row DB sang định dạng history mà prompt YAML hiểu."""
    return [{"role": row.role, "content": row.content} for row in rows]


def to_api_dicts(rows: list[MentorMessage]) -> list[dict[str, Any]]:
    """Serialize cho REST response."""
    return [
        {
            "id": str(row.id),
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "focus": row.focus,
            "prompt_version": row.prompt_version,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
