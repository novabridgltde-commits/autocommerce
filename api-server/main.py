"""
main.py — AutoCommerce V25 Entry Point
=======================================
FastAPI app with:
  - Multi-tenant JWT middleware
  - Alembic auto-migrations on startup (CLI-only in production)
  - Sentry error tracking
  - Structured JSON logging (structlog)
  - CORS with explicit origins (no wildcard in production)
  - Enterprise Security: SecurityHeaders, AuditLog, InputValidation, CSRF
  - Rate limiting via Redis (distributed, cross-worker)
  - Body size limits, trace IDs, PII redaction
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─────────────────────────────────────────────────────────────────────────────
# P0.7 FIX: payment_links_router removed from main.py — registered via api/v1/__init__.py
from api.v1 import router as api_router
from api.v1.health import router as health_router
from config import settings
from middleware.audit_log import AuditLogMiddleware
from middleware.body_limit import BodySizeLimitMiddleware
from middleware.csrf_protection import CSRFProtectionMiddleware  # P0-3 FIX: was defined but never imported
from middleware.input_validation import InputValidationMiddleware
from middleware.rate_limit import RateLimitExceeded, SlowAPIMiddleware, _rate_limit_exceeded_handler, limiter

# ── Enterprise Security Middlewares (v18) ─────────────────────────────────────
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.tenant import TenantMiddleware
from middleware.trace_id import TraceIDMiddleware
from models.database import engine
from preflight_secrets import check_secrets as _preflight_check_secrets

# ─── Logging ──────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)

# MED-7 FIX: PII Redactor ne doit jamais échouer silencieusement en production.
# AVANT: un bug dans pii_redactor.py faisait continuer le serveur en loggant des PII
# (noms, emails, numéros de téléphone clients) — violation RGPD potentielle sans alerte.
# CORRIGÉ: fail hard en production si le redactor ne peut pas s'installer.
# En développement: avertissement visible, mais on continue (DX prioritaire).
_pii_env = settings.ENV.lower()
try:
    from services.pii_redactor import install_pii_redactor
    install_pii_redactor()
except Exception as _pii_exc:  # noqa: BLE001
    if _pii_env in ("production", "prod", "staging"):
        raise RuntimeError(
            f"[RGPD] PII Redactor failed to install in {_pii_env}. "
            "Cannot start without PII protection — this would log customer data in plaintext. "
            f"Error: {_pii_exc}"
        ) from _pii_exc
    else:
        import warnings
        warnings.warn(
            f"[DEV] PII Redactor failed to install: {_pii_exc}. "
            "Customer PII may appear in logs. Fix before deploying to production.",
            RuntimeWarning,
            stacklevel=1,
        )

logger = structlog.get_logger()

# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preflight: refuse to start if critical secrets are missing or still placeholders.
    # Must run BEFORE anything else — no DB, no Sentry, nothing.
    _preflight_check_secrets()
    logger.info("preflight_secrets passed")

    logger.info("AutoCommerce V25 starting", env=settings.ENV)
    # Sentry
    if settings.SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            traces_sample_rate=0.2,
            environment=settings.ENV,
        )
        logger.info("Sentry initialized")
    
    # Database migrations are now CLI-only (SaaS best practice)
    logger.info("Database connection ready (migrations handled via CLI)")

    # ── Session cleanup job (background) ──────────────────────────────────
    # Nettoie périodiquement les password_reset_tokens expirés / utilisés.
    # S'exécute toutes les CLEANUP_INTERVAL_SECONDS (défaut : 1h).
    cleanup_task = None
    try:
        from services.session_cleanup import start_cleanup_job
        cleanup_task = asyncio.create_task(start_cleanup_job())
        logger.info("session_cleanup job scheduled")
    except Exception as _cleanup_err:
        logger.warning("session_cleanup job failed to start: %s", _cleanup_err)

    yield

    # Arrêt propre du job de nettoyage
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        await asyncio.gather(cleanup_task, return_exceptions=True)
        logger.info("session_cleanup job stopped")

    logger.info("AutoCommerce V25 shutting down")
    await engine.dispose()

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AutoCommerce V25",
    description="AI-powered Omnichannel Commerce SaaS — WhatsApp + Instagram + Facebook + TikTok",
    version="25.0.0",
    docs_url="/docs" if settings.ENV.lower() == "development" else None,
    redoc_url="/redoc" if settings.ENV.lower() == "development" else None,
    # redirect_slashes=False pour éviter que les 307 stripent le header Authorization
    # et le cookie HttpOnly
    redirect_slashes=False,
    lifespan=lifespan,
)

# ─── Middleware Stack ───────────────────────────────────────────────────
# Starlette rule: middleware added LAST runs FIRST on the request path.
# Desired effective request-order (incoming -> app):
#   TraceID -> BodyLimit -> InputValidation -> SecurityHeaders -> AuditLog
#                 -> CSRF -> CORS -> Tenant (auth) -> app
#
# P0-FIX (audit): InputValidation now runs BEFORE TenantMiddleware so that
# SQLi / XSS / path-traversal payloads are rejected with HTTP 400 at the
# transport layer — not masked behind a 401 from auth. This is what makes the
# security posture demonstrable in integration tests.
#
# To achieve `Tenant runs LAST = added FIRST` we now ADD MIDDLEWARES IN REVERSE
# ORDER OF EXECUTION.

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 8/ Tenant isolation (runs last -> added first)
app.add_middleware(TenantMiddleware)

# 7/ CORS
_cors_origins = [o.strip() for o in (settings.CORS_ORIGINS or "").split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = ["http://localhost:3000", "http://localhost:5173"]
logger.info("CORS origins", origins=_cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-CSRF-Token",
    ],
)

# 6/ CSRF Protection (only matters for browser-originated mutations)
app.add_middleware(CSRFProtectionMiddleware)

# 5/ Audit Logging
app.add_middleware(AuditLogMiddleware)

# 4/ Security Headers (HSTS, CSP, Cache-Control on sensitive paths)
app.add_middleware(SecurityHeadersMiddleware)

# 3/ Input Validation (SQLi / XSS / path traversal) — BEFORE auth so attacks
#    get a deterministic 400 instead of leaking behind a 401.
app.add_middleware(InputValidationMiddleware)

# 2/ Body size limit
app.add_middleware(BodySizeLimitMiddleware)

# 1/ Rate limit (slowapi) — still useful, runs near the edge
if os.getenv("SKIP_LIMITER") != "1":
    app.add_middleware(SlowAPIMiddleware)

# 0/ Trace ID (added LAST -> runs FIRST so every log line has a trace_id)
app.add_middleware(TraceIDMiddleware)

# ─── Security Overlay (non-intrusive) ─────────────────────────────────────────
# Adds central guard for AI cost / quota / kill-switch / abuse protection.
# ZERO modification to existing services — see backend/security_overlay/.
try:
    from security_overlay import install_security_overlay
    install_security_overlay(app)
except Exception as _overlay_err:  # noqa: BLE001
    logger.warning("security_overlay install failed: %s", _overlay_err)

# Routes
app.include_router(api_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api")
app.include_router(health_router)  # P0/P1: keep /api/health and /health aliases available
app.include_router(health_router, prefix="/api/v1")  # /api/v1/health* alias (attendu par le frontend/monitoring)
# P0.7 FIX: duplicate payment_links mount removed

# P2-B: Prometheus metrics at /metrics
# SEC-3 FIX: /metrics is now gated by X-Internal-Token.
# The instrumentator exposes raw metrics; we add a guard route that validates
# the token before delegating. Unauthenticated requests receive 403.
try:
    from fastapi import Header as _Header
    from fastapi import Request as _Request
    from fastapi.responses import PlainTextResponse as _PlainTextResponse
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from prometheus_fastapi_instrumentator import Instrumentator

    _instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(
        x_internal_token: str | None = _Header(None, alias="X-Internal-Token"),
    ):
        """Prometheus metrics — requires X-Internal-Token. Not public."""
        if not x_internal_token or x_internal_token != settings.INTERNAL_HEALTH_TOKEN:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="X-Internal-Token missing or invalid")
        return _PlainTextResponse(
            generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

except ImportError:
    pass  # prometheus_fastapi_instrumentator not installed — metrics disabled

# I8: OpenTelemetry Distributed Tracing
try:
    from services.opentelemetry_config import setup_opentelemetry
    setup_opentelemetry(app, engine)
except ImportError as e:
    logger.warning(f"OpenTelemetry not installed or configured properly: {e}")
except Exception as e:
    logger.warning(f"Failed to setup OpenTelemetry: {e}")

# ─── Global error handler ─────────────────────────────────────────────────────
# P0 FIX: do NOT swallow HTTPException — let FastAPI handle them with the proper
# status code instead of remapping every error to 500.
from fastapi import HTTPException as _HTTPException
from starlette.exceptions import HTTPException as _StarletteHTTPException


@app.exception_handler(_StarletteHTTPException)
async def http_exception_handler(request: Request, exc: _StarletteHTTPException):
    # Log only as warning (expected business errors), not as 'unhandled'
    logger.warning(
        "HTTP exception",
        path=request.url.path,
        status=exc.status_code,
        detail=str(exc.detail),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else "HTTP error"},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # P0: Re-raise HTTPException so FastAPI's own handler runs (defensive, in case
    # the dispatcher routed an HTTPException here).
    if isinstance(exc, (_HTTPException, _StarletteHTTPException)):
        return await http_exception_handler(request, exc)
    # HC-1 FIX: include trace_id + clean message, never leak stack traces to client
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error(
        "unhandled_exception",
        extra={
            "trace_id": trace_id,
            "path": request.url.path,
            "method": request.method,
            "exc_type": type(exc).__name__,
            "exc_msg": str(exc),
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "trace_id": trace_id,
            "message": "An unexpected error occurred. Please try again or contact support.",
        },
    )
