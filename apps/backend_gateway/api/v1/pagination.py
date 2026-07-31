from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def paginate(
    db: AsyncSession,
    stmt: Select,
    skip: int,
    limit: int,
) -> tuple[Sequence, int]:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(stmt.offset(skip).limit(limit))
    return result.scalars().all(), total
