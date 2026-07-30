import grpc
import numpy as np

from . import math_engine_pb2 as pb2
from . import math_engine_pb2_grpc as pb2_grpc
from engine.pricing.price_generator import MarketConfig, PriceGenerator
from engine.portfolio.portfolio_calc import Holding, calc_nav, calc_unrealized_pnl
from engine.portfolio.risk_metrics import calc_daily_returns, calc_sharpe_ratio, calc_max_drawdown, calc_volatility
from engine.penalty_calc.penalty import calc_cooldown_seconds, calc_risk_score_delta, calc_points_deducted


class MathEngineServiceServicer(pb2_grpc.MathEngineServiceServicer):

    def CalculatePortfolio(self, request, context):
        try:
            holdings = [
                Holding(
                    quantity=h.quantity,
                    average_buy_price=h.avg_buy_price,
                    current_price=h.current_price,
                )
                for h in request.holdings
            ]
            nav = calc_nav(request.cash, holdings)
            unrealized = calc_unrealized_pnl(holdings)

            return pb2.CalculatePortfolioResponse(
                nav=nav,
                unrealized_pnl=unrealized,
                success=True,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.CalculatePortfolioResponse(success=False)

    def GenerateNextPrices(self, request, context):
        try:
            config = MarketConfig(
                mu=request.mu,
                sigma=request.sigma,
                price_limit_pct=request.price_limit_pct,
                jump_lambda=request.jump_lambda,
                jump_mu=request.jump_mu,
                jump_sigma=request.jump_sigma,
            )
            seed = request.seed if request.HasField("seed") else None
            gen = PriceGenerator(config, seed=seed)
            path = gen.generate_price_path(
                start_price=request.current_price,
                dt_simulated_years=request.dt_years,
                steps=request.n_steps,
            )

            return pb2.GenerateNextPricesResponse(
                prices=path.tolist(),
                success=True,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.GenerateNextPricesResponse(success=False)

    def CalculateRiskMetrics(self, request, context):
        try:
            nav_array = np.array(request.nav_history, dtype=np.float64)

            if len(nav_array) < 2:
                return pb2.CalculateRiskMetricsResponse(
                    sharpe_ratio=0.0,
                    max_drawdown=0.0,
                    volatility=0.0,
                    success=True,
                )

            returns = calc_daily_returns(nav_array)
            sharpe = calc_sharpe_ratio(returns, risk_free_rate=request.risk_free_rate)
            mdd = calc_max_drawdown(nav_array)
            vol = calc_volatility(returns)

            return pb2.CalculateRiskMetricsResponse(
                sharpe_ratio=sharpe,
                max_drawdown=mdd,
                volatility=vol,
                success=True,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.CalculateRiskMetricsResponse(success=False)

    def CheckPenaltyStatus(self, request, context):
        try:
            risk_score = request.risk_score
            severity = request.trap_severity

            cooldown = calc_cooldown_seconds(risk_score)
            delta = calc_risk_score_delta(severity, risk_score)
            points = calc_points_deducted(severity)
            new_score = max(0, min(risk_score + delta, 100))

            return pb2.CheckPenaltyStatusResponse(
                cooldown_seconds=cooldown,
                risk_score_delta=delta,
                points_deducted=points,
                new_risk_score=new_score,
                success=True,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return pb2.CheckPenaltyStatusResponse(success=False)
