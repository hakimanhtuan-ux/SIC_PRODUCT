import json
import logging
import time
from typing import Any
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-backed cache with seamless in-memory fallback for standalone dev."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._redis_checked: bool = False
        self._memory_store: dict[str, tuple[float, str]] = {}

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        try:
            client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1.5,
            )
            await client.ping()
            self._redis = client
            logger.info("Connected to Redis cache at %s", settings.REDIS_URL)
        except Exception as exc:
            logger.warning("Redis unavailable (%s). Using in-memory cache fallback.", exc)
            self._redis = None
        return self._redis

    async def is_redis_connected(self) -> bool:
        client = await self._get_redis()
        return client is not None

    async def get_json(self, key: str) -> Any | None:
        client = await self._get_redis()
        if client is not None:
            try:
                raw = await client.get(key)
                return json.loads(raw) if raw else None
            except Exception:
                pass
        entry = self._memory_store.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if time.time() > expires_at:
            self._memory_store.pop(key, None)
            return None
        return json.loads(payload)

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        client = await self._get_redis()
        if client is not None:
            try:
                await client.setex(key, ttl_seconds, serialized)
                return
            except Exception:
                pass
        self._memory_store[key] = (time.time() + ttl_seconds, serialized)


cache_manager = CacheManager()

