import asyncio
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI, WebSocket, status
from fastapi.testclient import TestClient
from starlette.exceptions import WebSocketException
from starlette.websockets import WebSocketDisconnect
from websockets.connection_manager import ConnectionManager
from websockets.mentor_ws import create_mentor_endpoint


class FakeUser:
    def __init__(self, user_id: int = 42) -> None:
        self.id = user_id


class FastProvider:
    def __init__(self, parts: list[str]) -> None:
        self.parts = parts

    async def stream(self, *, user_id, message, session_id) -> AsyncIterator[str]:
        for part in self.parts:
            yield part


class SlowProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stream(self, *, user_id, message, session_id) -> AsyncIterator[str]:
        self.started.set()
        await self.release.wait()
        yield "phản hồi đầu tiên"
        yield "phản hồi thứ hai"


async def allow_auth(websocket: WebSocket) -> FakeUser:
    return FakeUser()


def _receive_until(ws, predicate, limit: int = 300):
    for _ in range(limit):
        message = ws.receive_json()
        if predicate(message):
            return message
    raise AssertionError("Không nhận được tin mong đợi trong giới hạn")


def test_mentor_ws_endpoint_streams_answer() -> None:
    manager = ConnectionManager()
    provider = FastProvider(["chunk một", "chunk hai"])
    app = FastAPI()
    app.add_websocket_route(
        "/ws/mentor", create_mentor_endpoint(manager, provider, allow_auth)
    )

    with TestClient(app) as client:
        with client.websocket_connect("/ws/mentor") as ws:
            ready = _receive_until(ws, lambda m: m["type"] == "mentor_ready")
            assert ready["data"]["user_id"] == "42"

            ws.send_json(
                {"action": "ask", "session_id": "s-1", "message": "Nên mua ACB không?"}
            )
            start = _receive_until(ws, lambda m: m["type"] == "mentor_start")
            assert start["data"]["session_id"] == "s-1"

            chunks = []
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "mentor_end":
                    assert msg["data"]["reason"] == "complete"
                    break
                if msg["type"] == "mentor_chunk":
                    chunks.append(msg["data"]["text"])
            assert chunks == ["chunk một", "chunk hai"]


def test_mentor_ws_endpoint_rejects_empty_message() -> None:
    manager = ConnectionManager()
    provider = FastProvider(["ok"])
    app = FastAPI()
    app.add_websocket_route("/ws/mentor", create_mentor_endpoint(manager, provider, allow_auth))

    with TestClient(app) as client:
        with client.websocket_connect("/ws/mentor") as ws:
            _receive_until(ws, lambda m: m["type"] == "mentor_ready")
            ws.send_json({"action": "ask", "session_id": "s-1", "message": "   "})
            error = _receive_until(ws, lambda m: m["type"] == "error")
            assert error["data"]["code"] == "invalid_message"

            ws.send_json({"action": "nope"})
            unknown = _receive_until(ws, lambda m: m["type"] == "error")
            assert unknown["data"]["code"] == "unknown_action"


def test_mentor_ws_endpoint_cancel() -> None:
    manager = ConnectionManager()
    provider = SlowProvider()
    app = FastAPI()
    app.add_websocket_route("/ws/mentor", create_mentor_endpoint(manager, provider, allow_auth))

    with TestClient(app) as client:
        with client.websocket_connect("/ws/mentor") as ws:
            _receive_until(ws, lambda m: m["type"] == "mentor_ready")

            ws.send_json(
                {"action": "ask", "session_id": "s-1", "message": "Nên bán VCB không?"}
            )
            _receive_until(ws, lambda m: m["type"] == "mentor_start")

            ws.send_json({"action": "cancel", "session_id": "s-1"})
            cancelled = _receive_until(ws, lambda m: m["type"] == "mentor_cancelled")
            assert cancelled["data"]["session_id"] == "s-1"

            ws.send_json({"action": "ping"})
            pong = _receive_until(ws, lambda m: m["type"] == "pong")
            assert pong["type"] == "pong"


def test_mentor_ws_endpoint_rejects_unauthenticated() -> None:
    async def deny_auth(websocket: WebSocket):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Denied in test"
        )

    manager = ConnectionManager()
    app = FastAPI()
    app.add_websocket_route(
        "/ws/mentor", create_mentor_endpoint(manager, FastProvider(["x"]), deny_auth)
    )

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/mentor"):
            pass
    assert exc_info.value.code == 1008
