import asyncio
import logging

from redis.asyncio import Redis

from core.config import settings

logger = logging.getLogger(__name__)

_client: Redis | None = None


def get_cache() -> Redis:
    global _client
    if _client is None:
        # socket_connect_timeout: không treo hàng giây khi Redis mất kết nối —
        # caller (leader lock, dedup, backplane) tự fallback về chế độ local.
        _client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.0,
        )
    return _client


async def ping_cache(timeout: float = 2.0) -> bool:
    try:
        client = get_cache()
        return bool(await asyncio.wait_for(client.ping(), timeout=timeout))
    except Exception as e:
        logger.error("Redis ping failed: %s", e)
        return False
