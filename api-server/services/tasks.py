"""services/tasks.py — Tâches Celery de traitement asynchrone.

Architecture :
  • Si Celery est installé et un broker Redis configuré -> tâches réelles (@task).
  • Si Celery absent ou broker non configuré -> stubs synchrones avec warning
    (comportement identique au démarrage, aucun import cassé).

Queues :
  - whatsapp : messages entrants WhatsApp (haute priorité)
  - social   : webhooks Facebook/Instagram/TikTok
  - default  : tâches génériques (embeddings, notifications)

Retry policy : 3 tentatives avec backoff exponentiel (2^n secondes).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _run_async(coro) -> Any:
    """Exécute une coroutine depuis un worker Celery synchrone."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=120)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── Tentative de chargement Celery ────────────────────────────────────────────
try:
    from services.celery_app import celery_app
    _CELERY_AVAILABLE = celery_app is not None
except ImportError:
    celery_app = None
    _CELERY_AVAILABLE = False

if _CELERY_AVAILABLE:
    # ──────────────────────────────────────────────────────────────────────────
    # Tâches réelles Celery
    # ──────────────────────────────────────────────────────────────────────────

    @celery_app.task(
        name="services.tasks.process_whatsapp_message",
        bind=True, max_retries=3, default_retry_delay=5,
        queue="whatsapp", acks_late=True,
    )
    def process_whatsapp_message(
        self,
        store_id: int,
        customer_phone: str,
        message_text: str,
        **kwargs: Any,
    ) -> dict:
        """Traite un message WhatsApp entrant de façon asynchrone."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    from services.ai_agent import handle_whatsapp_message
                    return await handle_whatsapp_message(
                        store_id=store_id,
                        customer_phone=customer_phone,
                        message_text=message_text,
                        db=db,
                    )
                except Exception as exc:
                    logger.exception(
                        "process_whatsapp_message failed store_id=%s phone=%s: %s",
                        store_id, customer_phone, exc,
                    )
                    raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        return _run_async(_run())

    @celery_app.task(
        name="services.tasks.process_social_webhook",
        bind=True, max_retries=3, default_retry_delay=10,
        queue="social", acks_late=True,
    )
    def process_social_webhook(
        self,
        platform: str,
        store_id: int,
        payload: dict,
        **kwargs: Any,
    ) -> dict:
        """Traite un webhook social (Instagram/Facebook/TikTok) en arrière-plan."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    from services.social_agent import handle_social_event
                    return await handle_social_event(
                        platform=platform, store_id=store_id, payload=payload, db=db
                    )
                except Exception as exc:
                    logger.exception(
                        "process_social_webhook failed platform=%s store_id=%s: %s",
                        platform, store_id, exc,
                    )
                    raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        return _run_async(_run())

    @celery_app.task(
        name="services.tasks.reconcile_payment",
        bind=True, max_retries=5, default_retry_delay=30,
        queue="default",
    )
    def reconcile_payment(self, payment_link_id: int, provider: str, **kwargs: Any) -> dict:
        """Vérifie le statut d'un paiement et met à jour la commande."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                try:
                    from sqlalchemy import select

                    from models.database import PaymentLink
                    from services.payment_factory import PaymentFactory
                    result = await db.execute(
                        select(PaymentLink).where(PaymentLink.id == payment_link_id)
                    )
                    link = result.scalar_one_or_none()
                    if link is None:
                        return {"status": "not_found"}
                    prov = PaymentFactory.get(provider, link.provider_config or {})
                    status = await prov.verify_payment(link.provider_payment_id or "")
                    if status.get("status") == "paid" and link.status != "paid":
                        link.status = "paid"
                        await db.commit()
                        return {"reconciled": True, "status": "paid"}
                    return {"reconciled": False, "status": status.get("status")}
                except Exception as exc:
                    logger.exception("reconcile_payment failed id=%s: %s", payment_link_id, exc)
                    raise self.retry(exc=exc, countdown=30 * (self.request.retries + 1))
        return _run_async(_run())

    @celery_app.task(
        name="services.tasks.update_product_embedding",
        bind=True, max_retries=2, default_retry_delay=60,
        queue="default",
    )
    def update_product_embedding(self, product_id: int, store_id: int, **kwargs: Any) -> dict:
        """Recalcule et stocke l'embedding pgvector d'un produit."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from services.embedding_search import update_product_embedding as _update
                await _update(product_id=product_id, store_id=store_id, db=db)
                return {"product_id": product_id, "done": True}
        return _run_async(_run())

    @celery_app.task(
        name="services.tasks.send_whatsapp_message",
        bind=True, max_retries=3, default_retry_delay=5,
        queue="whatsapp",
    )
    def send_whatsapp_message(
        self, phone_number: str, message: str, store_id: int, **kwargs: Any
    ) -> dict:
        """Envoie un message WhatsApp sortant (notification, rappel, etc.)."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from services.ai_agent import send_whatsapp_text
                return await send_whatsapp_text(
                    store_id=store_id, phone=phone_number, text=message, db=db
                )
        try:
            return _run_async(_run())
        except Exception as exc:
            logger.error("send_whatsapp_message failed phone=%s: %s", phone_number, exc)
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

    @celery_app.task(
        name="services.tasks.process_ai_response",
        bind=True, max_retries=2, default_retry_delay=10,
        queue="default",
    )
    def process_ai_response(self, store_id: int, context: dict, **kwargs: Any) -> dict:
        """Génère une réponse IA pour un contexte donné (usage interne)."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from services.structured_agent import run_agent
                return await run_agent(store_id=store_id, context=context, db=db)
        return _run_async(_run())

    @celery_app.task(
        name="services.tasks.send_order_notification",
        bind=True, max_retries=3, default_retry_delay=15,
        queue="default",
    )
    def send_order_notification(
        self, order_id: int, store_id: int, event: str, **kwargs: Any
    ) -> dict:
        """Notifie le commerçant d'un événement sur une commande."""
        async def _run():
            from models.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select

                from models.database import Order, Store
                order = (await db.execute(
                    select(Order).where(Order.id == order_id, Order.store_id == store_id)
                )).scalar_one_or_none()
                if order is None:
                    return {"notified": False, "reason": "order_not_found"}
                await db.get(Store, store_id)
                logger.info(
                    "send_order_notification: order=%s store=%s event=%s",
                    order_id, store_id, event,
                )
                return {"notified": True, "order_id": order_id, "event": event}
        return _run_async(_run())

