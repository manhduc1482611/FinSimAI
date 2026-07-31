import re
import uuid

from core.dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from schemas.company import CompanyListResponse, CompanyResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.pagination import paginate

router = APIRouter(prefix="/companies", tags=["companies"])


def _escape_like(s: str) -> str:
    return s.replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    sector: str | None = Query(None),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
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

    return CompanyListResponse(items=items, total=total)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company
