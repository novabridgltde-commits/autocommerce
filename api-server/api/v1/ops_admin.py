"""
api/v1/ops_admin.py — Ops/SRE administration endpoints (HARDENED)
HIGH-13 FIX: X-Operator-ID obligatoire sur les writes + ops_audit structuré.
"""
from __future__ import annotations

import json
import logging
import time

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)
ops_audit_log = structlog.get_logger("ops_audit")
router = APIRouter(prefix="/ops", tags=["Ops"])

KNOWN_DLQS = ("whatsapp.dlq", "payments.dlq", "social.dlq", "billing.dlq", "ai.dlq")
KNOWN_QUEUES = ("billing", "whatsapp", "social", "ai", "celery")


def _auth(token: str | None) -> None:
    if not token or token != settings.INTERNAL_HEALTH_TOKEN:
        raise HTTPException(status_code=403, detail="X-Internal-Token missing or invalid")


def _require_operator_id(operator_id: str | None, action: str) -> str:
    """HIGH-13 FIX: Header X-Operator-ID obligatoire sur les opérations write."""
    if not operator_id or not operator_id.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                f"X-Operator-ID header is required for write operation '{action}'. "
                "Format: team member identifier (e.g. 'sre-karim', 'oncall-2026-06')"
            ),
        )
    clean = "".join(c for c in operator_id.strip() if c.isalnum() or c in "-_@.")
    if len(clean) < 2:
        raise HTTPException(status_code=400,
            detail="X-Operator-ID must be at least 2 characters")
    return clean[:64]


def _log_ops_action(operator_id: str, action: str, target: str, result: str,
                    extra: dict | None = None, request: Request | None = None) -> None:
    """HIGH-13 FIX: Log structuré de chaque opération ops avec attribution."""
    client_ip = "unknown"
    if request and request.client:
        client_ip = request.client.host
    ops_audit_log.info("ops_action",
        operator_id=operator_id, action=action, target=target, result=result,
        timestamp=time.time(), client_ip=client_ip, **(extra or {}))


