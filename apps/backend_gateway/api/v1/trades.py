from decimal import Decimal

from core.dependencies import get_current_user, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.company import Company
from models.trade import Order, Portfolio
from models.user import User
from schemas.trade import (
    OrderRequest,
    OrderResponse,
    PortfolioListResponse,
    PortfolioResponse,
)
from services import penalty_service
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/portfolio", response_model=PortfolioListResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Portfolio, Company).join(
        Company, Portfolio.company_id == Company.id
    ).where(Portfolio.user_id == current_user.id, Portfolio.quantity > 0)
    result = await db.execute(stmt)
    rows = result.all()

    items: list[PortfolioResponse] = []
    total_nav = current_user.cash_balance + current_user.frozen_cash

    for portfolio, company in rows:
        market_value = portfolio.quantity * company.current_price
        cost_basis = portfolio.quantity * portfolio.average_buy_price
        unrealized_pnl = market_value - cost_basis
        total_nav += market_value

        items.append(
            PortfolioResponse(
                company_id=company.id,
                symbol=company.symbol,
                company_name=company.name,
                quantity=portfolio.quantity,
                average_buy_price=portfolio.average_buy_price,
                current_price=company.current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
            )
        )

    return PortfolioListResponse(
        items=items,
        total_cash=current_user.cash_balance,
        total_nav=total_nav,
    )


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lock = await penalty_service.enforce_cooldown(current_user.id, db)
    if lock is not None:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "code": "cooldown_locked",
                "message": (
                    "Tài khoản đang bị khóa giao dịch do vi phạm kỷ luật. "
                    "Hoàn thành bài tập phản tư với Mentor để mở khóa."
                ),
                "locked": True,
                "cooldown_until": (
                    lock["cooldown_until"].isoformat()
                    if lock["cooldown_until"] is not None
                    else None
                ),
                "remaining_seconds": lock["remaining_seconds"],
                "risk_score": lock["risk_score"],
                "reason": lock["reason"],
            },
        )

    company = await db.get(Company, body.company_id)
    if not company or not company.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    frozen_cash = Decimal("0.00")
    frozen_quantity = Decimal("0.0000")

    if body.side == "buy":
        user_stmt = select(User).where(User.id == current_user.id).with_for_update()
        user_result = await db.execute(user_stmt)
        locked_user = user_result.scalar_one()

        effective_price = company.current_price if body.type == "market" else body.price
        if effective_price is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Price is required for limit orders",
            )
        total_cost = body.quantity * effective_price
        available_cash = locked_user.cash_balance - locked_user.frozen_cash

        if total_cost > available_cash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient available cash",
            )

        locked_user.cash_balance -= total_cost
        locked_user.frozen_cash += total_cost
        frozen_cash = total_cost

    elif body.side == "sell":
        stmt = (
            select(Portfolio)
            .where(
                Portfolio.user_id == current_user.id,
                Portfolio.company_id == body.company_id,
            )
            .with_for_update()
        )
        result = await db.execute(stmt)
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No shares held in this company",
            )
        available_quantity = portfolio.quantity - portfolio.frozen_quantity
        if body.quantity > available_quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient available shares",
            )
        portfolio.frozen_quantity += body.quantity
        frozen_quantity = body.quantity

    order = Order(
        user_id=current_user.id,
        company_id=body.company_id,
        side=body.side,
        type=body.type,
        price=body.price if body.type == "limit" else None,
        quantity=body.quantity,
        frozen_cash=frozen_cash,
        frozen_quantity=frozen_quantity,
        simulated_at=company.updated_at,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Order).where(Order.user_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
