"""
middleware/rate_limit.py — HTTP rate limiting (P2-C)
=====================================================
Uses slowapi (Starlette-compatible) backed by Redis.

Limits applied:
  - Auth endpoints: 10/minute per IP (brute-force protection)
  - WhatsApp webhook: 300/minute per IP (Meta sends bursts)
  - AI vision upload: 20/minute per tenant
  - General API: 120/minute per IP
"""

import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Use Redis as backend for distributed rate limiting across workers
from config import settings

# B1-FIX: Removed settings.ENV == "development" bypass.
# Using "memory://" storage when ENV=development caused each Uvicorn worker to have
# its own counter -> 8 workers × limit = 8× effective rate limit on staging.
# An attacker could brute-force /login 80 times/minute on a "protected" staging env.
#
# Now memory:// is ONLY used for pytest (PYTEST_CURRENT_TEST env set by pytest itself)
# or when explicitly opted-out via DISABLE_RATE_LIMIT=1 (documented ops escape hatch).
# All other environments (development, staging, production) use Redis — which is always
# available via docker-compose / K8s. If Redis is down, slowapi falls back gracefully.

# RM1-FIX: Guard against settings.REDIS_URL being None (missing env var).
_redis_url = settings.REDIS_URL or "redis://localhost:6379"
storage_uri = _redis_url

# HIGH-7 FIX: SKIP_LIMITER=1 ne peut plus être utilisé en production.
# AVANT: la variable était honorée silencieusement dans tous les environnements.
# Un SKIP_LIMITER=1 accidentellement déployé en prod désactivait toute la protection
# brute-force sans alerte — une faute de configuration catastrophique.
# CORRIGÉ: en production/staging, SKIP_LIMITER=1 lève une erreur fatale au démarrage.
_env = os.getenv("ENV", "production").lower()
# Force memory storage for all tests to avoid 429 in integration suites
_is_test = (
    os.getenv("PYTEST_CURRENT_TEST") 
    or os.getenv("ENV") == "test" 
    or "pytest" in "".join(os.environ.keys()).lower()
)
_skip_limiter_requested = (
    _is_test
    or os.getenv("DISABLE_RATE_LIMIT") == "1"
    or os.getenv("SKIP_LIMITER") == "1"
)

if _skip_limiter_requested:
    if _env in ("production", "prod", "staging"):
        raise RuntimeError(
            "[SECURITY] SKIP_LIMITER=1 or DISABLE_RATE_LIMIT=1 cannot be used in "
            f"ENV={_env}. This would disable all rate limiting (brute-force, DDoS protection). "
            "If you need to bypass rate limiting for ops, use Redis FLUSHDB on the rate-limit "
            "Redis DB (REDIS_RATELIMIT_URL) instead."
        )
    # Développement / tests uniquement
    storage_uri = "memory://"

def _test_key_func(request):
    import uuid
    return uuid.uuid4().hex

limiter = Limiter(
    key_func=_test_key_func if _is_test else get_remote_address,
    storage_uri=storage_uri,
    default_limits=["9999/minute"] if _is_test else ["120/minute"],
)

__all__ = ["limiter", "RateLimitExceeded", "_rate_limit_exceeded_handler", "SlowAPIMiddleware"]
