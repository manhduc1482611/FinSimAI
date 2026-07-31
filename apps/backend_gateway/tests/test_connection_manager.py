import asyncio

import pytest
from websockets.connection_manager import (
    ClientConnection,
    ConnectionManager,
    build_message,
)
from ws_fakes import FakeWebSocket, SlowWebSocket


@pytest.mark.asyncio
async def test_build_message_shape() -> None:
    msg = build_message("price_tick", {"symbol": "ACB", "price": 42.0})
    assert msg["type"] == "price_tick"
    assert msg["data"] == {"symbol": "ACB", "price": 42.0}
    assert isinstance(msg["ts"], str)
    empty = build_message("pong")
    assert empty["data"] == {}


@pytest.mark.asyncio
async def test_connect_disconnect_cleanup() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    conn = await mgr.connect(ws)
    assert ws.accepted is True
    assert mgr.active_connections == 1
    await mgr.disconnect(conn)
    assert mgr.active_connections == 0
    assert conn.closed is True
    assert ws.closed is not None


@pytest.mark.asyncio
async def test_shutdown_connections_closes_with_1012() -> None:
    """Graceful shutdown đóng mọi kết nối bằng 1012 (Service Restart) để client
    reconnect có backoff — không Thundering Herd khi rolling deploy."""
    mgr = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await mgr.connect(ws1)
    await mgr.connect(ws2)

    closed = await mgr.shutdown_connections()

    assert closed == 2
    assert ws1.closed == (1012, "server restart — reconnect")
    assert ws2.closed == (1012, "server restart — reconnect")
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_join_leave_room_and_user_room() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    conn = await mgr.connect(ws)
    await mgr.join_room(conn, "prices:ACB")
    assert mgr.connection_count("prices:ACB") == 1
    assert "prices:ACB" in conn.rooms

    user_room = ConnectionManager.user_room(123)
    assert user_room == "user:123"
    await mgr.join_room(conn, user_room)
    assert mgr.connection_count(user_room) == 1

    await mgr.leave_room(conn, "prices:ACB")
    assert mgr.connection_count("prices:ACB") == 0
    assert "prices:ACB" not in conn.rooms
    assert mgr.connection_count(user_room) == 1

    await mgr.disconnect(conn)
    assert mgr.connection_count(user_room) == 0


