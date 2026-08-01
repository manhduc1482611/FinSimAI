"""Rate limiter dựa trên Redis cho các lời gọi LLM (Gemini).

Mục tiêu: bảo vệ API key khỏi bị khoá do vượt giới hạn RPM bằng **token
bucket phân tán** — chia sẻ trạng thái giữa nhiều worker/instance.

Thuật toán:
- Mỗi ngưỡng giới hạn có hai key trên Redis:
  - ``ratelimit:{name}:tokens`` — số token còn lại (float).
  - ``ratelimit:{name}:ts`` — mốc thời gian lần nạp gần nhất.
- Toàn bộ "đọc → tính → ghi" được bọc trong một **distributed lock**
  (``SET key NX EX``) để đảm bảo atomic giữa các worker mà KHÔNG cần Lua —
  tương thích cả với ``fakeredis`` (dùng trong test).

Khi hết token, caller chờ tới khi có token (tối đa ``max_wait_seconds``);
vượt quá → :class:`RateLimitExceeded`.
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

logger = logging.getLogger(__name__)

_LOCK_ACQUIRE_ATTEMPTS = 3
_LOCK_RETRY_DELAY = 0.05


class RateLimitExceeded(RuntimeError):
    """Không lấy được token trong thời gian chờ cho phép."""

    def __init__(self, name: str, wait_seconds: int) -> None:
        self.name = name
        self.wait_seconds = wait_seconds
        super().__init__(f"Rate limit {name}: cần chờ thêm {wait_seconds}s")


class RedisRateLimiter:
    """Token bucket phân tán qua Redis (atomic bằng distributed lock)."""

    def __init__(
        self,
        redis: Any,
        *,
        name: str = "gemini",
        capacity: int = 5,
        refill_per_sec: float = 0.25,
        max_wait_seconds: float = 90.0,
        lock_ttl_seconds: float = 3.0,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity phải >= 1")
        if refill_per_sec < 0:
            raise ValueError("refill_per_sec phải >= 0")
        self.redis = redis
        self.name = name
        self.capacity = float(capacity)
        self.refill_per_sec = refill_per_sec
        self.max_wait_seconds = max_wait_seconds
        self.lock_ttl_seconds = lock_ttl_seconds
        self._tokens_key = f"ratelimit:{name}:tokens"
        self._ts_key = f"ratelimit:{name}:ts"
        self._lock_key = f"ratelimit:{name}:lock"

    # ── API công khai ──────────────────────────────────────────────────────
    async def acquire(self) -> None:
        """Đợi tới khi có một token; ném :class:`RateLimitExceeded` khi quá hạn."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.max_wait_seconds
        while True:
            wait = await self._try_acquire(time.time())
            if wait == 0:
                return
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise RateLimitExceeded(self.name, wait)
            await asyncio.sleep(min(float(wait), remaining))

    # ── Nội bộ ─────────────────────────────────────────────────────────────
    async def _try_acquire(self, now: float) -> int:
        """Trả về 0 nếu đã lấy được token, ngược lại số giây cần chờ."""
        for _ in range(_LOCK_ACQUIRE_ATTEMPTS):
            if await self._lock(now):
                try:
                    return await self._consume_token(now)
                finally:
                    await self.redis.delete(self._lock_key)
        await asyncio.sleep(_LOCK_RETRY_DELAY)
        return 1

    async def _lock(self, now: float) -> bool:
        acquired = await self.redis.set(
            self._lock_key,
            str(now),
            nx=True,
            ex=int(self.lock_ttl_seconds),
        )
        return bool(acquired)

    async def _consume_token(self, now: float) -> int:
        raw_tokens = await self.redis.get(self._tokens_key)
        raw_ts = await self.redis.get(self._ts_key)
        tokens = self._to_float(raw_tokens, self.capacity)
        last = self._to_float(raw_ts, now)
        elapsed = max(0.0, now - last)
        tokens = min(self.capacity, tokens + elapsed * self.refill_per_sec)

        if tokens >= 1.0:
            await self.redis.set(self._tokens_key, str(tokens - 1.0))
            await self.redis.set(self._ts_key, str(now))
            return 0
        if self.refill_per_sec > 0:
            return max(1, math.ceil((1.0 - tokens) / self.refill_per_sec))
        return 1 << 20

    @staticmethod
    def _to_float(raw: Any, fallback: float) -> float:
        if raw is None:
            return fallback
        if isinstance(raw, bytes):
            return float(raw.decode("utf-8"))
        return float(raw)
