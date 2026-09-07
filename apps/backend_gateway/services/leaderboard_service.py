"""Bảng xếp hạng (Leaderboard) — theo NAV (giá trị tài sản) hoặc Điểm kỷ luật.

- ``nav``: tổng giá trị = cash_balance + frozen_cash + settling_cash + Σ vị thế
  (quantity × current_price). Hỗ trợ toàn cầu (thị trường chính, contest_id IS
  NULL) hoặc theo một contest.
- ``discipline``: xếp theo ``discipline_score`` DESC — độc lập với lợi nhuận.

Trả kèm ``my_rank`` (hạng của user hiện tại) để frontend hiển thị không cần nạp
toàn bộ danh sách. Tính NAV bằng SQL (JOIN + GROUP BY) — pattern đã có ở
``task_service._rank_in_contest``.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from models.company import Company
from models.contest import ContestMember
from models.trade import Portfolio
from models.user import User
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def _to_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


async def _nav_rankings(
    db: AsyncSession,
    contest_id: uuid.UUID | None,
) -> dict[object, Decimal]:
    """NAV mỗi user; ``contest_id=None`` → thị trường chính."""
    pf_scope = Portfolio.contest_id.is_(None) if contest_id is None else (
        Portfolio.contest_id == contest_id
    )

    cash_rows = await db.execute(select(User.id, User.cash_balance, User.frozen_cash, User.settling_cash))
    cash_map: dict[object, Decimal] = {}
    for uid, cash, frozen, settling in cash_rows.all():
        cash_map[uid] = (
            _to_decimal(cash) + _to_decimal(frozen) + _to_decimal(settling)
        )

    mv_rows = await db.execute(
        select(Portfolio.user_id, func.sum(Portfolio.quantity * Company.current_price))
        .join(Company, Portfolio.company_id == Company.id)
        .where(pf_scope)
        .group_by(Portfolio.user_id)
    )
    mv_map: dict[object, Decimal] = {}
    for uid, value in mv_rows.all():
        mv_map[uid] = _to_decimal(value)

    all_ids = set(cash_map) | set(mv_map)
    return {
        uid: cash_map.get(uid, Decimal("0.00")) + mv_map.get(uid, Decimal("0.00"))
        for uid in all_ids
    }


async def _discipline_rankings(db: AsyncSession) -> list[tuple[object, int]]:
    rows = await db.execute(
        select(User.id, User.discipline_score)
        .select_from(User)
        .order_by(User.discipline_score.desc(), User.created_at.asc())
    )
    return [(uid, int(score or 0)) for uid, score in rows.all()]


async def get_rankings(
    db: AsyncSession,
    *,
    kind: str = "nav",
    contest_id: uuid.UUID | None = None,
    limit: int = 50,
) -> dict:
    """Trả bảng xếp hạng (không phụ thuộc user hiện tại cho endpoint công khai)."""
    if kind == "discipline":
        raw = await _discipline_rankings(db)
        entries = [
            {"user_id": uid, "discipline_score": score, "rank": idx}
            for idx, (uid, score) in enumerate(raw[:limit], start=1)
        ]
        return {"kind": "discipline", "entries": entries, "total": len(raw)}

    rankings = await _nav_rankings(db, contest_id)
    ordered = sorted(rankings.items(), key=lambda item: item[1], reverse=True)
    entries = []
    for idx, (uid, nav) in enumerate(ordered[:limit], start=1):
        entries.append({"user_id": uid, "nav": nav, "rank": idx})
    return {"kind": "nav", "entries": entries, "total": len(ordered)}


async def get_rankings_for_user(
    db: AsyncSession,
    current_user_id: uuid.UUID,
    *,
    kind: str = "nav",
    contest_id: uuid.UUID | None = None,
    limit: int = 50,
) -> dict:
    """Như ``get_rankings`` nhưng kèm ``my_rank`` (hạng của user hiện tại)."""
    result = await get_rankings(
        db, kind=kind, contest_id=contest_id, limit=limit
    )
    my_rank: int | None = None

    if kind == "discipline":
        raw = await _discipline_rankings(db)
        for idx, (uid, _score) in enumerate(raw, start=1):
            if uid == current_user_id:
                my_rank = idx
                break
    else:
        rankings = await _nav_rankings(db, contest_id)
        # Nếu user chưa có vị thế/cash trong phạm vi, my_rank = None (chưa tham gia).
        ranks = {
            uid: idx
            for idx, (uid, _nav) in enumerate(
                sorted(rankings.items(), key=lambda item: item[1], reverse=True),
                start=1,
            )
        }
        my_rank = ranks.get(current_user_id)

    result["my_rank"] = my_rank
    return result
