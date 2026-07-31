import asyncio
import logging

import grpc
from core.config import settings

from clients.proto import math_engine_pb2 as pb2
from clients.proto import math_engine_pb2_grpc as pb2_grpc

logger = logging.getLogger(__name__)


class MathGrpcClient:
    def __init__(self) -> None:
        self._channel: grpc.aio.Channel | None = None
        self._stub: pb2_grpc.MathEngineServiceStub | None = None
        self._lock = asyncio.Lock()

    async def _ensure_connected(self) -> None:
        if self._channel is not None:
            return
        async with self._lock:
            if self._channel is not None:
                return
            target = f"{settings.math_engine_grpc_host}:{settings.math_engine_grpc_port}"
            self._channel = grpc.aio.insecure_channel(target)
            self._stub = pb2_grpc.MathEngineServiceStub(self._channel)
            logger.info("gRPC channel + stub created: %s", target)

    async def close(self) -> None:
        async with self._lock:
            if self._channel:
                await self._channel.close()
                self._channel = None
                self._stub = None
                logger.info("gRPC channel closed")

    async def ping(self, timeout: float = 2.0) -> bool:
        try:
            await self._ensure_connected()
            state = self._channel.get_state(try_to_connect=True)
            if state == grpc.ChannelConnectivity.READY:
                return True
            deadline = asyncio.get_running_loop().time() + timeout
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.1)
                state = self._channel.get_state(try_to_connect=True)
                if state == grpc.ChannelConnectivity.READY:
                    return True
            return False
        except Exception as e:
            logger.error("gRPC connectivity ping failed: %s", e)
            return False

    async def _call(self, method_name: str, request, timeout: int, fallback_factory):
        try:
            await self._ensure_connected()
            method = getattr(self._stub, method_name)
            resp = await method(request, timeout=timeout)
            return resp
        except Exception:
            logger.exception("gRPC call '%s' failed", method_name)
            return fallback_factory()

    async def calculate_portfolio(
        self,
        cash: float,
        holdings: list[dict],
        timeout: int = 5,
    ) -> dict:
        req = pb2.CalculatePortfolioRequest(
            cash=cash,
            holdings=[
                pb2.Holding(
                    quantity=h["quantity"],
                    avg_buy_price=h["avg_buy_price"],
                    current_price=h["current_price"],
                )
                for h in holdings
            ],
        )
        resp = await self._call(
            "CalculatePortfolio", req, timeout,
            lambda: pb2.CalculatePortfolioResponse(nav=cash, unrealized_pnl=0.0, success=False),
        )
        return {
            "nav": resp.nav,
            "unrealized_pnl": resp.unrealized_pnl,
            "success": resp.success,
        }

    async def generate_next_prices(
        self,
        current_price: float,
        mu: float,
        sigma: float,
        dt_years: float,
        n_steps: int,
        seed: int | None = None,
        price_limit_pct: float = 0.0,
        jump_lambda: float = 0.0,
        jump_mu: float = 0.0,
        jump_sigma: float = 0.0,
        timeout: int = 10,
    ) -> dict:
        req = pb2.GenerateNextPricesRequest(
            current_price=current_price,
            mu=mu,
            sigma=sigma,
            dt_years=dt_years,
            n_steps=n_steps,
            price_limit_pct=price_limit_pct,
            jump_lambda=jump_lambda,
            jump_mu=jump_mu,
            jump_sigma=jump_sigma,
        )
        if seed is not None:
            req.seed = seed

        resp = await self._call(
            "GenerateNextPrices", req, timeout,
            lambda: pb2.GenerateNextPricesResponse(prices=[], success=False),
        )
        return {
            "prices": list(resp.prices),
            "success": resp.success,
        }

    async def calculate_risk_metrics(
        self,
        nav_history: list[float],
        risk_free_rate: float = 0.05,
        timeout: int = 5,
    ) -> dict:
        req = pb2.CalculateRiskMetricsRequest(
            nav_history=nav_history,
            risk_free_rate=risk_free_rate,
        )
        resp = await self._call(
            "CalculateRiskMetrics", req, timeout,
            lambda: pb2.CalculateRiskMetricsResponse(
                sharpe_ratio=0.0, max_drawdown=0.0, volatility=0.0, success=False
            ),
        )
        return {
            "sharpe_ratio": resp.sharpe_ratio,
            "max_drawdown": resp.max_drawdown,
            "volatility": resp.volatility,
            "success": resp.success,
        }

    async def check_penalty_status(
        self,
        risk_score: int,
        trap_severity: int,
        timeout: int = 5,
    ) -> dict:
        req = pb2.CheckPenaltyStatusRequest(
            risk_score=risk_score,
            trap_severity=trap_severity,
        )
        resp = await self._call(
            "CheckPenaltyStatus", req, timeout,
            lambda: pb2.CheckPenaltyStatusResponse(
                cooldown_seconds=0.0, risk_score_delta=0,
                points_deducted=0, new_risk_score=risk_score,
                success=False,
            ),
        )
        return {
            "cooldown_seconds": resp.cooldown_seconds,
            "risk_score_delta": resp.risk_score_delta,
            "points_deducted": resp.points_deducted,
            "new_risk_score": resp.new_risk_score,
            "success": resp.success,
        }


math_grpc_client = MathGrpcClient()
