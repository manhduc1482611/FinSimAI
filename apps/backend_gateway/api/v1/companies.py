import uuid
from typing import Annotated, cast

from core.dependencies import get_current_user_optional, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from models.user import User
from schemas.company import CompanyListResponse, CompanyResponse
from services import task_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/companies", tags=["companies"])


def _escape_like(s: str) -> str:
    return s.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    sector: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
) -> CompanyListResponse:
    stmt = select(Company).where(Company.is_active.is_(True))

    if sector:
        stmt = stmt.where(Company.sector == sector)
    if search:
        pattern = f"%{_escape_like(search)}%"
        stmt = stmt.where(
            (Company.symbol.ilike(pattern)) | (Company.name.ilike(pattern))
        )

    stmt = stmt.order_by(Company.symbol)
    items, total = await paginate(db, stmt, skip, limit)

    return CompanyListResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)] = cast(AsyncSession, None),
    current_user: User | None = Depends(get_current_user_optional),
) -> Company:
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if current_user is not None:
        await task_service.record_event(db, current_user, "company_view")
    return company
