from collections.abc import Sequence
from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

_T = TypeVar("_T")


async def paginate(
    db: AsyncSession,
    stmt: Select[tuple[_T]],
    skip: int,
    limit: int,
) -> tuple[Sequence[_T], int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.offset(skip).limit(limit))
    return result.scalars().all(), total
