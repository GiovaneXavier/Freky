"""
Cliente Redis compartilhado para cache de queries de auditoria.
"""
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from core.settings import settings

log = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def cache_get(key: str) -> Any | None:
    try:
        raw = await get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        log.warning("Cache GET falhou (%s): %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    try:
        await get_redis().setex(key, ttl_seconds, json.dumps(value))
    except Exception as exc:
        log.warning("Cache SET falhou (%s): %s", key, exc)


async def cache_delete_pattern(pattern: str) -> None:
    try:
        r = get_redis()
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
    except Exception as exc:
        log.warning("Cache DELETE pattern falhou (%s): %s", pattern, exc)
