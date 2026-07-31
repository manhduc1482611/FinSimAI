import asyncio
import json

import pytest
from websockets import backplane as backplane_module
from websockets.backplane import DEFAULT_CHANNEL_PREFIX, Backplane
from websockets.connection_manager import ConnectionManager, build_message
from ws_fakes import FakeWebSocket


class FakePubSub:
    def __init__(self, owner: "FakeRedis") -> None:
        self.owner = owner
        self.subscribed: set[str] = set()
        self.pattern: str | None = None
        self.messages: asyncio.Queue = asyncio.Queue()
        self.closed = False
        self.subscribe_gate: asyncio.Event | None = None

    async def subscribe(self, *channels: str) -> list[str]:
        if not self.owner.up:
            raise ConnectionError("redis down")
        if self.subscribe_gate is not None:
            await self.subscribe_gate.wait()
        for channel in channels:
            if channel in self.subscribed:
                continue
            self.subscribed.add(channel)
            self.messages.put_nowait({"type": "subscribe", "channel": channel, "data": 1})
        return list(channels)

    async def unsubscribe(self, *channels: str) -> list[str]:
        if not self.owner.up:
            raise ConnectionError("redis down")
        for channel in channels:
            self.subscribed.discard(channel)
        return list(channels)

    async def psubscribe(self, pattern: str) -> None:
        if not self.owner.up:
            raise ConnectionError("redis down")
        self.pattern = pattern

    async def listen(self):
        while True:
            message = await self.messages.get()
            yield message

    async def aclose(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self, up: bool = True) -> None:
        self.up = up
        self.published: list[tuple[str, str]] = []
        self.raise_on_publish = False
        self.pubsub_obj = FakePubSub(self)

    async def ping(self) -> bool:
        if not self.up:
            raise ConnectionError("redis down")
        return True

    def pubsub(self) -> FakePubSub:
        return self.pubsub_obj

    async def publish(self, channel: str, payload: str) -> None:
        if self.raise_on_publish or not self.up:
            raise ConnectionError("redis down")
        self.published.append((channel, payload))


class FreshPubSubRedis(FakeRedis):
    """pubsub() trả đối tượng MỚI mỗi lần (như redis-py thật) để đo rò handle."""

    def __init__(self, up: bool = True) -> None:
        super().__init__(up=up)
        self.pubsub_objects: list[FakePubSub] = []

    def pubsub(self) -> FakePubSub:
        ps = FakePubSub(self)
        self.pubsub_objects.append(ps)
        return ps


def make_message(channel: str, payload: str, mtype: str = "message") -> dict:
    return {
        "type": mtype,
        "channel": channel,
        "data": payload,
    }


def envelope(room: str, payload: str, sender: str, qos: str = "best_effort") -> str:
    return json.dumps(
        {"room": room, "payload": payload, "sender": sender, "qos": qos}
    )


async def wait_for(predicate, limit: int = 300) -> None:
    for _ in range(limit):
        await asyncio.sleep(0.01)
        if predicate():
            return
    raise AssertionError("Điều kiện không thoả trong giới hạn")


@pytest.mark.asyncio
async def test_publish_room_writes_redis_channel_with_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    payload = json.dumps(build_message("price_tick", {"n": 1}))
    await bp.publish_room("prices:ACB", payload)

    assert len(fake.published) == 1
    channel, raw = fake.published[0]
    assert channel == DEFAULT_CHANNEL_PREFIX + "prices:ACB"
    parsed = json.loads(raw)
    assert parsed["room"] == "prices:ACB"
    assert parsed["payload"] == payload
    assert parsed["sender"] == bp._publisher_id
    assert parsed["qos"] == "best_effort"  # mặc định best-effort (tick giá)