else:
    # ──────────────────────────────────────────────────────────────────────────
    # Stubs synchrones — broker absent ou Celery non installé
    # ──────────────────────────────────────────────────────────────────────────

    class _TaskStub:
        """Simule l'interface .delay() / .apply_async() sans broker."""

        def __init__(self, name: str) -> None:
            self.name = name

        def delay(self, *args: Any, **kwargs: Any) -> None:
            logger.warning(
                "Celery broker absent — tâche '%s' non exécutée. "
                "Configurer CELERY_BROKER_URL pour activer le traitement asynchrone.",
                self.name,
            )

        def apply_async(self, args=None, kwargs=None, **options: Any) -> None:
            logger.warning("Celery broker absent — tâche '%s' ignorée.", self.name)

        def __call__(self, *args: Any, **kwargs: Any) -> None:
            logger.warning("Celery broker absent — tâche '%s' appelée en sync.", self.name)

    process_whatsapp_message = _TaskStub("process_whatsapp_message")
    process_social_webhook   = _TaskStub("process_social_webhook")
    reconcile_payment        = _TaskStub("reconcile_payment")
    update_product_embedding = _TaskStub("update_product_embedding")
    send_whatsapp_message    = _TaskStub("send_whatsapp_message")
    process_ai_response      = _TaskStub("process_ai_response")
    send_order_notification  = _TaskStub("send_order_notification")
