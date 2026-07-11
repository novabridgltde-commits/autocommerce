"""security_overlay/models.py — Modèles de données facturation SaaS.

Modèles de données facturation SaaS.
Dataclasses et ORM SQLAlchemy pour les abonnements tenant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from models.database import Base


@dataclass
class SaaSPlan:
    code: str
    name: str
    price_monthly: float = 0.0
    features: list[str] = field(default_factory=list)
    is_public: bool = True


@dataclass
class SaaSSubscription:
    store_id: int
    plan_code: str
    status: str = "active"
    expires_at: str | None = None


@dataclass
class CreditTopUpPack:
    pack_id: str
    credits: int
    price: float
    currency: str = "TND"


@dataclass
class TenantUsage:
    store_id: int
    credits_used: int = 0
    credits_remaining: int = 0
    plan_code: str = "free"


class CreditTopUpPackModel(Base):
    __tablename__ = "credit_top_up_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pack_code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    price_dt: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    price_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    price_paid_dt: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    price_paid_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_7d_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_1d_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class CreditLedger(Base):
    """
    P0-FIX (audit): CreditLedger model was missing, causing 500 in admin stats.
    Maps to 'credit_events' table created by migration 0033.
    """
    __tablename__ = "credit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True) # allocate, deduct, topup, expire, reset, refund
    credits_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # P0-FIX: These fields were expected by credits_admin.py but missing from DB schema.
    # We add them as aliases or properties if possible, or just fix the query in credits_admin.py.
    # Looking at credits_admin.py:
    # CreditLedger.plan_code
    # CreditLedger.entry_type == "consumption"
    
    # We'll fix credits_admin.py to join with Store to get plan_code and use event_type.
