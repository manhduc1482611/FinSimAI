import asyncio
import json
import uuid
from typing import Any

from realtime.connection_manager import ConnectionManager


class FakeWebSocket:
    """In-memory WebSocket dùng cho test thuần asyncio."""

    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self.closed: tuple[int, str | None] | None = None
        self._incoming: asyncio.Queue[str] = asyncio.Queue()
        self.query_params: dict[str, str] = {}
        self.scope = {"client": ("testclient", 50000)}

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive_text(self) -> str:
        return await self._incoming.get()

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = (code, reason)

    def send(self, raw: str) -> None:
        self._incoming.put_nowait(raw)

    def sent_messages(self) -> list[dict[str, Any]]:
        return [json.loads(s) for s in self.sent]


class SlowWebSocket(FakeWebSocket):
    """Ghi chậm: send_text block cho tới khi release, dùng test drop-oldest."""

    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()
        self.started = asyncio.Event()

    async def send_text(self, text: str) -> None:
        self.started.set()
        await self.release.wait()
        self.sent.append(text)


class FakeManager(ConnectionManager):
    """Manager thay thế cho ConnectionManager trong test component."""

    def __init__(self) -> None:
        self.room_messages: dict[str, list[dict[str, Any]]] = {}
        self.user_messages: dict[str, list[dict[str, Any]]] = {}
        self.sent: list[dict[str, Any]] = []

    async def broadcast_to_room(
        self, room: str, message: dict[str, Any] | str
    ) -> int:
        self.room_messages.setdefault(room, []).append(
            message if isinstance(message, dict) else {"payload": message}
        )
        return 1

    async def broadcast_to_user(
        self, user_id: str | uuid.UUID, message: dict[str, Any] | str
    ) -> int:
        self.user_messages.setdefault(str(user_id), []).append(
            message if isinstance(message, dict) else {"payload": message}
        )
        return 1

    async def broadcast_to_user_reliable(
        self, user_id: str | uuid.UUID, message: dict[str, Any] | str
    ) -> int:
        return await self.broadcast_to_user(user_id, message)

    async def broadcast_to_room_reliable(
        self, room: str, message: dict[str, Any] | str
    ) -> int:
        return await self.broadcast_to_room(room, message)

    async def send(self, conn: Any, message: dict[str, Any]) -> bool:
        self.sent.append(message)
        return True


class FakePipeline:
    """Redis pipeline in-memory: gom nhiều lệnh, execute 1 lần."""

    def __init__(self, cache: "FakeCache") -> None:
        self.cache = cache
        self.ops: list[tuple[Any, ...]] = []

    def set(self, key: str, value: Any, **kwargs: Any) -> "FakePipeline":
        self.ops.append(("set", key, value, kwargs))
        return self

    def exists(self, *keys: str) -> "FakePipeline":
        self.ops.append(("exists", keys))
        return self

    def incr(self, key: str) -> "FakePipeline":
        self.ops.append(("incr", key))
        return self

    async def execute(self) -> list[Any]:
        results: list[Any] = []
        for op in self.ops:
            if op[0] == "set":
                _, key, value, kwargs = op
                nx = kwargs.get("nx", False)
                if nx and key in self.cache.data:
                    results.append(False)
                else:
                    self.cache.data[key] = value
                    results.append(True)
                self.cache.pipeline_sets.append((key, kwargs))
            elif op[0] == "exists":
                _, keys = op
                results.append(sum(1 for k in keys if k in self.cache.data))
            elif op[0] == "incr":
                _, key = op
                self.cache.data[key] = int(self.cache.data.get(key, 0)) + 1
                results.append(self.cache.data[key])
        self.ops = []
        return results


class FakeCache:
    """Redis stub in-memory dùng cho test persist/load state (watermark, snapshot)."""

    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.pipeline_sets: list[tuple[str, dict[str, Any]]] = []

    def pipeline(self) -> FakePipeline:
        return FakePipeline(self)

    async def set(self, key: str, value: Any, **kwargs: Any) -> bool:
        self.data[key] = value
        return True

    async def incr(self, key: str) -> int:
        self.data[key] = int(self.data.get(key, 0)) + 1
        return int(self.data[key])

    async def get(self, key: str) -> Any:
        return self.data.get(key)

    async def getdel(self, key: str) -> Any:
        """Tiêu thụ ticket single-use nguyên tử (Redis GETDEL)."""
        return self.data.pop(key, None)

    async def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self.data)

    async def expire(self, key: str, ttl: int) -> bool:
        return True

    async def hset(self, key: str, mapping: dict[str, str] | None = None, **kwargs: Any) -> int:
        self.hashes.setdefault(key, {}).update(mapping or {})
        return len(mapping or {})

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))
