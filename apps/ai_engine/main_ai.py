"""AI Engine Web API bootstrap (FastAPI).

Entry-point cho service ``ai-engine-api`` trên Render.
Chứa các endpoint health-check + cấu trúc FastAPI để các route AI được
thêm vào sau này. Không chứa business logic — chỉ là bootstrap cấu hình.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger("ai_engine_api")

app = FastAPI(
    title="FinSimAI AI Engine API",
    description="AI Engine Web API — mentors, news intelligence & social agents",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/health/live", tags=["health"])
async def health_live() -> dict[str, str]:
    return {"status": "ok", "service": "ai_engine_api"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> JSONResponse:
    """Kiểm tra sẵn sàng: Redis (nếu có) và Gemini (nếu có key)."""
    checks: dict[str, str] = {}

    try:
        from integrations.gemini import GeminiClient

        client = GeminiClient()
        checks["gemini"] = "available" if client.available else "missing_api_key"
    except Exception as e:  # noqa: BLE001
        logger.error("Gemini check failed: %s", e)
        checks["gemini"] = "error"

    try:
        import arq
        from arq.connections import RedisSettings

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        redis_settings = RedisSettings.from_dsn(url)
        pool = await arq.create_pool(redis_settings)
        await pool.ping()
        await pool.close(close_connection_pool=True)
        checks["redis"] = "ok"
    except Exception as e:  # noqa: BLE001
        logger.error("Redis check failed: %s", e)
        checks["redis"] = "error"

    healthy = checks.get("redis", "error") == "ok"
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )


@app.get("/health", tags=["health"])
async def health() -> JSONResponse:
    return await health_ready()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "main_ai:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        proxy_headers=True,
        log_level="info",
    )
