"""Tests cho P5 — metrics registry + middleware endpoint ``/metrics``."""

import uuid

import httpx
import pytest
from core import metrics
from core.middleware import setup_middleware
from fastapi import FastAPI
from starlette.responses import PlainTextResponse


def test_bucket_path_normalizes_ids() -> None:
    assert metrics._bucket_path("/api/v1/news") == "/api/v1/news"
    assert metrics._bucket_path(f"/api/v1/news/{uuid.uuid4()}") == "/api/v1/news/{id}"
    assert metrics._bucket_path("/api/v1/social/12345") == "/api/v1/social/{id}"
    assert metrics._bucket_path("/api/v1/contests/abc-def") == "/api/v1/contests/abc-def"


def test_collect_output_contains_metrics() -> None:
    metrics._requests.clear()
    metrics._latency.clear()
    metrics.record_request("/api/v1/news", "GET", 200, 0.01)
    metrics.record_request(f"/api/v1/news/{uuid.uuid4()}", "GET", 200, 0.02)
    metrics.record_request("/api/v1/auth/login", "POST", 401, 0.5)
    metrics.record_request("/api/v1/boom", "GET", 500, 3.0)

    out = metrics.collect()
    assert (
        'finsim_http_requests_total{route="/api/v1/news",method="GET",status="200"} 1'
        in out
    )
    assert (
        'finsim_http_requests_total{route="/api/v1/news/{id}",method="GET",status="200"} 1'
        in out
    )
    assert (
        'finsim_http_requests_total{route="/api/v1/auth/login",method="POST",status="401"} 1'
        in out
    )
    assert "finsim_http_errors_total 1" in out
    assert 'finsim_http_request_duration_seconds_bucket{le="0.05"}' in out
    assert "finsim_http_request_duration_seconds_sum" in out
    assert "finsim_http_request_duration_seconds_count 4" in out
    assert "finsim_uptime_seconds" in out
    assert "finsim_ws_active_connections" in out


@pytest.mark.asyncio
async def test_metrics_endpoint_via_app() -> None:
    app = FastAPI()
    setup_middleware(app)

    @app.get("/metrics")
    async def m() -> PlainTextResponse:
        return PlainTextResponse(metrics.collect())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.get("/api/v1/news/abc")
        resp = await c.get("/metrics")
    assert resp.status_code == 200
    assert "finsim_http_requests_total" in resp.text