@pytest.mark.asyncio
async def test_publish_room_falls_back_to_local_when_redis_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    fake.raise_on_publish = True
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager, retry_initial=0.01, retry_max=0.05)
    try:
        payload = json.dumps(build_message("price_tick", {"n": 1}))
        sent = await bp.publish_room("prices:ACB", payload)

        assert sent == 1
        # Ngay sau khi publish thất bại: rơi local-only (trước khi reconnect chạy).
        assert bp._fallback_mode is True
        assert bp.status == "degraded"
        await asyncio.sleep(0.05)
        types = [json.loads(s)["type"] for s in ws.sent]
        assert types.count("price_tick") == 1
        # Client nhận feed_status degraded (reconnect có thể đã phát thêm live sau).
        statuses = [
            json.loads(s)["data"]["status"]
            for s in ws.sent
            if json.loads(s)["type"] == "feed_status"
        ]
        assert statuses[0] == "degraded"
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_publisher_broadcasts_local_immediately_and_skips_own_echo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    await bp.start()
    try:
        payload = json.dumps(build_message("price_tick", {"n": 3}))
        sent = await bp.publish_room("prices:ACB", payload)

        # Client local nhận NGAY (không chờ echo Pub/Sub) — Fix "không phụ thuộc
        # tuyệt đối vào độ trễ Redis Pub/Sub".
        assert sent == 1
        await asyncio.sleep(0.01)
        assert len(ws.sent) == 1

        # Message do chính worker này publish khi quay về từ Redis bị BỎ QUA →
        # client local không nhận trùng lần 2.
        own = envelope("prices:ACB", payload, bp._publisher_id)
        await fake.pubsub_obj.messages.put(
            make_message(DEFAULT_CHANNEL_PREFIX + "prices:ACB", own)
        )
        await asyncio.sleep(0.02)
        assert len(ws.sent) == 1
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_listener_relays_redis_message_to_local_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    await bp.start()
    try:
        # Dynamic subscription: chỉ subscribe channel của room có client local,
        # KHÔNG pattern-subscribe toàn bộ "finsim:ws:*".
        assert fake.pubsub_obj.subscribed == {"finsim:ws:prices:ACB"}
        payload = json.dumps(build_message("price_tick", {"n": 5}))
        await fake.pubsub_obj.messages.put(make_message("finsim:ws:prices:ACB", payload))

        await wait_for(lambda: bool(ws.sent))
        assert len(ws.sent) == 1
        assert json.loads(ws.sent[0])["data"]["n"] == 5
    finally:
        await bp.stop()
    assert fake.pubsub_obj.closed is True


