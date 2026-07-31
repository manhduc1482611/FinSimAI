import uuid

from core.dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.knowledge import KnowledgeBase
from schemas.knowledge import (
    KnowledgeListResponse,
    KnowledgeMatchRequest,
    KnowledgeMatchResponse,
    KnowledgeResponse,
)
from services.knowledge_service import match_knowledge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=KnowledgeListResponse)
async def list_knowledge(
    category: str | None = Query(None),
    difficulty: int | None = Query(None, ge=1, le=5),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeBase)
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)
    if difficulty:
        stmt = stmt.where(KnowledgeBase.difficulty == difficulty)

    stmt = stmt.order_by(KnowledgeBase.keyword)
    items, total = await paginate(db, stmt, skip, limit)

    return KnowledgeListResponse(items=items, total=total)


@router.get("/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(knowledge_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(KnowledgeBase, knowledge_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge entry not found"
        )
    return entry


@router.post("/match", response_model=KnowledgeMatchResponse)
async def match(body: KnowledgeMatchRequest, db: AsyncSession = Depends(get_db)):
    matches = await match_knowledge(body.text, db)
    return KnowledgeMatchResponse(matches=matches)
