"""services/token_store.py — In-memory + Redis token store for password reset etc.

Provides set_token, get_token, delete_token for short-lived opaque tokens.
Falls back to in-memory dict when Redis is unavailable (single-process only).
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# In-memory fallback: {token: (value, expires_at)}
_mem_store: dict[str, tuple[Any, float]] = {}


def _mem_cleanup() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _mem_store.items() if exp < now]
    for k in expired:
        del _mem_store[k]


async def set_token(token: str, value: Any, ttl_seconds: int = 3600) -> None:
    """Store a token with a TTL. Uses Redis if available, in-memory fallback."""
    try:
        import json

        from services.redis_lock import get_redis
        redis = get_redis()
        await redis.setex(f"tok:{token}", ttl_seconds, json.dumps(value))
        return
    except Exception as exc:
        logger.debug("token_store.set_token: Redis unavailable (%s) — using memory", exc)

    _mem_cleanup()
    _mem_store[token] = (value, time.time() + ttl_seconds)


async def get_token(token: str) -> Any | None:
    """Retrieve a token value. Returns None if expired or not found."""
    try:
        import json

        from services.redis_lock import get_redis
        redis = get_redis()
        raw = await redis.get(f"tok:{token}")
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.debug("token_store.get_token: Redis unavailable (%s) — using memory", exc)

    entry = _mem_store.get(token)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _mem_store[token]
        return None
    return value


async def delete_token(token: str) -> None:
    """Delete a token."""
    try:
        from services.redis_lock import get_redis
        redis = get_redis()
        await redis.delete(f"tok:{token}")
        return
    except Exception as exc:
        logger.debug("token_store.delete_token: Redis unavailable (%s) — using memory", exc)

    _mem_store.pop(token, None)
