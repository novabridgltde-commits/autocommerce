"""services/celery_app.py — Configuration de l'application Celery.

Configuration Celery production.
Broker : CELERY_BROKER_URL (défaut : REDIS_URL ou redis://localhost:6379/0).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from celery import Celery
    broker_url = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    backend_url = os.environ.get("CELERY_RESULT_BACKEND", broker_url)
    
    celery_app = Celery(
        "autocommerce",
        broker=broker_url,
        backend=backend_url,
    )
    celery_app.config_from_object({
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "UTC",
        "enable_utc": True,
        "task_acks_late": True,
        "worker_prefetch_multiplier": 1,
        "task_routes": {
            "services.tasks.process_whatsapp_message": {"queue": "whatsapp"},
            "services.tasks.process_social_webhook": {"queue": "social"},
        },
    })
    celery_app.autodiscover_tasks(["services.tasks"], force=True)
    logger.info("Celery app initialized broker=%s", broker_url)
except ImportError:
    celery_app = None
    logger.warning("Celery not installed — async task processing disabled")
