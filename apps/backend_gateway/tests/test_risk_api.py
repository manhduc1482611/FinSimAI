"""API tests cho cơ chế phạt cooldown (Bước 5.1).

Kiểm tra contract HTTP: ``GET /risk/cooldown``, ``POST /risk/penalties``,
``POST /risk/cooldown/clear`` và đặc biệt là **HTTP 423** khi đặt lệnh trong
lúc tài khoản đang bị khóa. Service layer được monkeypatch — không cần DB.
"""

import uuid
from types import SimpleNamespace

import httpx
import pytest
from api.v1 import risk as risk_api
from api.v1 import trades as trades_api
from core.dependencies import get_current_user, get_db
from fastapi import FastAPI
from services import penalty_service


class FakeDb:
    """DB thật không dùng tới trong test — chỉ cần ``get`` cho luồng order."""

    async def get(self, model, pk):
        return None


@pytest.fixture
def app():
    # Dùng app tối giản chỉ với 2 router — tránh Prometheus instrumentator
    # middleware (lỗi có sẵn của thư viện với `_IncludedRouter`), không cần DB.
    app = FastAPI()
    app.include_router(risk_api.router, prefix="/api/v1")
    app.include_router(trades_api.router, prefix="/api/v1")

    fake_user = SimpleNamespace(id=uuid.uuid4(), risk_score=50, is_active=True)

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: FakeDb()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ─── GET /api/v1/risk/cooldown ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_cooldown_status_locked(client, monkeypatch):
    async def fake_status(user_id, db):
        return {
            "success": True,
            "locked": True,
            "cooldown_until": None,
            "remaining_seconds": 42,
            "risk_score": 66,
            "reason": "Vi phạm kỷ luật giao dịch — fomo",
        }

    monkeypatch.setattr(penalty_service, "get_penalty_status", fake_status)

    resp = await client.get("/api/v1/risk/cooldown")

    assert resp.status_code == 200
    data = resp.json()
    assert data["locked"] is True
    assert data["remaining_seconds"] == 42
    assert data["risk_score"] == 66
    assert data["reason"] is not None


@pytest.mark.asyncio
async def test_cooldown_status_unlocked(client, monkeypatch):
    async def fake_status(user_id, db):
        return {
            "success": True,
            "locked": False,
            "cooldown_until": None,
            "remaining_seconds": 0,
            "risk_score": 10,
            "reason": None,
        }

    monkeypatch.setattr(penalty_service, "get_penalty_status", fake_status)

    resp = await client.get("/api/v1/risk/cooldown")

    assert resp.status_code == 200
    assert resp.json()["locked"] is False


# ─── POST /api/v1/risk/penalties ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_penalty_201(client, monkeypatch):
    async def fake_apply(user_id, severity, db, *, trap_type, description):
        return {
            "success": True,
            "cooldown_seconds": 30.0,
            "risk_score_delta": 5,
            "points_deducted": 25,
            "new_risk_score": 55,
            "cooldown_until": None,
            "reason": "Vi phạm — fomo",
        }

    monkeypatch.setattr(penalty_service, "apply_penalty", fake_apply)

    resp = await client.post(
        "/api/v1/risk/penalties",
        json={"trap_type": "fomo", "severity": 4, "description": "Đu đỉnh"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["new_risk_score"] == 55
    assert data["points_deducted"] == 25
    assert data["cooldown_seconds"] == 30.0


@pytest.mark.asyncio
async def test_create_penalty_rejects_bad_severity(client):
    resp = await client.post(
        "/api/v1/risk/penalties",
        json={"trap_type": "fomo", "severity": 9},
    )
    assert resp.status_code == 422


# ─── POST /api/v1/risk/cooldown/clear ────────────────────────────────────


@pytest.mark.asyncio
async def test_clear_cooldown_200(client, monkeypatch):
    async def fake_clear(user_id, db):
        return {
            "success": True,
            "cleared": True,
            "locked": False,
            "cooldown_until": None,
            "remaining_seconds": 0,
            "risk_score": 55,
            "reason": None,
        }

    monkeypatch.setattr(penalty_service, "clear_cooldown", fake_clear)

    resp = await client.post("/api/v1/risk/cooldown/clear")

    assert resp.status_code == 200
    assert resp.json()["locked"] is False


@pytest.mark.asyncio
async def test_clear_cooldown_still_locked(client, monkeypatch):
    async def fake_clear(user_id, db):
        return {
            "success": True,
            "cleared": False,
            "locked": True,
            "cooldown_until": None,
            "remaining_seconds": 120,
            "risk_score": 55,
            "reason": "Vẫn trong thời gian phạt",
        }

    monkeypatch.setattr(penalty_service, "clear_cooldown", fake_clear)

    resp = await client.post("/api/v1/risk/cooldown/clear")

    assert resp.status_code == 200
    assert resp.json()["locked"] is True


# ─── POST /api/v1/trades/orders (gate 423) ───────────────────────────────


@pytest.mark.asyncio
async def test_create_order_blocked_with_423(client, monkeypatch):
    async def fake_enforce(user_id, db):
        return {
            "locked": True,
            "cooldown_until": None,
            "remaining_seconds": 300,
            "risk_score": 60,
            "reason": "Vi phạm kỷ luật giao dịch — panic",
        }

    monkeypatch.setattr(penalty_service, "enforce_cooldown", fake_enforce)

    resp = await client.post(
        "/api/v1/trades/orders",
        json={
            "company_id": str(uuid.uuid4()),
            "side": "buy",
            "type": "market",
            "quantity": "10",
        },
    )

    assert resp.status_code == 423
    detail = resp.json()["detail"]
    assert detail["code"] == "cooldown_locked"
    assert detail["remaining_seconds"] == 300
    assert detail["risk_score"] == 60


@pytest.mark.asyncio
async def test_create_order_passes_gate_when_unlocked(client, monkeypatch):
    async def fake_enforce(user_id, db):
        return None

    monkeypatch.setattr(penalty_service, "enforce_cooldown", fake_enforce)

    # Qua được gate → đi tiếp tới company lookup (DB fake trả None → 404).
    resp = await client.post(
        "/api/v1/trades/orders",
        json={
            "company_id": str(uuid.uuid4()),
            "side": "buy",
            "type": "market",
            "quantity": "10",
        },
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Company not found"
