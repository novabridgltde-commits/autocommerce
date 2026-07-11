"""services/idempotency.py — Clés d'idempotence pour les opérations critiques.

Stratégie : Redis SET NX avec TTL.
  • is_already_processed(key) -> True si déjà exécuté dans la fenêtre TTL.
  • mark_processed(key, ttl)  -> marque comme exécuté.
  • build_idempotency_key()   -> hash SHA-256 déterministe à partir du namespace + parts.

Fallback in-memory : si Redis est indisponible, utilise un dict thread-local
(sûr par worker Uvicorn, ne survit pas au redémarrage — acceptable pour idempotence
best-effort).
"""
from __future__ import annotations

import hashlib
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)


def get_redis():
    """Wrapper exposé au niveau module (patchable directement en test), qui
    délègue à services.redis_lock.get_redis via un import dynamique — ce qui
    reste compatible avec les tests qui patchent services.redis_lock.get_redis
    directement (résolution au moment de l'appel, pas à l'import)."""
    from services.redis_lock import get_redis as _real_get_redis
    return _real_get_redis()

# ── Fallback in-memory ────────────────────────────────────────────────────────
_local_store: dict[str, float] = {}  # key -> expiry timestamp
_local_lock = Lock()


def build_idempotency_key(namespace: str, *parts: str) -> str:
    """Construit une clé d'idempotence déterministe.

    Ex: build_idempotency_key("whatsapp", "123", "hello") ->
        "whatsapp:<sha256[:16]>"
    """
    raw = ":".join(str(p) for p in parts)
    return f"{namespace}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _local_exists(key: str) -> bool:
    with _local_lock:
        expiry = _local_store.get(key)
        if expiry is None:
            return False
        if time.monotonic() > expiry:
            del _local_store[key]
            return False
        return True


def _local_set(key: str, ttl_seconds: int) -> None:
    with _local_lock:
        _local_store[key] = time.monotonic() + ttl_seconds


async def is_already_processed(key: str) -> bool:
    """Retourne True si la clé existe déjà (opération déjà traitée)."""
    try:
        r = get_redis()
        return bool(await r.exists(key))
    except Exception as exc:
        logger.debug("idempotency.redis_unavailable key=%s: %s — using in-memory fallback", key, exc)
        return _local_exists(key)


async def mark_processed(key: str, ttl_seconds: int = 86400) -> None:
    """Marque une opération comme traitée pendant ttl_seconds."""
    try:
        r = get_redis()
        await r.set(key, str(int(time.time())), ex=ttl_seconds, nx=True)
    except Exception as exc:
        logger.debug("idempotency.redis_unavailable key=%s: %s — using in-memory fallback", key, exc)
        _local_set(key, ttl_seconds)


# Alias : certains appelants (et tests/test_whatsapp_enterprise.py) utilisent
# ce nom. On garde mark_processed comme nom canonique et on expose l'alias
# pour ne pas casser les deux conventions de nommage en usage dans le repo.
mark_as_processed = mark_processed


async def check_and_mark(key: str, ttl_seconds: int = 86400) -> bool:
    """Vérifie et marque atomiquement. Retourne True si DÉJÀ traité (doublon).

    Usage pattern :
        if await check_and_mark(key):
            return  # doublon, skip
        # ... traitement ...
    """
    try:
        r = get_redis()
        # SET NX : retourne True si la clé a été créée (= première fois)
        # On inverse : True = déjà existait = doublon
        created = await r.set(key, str(int(time.time())), ex=ttl_seconds, nx=True)
        return not bool(created)  # True = déjà traité
    except Exception as exc:
        logger.debug("idempotency.check_and_mark redis error: %s — fallback", exc)
        if _local_exists(key):
            return True
        _local_set(key, ttl_seconds)
        return False
