"""API test biên độ giá trần/sàn (P0 #5) + đóng băng lệnh market (P0 #4).

``POST /api/v1/trades/orders``:
- từ chối lệnh limit ngoài ±7% quanh giá tham chiếu (HTTP 422, mã
  ``price_out_of_band``); lệnh trong biên độ đi tiếp qua cổng giá;
- lệnh market buy đóng băng thêm buffer trượt giá (`max_slippage_impact`).
Service penalty bị monkeypatch — không cần DB thật.
"""

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from api.v1 import trades as trades_api
from core.config import settings
from core.dependencies import get_current_user, get_db
from fastapi import FastAPI
from services import penalty_service, task_service


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one(self) -> Any:
        return self._value

    def scalar_one_or_none(self) -> Any:
        return self._value


class FakeDb:
    """Trả về 1 công ty + 1 user với số dư cấu hình; đủ cho luồng create_order."""

    def __init__(self, *, current_price: str = "100.00", cash: str = "0.00") -> None:
        self.company = SimpleNamespace(
            id=uuid.uuid4(),
            current_price=Decimal(current_price),
            is_active=True,
            updated_at=datetime.now(timezone.utc),
        )
        self.user = SimpleNamespace(
            id=uuid.uuid4(),
            cash_balance=Decimal(cash),
            frozen_cash=Decimal("0.00"),
        )
        self.added: list[Any] = []

    async def get(self, model: Any, pk: Any) -> Any:
        return self.company

    async def execute(self, stmt: Any) -> _ScalarResult:
        return _ScalarResult(self.user)

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def refresh(self, obj: Any) -> None:
        # server_default (id/created_at) + default cột chỉ có sau flush/commit.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(timezone.utc)
        if getattr(obj, "status", None) is None:
            obj.status = "pending"
        if getattr(obj, "filled_quantity", None) is None:
            obj.filled_quantity = Decimal("0")


def _build_app(db: FakeDb) -> FastAPI:
    app = FastAPI()
    app.include_router(trades_api.router, prefix="/api/v1")
    fake_user = SimpleNamespace(id=uuid.uuid4(), risk_score=50, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = lambda: db
    return app


@pytest.fixture
def app() -> Iterator[FastAPI]:
    app = _build_app(FakeDb())
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _unlock_trading(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_enforce(user_id: Any, db: Any) -> None:
        return None

    monkeypatch.setattr(penalty_service, "enforce_cooldown", fake_enforce)


def _order_json(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "company_id": str(uuid.uuid4()),
        "side": "buy",
        "type": "limit",
        "price": "100.00",
        "quantity": "10",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_limit_price_above_band_rejected_422(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/trades/orders", json=_order_json(price="107.01")
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["code"] == "price_out_of_band"
    assert detail["reference_price"] == "100.00"
    assert detail["lower"] == "93.00"
    assert detail["upper"] == "107.00"


@pytest.mark.asyncio
async def test_limit_price_below_band_rejected_422(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/trades/orders", json=_order_json(price="92.99")
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "price_out_of_band"


@pytest.mark.asyncio
async def test_limit_price_at_band_edge_passes_gate(client: httpx.AsyncClient) -> None:
    # Trong biên độ → qua cổng giá, tới kiểm tra vốn (cash = 0) → 400.
    resp = await client.post(
        "/api/v1/trades/orders", json=_order_json(price="107.00")
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Insufficient available cash"


@pytest.mark.asyncio
async def test_market_order_ignores_band(client: httpx.AsyncClient) -> None:
    # Market không có giá → không qua kiểm tra biên độ, tới kiểm tra vốn → 400.
    resp = await client.post(
        "/api/v1/trades/orders", json=_order_json(type="market", price=None)
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Insufficient available cash"


@pytest.mark.asyncio
async def test_market_buy_freezes_with_slippage_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lệnh market buy đóng băng giá hiện tại × (1+max_slippage_impact) × (1+fee)."""

    async def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(task_service, "record_event", _noop)

    db = FakeDb(current_price="100.00", cash="1000000.00")
    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/v1/trades/orders",
            json=_order_json(type="market", price=None, quantity="100"),
        )

    assert resp.status_code == 201
    assert len(db.added) == 1
    order = db.added[0]

    slip = Decimal(str(settings.max_slippage_impact))
    fee = Decimal(str(settings.trading_fee_rate))
    expected = Decimal("100") * Decimal("100") * (Decimal("1") + slip) * (Decimal("1") + fee)
    assert order.frozen_cash == expected
