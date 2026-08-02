import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from api.v1.router import api_router
from clients.math_grpc_client import math_grpc_client
from core.config import settings
from core.database import dispose_engine, engine
from core.middleware import setup_middleware
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from realtime.router import (
    register_websocket_routes,
    start_ws_background,
    stop_ws_background,
)
from run_migrations import run_migrations
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _check_database(timeout: float | None = None) -> bool:
    if timeout is None:
        timeout = settings.health_check_timeout
    try:
        async with asyncio.timeout(timeout):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Running database migrations (alembic upgrade head)…")
    await asyncio.to_thread(run_migrations)

    if not await _check_database():
        raise RuntimeError("Database unreachable at startup")
    logger.info("Database connectivity confirmed at startup")

    ws_handles = await start_ws_background(app)
    logger.info("WebSocket realtime layer started (price + trade notifier)")

    yield

    logger.info("Draining in-flight traffic before shutdown...")
    await stop_ws_background(ws_handles)
    await asyncio.sleep(3.0)
    await math_grpc_client.close()
    await dispose_engine()
    logger.info("Shutdown complete: gRPC channel and database engine disposed")


def _setup_metrics(app: FastAPI) -> None:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app,
            endpoint="/metrics",
            include_in_schema=False,
        )
        logger.info("Prometheus /metrics enabled")
    except ImportError:
        logger.warning("prometheus-fastapi-instrumentator not installed; /metrics disabled")


async def _run_health_checks() -> dict:
    checks: dict = {}
    healthy = True

    async def _check(name: str, coro, hard: bool = True) -> None:
        nonlocal healthy
        try:
            async with asyncio.timeout(settings.health_check_timeout):
                ok = await coro
        except Exception as e:
            logger.error("Health check '%s' failed: %s", name, e)
            ok = False
        checks[name] = "ok" if ok else "error"
        if not ok and hard:
            healthy = False

    async def _redis_ok() -> bool:
        from core.cache import ping_cache

        return await ping_cache()

    await asyncio.gather(
        _check("database", _check_database()),
        _check("math_engine", math_grpc_client.ping()),
        _check("redis", _redis_ok(), hard=False),
    )

    checks["healthy"] = healthy
    return checks


def create_app() -> FastAPI:
    is_production = settings.environment.lower() == "production"

    app = FastAPI(
        title="FinSimAI API Gateway",
        description="Financial Simulation & AI Mentor Platform",
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
        lifespan=lifespan,
    )

    setup_middleware(app)
    app.include_router(api_router)
    register_websocket_routes(app)
    _setup_metrics(app)

    @app.get("/health/live", tags=["health"])
    async def health_live():
        return {"status": "ok", "service": "backend_gateway"}

    @app.get("/health/ready", tags=["health"])
    async def health_ready():
        checks = await _run_health_checks()
        healthy = checks.pop("healthy")
        if not healthy:
            return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
        return {"status": "ok", "checks": checks}

    @app.get("/health", tags=["health"])
    async def health():
        return await health_ready()

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.debug,
        ws="wsproto",
        proxy_headers=True,
        log_level="debug" if settings.debug else "info",
    )
