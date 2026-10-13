"""Integration test: dựng TOÀN BỘ app gateway (main.create_app) rồi gọi qua HTTP.

Khác với các test đơn vị (dựng mini-app), test này kiểm tra app **thật** đã lắp
đủ router + middleware + exception handler + observability. Không chạy lifespan
(httpx.ASGITransport không kích hoạt startup) nên KHÔNG cần Postgres/Redis thật.
"""

from collections.abc import AsyncIterator

import httpx
import pytest
from core.config import settings
from main import app

INTERNAL_KEY = "test-internal-key"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def internal_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "internal_api_key", INTERNAL_KEY)
    return INTERNAL_KEY


async def test_health_live_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "backend_gateway"}


async def test_metrics_records_traffic(
    client: httpx.AsyncClient, internal_key: str
) -> None:
    await client.get("/health/live")
    resp = await client.get("/metrics", headers={"X-Internal-Api-Key": internal_key})
    assert resp.status_code == 200
    assert "finsim_http_requests_total" in resp.text
    assert "finsim_uptime_seconds" in resp.text


async def test_metrics_requires_internal_key(
    client: httpx.AsyncClient, internal_key: str
) -> None:
    resp = await client.get("/metrics")
    assert resp.status_code == 403


async def test_metrics_locked_when_key_unconfigured(client: httpx.AsyncClient) -> None:
    # Fail-closed: INTERNAL_API_KEY trống (mặc định test) → khoá kể cả có header.
    resp = await client.get("/metrics", headers={"X-Internal-Api-Key": "bat-ky"})
    assert resp.status_code == 403


async def test_cors_preflight_allows_frontend_origin(client: httpx.AsyncClient) -> None:
    resp = await client.options(
        "/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_unknown_route_is_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/khong-ton-tai")
    assert resp.status_code == 404


async def test_openapi_available_in_dev(client: httpx.AsyncClient) -> None:
    # conftest đặt ENVIRONMENT mặc định = development → docs mở.
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "Capia API Gateway"
