"""Rate limiter fixed-window trên Redis cho endpoint nhạy cảm (login).

- Mỗi key (``identifier`` — email/username hoặc IP) đếm số lần truy cập trong
  cửa sổ thời gian; quá ``max_attempts`` → trả False (caller trả 429).
- Dùng pipeline INCR + EXPIRE (1 round-trip). Không cần Lua.
- Redis hỏng → fallback về RAM của process hiện tại (fail-open availability, vẫn
  chặn được kẻ bắn phá trên instance đang phục vụ; nhiều replica thì hiệu lực
  giảm nhưng không bao giờ chặn nhầm người dùng hợp lệ do Redis tạm ngắt).
"""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from core.cache import get_cache

logger = logging.getLogger(__name__)

_RATE_KEY_PREFIX = "finsim:ratelimit:"

# Fallback RAM khi Redis không khả dụng: key -> (window_end_monotonic, count).
_memory: dict[str, tuple[float, int]] = {}


def _mem_count(key: str, now: float) -> int:
    entry = _memory.get(key)
    if entry is None or entry[0] < now:
        return 0
    return entry[1]


def _mem_record(key: str, window_seconds: int, now: float) -> int:
    entry = _memory.get(key)
    if entry is None or entry[0] < now:
        _memory[key] = (now + window_seconds, 1)
        return 1
    new_count = entry[1] + 1
    _memory[key] = (entry[0], new_count)
    return new_count


async def check_rate(
    identifier: str,
    *,
    max_attempts: int,
    window_seconds: int,
    now: float | None = None,
) -> bool:
    """Ghi nhận 1 lần truy cập; trả ``False`` khi vượt ngưỡng trong cửa sổ."""
    now = time.monotonic() if now is None else now
    key = f"{_RATE_KEY_PREFIX}{identifier}"
    try:
        client = cast(Any, get_cache())
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        count, _ = await pipe.execute()
        return int(count) <= max_attempts
    except Exception as exc:  # noqa: BLE001 - Redis chập chờn → fallback RAM
        logger.warning("Rate limit Redis failed (%s) — fallback in-memory", exc)
        return _mem_record(key, window_seconds, now) <= max_attempts


async def peek_rate(
    identifier: str,
    *,
    max_attempts: int,
    now: float | None = None,
) -> bool:
    """Kiểm tra hạn mức mà KHÔNG ghi nhận lượt truy cập (chỉ đọc bộ đếm).

    Trả ``True`` khi số lần đã ghi trong cửa sổ còn dưới ``max_attempts``.
    Dùng cho luồng login: kiểm tra trước rồi chỉ ghi nhận khi xác thực THẤT BẠI —
    tránh tính cả lần đăng nhập thành công vào ngưỡng brute-force.
    """
    now = time.monotonic() if now is None else now
    key = f"{_RATE_KEY_PREFIX}{identifier}"
    try:
        client = cast(Any, get_cache())
        raw = await client.get(key)
        count = int(raw) if raw is not None else 0
    except Exception as exc:  # noqa: BLE001 - Redis chập chờn → fallback RAM
        logger.warning("Rate limit Redis get failed (%s) — fallback in-memory", exc)
        count = _mem_count(key, now)
    return count < max_attempts


async def record_rate(
    identifier: str,
    *,
    window_seconds: int,
    now: float | None = None,
) -> int:
    """Ghi nhận 1 lượt truy cập (tăng bộ đếm); trả số lượt trong cửa sổ hiện tại."""
    now = time.monotonic() if now is None else now
    key = f"{_RATE_KEY_PREFIX}{identifier}"
    try:
        client = cast(Any, get_cache())
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        count, _ = await pipe.execute()
        return int(count)
    except Exception as exc:  # noqa: BLE001 - Redis chập chờn → fallback RAM
        logger.warning("Rate limit Redis failed (%s) — fallback in-memory", exc)
        return _mem_record(key, window_seconds, now)


async def reset_rate(identifier: str) -> None:
    """Xoá bộ đếm của ``identifier`` (ví dụ sau khi đăng nhập thành công)."""
    key = f"{_RATE_KEY_PREFIX}{identifier}"
    try:
        client = cast(Any, get_cache())
        await client.delete(key)
    except Exception as exc:  # noqa: BLE001 - Redis chập chờn → vẫn xoá RAM
        logger.warning("Rate limit Redis delete failed (%s) — fallback in-memory", exc)
    _memory.pop(key, None)