@pytest.mark.asyncio
async def test_broadcast_to_room_delivers_and_counts() -> None:
    mgr = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    c1 = await mgr.connect(ws1)
    c2 = await mgr.connect(ws2)
    await mgr.join_room(c1, "prices:ACB")
    await mgr.join_room(c2, "prices:ACB")

    sent = await mgr.broadcast_to_room("prices:ACB", build_message("price_tick", {"n": 1}))
    assert sent == 2
    await asyncio.sleep(0.01)
    assert len(ws1.sent) == 1
    assert len(ws2.sent) == 1

    sent = await mgr.broadcast_to_user(123, build_message("trade_fill", {"n": 2}))
    assert sent == 0

    await mgr.disconnect(c1)
    await mgr.disconnect(c2)
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_handle_connection_keepalive_ping_on_silence_does_not_kick() -> None:
    mgr = ConnectionManager(max_queue_size=8)
    ws = FakeWebSocket()

    async def on_message(conn, payload: dict):
        await mgr.send(conn, build_message("echo", payload))

    task = asyncio.create_task(
        mgr.handle_connection(ws, on_message, heartbeat_seconds=0.05)
    )
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ws.accepted:
            break

    ws.send('{"hello": "world"}')
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "echo" for m in ws.sent_messages()):
            break
    echo = next(m for m in ws.sent_messages() if m["type"] == "echo")
    assert echo["data"]["hello"] == "world"

    ws.send("not-json")
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "error" for m in ws.sent_messages()):
            break
    errors = [m for m in ws.sent_messages() if m["type"] == "error"]
    assert errors and errors[-1]["data"]["code"] == "invalid_json"

    ws.send('{"action": "ping"}')
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "pong" for m in ws.sent_messages()):
            break
    assert any(m["type"] == "pong" for m in ws.sent_messages())

    # Im lặng hoàn toàn → server chỉ gửi keepalive, KHÔNG kick passive client.
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "ping" for m in ws.sent_messages()):
            break
    assert any(m["type"] == "ping" for m in ws.sent_messages())
    assert ws.closed is None

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_handle_connection_revalidates_periodically_and_closes() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    calls = 0

    async def on_validate(conn: ClientConnection) -> bool:
        nonlocal calls
        calls += 1
        return calls < 2  # lần 1 hợp lệ; lần 2 → token hết hạn / user bị khoá

    task = asyncio.create_task(
        mgr.handle_connection(ws, on_validate=on_validate, heartbeat_seconds=0.05)
    )
    await asyncio.wait_for(task, timeout=5)

    assert calls >= 2
    assert ws.closed is not None
    assert ws.closed[0] == 1008
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_handle_connection_validate_error_keeps_connection_alive() -> None:
    """on_validate ném lỗi DB (1-2s Postgres chập chờn) → KHÔNG sập vòng lặp,
    KHÔNG đóng socket: giữ kết nối và thử lại ở nhịp heartbeat sau."""
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    calls = 0

    async def on_validate(conn: ClientConnection) -> bool:
        nonlocal calls
        calls += 1
        raise RuntimeError("db blip")

    task = asyncio.create_task(
        mgr.handle_connection(ws, on_validate=on_validate, heartbeat_seconds=0.05)
    )
    for _ in range(200):
        await asyncio.sleep(0.01)
        if calls >= 2:
            break

    assert calls >= 2
    assert not task.done()  # vòng lặp vẫn chạy, không sập như lỗi cũ
    assert ws.closed is None  # socket không bị đóng đồng loạt

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_handle_connection_internal_error_reports_but_keeps_open() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()

    async def on_message(conn, payload: dict):
        raise RuntimeError("boom")

    task = asyncio.create_task(mgr.handle_connection(ws, on_message, heartbeat_seconds=5))
    for _ in range(100):
        await asyncio.sleep(0.01)
        if ws.accepted:
            break

    ws.send('{"action": "ask"}')
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "error" for m in ws.sent_messages()):
            break
    errors = [m for m in ws.sent_messages() if m["type"] == "error"]
    assert errors[-1]["data"]["code"] == "internal_error"

    ws.send('{"action": "ping"}')
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "pong" for m in ws.sent_messages()):
            break
    assert any(m["type"] == "pong" for m in ws.sent_messages())

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_on_connect_and_on_disconnect_hooks() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    events: list[str] = []

    async def on_connect(conn: ClientConnection) -> None:
        events.append("connect")
        await mgr.send(conn, build_message("greeting"))

    async def on_disconnect(conn: ClientConnection) -> None:
        events.append("disconnect")

    task = asyncio.create_task(
        mgr.handle_connection(
            ws,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            heartbeat_seconds=0.05,
        )
    )
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "greeting" for m in ws.sent_messages()):
            break
    assert any(m["type"] == "greeting" for m in ws.sent_messages())

    # Passive listener không bị kick; đóng bằng cách huỷ task → finally chạy on_disconnect.
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert events == ["connect", "disconnect"]
    assert ws.closed is not None


@pytest.mark.asyncio
async def test_drop_oldest_when_consumer_slow() -> None:
    mgr = ConnectionManager(max_queue_size=2)
    ws = SlowWebSocket()
    conn = await mgr.connect(ws)

    await mgr.send(conn, build_message("m", {"n": 1}))
    await asyncio.wait_for(ws.started.wait(), timeout=1)

    await mgr.send(conn, build_message("m", {"n": 2}))
    await mgr.send(conn, build_message("m", {"n": 3}))
    await mgr.send(conn, build_message("m", {"n": 4}))
    assert conn.dropped_messages == 1

    ws.release.set()
    for _ in range(100):
        await asyncio.sleep(0.01)
        if len(ws.sent) >= 3:
            break
    delivered = {json_of(s)["data"]["n"] for s in ws.sent}
    assert delivered == {1, 3, 4}
    assert 2 not in delivered

    await mgr.disconnect(conn)


@pytest.mark.asyncio
async def test_writer_send_timeout_closes_stalled_socket() -> None:
    """Slowloris / TCP zero-window: send_text treo → writer timeout → đóng kết nối."""

    class StalledSocket(FakeWebSocket):
        async def send_text(self, text: str) -> None:
            await asyncio.sleep(3600)

    mgr = ConnectionManager(write_timeout=0.05)
    ws = StalledSocket()
    conn = await mgr.connect(ws)
    await mgr.send(conn, build_message("m", {"n": 1}))

    for _ in range(200):
        await asyncio.sleep(0.01)
        if conn.closed:
            break

    assert conn.closed is True
    assert mgr.active_connections == 0
    assert conn.writer_task is not None
    assert conn.writer_task.done() is True


def json_of(raw: str) -> dict:
    import json

    return json.loads(raw)


