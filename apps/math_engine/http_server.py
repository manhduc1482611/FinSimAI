"""FinSimAI Math Engine — FastAPI HTTP server.

Chạy trên Render như một free web service (gRPC không được Render hỗ trợ trên
public web services). Endpoint trả JSON giống hệt cấu trúc proto response cũ để
backend không phải đổi logic gọi.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

from engine.penalty_calc.penalty import (
    calc_cooldown_seconds,
    calc_points_deducted,
    calc_risk_score_delta,
)
from engine.portfolio.portfolio_calc import Holding, calc_nav, calc_unrealized_pnl
from engine.portfolio.risk_metrics import (
    calc_daily_returns,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_volatility,
)
from engine.pricing.price_generator import MarketConfig, PriceGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FinSimAI Math Engine", version="0.1.0")


class HoldingIn(BaseModel):
    quantity: float
    avg_buy_price: float
    current_price: float


class CalculatePortfolioRequest(BaseModel):
    cash: float
    holdings: list[HoldingIn] = Field(default_factory=list)


class CalculatePortfolioResponse(BaseModel):
    nav: float
    unrealized_pnl: float
    success: bool


class GenerateNextPricesRequest(BaseModel):
    current_price: float
    mu: float = 0.10
    sigma: float = 0.25
    dt_years: float
    n_steps: int
    seed: int | None = None
    # Biên giá VN (7%) — bằng default của MarketConfig. Không để 0.0: clip với
    # floor = ceil = start sẽ khoá path về đúng giá hiện tại, thị trường đứng yên.
    price_limit_pct: float = 0.07
    jump_lambda: float = 0.0
    jump_mu: float = 0.0
    jump_sigma: float = 0.0


class GenerateNextPricesResponse(BaseModel):
    prices: list[float]
    success: bool


class CalculateRiskMetricsRequest(BaseModel):
    nav_history: list[float]
    risk_free_rate: float = 0.05


class CalculateRiskMetricsResponse(BaseModel):
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    success: bool


class CheckPenaltyStatusRequest(BaseModel):
    risk_score: int
    trap_severity: int


class CheckPenaltyStatusResponse(BaseModel):
    cooldown_seconds: float
    risk_score_delta: int
    points_deducted: int
    new_risk_score: int
    success: bool


@app.get("/health/live")
async def health_live() -> dict:
    return {"status": "ok", "service": "math_engine"}


@app.post("/api/v1/portfolio/calculate", response_model=CalculatePortfolioResponse)
async def calculate_portfolio(req: CalculatePortfolioRequest) -> CalculatePortfolioResponse:
    try:
        holdings = [
            Holding(
                quantity=h.quantity,
                average_buy_price=h.avg_buy_price,
                current_price=h.current_price,
            )
            for h in req.holdings
        ]
        nav = calc_nav(req.cash, holdings)
        unrealized = calc_unrealized_pnl(holdings)
        return CalculatePortfolioResponse(nav=nav, unrealized_pnl=unrealized, success=True)
    except Exception as e:  # noqa: BLE001
        logger.error("calculate_portfolio failed: %s", e)
        return CalculatePortfolioResponse(nav=0.0, unrealized_pnl=0.0, success=False)


@app.post("/api/v1/prices/generate", response_model=GenerateNextPricesResponse)
async def generate_next_prices(req: GenerateNextPricesRequest) -> GenerateNextPricesResponse:
    try:
        config = MarketConfig(
            mu=req.mu,
            sigma=req.sigma,
            price_limit_pct=req.price_limit_pct,
            jump_lambda=req.jump_lambda,
            jump_mu=req.jump_mu,
            jump_sigma=req.jump_sigma,
        )
        gen = PriceGenerator(config, seed=req.seed)
        path = gen.generate_price_path(
            start_price=req.current_price,
            dt_simulated_years=req.dt_years,
            steps=req.n_steps,
        )
        return GenerateNextPricesResponse(prices=path.tolist(), success=True)
    except Exception as e:  # noqa: BLE001
        logger.error("generate_next_prices failed: %s", e)
        return GenerateNextPricesResponse(prices=[], success=False)


@app.post("/api/v1/risk/calculate", response_model=CalculateRiskMetricsResponse)
async def calculate_risk_metrics(req: CalculateRiskMetricsRequest) -> CalculateRiskMetricsResponse:
    try:
        nav_array = np.array(req.nav_history, dtype=np.float64)
        if len(nav_array) < 2:
            return CalculateRiskMetricsResponse(
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                volatility=0.0,
                success=True,
            )
        returns = calc_daily_returns(nav_array)
        sharpe = calc_sharpe_ratio(returns, risk_free_rate=req.risk_free_rate)
        mdd = calc_max_drawdown(nav_array)
        vol = calc_volatility(returns)
        return CalculateRiskMetricsResponse(
            sharpe_ratio=sharpe,
            max_drawdown=mdd,
            volatility=vol,
            success=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("calculate_risk_metrics failed: %s", e)
        return CalculateRiskMetricsResponse(
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            success=False,
        )


@app.post("/api/v1/penalty/check", response_model=CheckPenaltyStatusResponse)
async def check_penalty_status(req: CheckPenaltyStatusRequest) -> CheckPenaltyStatusResponse:
    try:
        risk_score = req.risk_score
        severity = req.trap_severity
        cooldown = calc_cooldown_seconds(risk_score)
        delta = calc_risk_score_delta(severity, risk_score)
        points = calc_points_deducted(severity)
        new_score = max(0, min(risk_score + delta, 100))
        return CheckPenaltyStatusResponse(
            cooldown_seconds=cooldown,
            risk_score_delta=delta,
            points_deducted=points,
            new_risk_score=new_score,
            success=True,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("check_penalty_status failed: %s", e)
        return CheckPenaltyStatusResponse(
            cooldown_seconds=0.0,
            risk_score_delta=0,
            points_deducted=0,
            new_risk_score=0,
            success=False,
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
