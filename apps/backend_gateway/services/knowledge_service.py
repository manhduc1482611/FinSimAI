import re

from models.knowledge import KnowledgeBase
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession


async def match_knowledge(text: str, db: AsyncSession) -> list[KnowledgeBase]:
    text_stripped = text.strip()
    if not text_stripped:
        return []

    words = list(set(re.findall(r"\w+", text_stripped.lower())))
    if not words:
        return []

    stmt = (
        select(KnowledgeBase)
        .where(
            or_(
                KnowledgeBase.keyword.in_(words),
                KnowledgeBase.related_keywords.overlap(words),
            )
        )
        .order_by(KnowledgeBase.difficulty)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
