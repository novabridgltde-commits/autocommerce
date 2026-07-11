"""services/ai_guardrails.py — Guardrails IA et gestion des crédits tenant.

Implémentation production :
  - Quota crédits IA par tenant stocké dans Redis (clé mensuelle YYYYMM).
  - Initialisation du quota depuis plan_limits (table DB) ou catalogue statique.
  - Fallback in-memory si Redis est indisponible (best-effort, non partagé entre workers).
  - check_tenant_credit  : vérifie sans déduire.
  - deduct_tenant_credit : déduit de manière atomique (DECRBY + plancher 0).
  - get_tenant_credit_stats : stats pour /billing/usage.

Coûts :
  text  = 1 crédit
  audio = 5 crédits
  image = 10 crédits
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("ai_guardrails")

# Fallback in-memory (single-worker) quand Redis est indisponible
_MEMORY_CREDITS: dict[str, int] = {}   # clé: "credits:{store_id}:{YYYYMM}"
_MEMORY_USED: dict[str, int] = {}      # clé: "used:{store_id}:{YYYYMM}"

# ── Quota par défaut (crédits IA par plan, miroir de plan_limits) ─────────────
_DEFAULT_QUOTAS: dict[str, int] = {
    "free": 0,
    "starter": 500,
    "business": 2000,
    "premium": 5000,
    "pro_whatsapp": 10000,
    "pro": 5000,
    "enterprise": 20000,
}


def _month_suffix() -> str:
    return datetime.now(UTC).strftime("%Y%m")


def _credit_key(store_id: int) -> str:
    return f"ai_credits:remaining:{store_id}:{_month_suffix()}"


def _used_key(store_id: int) -> str:
    return f"ai_credits:used:{store_id}:{_month_suffix()}"


def _allocated_key(store_id: int) -> str:
    return f"ai_credits:allocated:{store_id}:{_month_suffix()}"


# ── Redis helper ──────────────────────────────────────────────────────────────

async def _get_redis():
    """Retourne le client Redis async (pool partagé) ou None si indisponible."""
    try:
        from lib.redis_client import get_redis as _shared_get_redis
        client = await _shared_get_redis()
        await client.ping()
        return client
    except Exception:
        return None


# Alias demandé par auth.py : from services.ai_guardrails import get_redis
def get_redis():
    """Alias synchrone vers services.redis_lock.get_redis (compatibilité auth.py)."""
    try:
        from services.redis_lock import get_redis as _get  # type: ignore[import]
        return _get()
    except Exception:
        try:
            import os

            import redis as redis_lib  # type: ignore[import]
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            return redis_lib.Redis.from_url(url, socket_connect_timeout=1)
        except Exception:
            return None


# ── Initialisation quota ──────────────────────────────────────────────────────

async def _get_plan_quota(store_id: int) -> int:
    """Lit le quota mensuel du plan actif depuis la DB ou le catalogue statique."""
    try:
        from models.database import AsyncSessionLocal
        from services.saas_billing import get_active_subscription, get_plan_by_code
        async with AsyncSessionLocal() as db:
            sub = await get_active_subscription(db, store_id)
            plan_code = sub.plan_code if sub else "free"
            plan = await get_plan_by_code(db, plan_code)
            return int((plan or {}).get("monthly_ai_credits", 0))
    except Exception as exc:
        logger.warning("_get_plan_quota db error store_id=%d: %s", store_id, exc)
        return 0


async def _ensure_credits_initialized(store_id: int, redis) -> int:
    """S'assure que le quota mensuel est initialisé dans Redis.

    Si la clé n'existe pas (nouveau mois ou première fois), lit le quota
    depuis la DB et l'initialise avec un TTL jusqu'à la fin du mois.

    Returns:
        Quota alloué pour ce mois.
    """
    allocated_key = _allocated_key(store_id)
    credit_key = _credit_key(store_id)

    if redis:
        try:
            allocated_str = await redis.get(allocated_key)
            if allocated_str is not None:
                return int(allocated_str)
        except Exception:
            pass

    # Calculer TTL jusqu'à la fin du mois
    now = datetime.now(UTC)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0)
    ttl_seconds = int((next_month - now).total_seconds()) + 86400  # +1 jour de marge

    quota = await _get_plan_quota(store_id)

    if redis:
        try:
            pipe = redis.pipeline()
            # Initialise le quota si pas encore défini ce mois
            pipe.set(allocated_key, quota, ex=ttl_seconds, nx=True)
            pipe.set(credit_key, quota, ex=ttl_seconds, nx=True)
            await pipe.execute()
        except Exception as exc:
            logger.warning("_ensure_credits_initialized redis error store_id=%d: %s", store_id, exc)

    # Fallback mémoire
    # AUDIT FIX : vérifiait la présence de `mem_key_alloc` (clé "allocated",
    # quasiment jamais peuplée) pour décider d'écraser `credit_key` (clé
    # "credit", celle qui contient le solde réellement décrémenté). Résultat :
    # à chaque appel sans Redis, le solde en mémoire était systématiquement
    # réinitialisé au quota plein, effaçant toute déduction précédente.
    if credit_key not in _MEMORY_CREDITS:
        _MEMORY_CREDITS[credit_key] = quota

    return quota


# ── Interface publique ────────────────────────────────────────────────────────

async def check_tenant_credit(store_id: int, cost: int = 1) -> bool:
    """Vérifie si le tenant dispose de suffisamment de crédits IA.

    N'effectue aucune déduction — appeler deduct_tenant_credit après usage.

    Args:
        store_id : ID du tenant.
        cost     : Coût en crédits de l'action demandée.

    Returns:
        True si suffisamment de crédits disponibles (ou quota = 0 = illimité).
        False si quota épuisé.
    """
    redis = await _get_redis()
    quota = await _ensure_credits_initialized(store_id, redis)

    if quota == 0:
        # Plan free ou non configuré : on bloque l'IA
        logger.debug("check_tenant_credit store_id=%d quota=0 (plan free — IA bloquée)", store_id)
        return False

    if quota < 0:
        # -1 = illimité (ex: plan enterprise custom)
        return True

    credit_key = _credit_key(store_id)

    if redis:
        try:
            remaining_str = await redis.get(credit_key)
            remaining = int(remaining_str or quota)
            result = remaining >= cost
            logger.debug(
                "check_tenant_credit store_id=%d remaining=%d cost=%d result=%s",
                store_id, remaining, cost, result,
            )
            return result
        except Exception as exc:
            logger.warning("check_tenant_credit redis error store_id=%d: %s — fail-open", store_id, exc)
            return True

    # Fallback mémoire
    remaining = _MEMORY_CREDITS.get(credit_key, quota)
    return remaining >= cost


async def deduct_tenant_credit(store_id: int, cost: int = 1) -> bool:
    """Déduit des crédits IA après consommation réelle.

    Utilise DECRBY Redis avec plancher à 0 (pas de négatif).
    Best-effort — n'interrompt pas le flow en cas d'erreur.

    Args:
        store_id : ID du tenant.
        cost     : Crédits à déduire.

    Returns:
        True si la déduction a été appliquée, False en cas d'erreur.
    """
    redis = await _get_redis()
    credit_key = _credit_key(store_id)
    used_key = _used_key(store_id)

    if redis:
        try:
            pipe = redis.pipeline()
            pipe.decrby(credit_key, cost)
            pipe.incrby(used_key, cost)
            results = await pipe.execute()
            new_balance = results[0]
            # Empêcher balance négative
            if new_balance < 0:
                await redis.set(credit_key, 0)
            logger.debug(
                "deduct_tenant_credit store_id=%d cost=%d new_balance=%d",
                store_id, cost, max(0, new_balance),
            )
            return True
        except Exception as exc:
            logger.warning("deduct_tenant_credit redis error store_id=%d: %s", store_id, exc)

    # Fallback mémoire
    current = _MEMORY_CREDITS.get(credit_key, 0)
    _MEMORY_CREDITS[credit_key] = max(0, current - cost)
    _MEMORY_USED[used_key] = _MEMORY_USED.get(used_key, 0) + cost
    return True


async def get_tenant_credit_stats(store_id: int) -> dict[str, Any]:
    """Retourne les statistiques de crédits IA pour un tenant.

    Appelé par SecurityGuard.dump_stats() -> GET /billing/usage.

    Returns:
        dict avec credits_allocated, credits_used, credits_remaining, period.
    """
    redis = await _get_redis()
    quota = await _ensure_credits_initialized(store_id, redis)
    credit_key = _credit_key(store_id)
    used_key = _used_key(store_id)

    remaining = quota
    used = 0

    if redis:
        try:
            remaining_str = await redis.get(credit_key)
            used_str = await redis.get(used_key)
            remaining = int(remaining_str) if remaining_str is not None else quota
            used = int(used_str) if used_str is not None else 0
        except Exception as exc:
            logger.warning("get_tenant_credit_stats redis error store_id=%d: %s", store_id, exc)
    else:
        remaining = _MEMORY_CREDITS.get(credit_key, quota)
        used = _MEMORY_USED.get(used_key, 0)

    return {
        # AUDIT-FIX: tests/test_ai_guardrails.py and other consumers expect
        # these plain keys (store_id, remaining, used) — they were missing
        # entirely before, causing KeyError on the test suite.
        "store_id": store_id,
        "remaining": max(0, remaining),
        "used": used,
        "allocated": quota,
        # Alias legacy conservés pour compat avec d'autres appelants existants.
        "credits_allocated": quota,
        "credits_used": used,
        "credits_remaining": max(0, remaining),
        "credits_percent_used": round((used / quota * 100) if quota > 0 else 0, 1),
        "period": _month_suffix(),
    }


async def add_tenant_credits(store_id: int, amount: int, reason: str = "top_up") -> int:
    """Ajoute des crédits IA à un tenant (achat de recharge, bonus admin).

    Args:
        store_id : ID du tenant.
        amount   : Nombre de crédits à ajouter.
        reason   : Motif (top_up | bonus | renewal | refund).

    Returns:
        Nouveau solde de crédits restants.
    """
    redis = await _get_redis()
    credit_key = _credit_key(store_id)
    allocated_key = _allocated_key(store_id)

    new_balance = amount  # fallback

    if redis:
        try:
            pipe = redis.pipeline()
            pipe.incrby(credit_key, amount)
            pipe.incrby(allocated_key, amount)
            results = await pipe.execute()
            new_balance = results[0]
        except Exception as exc:
            logger.warning("add_tenant_credits redis error store_id=%d: %s", store_id, exc)
    else:
        current = _MEMORY_CREDITS.get(credit_key, 0)
        new_balance = current + amount
        _MEMORY_CREDITS[credit_key] = new_balance

    logger.info(
        "add_tenant_credits store_id=%d amount=%d reason=%s new_balance=%d",
        store_id, amount, reason, new_balance,
    )
    return max(0, new_balance)


async def reset_monthly_credits(store_id: int) -> int:
    """Réinitialise les crédits mensuels (appelé par Celery au renouvellement).

    Returns:
        Nouveau quota alloué.
    """
    redis = await _get_redis()
    quota = await _get_plan_quota(store_id)
    credit_key = _credit_key(store_id)
    used_key = _used_key(store_id)
    allocated_key = _allocated_key(store_id)

    now = datetime.now(UTC)
    if now.month == 12:
        next_month = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0)
    else:
        next_month = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0)
    ttl = int((next_month - now).total_seconds()) + 86400

    if redis:
        try:
            pipe = redis.pipeline()
            pipe.set(credit_key, quota, ex=ttl)
            pipe.set(allocated_key, quota, ex=ttl)
            pipe.set(used_key, 0, ex=ttl)
            await pipe.execute()
        except Exception as exc:
            logger.warning("reset_monthly_credits redis error store_id=%d: %s", store_id, exc)

    _MEMORY_CREDITS[credit_key] = quota
    _MEMORY_USED[used_key] = 0

    logger.info("reset_monthly_credits store_id=%d quota=%d", store_id, quota)
    return quota
