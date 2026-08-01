import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
import realtime.price_ws as price_ws_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from realtime.connection_manager import ConnectionManager
from realtime.price_ws import ALL_SYMBOLS_ROOM, PRICE_ROOM_PREFIX, PriceBroadcaster
from ws_fakes import FakeCache, FakeManager

ANCHOR = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakePriceSource:
    def __init__(self, prices: dict[str, float]) -> None:
        self.ids = {symbol: uuid.uuid4() for symbol in prices}
        self.prices = dict(prices)
        self.calls = 0

    async def __call__(self) -> list[dict]:
        self.calls += 1
        return [
            {
                "company_id": self.ids[symbol],
                "symbol": symbol,
                "name": symbol,
                "sector": "TEST",
                "price": price,
                "market_cap": price * 1000.0,
                "updated_at": datetime.now(timezone.utc),
            }
            for symbol, price in self.prices.items()
        ]


class FakeClock:
    now_value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz: object = None) -> datetime:
        if tz is not None:
            return cls.now_value.astimezone(tz)
        return cls.now_value


def make_broadcaster(manager=None, source=None, **kwargs):
    return PriceBroadcaster(
        manager or FakeManager(),
        source or FakePriceSource({"ACB": 100.0}),
        sim_anchor=ANCHOR,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_process_snapshots_publishes_first_ticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(price_ws_module, "datetime", FakeClock)
    FakeClock.now_value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    manager = FakeManager()
    broadcaster = make_broadcaster(manager=manager)
    ticks = await broadcaster.process_snapshots(await broadcaster.price_source())

    assert {t["symbol"] for t in ticks} == {"ACB"}
    tick = ticks[0]
    assert tick["price"] == 100.0
    assert tick["change"] == 0.0
    assert tick["change_pct"] == 0.0
    assert tick["prev_close"] == 100.0
    assert tick["sim_day"] == 720
    assert "(Sim Day 720)" in tick["simulated_at"]

    assert len(manager.room_messages[f"{PRICE_ROOM_PREFIX}ACB"]) == 1
    assert len(manager.room_messages[ALL_SYMBOLS_ROOM]) == 1

    no_change = await broadcaster.process_snapshots(await broadcaster.price_source())
    assert no_change == []


@pytest.mark.asyncio
async def test_price_change_computes_change_and_pct() -> None:
    manager = FakeManager()
    source = FakePriceSource({"ACB": 100.0})
    broadcaster = make_broadcaster(manager=manager, source=source)
    await broadcaster.process_snapshots(await source())

    source.prices["ACB"] = 102.0
    ticks = await broadcaster.process_snapshots(await source())
    assert len(ticks) == 1
    assert ticks[0]["change"] == 2.0
    assert ticks[0]["change_pct"] == 2.0


@pytest.mark.asyncio
async def test_session_high_low_track() -> None:
    source = FakePriceSource({"ACB": 100.0})
    broadcaster = make_broadcaster(source=source)
    await broadcaster.process_snapshots(await source())

    source.prices["ACB"] = 105.0
    await broadcaster.process_snapshots(await source())

    source.prices["ACB"] = 98.0
    ticks = await broadcaster.process_snapshots(await source())

    assert ticks[0]["open"] == 100.0
    assert ticks[0]["high"] == 105.0
    assert ticks[0]["low"] == 98.0


@pytest.mark.asyncio
async def test_sim_day_rollover_resets_session(monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakePriceSource({"ACB": 100.0})
    broadcaster = make_broadcaster(source=source)
    monkeypatch.setattr(price_ws_module, "datetime", FakeClock)

    FakeClock.now_value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    await broadcaster.process_snapshots(await source())

    source.prices["ACB"] = 110.0
    same_day = await broadcaster.process_snapshots(await source())
    assert same_day[0]["change"] == 10.0

    FakeClock.now_value = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    source.prices["ACB"] = 112.0
    next_day = await broadcaster.process_snapshots(await source())
    assert next_day[0]["sim_day"] == same_day[0]["sim_day"] + 1440
    assert next_day[0]["open"] == 112.0
    assert next_day[0]["prev_close"] == 110.0
    assert next_day[0]["change"] == 2.0


@pytest.mark.asyncio
async def test_sim_day_rollover_emits_tick_even_when_price_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = FakePriceSource({"ACB": 100.0})
    broadcaster = make_broadcaster(source=source)
    monkeypatch.setattr(price_ws_module, "datetime", FakeClock)

    FakeClock.now_value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    first = await broadcaster.process_snapshots(await source())
    assert len(first) == 1

    FakeClock.now_value = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    same_price = await broadcaster.process_snapshots(await source())
    assert len(same_price) == 1
    assert same_price[0]["sim_day"] == first[0]["sim_day"] + 1440
    assert same_price[0]["open"] == 100.0
    assert same_price[0]["prev_close"] == 100.0


@pytest.mark.asyncio
async def test_leader_takeover_rebuilds_session_state_from_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leader mới kế thừa O/H/L/prev_close từ snapshot cache khi failover."""
    cache = FakeCache()
    monkeypatch.setattr(price_ws_module, "get_cache", lambda: cache)

    broadcaster = make_broadcaster()
    source = FakePriceSource({"ACB": 100.0})
    await broadcaster.process_snapshots(await source())
    await broadcaster._persist_snapshots()
    assert cache.hashes["finsim:ws:prices:snapshot"]

    # Mô phỏng leader mới: state trong RAM bị reset → load lại từ Redis cache.
    broadcaster._session.clear()
    broadcaster._last_price.clear()
    broadcaster._current.clear()
    await broadcaster._load_state_from_cache()

    assert broadcaster._last_price["ACB"] == 100.0
    session = broadcaster._session["ACB"]
    assert session["open"] == 100.0
    assert session["high"] == 100.0
    assert session["low"] == 100.0
    assert session["prev_close"] == 100.0
    assert broadcaster._current["ACB"]["price"] == 100.0


@pytest.mark.asyncio
async def test_secondary_worker_caches_snapshot_locally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker phụ: 2 client xin snapshot liên tiếp → 1 lệnh HGETALL (TTL cache 1s)."""
    import json as jsonlib

    class CountingCache(FakeCache):
        def __init__(self) -> None:
            super().__init__()
            self.hgetall_calls = 0

        async def hgetall(self, key: str) -> dict[str, str]:
            self.hgetall_calls += 1
            return await super().hgetall(key)

    cache = CountingCache()
    monkeypatch.setattr(price_ws_module, "get_cache", lambda: cache)

    broadcaster = make_broadcaster()
    tick = {
        "symbol": "ACB",
        "price": 100.0,
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "prev_close": 100.0,
        "sim_day": 720,
    }
    await cache.hset(broadcaster._snapshot_key, {"ACB": jsonlib.dumps(tick)})

    first = await broadcaster.snapshots_for_delivery()
    assert first["ACB"]["price"] == 100.0
    second = await broadcaster.snapshots_for_delivery()
    assert second["ACB"]["price"] == 100.0
    # Lần 2 được phục vụ từ RAM local — KHÔNG gọi HGETALL lần nữa.
    assert cache.hgetall_calls == 1


class LostLeadership:
    """is_leader đúng 1 lần (lần kiểm tra đầu), rồi mất lock vĩnh viễn."""

    def __init__(self) -> None:
        self._leader = True

    @property
    def is_leader(self) -> bool:
        value = self._leader
        self._leader = False
        return value

    async def acquire(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_leader_lost_during_db_read_skips_broadcast() -> None:
    """Lock hết hạn trong lúc đọc DB (leader khác đã thay thế) → KHÔNG phát tick trùng.

    Vòng lặp không tin trạng thái leader trong RAM giữa hai nhịp acquire: sau khi
    `price_source()` trả về, re-check `is_leader()` ngay trước broadcast. Nếu bỏ qua
    bước này, 2 worker cùng đẩy 1 tick xuống client (split-brain ngắn).
    """
    import asyncio

    manager = FakeManager()
    source = FakePriceSource({"ACB": 100.0})
    broadcaster = make_broadcaster(manager=manager, source=source)
    broadcaster._election = LostLeadership()

    task = asyncio.create_task(broadcaster._run_loop())
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert f"{PRICE_ROOM_PREFIX}ACB" not in manager.room_messages
    assert ALL_SYMBOLS_ROOM not in manager.room_messages


def _receive_until(ws, predicate, limit: int = 300):
    for _ in range(limit):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("Không nhận được tin mong đợi trong giới hạn")


def test_price_ws_endpoint_full_flow() -> None:
    manager = ConnectionManager()
    source = FakePriceSource({"ACB": 100.0, "VCB": 50.0})
    broadcaster = make_broadcaster(manager=manager, source=source, tick_seconds=0.05)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await broadcaster.start()
        yield
        await broadcaster.stop()

    from realtime.router import register_websocket_routes

    app = FastAPI(lifespan=lifespan)
    register_websocket_routes(app, manager=manager, price_broadcaster=broadcaster)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/prices") as ws:
            welcome = _receive_until(ws, lambda m: m["type"] == "welcome")
            assert welcome["data"]["connection_id"]

            ws.send_json({"action": "subscribe", "channels": ["prices:ACB"]})
            subscribed = _receive_until(ws, lambda m: m["type"] == "subscribed")
            assert "prices:ACB" in subscribed["data"]["active_rooms"]

            source.prices["ACB"] = 105.0
            tick = _receive_until(
                ws,
                lambda m: m["type"] == "price_tick" and m["data"]["symbol"] == "ACB",
            )
            assert tick["data"]["price"] == 105.0
            assert tick["data"]["change"] == 5.0

            ws.send_json({"action": "unsubscribe", "channels": ["prices:ACB"]})
            unsubscribed = _receive_until(ws, lambda m: m["type"] == "unsubscribed")
            assert "prices:ACB" not in unsubscribed["data"]["active_rooms"]

            source.prices["ACB"] = 108.0
            ws.send_json({"action": "ping"})
            pong = _receive_until(ws, lambda m: m["type"] == "pong")
            assert pong["type"] == "pong"

            ws.send_json({"action": "nope"})
            error = _receive_until(ws, lambda m: m["type"] == "error")
            assert error["data"]["code"] == "unknown_action"

            ws.send_json({"action": "subscribe", "channels": "not-a-list"})
            bad = _receive_until(
                ws, lambda m: m["type"] == "error" and m["data"]["code"] == "invalid_channels"
            )
            assert bad["data"]["code"] == "invalid_channels"
