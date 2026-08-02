import logging

import httpx
from core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUTS = httpx.Timeout(connect=2.0, read=10.0, write=10.0, pool=2.0)


class MathClient:
    """HTTP client tới Math Engine (web service). JSON API thay cho gRPC."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=settings.math_engine_url.rstrip("/"),
                timeout=_TIMEOUTS,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Math engine HTTP client closed")

    async def ping(self, timeout: float = 2.0) -> bool:
        try:
            client = await self._ensure_client()
            resp = await client.get("/health/live", timeout=timeout)
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception as e:  # noqa: BLE001
            logger.error("Math engine health check failed: %s", e)
            return False

    async def _post(self, path: str, payload: dict, timeout: float) -> dict:
        client = await self._ensure_client()
        resp = await client.post(path, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    async def calculate_portfolio(
        self,
        cash: float,
        holdings: list[dict],
        timeout: int = 5,
    ) -> dict:
        try:
            data = await self._post(
                "/api/v1/portfolio/calculate",
                {"cash": cash, "holdings": holdings},
                timeout,
            )
            return {
                "nav": data["nav"],
                "unrealized_pnl": data["unrealized_pnl"],
                "success": data["success"],
            }
        except Exception:  # noqa: BLE001
            logger.exception("Math engine 'calculate_portfolio' failed")
            return {"nav": cash, "unrealized_pnl": 0.0, "success": False}

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
        payload = {
            "current_price": current_price,
            "mu": mu,
            "sigma": sigma,
            "dt_years": dt_years,
            "n_steps": n_steps,
            "price_limit_pct": price_limit_pct,
            "jump_lambda": jump_lambda,
            "jump_mu": jump_mu,
            "jump_sigma": jump_sigma,
        }
        if seed is not None:
            payload["seed"] = seed
        try:
            data = await self._post("/api/v1/prices/generate", payload, timeout)
            return {"prices": data["prices"], "success": data["success"]}
        except Exception:  # noqa: BLE001
            logger.exception("Math engine 'generate_next_prices' failed")
            return {"prices": [], "success": False}

    async def calculate_risk_metrics(
        self,
        nav_history: list[float],
        risk_free_rate: float = 0.05,
        timeout: int = 5,
    ) -> dict:
        try:
            data = await self._post(
                "/api/v1/risk/calculate",
                {"nav_history": nav_history, "risk_free_rate": risk_free_rate},
                timeout,
            )
            return {
                "sharpe_ratio": data["sharpe_ratio"],
                "max_drawdown": data["max_drawdown"],
                "volatility": data["volatility"],
                "success": data["success"],
            }
        except Exception:  # noqa: BLE001
            logger.exception("Math engine 'calculate_risk_metrics' failed")
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "volatility": 0.0,
                "success": False,
            }

    async def check_penalty_status(
        self,
        risk_score: int,
        trap_severity: int,
        timeout: int = 5,
    ) -> dict:
        try:
            data = await self._post(
                "/api/v1/penalty/check",
                {"risk_score": risk_score, "trap_severity": trap_severity},
                timeout,
            )
            return {
                "cooldown_seconds": data["cooldown_seconds"],
                "risk_score_delta": data["risk_score_delta"],
                "points_deducted": data["points_deducted"],
                "new_risk_score": data["new_risk_score"],
                "success": data["success"],
            }
        except Exception:  # noqa: BLE001
            logger.exception("Math engine 'check_penalty_status' failed")
            return {
                "cooldown_seconds": 0.0,
                "risk_score_delta": 0,
                "points_deducted": 0,
                "new_risk_score": risk_score,
                "success": False,
            }


math_client = MathClient()