@router.get("/dlq")
async def list_dlqs(request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    _auth(x_internal_token)
    operator = x_operator_id or "monitoring"
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        sizes = {}
        for q in KNOWN_DLQS:
            try:
                sizes[q] = await r.llen(f"dlq:{q}")
            except Exception as exc:
                sizes[q] = f"error:{exc}"
        _log_ops_action(operator, "dlq_list", "all", "ok", request=request)
        return {"dlqs": sizes, "operator_id": operator}
    finally:
        await r.aclose()


@router.get("/dlq/{name}")
async def peek_dlq(name: str, request: Request,
    limit: int = Query(20, ge=1, le=200),
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    _auth(x_internal_token)
    operator = x_operator_id or "monitoring"
    if name not in KNOWN_DLQS:
        raise HTTPException(status_code=400, detail=f"Unknown DLQ. Allowed: {KNOWN_DLQS}")
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        items = await r.lrange(f"dlq:{name}", 0, limit - 1)
        parsed = []
        for it in items:
            try:
                parsed.append(json.loads(it))
            except Exception as _exc:
                logger.warning("peek_dlq failed: %s", _exc)
                parsed.append({"raw": it[:500]})
        _log_ops_action(operator, "dlq_peek", name, f"count={len(parsed)}", request=request)
        return {"dlq": name, "count": len(parsed), "items": parsed, "operator_id": operator}
    finally:
        await r.aclose()


class DLQReplayRequest(BaseModel):
    dlq: str
    count: int = 1


@router.post("/dlq/replay")
async def replay_dlq(body: DLQReplayRequest, request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    """Replay DLQ. Requires X-Operator-ID (HIGH-13 fix)."""
    _auth(x_internal_token)
    operator = _require_operator_id(x_operator_id, "dlq/replay")
    if body.dlq not in KNOWN_DLQS:
        raise HTTPException(status_code=400, detail=f"Unknown DLQ: {body.dlq}")
    count = max(1, min(body.count, 50))
    import redis.asyncio as aioredis

    from services.celery_app import celery_app
    dlq_to_task = {
        "whatsapp.dlq": "services.tasks.process_whatsapp_message",
        "payments.dlq": "services.tasks.reconcile_payment",
        "social.dlq": "services.tasks.process_social_webhook",
        "ai.dlq": "services.tasks.update_product_embedding",
        "billing.dlq": "services.tasks.reconcile_payment",
    }
    target_task_name = dlq_to_task[body.dlq]
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    replayed = 0
    failed = []
    try:
        for _ in range(count):
            raw = await r.lpop(f"dlq:{body.dlq}")
            if not raw:
                break
            try:
                rec = json.loads(raw)
            except Exception as _exc:
                logger.warning("operation failed: %s", _exc)
                failed.append({"reason": "invalid_json", "raw": raw[:200]})
                continue
            args = rec.get("args") or []
            kwargs = rec.get("kwargs") or {}
            try:
                celery_app.send_task(target_task_name, args=args, kwargs=kwargs)
                replayed += 1
            except Exception as exc:
                await r.rpush(f"dlq:{body.dlq}", raw)
                failed.append({"reason": str(exc)[:200]})
        _log_ops_action(operator, "dlq_replay", body.dlq,
            f"replayed={replayed} failed={len(failed)}",
            extra={"count_requested": count}, request=request)
        return {"dlq": body.dlq, "replayed": replayed, "failed": failed, "operator_id": operator}
    finally:
        await r.aclose()


@router.get("/circuit-breakers")
async def list_breakers(request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    _auth(x_internal_token)
    operator = x_operator_id or "monitoring"
    from services.circuit_breaker import (
        deepseek_breaker,
        meta_breaker,
        openai_breaker,
        shopify_breaker,
        stripe_breaker,
        tiktok_breaker,
    )
    statuses = []
    for b in (deepseek_breaker, openai_breaker, stripe_breaker, shopify_breaker, meta_breaker, tiktok_breaker):
        statuses.append(await b.status())
    _log_ops_action(operator, "cb_list", "all", "ok", request=request)
    return {"breakers": statuses, "operator_id": operator}


@router.post("/circuit-breakers/{name}/reset")
async def reset_breaker(name: str, request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    """Reset circuit breaker. Requires X-Operator-ID (HIGH-13 fix)."""
    _auth(x_internal_token)
    operator = _require_operator_id(x_operator_id, f"circuit-breakers/{name}/reset")
    from services.circuit_breaker import get_breaker
    breaker = get_breaker(name)
    if not breaker:
        raise HTTPException(status_code=404, detail=f"Unknown breaker: {name}")
    await breaker.reset()
    _log_ops_action(operator, "cb_reset", name, "reset", request=request)
    return {"name": name, "reset": True, "operator_id": operator}


@router.get("/ai-providers")
async def ai_provider_status(request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    _auth(x_internal_token)
    operator = x_operator_id or "monitoring"
    from services.ai_provider_manager import get_fallback_stats
    from services.circuit_breaker import deepseek_breaker, openai_breaker
    deepseek_status = await deepseek_breaker.status()
    openai_status = await openai_breaker.status()
    _log_ops_action(operator, "ai_providers_read", "all", "ok", request=request)
    return {
        "config": {
            "deepseek_enabled": bool(getattr(settings, "FEATURE_FLAG_DEEPSEEK", True)),
            "openai_fallback_enabled": bool(getattr(settings, "FEATURE_FLAG_OPENAI_FALLBACK", True)),
            "deepseek_configured": bool(getattr(settings, "DEEPSEEK_API_KEY", "")),
            "openai_configured": bool(getattr(settings, "OPENAI_API_KEY", "")),
            "deepseek_base_url": getattr(settings, "DEEPSEEK_BASE_URL", ""),
            "openai_model": getattr(settings, "OPENAI_MODEL", ""),
        },
        "breakers": {"deepseek": deepseek_status, "openai": openai_status},
        "fallback_stats": get_fallback_stats(),
        "operator_id": operator,
    }


@router.get("/queues")
async def queue_depths(request: Request,
    x_internal_token: str | None = Header(None, alias="X-Internal-Token"),
    x_operator_id: str | None = Header(None, alias="X-Operator-ID")):
    _auth(x_internal_token)
    operator = x_operator_id or "monitoring"
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        sizes: dict[str, int | None] = {}
        for q in KNOWN_QUEUES:
            try:
                sizes[q] = await r.llen(q)
            except Exception as _exc:
                logger.warning("queue_depths failed: %s", _exc)
                sizes[q] = None
        dlq_sizes: dict[str, int | None] = {}
        for q in KNOWN_DLQS:
            try:
                dlq_sizes[q] = await r.llen(f"dlq:{q}")
            except Exception as _exc:
                logger.warning("queue_depths failed: %s", _exc)
                dlq_sizes[q] = None
        _log_ops_action(operator, "queues_read", "all", "ok", request=request)
        return {"queues": sizes, "dlq_lists": dlq_sizes, "operator_id": operator}
    finally:
        await r.aclose()


__all__ = ["router"]
