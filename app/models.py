from __future__ import annotations
from typing import Optional, List, Any
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, BigInteger, Integer, DateTime, JSON, UniqueConstraint, func, Float, Boolean, Index
)
from .database import Base

# ----------------------------
# Webhook events (used by Celery)
# ----------------------------
class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)  # <- added
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    topic: Mapped[Optional[str]] = mapped_column(String(128))
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")  # <- added
    processed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ----------------------------
# Device fingerprint captures
# ----------------------------
class DeviceCapture(Base):
    __tablename__ = "device_captures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(128))
    cart_token: Mapped[Optional[str]] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(256))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

# ----------------------------
# Order risk results
# ----------------------------
class OrderRisk(Base):
    __tablename__ = "order_risk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[Optional[str]] = mapped_column(String, index=True)
    order_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    total_price: Mapped[Optional[float]] = mapped_column(Float)
    currency: Mapped[Optional[str]] = mapped_column(String(8))
    email: Mapped[Optional[str]] = mapped_column(String)
    ip: Mapped[Optional[str]] = mapped_column(String)
    country: Mapped[Optional[str]] = mapped_column(String(4))
    score: Mapped[Optional[float]] = mapped_column(Float)        # final combined
    rules_score: Mapped[Optional[float]] = mapped_column(Float)  # rules-only
    verdict: Mapped[Optional[str]] = mapped_column(String(12))   # green|yellow|red
    reasons: Mapped[Optional[List[str]]] = mapped_column(JSON)   # list of strings
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

# ----------------------------
# Evidence log (debug/audit)
# ----------------------------
class EvidenceLog(Base):
    __tablename__ = "evidence_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)
    value: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

# ----------------------------
# Velocity identity counters
# ----------------------------
class RiskIdentity(Base):
    __tablename__ = "risk_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)          # email|ip|device
    hash: Mapped[str] = mapped_column(String, nullable=False, index=True)  # sha256 of pepper+value
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_seen: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("kind", "hash", name="uq_kind_hash"),
    )

Index("ix_risk_identity_kind_hash", RiskIdentity.kind, RiskIdentity.hash, unique=True)