@pytest.mark.asyncio
async def test_listener_relays_message_from_other_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    await bp.start()
    try:
        payload = json.dumps(build_message("price_tick", {"n": 7}))
        other = envelope("prices:ACB", payload, "other-worker")
        await fake.pubsub_obj.messages.put(make_message("finsim:ws:prices:ACB", other))

        await wait_for(lambda: bool(ws.sent))
        assert len(ws.sent) == 1
        assert json.loads(ws.sent[0])["data"]["n"] == 7
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_dynamic_subscription_only_for_rooms_with_local_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker KHÔNG subscribe channel của room không có client local (cắt CPU thừa)."""
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    manager.attach_backplane(bp)
    await bp.start()
    try:
        assert fake.pubsub_obj.subscribed == set()

        await manager.join_room(conn, "prices:ACB")
        assert fake.pubsub_obj.subscribed == {"finsim:ws:prices:ACB"}

        # Client rời → room rỗng → unsubscribe, không còn bắt tin thừa của room đó.
        await manager.leave_room(conn, "prices:ACB")
        assert fake.pubsub_obj.subscribed == set()

        # Room không có client local: vẫn publish lên Redis cho worker khác,
        # nhưng worker NÀY không subscribe → không phải xử lý (cắt CPU thừa).
        await manager.broadcast_to_room("prices:VCB", build_message("price_tick", {"n": 1}))
        assert fake.pubsub_obj.subscribed == set()
        assert any(c == "finsim:ws:prices:VCB" for c, _ in fake.published)
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_reconnect_loop_recovers_when_redis_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis(up=False)
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager, retry_initial=0.01, retry_max=0.05)
    await bp.start()
    assert bp._fallback_mode is True
    assert bp.status == "degraded"

    # Redis quay lại → backplane tự phục hồi (không cần restart dịch vụ).
    fake.up = True
    await wait_for(
        lambda: bp._fallback_mode is False
        and bp._task is not None
        and not bp._task.done()
    )
    assert bp.status == "live"
    # Reconnect re-subscribe lại các room đang có client local.
    assert "finsim:ws:prices:ACB" in fake.pubsub_obj.subscribed

    # Client nhận feed_status theo đúng thứ tự trạng thái: degraded → live.
    await wait_for(
        lambda: any(
            json.loads(s)["type"] == "feed_status"
            and json.loads(s)["data"]["status"] == "live"
            for s in ws.sent
        )
    )
    statuses = [
        json.loads(s)["data"]["status"]
        for s in ws.sent
        if json.loads(s)["type"] == "feed_status"
    ]
    assert statuses == ["degraded", "live"]

    # Sau khi phục hồi, message từ worker khác được relay tới client local.
    payload = json.dumps(build_message("price_tick", {"n": 9}))
    other = envelope("prices:ACB", payload, "other-worker")
    await fake.pubsub_obj.messages.put(make_message("finsim:ws:prices:ACB", other))
    await wait_for(
        lambda: any(
            json.loads(s)["type"] == "price_tick" for s in ws.sent
        )
    )
    await bp.stop()


@pytest.mark.asyncio
async def test_manager_broadcast_routes_through_backplane_when_attached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    manager.attach_backplane(bp)

    await manager.broadcast_to_room("prices:ACB", build_message("price_tick", {"n": 1}))

    # Client local nhận ngay + message được publish lên Redis cho worker khác.
    await wait_for(lambda: bool(ws.sent))
    assert len(ws.sent) == 1
    assert fake.published and fake.published[0][0] == DEFAULT_CHANNEL_PREFIX + "prices:ACB"


@pytest.mark.asyncio
async def test_interleaved_join_leave_does_not_leak_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Join/leave đan xen (subscribe chậm mạng) → không lệch trạng thái room.

    Không lock: sự kiện leave chạy trước khi subscribe của join hoàn thành sẽ bỏ
    qua unsubscribe → room đã rỗng nhưng vẫn subscribe (rò). Lock + đọc lại số
    client thực buộc trạng thái hội tụ về đúng: rỗng → unsubscribe.
    """
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    manager.attach_backplane(bp)
    await bp.start()
    assert fake.pubsub_obj.subscribed == set()

    # Làm subscribe chậm (mô phỏng mạng trễ) để ép interleaving với unsubscribe.
    gate = asyncio.Event()
    fake.pubsub_obj.subscribe_gate = gate

    join_task = asyncio.create_task(manager.join_room(conn, "prices:ACB"))
    await asyncio.sleep(0.02)  # join đang kẹt ở subscribe
    leave_task = asyncio.create_task(manager.leave_room(conn, "prices:ACB"))
    await asyncio.sleep(0.02)  # leave chờ lock

    gate.set()
    await asyncio.wait_for(asyncio.gather(join_task, leave_task), timeout=5)

    # Room đã rỗng → channel phải được unsubscribe (không rò handle subscribe).
    assert fake.pubsub_obj.subscribed == set()
    assert bp._subscribed == set()
    await bp.stop()


@pytest.mark.asyncio
async def test_reconnect_closes_old_pubsub_and_stops_old_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconnect không để rò handle PubSub cũ trong event loop."""
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FreshPubSubRedis(up=False)
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager, retry_initial=0.01, retry_max=0.05)
    await bp.start()
    assert bp._fallback_mode is True
    assert len(fake.pubsub_objects) == 1
    first = fake.pubsub_objects[0]
    # start() khi Redis down phải đóng pubsub vừa tạo (không để rò handle).
    assert first.closed is True

    fake.up = True
    await wait_for(
        lambda: bp._fallback_mode is False
        and bp._task is not None
        and not bp._task.done()
    )

    # Chỉ pubsub mới nhất còn "sống"; cái cũ đã được aclose().
    assert len(fake.pubsub_objects) == 2
    active = [ps for ps in fake.pubsub_objects if not ps.closed]
    assert len(active) == 1
    assert bp._pubsub is active[0]
    await bp.stop()
    assert fake.pubsub_objects[-1].closed is True


@pytest.mark.asyncio
async def test_reconnect_after_publish_failure_stops_old_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publish lỗi (listener cũ VẪN SỐNG) → reconnect phải hủy listener cũ.

    Nếu không, hai listener cùng relay → message bị trùng tới client local.
    """
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FreshPubSubRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager, retry_initial=0.01, retry_max=0.05)
    await bp.start()
    first = fake.pubsub_objects[0]
    old_listener = bp._task
    assert old_listener is not None and not old_listener.done()

    # Publish thất bại nhưng listener cũ vẫn sống (subscribe vẫn OK).
    fake.raise_on_publish = True
    await bp.publish_room("prices:ACB", json.dumps(build_message("price_tick", {"n": 1})))
    assert bp._fallback_mode is True
    assert not old_listener.done()

    fake.raise_on_publish = False
    await wait_for(
        lambda: bp._fallback_mode is False
        and bp._task is not None
        and bp._task is not old_listener
    )

    # Listener cũ bị hủy + pubsub cũ bị đóng → không còn hai listener cùng relay.
    assert old_listener.done()
    assert first.closed is True
    assert len(fake.pubsub_objects) == 2
    await bp.stop()


