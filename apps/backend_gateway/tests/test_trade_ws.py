import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, NoReturn, cast

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from realtime.connection_manager import ConnectionManager
from realtime.trade_ws import TradeNotifier, create_trade_endpoint
from starlette import status as http_status
from starlette.exceptions import WebSocketException
from starlette.websockets import WebSocketDisconnect
from ws_fakes import FakeCache, FakeManager, FakePipeline


class FakeUser:
    def __init__(self, user_id: int = 42) -> None:
        self.id = user_id


async def deny_auth(websocket: WebSocket) -> NoReturn:
    raise WebSocketException(
        code=http_status.WS_1008_POLICY_VIOLATION, reason="Denied in test"
    )


async def allow_auth(websocket: WebSocket) -> Any:
    return FakeUser()


def tx_row(user_id: int = 42, symbol: str | None = None) -> dict[str, Any]:
    return {
        "transaction_id": str(uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "user_id": str(user_id),
        "company_id": str(uuid.uuid4()),
        "side": "buy",
        "quantity": 10,
        "price": 50.0,
        "simulated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "symbol": symbol,
        "company_name": symbol,
    }


@pytest.mark.asyncio
async def test_notify_transactions_pushes_enriched_fill() -> None:
    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    row = tx_row(symbol="ACB")

    sent = await notifier.notify_transactions([row])

    assert sent == 1
    messages = manager.user_messages["42"]
    assert len(messages) == 1
    fill = messages[0]
    assert fill["type"] == "trade_fill"
    data = fill["data"]
    assert data["symbol"] == "ACB"
    assert data["user_id"] == "42"
    assert data["total"] == 500.0


@pytest.mark.asyncio
async def test_enrich_resolves_symbol_via_resolver() -> None:
    manager = FakeManager()
    calls: list[object] = []

    async def resolver(company_id: Any) -> dict[str, str] | None:
        calls.append(company_id)
        return {"symbol": "VCB", "name": "Vietcombank"}

    notifier = TradeNotifier(manager, symbol_resolver=resolver, poll_interval=60.0)
    row = tx_row(symbol=None)

    sent = await notifier.notify_transactions([row])
    assert sent == 1
    assert len(calls) == 1
    data = manager.user_messages["42"][0]["data"]
    assert data["symbol"] == "VCB"
    assert data["company_name"] == "Vietcombank"


@pytest.mark.asyncio
async def test_enrich_skips_when_symbol_unresolvable() -> None:
    manager = FakeManager()

    async def resolver(company_id: Any) -> Any:
        return None

    notifier = TradeNotifier(manager, symbol_resolver=resolver, poll_interval=60.0)
    sent = await notifier.notify_transactions([tx_row(symbol=None)])
    assert sent == 0
    assert "42" not in manager.user_messages


@pytest.mark.asyncio
async def test_push_batch_resolves_missing_symbols_in_single_call() -> None:
    """N giao dịch thiếu symbol → batch resolver được gọi ĐÚNG 1 lần với N id.

    Trước đây ``_enrich`` chạy N lần ``session.get`` (N+1) cho từng giao dịch
    thiếu symbol khi match_orders tạo nhiều khớp cùng lúc.
    """
    manager = FakeManager()
    batch_calls: list[list[object]] = []
    per_item_calls: list[object] = []

    async def batch_resolver(company_ids: list[Any]) -> dict[str, dict[str, str]]:
        batch_calls.append(company_ids)
        return {
            str(cid): {"symbol": f"SYM{cid}", "name": f"Company{cid}"}
            for cid in company_ids
        }

    async def per_item_resolver(company_id: Any) -> Any:
        per_item_calls.append(company_id)
        return None

    notifier = TradeNotifier(
        manager,
        symbol_resolver=per_item_resolver,
        batch_symbol_resolver=cast(Any, batch_resolver),
        poll_interval=60.0,
    )
    rows = [tx_row(symbol=None, user_id=i) for i in (1, 2, 3)]

    sent = await notifier.notify_transactions(rows)

    assert sent == 3
    assert len(batch_calls) == 1
    assert len(batch_calls[0]) == 3
    assert per_item_calls == []
    for i in (1, 2, 3):
        data = manager.user_messages[str(i)][0]["data"]
        assert data["symbol"].startswith("SYM")
        assert data["company_name"].startswith("Company")


@pytest.mark.asyncio
async def test_push_falls_back_to_single_resolver_when_batch_fails() -> None:
    """Batch resolver lỗi (DB down) → fallback per-item resolver, không mất tin."""
    manager = FakeManager()
    per_item_calls: list[object] = []

    async def failing_batch(company_ids: list[Any]) -> NoReturn:
        raise ConnectionError("database unavailable")

    async def per_item_resolver(company_id: Any) -> dict[str, str] | None:
        per_item_calls.append(company_id)
        return {"symbol": "VCB", "name": "Vietcombank"}

    notifier = TradeNotifier(
        manager,
        symbol_resolver=per_item_resolver,
        batch_symbol_resolver=failing_batch,
        poll_interval=60.0,
    )

    sent = await notifier.notify_transactions([tx_row(symbol=None)])

    assert sent == 1
    assert len(per_item_calls) == 1
    data = manager.user_messages["42"][0]["data"]
    assert data["symbol"] == "VCB"


@pytest.mark.asyncio
async def test_default_batch_symbol_resolver_builds_single_in_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Batch resolver mặc định gom toàn bộ id vào MỘT query ``IN`` (chống N+1)."""
    import realtime.trade_ws as trade_ws_module

    class EmptyRows:
        def all(self) -> list[Any]:
            return []

    class CapturingSession:
        def __init__(self) -> None:
            self.executed: Any = None

        async def execute(self, stmt: Any) -> EmptyRows:
            self.executed = stmt
            return EmptyRows()

        async def __aenter__(self) -> "CapturingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    session = CapturingSession()
    monkeypatch.setattr(trade_ws_module, "async_session_factory", lambda: session)

    notifier = TradeNotifier(FakeManager(), poll_interval=60.0)
    result = await notifier._default_batch_symbol_resolver(
        [uuid.uuid4() for _ in range(3)]
    )

    assert result == {}
    assert "IN" in str(session.executed)


@pytest.mark.asyncio
async def test_poll_once_delivers_and_dedupes() -> None:
    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    first = tx_row(symbol="ACB")
    second = tx_row(symbol="VCB", user_id=7)

    rows = [first]
    await notifier._poll_once()
    assert manager.user_messages["42"]

    rows = [first, second]
    await notifier._poll_once()
    assert "7" in manager.user_messages
    assert len(manager.user_messages["42"]) == 1

    assert notifier._watermark is not None


@pytest.mark.asyncio
async def test_poll_once_composite_watermark_handles_same_timestamp() -> None:
    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        if watermark is None:
            return list(rows)
        wm_ts, wm_id = watermark
        return [
            r
            for r in rows
            if r["created_at"] > wm_ts
            or (r["created_at"] == wm_ts and str(r["transaction_id"]) > wm_id)
        ]

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    same_ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    first = tx_row(symbol="ACB", user_id=1)
    second = tx_row(symbol="VCB", user_id=2)
    first["created_at"] = same_ts
    second["created_at"] = same_ts
    first["transaction_id"] = "00000000-0000-0000-0000-000000000001"
    second["transaction_id"] = "00000000-0000-0000-0000-000000000002"

    rows = [first, second]
    await notifier._poll_once()
    await notifier._poll_once()

    assert "1" in manager.user_messages
    assert "2" in manager.user_messages


@pytest.mark.asyncio
async def test_notify_then_poll_does_not_double_deliver() -> None:
    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    row = tx_row(symbol="ACB")
    rows = [row]

    sent = await notifier.notify_transactions([row])
    assert sent == 1
    await notifier._poll_once()

    assert len(manager.user_messages["42"]) == 1


@pytest.mark.asyncio
async def test_watermark_persists_and_loads_on_leader_takeover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leader mới kế thừa watermark từ Redis — không quét lại bảng từ đầu."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    row = tx_row(symbol="ACB")
    rows = [row]
    await notifier._poll_once()
    assert notifier._watermark is not None
    assert cache.data.get("finsim:ws:trade:watermark")

    # Mô phỏng leader mới: watermark trong RAM bị reset → load lại từ Redis.
    notifier._watermark = None
    await notifier._load_watermark()
    assert notifier._watermark is not None
    assert notifier._watermark[1] == row["transaction_id"]


@pytest.mark.asyncio
async def test_leader_takeover_with_watermark_does_not_rescan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll sau khi load watermark chỉ lấy giao dịch mới hơn watermark."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    old = tx_row(symbol="ACB")
    new = tx_row(symbol="VCB", user_id=7)
    old["created_at"] = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    new["created_at"] = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)

    rows = [old]
    await notifier._poll_once()
    await notifier._persist_watermark()

    # Leader mới kế thừa watermark rồi poll: poll_source nhận watermark của leader cũ.
    notifier._watermark = None
    await notifier._load_watermark()
    captured: list[object] = []

    async def tracking_poll_source(watermark: Any) -> list[dict[str, Any]]:
        captured.append(watermark)
        return []

    notifier._poll_source = tracking_poll_source
    await notifier._poll_once()
    assert captured and captured[0] is not None


@pytest.mark.asyncio
async def test_pipeline_batches_mark_delivered_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    """50 giao dịch → 2 Redis Pipeline (1 SETNX claim + 1 INCR seq) thay vì 100 lệnh."""
    import realtime.trade_ws as trade_ws_module

    class CountingCache(FakeCache):
        def __init__(self) -> None:
            super().__init__()
            self.pipeline_executions = 0

        def pipeline(self) -> FakePipeline:
            self.pipeline_executions += 1
            return super().pipeline()

    cache = CountingCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    rows = [tx_row(symbol="ACB") for _ in range(50)]

    await notifier._push_transactions(rows)

    assert len(manager.user_messages["42"]) == 50
    # claim (SETNX) + assign seq (INCR), mỗi cái 1 pipeline cho cả batch.
    assert cache.pipeline_executions == 2
    assert cache.data  # dedupe SETNX + watermark ghi qua pipeline


@pytest.mark.asyncio
async def test_poll_dedupe_check_uses_single_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import realtime.trade_ws as trade_ws_module

    class CountingCache(FakeCache):
        def __init__(self) -> None:
            super().__init__()
            self.pipeline_executions = 0

        def pipeline(self) -> FakePipeline:
            self.pipeline_executions += 1
            return super().pipeline()

    cache = CountingCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    rows = [tx_row(symbol="ACB") for _ in range(20)]

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    before = cache.pipeline_executions
    await notifier._poll_once()

    assert len(manager.user_messages["42"]) == 20
    # 1 pipeline cho dedupe-check (exists) + 1 cho mark-delivered (setnx) + 1 cho seq.
    assert cache.pipeline_executions - before == 3


@pytest.mark.asyncio
async def test_push_claims_before_broadcast_closes_poll_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claim-first: vệt delivered (SETNX) phải tồn tại TRƯỚC khi tin rời server.

    Đóng cửa sổ race giữa event-push và poll catch-up (leader): poll SELECT DB
    đúng lúc giữa broadcast cũ và mark-delivered sẽ đẩy trùng trade_fill.
    """
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    class ClaimOrderManager(FakeManager):
        def __init__(self) -> None:
            super().__init__()
            self.all_claimed_at_broadcast = True

        async def broadcast_to_user(
            self, user_id: str | uuid.UUID, message: dict[str, Any] | str
        ) -> int:
            tx_id = cast(dict[str, Any], message)["data"]["transaction_id"]
            if f"{trade_ws_module.DEDUP_PREFIX}{tx_id}" not in cache.data:
                self.all_claimed_at_broadcast = False
            return await super().broadcast_to_user(user_id, message)

    manager = ClaimOrderManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    rows = [tx_row(symbol="ACB") for _ in range(5)]

    await notifier._push_transactions(rows)

    assert len(manager.user_messages["42"]) == 5
    assert manager.all_claimed_at_broadcast is True


@pytest.mark.asyncio
async def test_push_skips_already_delivered_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tin đã delivered (poll của worker khác đã phát) → event-push bỏ qua,
    không đẩy trùng trade_fill."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    row = tx_row(symbol="ACB")
    # Vệt delivered đã tồn tại (poll catch-up của leader worker khác đã phát tin).
    cache.data[f"{trade_ws_module.DEDUP_PREFIX}{row['transaction_id']}"] = "1"

    sent = await notifier.notify_transactions([row])

    assert sent == 0
    assert "42" not in manager.user_messages


@pytest.mark.asyncio
async def test_poll_advances_watermark_over_already_delivered_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll không dừng watermark ở tin delivered cuối bảng (tránh lặp lại vĩnh viễn)."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    notifier = TradeNotifier(manager, poll_source=poll_source, poll_interval=60.0)
    old = tx_row(symbol="ACB")
    new = tx_row(symbol="VCB", user_id=7)
    old["created_at"] = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    new["created_at"] = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
    cache.data[f"{trade_ws_module.DEDUP_PREFIX}{old['transaction_id']}"] = "1"

    rows = [old, new]
    await notifier._poll_once()

    # old đã delivered → không phát lại; new được phát; watermark vượt qua cả hai.
    assert "42" not in manager.user_messages
    assert "7" in manager.user_messages
    assert notifier._watermark == (new["created_at"], new["transaction_id"])


@pytest.mark.asyncio
async def test_notify_order_update() -> None:
    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    sent = await notifier.notify_order_update(
        {
            "user_id": 42,
            "order_id": str(uuid.uuid4()),
            "company_id": str(uuid.uuid4()),
            "symbol": "ACB",
            "status": "filled",
            "side": "buy",
            "quantity": 10,
            "filled_quantity": 10,
            "simulated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
    )
    assert sent == 1
    update = manager.user_messages["42"][0]
    assert update["type"] == "order_update"
    assert update["data"]["status"] == "filled"


@pytest.mark.asyncio
async def test_push_attaches_increasing_seq_per_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mỗi tin trade_fill gắn seq tăng dần theo kênh user — client dò gap để resync."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    rows = [tx_row(symbol="ACB"), tx_row(symbol="VCB")]

    await notifier._push_transactions(rows)

    fills = manager.user_messages["42"]
    assert [m["seq"] for m in fills] == [1, 2]
    assert cache.data["finsim:ws:seq:user:42"] == 2


@pytest.mark.asyncio
async def test_order_update_continues_channel_seq(monkeypatch: pytest.MonkeyPatch) -> None:
    """order_update dùng chung chuỗi seq với trade_fill trên cùng kênh user."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    manager = FakeManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    await notifier._push_transactions([tx_row(symbol="ACB")])

    sent = await notifier.notify_order_update(
        {
            "user_id": 42,
            "order_id": str(uuid.uuid4()),
            "symbol": "ACB",
            "status": "cancelled",
            "quantity": 1,
        }
    )

    assert sent == 1
    assert manager.user_messages["42"][-1]["seq"] == 2


@pytest.mark.asyncio
async def test_dedup_setnx_uses_ttl_and_namespaced_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SETNX dedup gắn ex=TTL và prefix rõ ràng `dedup:trade:{id}` (tránh rò RAM)."""
    import realtime.trade_ws as trade_ws_module

    cache = FakeCache()
    monkeypatch.setattr(trade_ws_module, "get_cache", lambda: cache)

    notifier = TradeNotifier(FakeManager(), poll_interval=60.0, dedup_ttl=300)
    row = tx_row(symbol="ACB")

    await notifier._push_transactions([row])

    assert cache.pipeline_sets
    key, kwargs = cache.pipeline_sets[0]
    assert key == f"finsim:ws:dedup:trade:{row['transaction_id']}"
    assert kwargs["nx"] is True
    assert kwargs["ex"] == 300


@pytest.mark.asyncio
async def test_default_poll_source_uses_lookback_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Poll không bỏ sót giao dịch "commit lệch thời gian" (Postgres now() = start tx).

    Watermark tiến lên mà một transaction bắt đầu TRƯỚC watermark nhưng commit SAU
    poll sẽ có created_at < watermark → bị bỏ sót vĩnh viễn nếu chỉ đọc
    ``created_at > watermark``. Lookback window đọc lại từ ``watermark - 5s``.
    """
    import realtime.trade_ws as trade_ws_module
    from sqlalchemy.dialects import postgresql

    class EmptyRows:
        def all(self) -> list[Any]:
            return []

    class CapturingSession:
        def __init__(self) -> None:
            self.executed: Any = None

        async def execute(self, stmt: Any) -> EmptyRows:
            self.executed = stmt
            return EmptyRows()

        async def __aenter__(self) -> "CapturingSession":
            return self

        async def __aexit__(self, *exc: Any) -> bool:
            return False

    session = CapturingSession()
    monkeypatch.setattr(trade_ws_module, "async_session_factory", lambda: session)

    notifier = TradeNotifier(FakeManager(), poll_interval=60.0)
    wm_ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    await notifier._default_poll_source((wm_ts, "id-1"))
    sql = str(
        session.executed.compile(
            dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "created_at >= " in sql
    assert "2026-01-02 03:04:00" in sql  # watermark − lookback 5s
    assert "ORDER BY" in sql


def test_trade_ws_endpoint_streams_fills() -> None:
    manager = ConnectionManager()
    rows: list[dict[str, Any]] = []

    async def poll_source(watermark: Any) -> list[dict[str, Any]]:
        return list(rows)

    async def no_resolver(company_id: Any) -> Any:
        return None

    notifier = TradeNotifier(
        manager, poll_source=poll_source, symbol_resolver=no_resolver, poll_interval=0.05
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await notifier.start()
        yield
        await notifier.stop()

    app = FastAPI(lifespan=lifespan)
    app.add_websocket_route("/ws/trades", create_trade_endpoint(manager, notifier, allow_auth))

    with TestClient(app) as client:
        with client.websocket_connect("/ws/trades") as ws:
            ready = _receive_until(ws, lambda m: m["type"] == "welcome")
            assert ready["data"]["user_id"] == "42"
            assert ready["data"]["channel"] == "user:42"

            ws.send_json({"action": "subscribe"})
            subscribed = _receive_until(ws, lambda m: m["type"] == "subscribed")
            assert subscribed["data"]["channel"] == "user:42"

            rows.append(tx_row(symbol="ACB"))
            fill = _receive_until(ws, lambda m: m["type"] == "trade_fill")
            assert fill["data"]["symbol"] == "ACB"
            assert fill["data"]["user_id"] == "42"

            ws.send_json({"action": "bogus"})
            error = _receive_until(ws, lambda m: m["type"] == "error")
            assert error["data"]["code"] == "unknown_action"


def test_trade_ws_endpoint_rejects_unauthenticated() -> None:
    manager = ConnectionManager()
    notifier = TradeNotifier(manager, poll_interval=60.0)
    app = FastAPI()
    app.add_websocket_route("/ws/trades", create_trade_endpoint(manager, notifier, deny_auth))

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/trades"):
            pass
    assert exc_info.value.code == 1008


def _receive_until(
    ws: Any, predicate: Callable[[dict[str, Any]], bool], limit: int = 300
) -> dict[str, Any]:
    for _ in range(limit):
        message = ws.receive_json()
        if predicate(message):
            return cast(dict[str, Any], message)
    raise AssertionError("Không nhận được tin mong đợi trong giới hạn")
