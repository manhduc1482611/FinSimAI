"""Tests cho P0.3 — cơ chế "tin tức → giá" (market_service).

Tin tức gần đây bẻ drift GBM (``mu``) theo hướng ``sentiment × impact``, phân rã
theo độ tuổi, rồi qua ``tanh`` chặn mềm. Không tin → momentum 0 → ``mu = 0``
(hành vi GBM trần giữ nguyên).
"""

import math
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from realtime.simtime import sim_now


def test_sentiment_sign() -> None:
    from services import market_service

    assert market_service._sentiment_sign("positive") == 1
    assert market_service._sentiment_sign("negative") == -1
    assert market_service._sentiment_sign("neutral") == 0
    assert market_service._sentiment_sign("POSITIVE") == 1
    assert market_service._sentiment_sign("") == 0
    assert market_service._sentiment_sign(None) == 0


def test_aggregate_news_momentum_empty_is_zero() -> None:
    from services import market_service

    assert market_service._aggregate_news_momentum([]) == 0.0


def test_aggregate_news_momentum_positive_drives_up() -> None:
    from services import market_service

    # positive impact 8, tuổi 0 (mới đăng) → tanh(0.8) > 0.
    momentum = market_service._aggregate_news_momentum([("positive", 8.0, 0.0)])
    assert momentum == pytest.approx(math.tanh(0.8))


def test_aggregate_news_momentum_negative_drives_down() -> None:
    from services import market_service

    momentum = market_service._aggregate_news_momentum([("negative", 6.0, 0.0)])
    assert momentum == pytest.approx(math.tanh(-0.6))


def test_aggregate_news_momentum_neutral_is_zero() -> None:
    from services import market_service

    # impact mạnh nhưng sentiment neutral → không bẻ giá.
    assert market_service._aggregate_news_momentum([("neutral", 10.0, 0.0)]) == 0.0


def test_aggregate_news_momentum_decays_with_age() -> None:
    from services import market_service

    fresh = market_service._aggregate_news_momentum([("positive", 10.0, 0.0)])
    # 300 giây thực = 5 ngày mô phỏng (~1.7 half-life) → trọng số tàn phai.
    old = market_service._aggregate_news_momentum([("positive", 10.0, 300.0)])
    assert 0.0 < old < fresh


def test_aggregate_news_momentum_saturates_with_many_news() -> None:
    from services import market_service

    entries = [("positive", 10.0, 0.0)] * 5
    momentum = market_service._aggregate_news_momentum(entries)
    # tanh chặn mềm: nhiều tin cùng hướng tiến tới 1, không vượt [-1, 1].
    assert momentum < 1.0
    assert momentum > 0.9


class _FakeNewsDB:
    """Fake AsyncSession chỉ phục vụ ``_fetch_news_momentum_map`` (execute → rows)."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> Any:
        return SimpleNamespace(all=lambda: self._rows)


@pytest.mark.asyncio
async def test_fetch_news_momentum_map_company_plus_macro() -> None:
    from services import market_service

    cid_a = uuid.uuid4()
    cid_b = uuid.uuid4()
    now = sim_now()
    rows = [
        (cid_a, "positive", 8.0, now),   # +0.8 cho A
        (cid_b, "negative", 6.0, now),   # -0.6 cho B
        (None, "negative", 5.0, now),    # macro -0.5 cho cả hai
    ]
    momentum = await market_service._fetch_news_momentum_map(
        _FakeNewsDB(rows), [cid_a, cid_b], None
    )

    # simulated_at lệch vài micro-giây so với mốc nội bộ → weight ≈ impact/10,
    # dùng abs tolerance thay vì so khớp chặt.
    assert momentum[cid_a] == pytest.approx(math.tanh(0.8 - 0.5), abs=1e-5)
    assert momentum[cid_b] == pytest.approx(math.tanh(-0.6 - 0.5), abs=1e-5)


@pytest.mark.asyncio
async def test_fetch_news_momentum_map_ignores_unknown_company() -> None:
    from services import market_service

    cid_known = uuid.uuid4()
    cid_unknown = uuid.uuid4()
    now = sim_now()
    rows = [
        (cid_known, "positive", 8.0, now),
        (cid_unknown, "positive", 9.0, now),  # không nằm trong set → bỏ qua
    ]
    momentum = await market_service._fetch_news_momentum_map(
        _FakeNewsDB(rows), [cid_known], None
    )

    assert cid_known in momentum
    assert momentum[cid_known] == pytest.approx(math.tanh(0.8), abs=1e-5)
    assert cid_unknown not in momentum


@pytest.mark.asyncio
async def test_fetch_news_momentum_map_no_news_returns_empty() -> None:
    from services import market_service

    momentum = await market_service._fetch_news_momentum_map(
        _FakeNewsDB([]), [uuid.uuid4()], None
    )
    assert momentum == {}


@pytest.mark.asyncio
async def test_fetch_price_values_forwards_mu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import market_service

    captured: dict[str, object] = {}

    class FakeClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"prices": [kwargs["current_price"], 42.00], "success": True}

    monkeypatch.setattr(market_service, "math_client", FakeClient())

    await market_service._fetch_price_values(
        42.10, 0.019, 1.0 / 252, 7, reference_price=40.0, mu=0.75
    )

    assert captured["mu"] == 0.75
    assert captured["reference_price"] == 40.0


@pytest.mark.asyncio
async def test_fallback_uses_mu(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import market_service

    captured: dict[str, object] = {}

    class BrokenClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            return {"success": False, "prices": []}

    def fake_fallback(
        current_price: float, sigma: float, dt_years: float, seed: int | None, mu: float = 0.0
    ) -> float:
        captured["mu"] = mu
        return 42.5

    monkeypatch.setattr(market_service, "math_client", BrokenClient())
    monkeypatch.setattr(market_service, "_fallback_price", fake_fallback)

    price = await market_service._fetch_price_values(
        42.10, 0.019, 1.0 / 252, 7, mu=0.9
    )

    assert price == Decimal("42.5")
    assert captured["mu"] == 0.9


@pytest.mark.asyncio
async def test_fetch_price_forwards_mu(monkeypatch: pytest.MonkeyPatch) -> None:
    from services import market_service

    captured: dict[str, object] = {}

    class FakeClient:
        async def generate_next_prices(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"prices": [kwargs["current_price"], 42.36], "success": True}

    monkeypatch.setattr(market_service, "math_client", FakeClient())
    market_service._DAY_REFERENCE.clear()

    company = SimpleNamespace(
        id=uuid.uuid4(),
        current_price=Decimal("42.10"),
        volatility=Decimal("0.019"),
    )
    try:
        await market_service._fetch_price(company, 1.0 / 252, 7, mu=1.2)
    finally:
        market_service._DAY_REFERENCE.clear()

    assert captured["mu"] == 1.2
    assert captured["reference_price"] == pytest.approx(42.10)