@pytest.mark.asyncio
async def test_publish_room_reliable_marks_envelope_qos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tin reliable (trade fill) mang qos=reliable trong envelope → worker khác relay
    qua kênh reliable (không drop)."""
    manager = ConnectionManager()
    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    payload = json.dumps(build_message("trade_fill", {"n": 1}))
    await bp.publish_room("user:7", payload, reliable=True)

    assert len(fake.published) == 1
    parsed = json.loads(fake.published[0][1])
    assert parsed["qos"] == "reliable"


@pytest.mark.asyncio
async def test_listener_relays_reliable_message_via_reliable_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker nhận envelope qos=reliable → broadcast_local_room_reliable
    (không đi qua best-effort drop-oldest)."""
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "user:7")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    await bp.start()
    try:
        payload = json.dumps(build_message("trade_fill", {"n": 7}))
        other = envelope("user:7", payload, "other-worker", qos="reliable")
        await fake.pubsub_obj.messages.put(make_message("finsim:ws:user:7", other))

        await wait_for(lambda: bool(ws.sent))
        assert json.loads(ws.sent[0])["data"]["n"] == 7
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_realtime_status_reflects_backplane_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Welcome frame của client mới phản ánh đúng trạng thái nguồn realtime."""
    manager = ConnectionManager()
    ws = FakeWebSocket()
    conn = await manager.connect(ws)
    await manager.join_room(conn, "prices:ACB")

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    manager.attach_backplane(bp)
    await bp.start()
    try:
        assert manager.realtime_status() == "live"

        fake.raise_on_publish = True
        await bp.publish_room("prices:ACB", json.dumps(build_message("price_tick", {"n": 1})))
        assert bp.status == "degraded"
        assert manager.realtime_status() == "degraded"
    finally:
        await bp.stop()


@pytest.mark.asyncio
async def test_feed_status_broadcast_only_on_state_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """feed_status chỉ phát khi trạng thái THAY ĐỔI — không spam client mỗi lần
    publish gặp lỗi liên tiếp."""
    manager = ConnectionManager()
    ws = FakeWebSocket()
    await manager.connect(ws)

    fake = FakeRedis()
    monkeypatch.setattr(backplane_module, "get_cache", lambda: fake)

    bp = Backplane(manager)
    await bp.start()
    try:
        for _ in range(3):
            await bp._set_status(
                "degraded", "realtime_bridge_down", resync_via=["/api/v1/trades/orders"]
            )
        await asyncio.sleep(0.02)
        frames = [json.loads(s) for s in ws.sent if json.loads(s)["type"] == "feed_status"]
        assert len(frames) == 1
        assert frames[0]["data"]["status"] == "degraded"
        assert frames[0]["data"]["resync_via"] == ["/api/v1/trades/orders"]

        await bp._set_status("live", "realtime_restored")
        await asyncio.sleep(0.02)
        frames = [json.loads(s) for s in ws.sent if json.loads(s)["type"] == "feed_status"]
        assert len(frames) == 2
        assert frames[-1]["data"]["status"] == "live"
    finally:
        await bp.stop()