@pytest.mark.asyncio
async def test_writer_failure_cleans_up_connection() -> None:
    class BrokenSocket(FakeWebSocket):
        async def send_text(self, text: str) -> None:
            raise ConnectionError("socket broken")

    mgr = ConnectionManager()
    ws = BrokenSocket()
    conn = await mgr.connect(ws)
    await mgr.send(conn, build_message("m", {"n": 1}))

    for _ in range(100):
        await asyncio.sleep(0.01)
        if conn.closed:
            break

    assert conn.closed is True
    assert mgr.active_connections == 0
    assert conn.writer_task is not None
    assert conn.writer_task.done() is True


@pytest.mark.asyncio
async def test_welcome_includes_realtime_status() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    task = asyncio.create_task(mgr.handle_connection(ws, heartbeat_seconds=5))
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any(m["type"] == "welcome" for m in ws.sent_messages()):
            break
    welcome = next(m for m in ws.sent_messages() if m["type"] == "welcome")
    assert welcome["data"]["realtime_status"] == "live"

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_reliable_message_prioritized_over_best_effort() -> None:
    """Khi cả 2 queue đều có tin, writer gửi reliable trước (trade fill ưu tiên)."""
    mgr = ConnectionManager()
    ws = SlowWebSocket()
    conn = await mgr.connect(ws)

    await mgr.send(conn, build_message("m", {"n": 1}))  # best-effort — writer đang ghi
    await asyncio.wait_for(ws.started.wait(), timeout=1)
    await mgr.send(conn, build_message("m", {"n": 3}))  # best-effort xếp hàng
    await mgr.send_reliable(conn, build_message("trade_fill", {"n": 2}))  # reliable

    ws.release.set()
    for _ in range(100):
        await asyncio.sleep(0.01)
        if len(ws.sent) >= 3:
            break
    delivered = [json_of(s)["data"]["n"] for s in ws.sent]
    assert delivered == [1, 2, 3]  # reliable (2) đi trước best-effort (3)

    await mgr.disconnect(conn)


@pytest.mark.asyncio
async def test_reliable_overflow_closes_connection_with_1011() -> None:
    """Reliable queue đầy → đóng kết nối (1011) để client reconnect + resync qua REST,
    KHÔNG drop tin giao dịch thầm lặng."""
    mgr = ConnectionManager(max_queue_size=8, reliable_max_queue_size=2)
    ws = SlowWebSocket()
    conn = await mgr.connect(ws)

    await mgr.send_reliable(conn, build_message("trade_fill", {"n": 1}))
    await asyncio.wait_for(ws.started.wait(), timeout=1)  # writer đang ghi n1
    await mgr.send_reliable(conn, build_message("trade_fill", {"n": 2}))
    await mgr.send_reliable(conn, build_message("trade_fill", {"n": 3}))
    await mgr.send_reliable(conn, build_message("trade_fill", {"n": 4}))  # tràn

    for _ in range(100):
        await asyncio.sleep(0.01)
        if conn.closed:
            break

    assert conn.closed is True
    assert conn.reliable_overflow is True
    assert conn.dropped_messages == 0  # kênh best-effort không bị ảnh hưởng
    assert ws.closed == (1011, "reliable queue overflow — reconnect to resync")
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_broadcast_to_user_reliable_delivers() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    conn = await mgr.connect(ws)
    await mgr.join_room(conn, mgr.user_room(123))

    sent = await mgr.broadcast_to_user_reliable(
        123, build_message("trade_fill", {"n": 5})
    )
    assert sent == 1
    await asyncio.sleep(0.01)
    assert json_of(ws.sent[0])["type"] == "trade_fill"

    await mgr.disconnect(conn)


@pytest.mark.asyncio
async def test_broadcast_status_reaches_all_connections() -> None:
    """feed_status gửi tới MỌI kết nối local (không qua backplane) kèm resync_via."""
    mgr = ConnectionManager()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    c1 = await mgr.connect(ws1)
    c2 = await mgr.connect(ws2)

    sent = await mgr.broadcast_status(
        "degraded", "realtime_bridge_down", resync_via=["/api/v1/trades/orders"]
    )
    assert sent == 2
    await asyncio.sleep(0.01)

    frame = next(m for m in ws1.sent_messages() if m["type"] == "feed_status")
    assert frame["data"]["status"] == "degraded"
    assert frame["data"]["reason"] == "realtime_bridge_down"
    assert frame["data"]["resync_via"] == ["/api/v1/trades/orders"]
    assert any(m["type"] == "feed_status" for m in ws2.sent_messages())

    await mgr.disconnect(c1)
    await mgr.disconnect(c2)
