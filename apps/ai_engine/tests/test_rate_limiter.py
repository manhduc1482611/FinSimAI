"""Test rate limiter Redis: burst, chờ refill, vượt hạn chờ, chia sẻ bucket."""

import fakeredis.aioredis
import pytest

from integrations.rate_limiter import RateLimitExceeded, RedisRateLimiter


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


async def test_burst_allows_capacity_then_blocks(redis):
    limiter = RedisRateLimiter(
        redis, name="burst", capacity=3, refill_per_sec=0.001, max_wait_seconds=0.01
    )
    for _ in range(3):
        await limiter.acquire()
    with pytest.raises(RateLimitExceeded):
        await limiter.acquire()


async def test_waits_for_refill(redis):
    # capacity 1, refill 10 token/s → token mới sau ~0.1s.
    limiter = RedisRateLimiter(
        redis, name="refill", capacity=1, refill_per_sec=10.0, max_wait_seconds=2.0
    )
    await limiter.acquire()
    await limiter.acquire()  # phải chờ refill rồi thành công


async def test_bucket_shared_between_limiter_instances(redis):
    first = RedisRateLimiter(
        redis, name="shared", capacity=1, refill_per_sec=0.001, max_wait_seconds=0.01
    )
    second = RedisRateLimiter(
        redis, name="shared", capacity=1, refill_per_sec=0.001, max_wait_seconds=0.01
    )
    await first.acquire()
    with pytest.raises(RateLimitExceeded):
        await second.acquire()


async def test_tokens_refill_over_time(redis):
    limiter = RedisRateLimiter(
        redis, name="timed", capacity=1, refill_per_sec=50.0, max_wait_seconds=2.0
    )
    await limiter.acquire()
    # Ngủ 0.2s: tích được ~10 token, nhưng capacity=1 nên chỉ 1 token.
    import asyncio

    await asyncio.sleep(0.2)
    await limiter.acquire()
    await limiter.acquire()  # vẫn chỉ được 1 token sau mỗi lần refill
