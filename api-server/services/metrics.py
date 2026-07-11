"""services/metrics.py — Métriques Prometheus Enterprise (Phase 4 + Phase 6).

Nouvelles métriques (Phase 6) :
  - message_queue_length          : taille de la file Redis Streams
  - message_queue_dlq_length      : taille de la DLQ
  - message_queue_pending         : messages en attente d'acquittement
  - webhook_latency_seconds       : latence webhook WhatsApp (end-to-end)
  - active_conversations_total    : conversations actives par store
  - openai_errors_total           : erreurs OpenAI par type

Graceful fallback no-op si prometheus_client absent.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class _NoOpMetric:
    """Métrique no-op : ne lève jamais d'exception."""
    def labels(self, **kwargs) -> _NoOpMetric: return self
    def inc(self, amount: float = 1) -> None: pass
    def dec(self, amount: float = 1) -> None: pass
    def observe(self, amount: float) -> None: pass
    def set(self, value: float) -> None: pass


try:
    from prometheus_client import Counter, Gauge, Histogram, Summary

    # ── Webhooks ──────────────────────────────────────────────────────────────
    webhook_events_total = Counter(
        "webhook_events_total",
        "Total webhook events received",
        ["channel", "event_type"],
    )
    webhook_inflight = Gauge(
        "webhook_inflight",
        "Webhook events currently being processed",
        ["channel"],
    )
    webhook_processing_duration_seconds = Histogram(
        "webhook_processing_duration_seconds",
        "Webhook processing duration in seconds",
        ["channel", "outcome"],
    )
    webhook_latency_seconds = Histogram(
        "webhook_latency_seconds",
        "End-to-end webhook processing latency (reception -> 200 OK)",
        ["channel"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
    )

    # ── FSM / OmniCall Enterprise ─────────────────────────────────────────────
    fsm_transitions_total = Counter(
        "fsm_transitions_total",
        "FSM state transitions",
        ["store_id", "from_state", "to_state"],
    )
    emotion_detections_total = Counter(
        "emotion_detections_total",
        "Emotion detection results",
        ["emotion", "method"],  # method: heuristic|llm
    )
    human_handoffs_total = Counter(
        "human_handoffs_total",
        "Human handoff escalations created",
        ["store_id", "reason"],
    )
    lead_score_distribution = Histogram(
        "lead_score_distribution",
        "Distribution of computed lead scores",
        buckets=[0, 10, 20, 35, 50, 65, 80, 90, 100],
    )

    # ── Billing / Credits ─────────────────────────────────────────────────────
    ai_credits_consumed_total = Counter(
        "ai_credits_consumed_total",
        "AI credits consumed",
        ["store_id", "agent_name"],
    )
    billing_events_total = Counter(
        "billing_events_total",
        "Billing events processed",
        ["event_type", "provider"],
    )

    # ── API Performance ───────────────────────────────────────────────────────
    api_request_duration_seconds = Histogram(
        "api_request_duration_seconds",
        "API request duration",
        ["method", "endpoint", "status_code"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    tenant_active_total = Gauge(
        "tenant_active_total",
        "Number of currently active tenants",
    )
    redis_operations_total = Counter(
        "redis_operations_total",
        "Redis operations",
        ["operation", "outcome"],
    )
    llm_calls_total = Counter(
        "llm_calls_total",
        "LLM API calls",
        ["provider", "model", "agent_name", "outcome"],
    )
    llm_tokens_total = Counter(
        "llm_tokens_total",
        "LLM tokens consumed",
        ["provider", "model", "token_type"],
    )

    # ── Phase 6 : Message Queue ───────────────────────────────────────────────
    message_queue_length = Gauge(
        "message_queue_length",
        "Number of messages in the WhatsApp processing queue (Redis Streams)",
        ["queue"],
    )
    message_queue_dlq_length = Gauge(
        "message_queue_dlq_length",
        "Number of messages in the Dead Letter Queue",
    )
    message_queue_pending = Gauge(
        "message_queue_pending",
        "Number of messages pending acknowledgement in the consumer group",
        ["consumer_group"],
    )

    # ── Phase 6 : Active Conversations ───────────────────────────────────────
    active_conversations_total = Gauge(
        "active_conversations_total",
        "Number of active WhatsApp conversations (not IDLE) across all stores",
    )

    # ── Phase 6 : OpenAI Errors ───────────────────────────────────────────────
    openai_errors_total = Counter(
        "openai_errors_total",
        "OpenAI API errors by type",
        ["error_type", "agent_name"],
    )

    # ── Phase 6 : Message Processing Time ─────────────────────────────────────
    message_processing_duration_seconds = Histogram(
        "message_processing_duration_seconds",
        "Time to process a WhatsApp message through the full AI pipeline",
        ["store_id", "intent"],
        buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )

    logger.debug("Prometheus enterprise metrics initialized (Phase 6 extended)")

except ImportError:
    logger.warning("prometheus_client not installed — using no-op metrics stubs")
    webhook_events_total             = _NoOpMetric()
    webhook_inflight                 = _NoOpMetric()
    webhook_processing_duration_seconds = _NoOpMetric()
    webhook_latency_seconds          = _NoOpMetric()
    fsm_transitions_total            = _NoOpMetric()
    emotion_detections_total         = _NoOpMetric()
    human_handoffs_total             = _NoOpMetric()
    lead_score_distribution          = _NoOpMetric()
    ai_credits_consumed_total        = _NoOpMetric()
    billing_events_total             = _NoOpMetric()
    api_request_duration_seconds     = _NoOpMetric()
    tenant_active_total              = _NoOpMetric()
    redis_operations_total           = _NoOpMetric()
    llm_calls_total                  = _NoOpMetric()
    llm_tokens_total                 = _NoOpMetric()
    message_queue_length             = _NoOpMetric()
    message_queue_dlq_length         = _NoOpMetric()
    message_queue_pending            = _NoOpMetric()
    active_conversations_total       = _NoOpMetric()
    openai_errors_total              = _NoOpMetric()
    message_processing_duration_seconds = _NoOpMetric()
