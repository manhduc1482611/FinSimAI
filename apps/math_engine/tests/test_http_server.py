"""Tests cho Math Engine HTTP server: giới hạn tham số + shared-secret auth.

Bối cảnh (P0): endpoint mở công khai, ``n_steps`` không giới hạn → ``n_steps=10**9``
cấp phát mảng numpy khổng lồ + vòng lặp Python, DoS instance free. Thêm trần tham
số và yêu cầu ``X-Internal-Api-Key`` khi cấu hình.
"""

from typing import Any

import httpx
import pytest

from http_server import MAX_N_STEPS, MAX_NAV_POINTS, app

HEADER = "X-Internal-Api-Key"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _price_payload(**over: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "current_price": 100.0,
        "dt_years": 0.001,
        "n_steps": 1,
    }
    payload.update(over)
    return payload


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_API_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


async def test_valid_price_request_succeeds() -> None:
    async with _client() as c:
        resp = await c.post("/api/v1/prices/generate", json=_price_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["prices"]) == 2  # start + 1 step


async def test_reference_price_anchors_band() -> None:
    # Biên ±7% neo vào reference_price (50) chứ không phải current_price (100):
    # bước đi bị kẹp về trần 53.5.
    async with _client() as c:
        resp = await c.post(
            "/api/v1/prices/generate",
            json=_price_payload(
                current_price=100.0,
                reference_price=50.0,
                mu=0.0,
                sigma=0.0,
                price_limit_pct=0.07,
                n_steps=1,
            ),
        )
    assert resp.status_code == 200
    prices = resp.json()["prices"]
    assert prices[0] == 100.0
    assert prices[-1] == 53.5


async def test_n_steps_over_limit_rejected() -> None:
    async with _client() as c:
        resp = await c.post(
            "/api/v1/prices/generate", json=_price_payload(n_steps=MAX_N_STEPS + 1)
        )
    assert resp.status_code == 422


async def test_n_steps_zero_rejected() -> None:
    async with _client() as c:
        resp = await c.post("/api/v1/prices/generate", json=_price_payload(n_steps=0))
    assert resp.status_code == 422


async def test_nav_history_over_limit_rejected() -> None:
    huge = [1.0] * (MAX_NAV_POINTS + 1)
    async with _client() as c:
        resp = await c.post("/api/v1/risk/calculate", json={"nav_history": huge})
    assert resp.status_code == 422


async def test_requires_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    async with _client() as c:
        resp = await c.post("/api/v1/prices/generate", json=_price_payload())
    assert resp.status_code == 403


async def test_accepts_correct_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    async with _client() as c:
        resp = await c.post(
            "/api/v1/prices/generate",
            json=_price_payload(),
            headers={HEADER: "s3cret-internal"},
        )
    assert resp.status_code == 200


async def test_rejects_wrong_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_KEY", "s3cret-internal")
    async with _client() as c:
        resp = await c.post(
            "/api/v1/prices/generate",
            json=_price_payload(),
            headers={HEADER: "wrong"},
        )
    assert resp.status_code == 403


async def test_production_without_key_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    async with _client() as c:
        resp = await c.post("/api/v1/prices/generate", json=_price_payload())
    assert resp.status_code == 503


async def test_dev_without_key_allowed() -> None:
    async with _client() as c:
        resp = await c.post("/api/v1/prices/generate", json=_price_payload())
    assert resp.status_code == 200


async def test_health_open_even_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    async with _client() as c:
        resp = await c.get("/health/live")
    assert resp.status_code == 200
