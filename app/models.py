from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, BigInteger, Integer, DateTime, JSON, LargeBinary, UniqueConstraint, func
from .database import Base

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    processed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Observation(Base):
    __tablename__ = "rv_observations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(64), nullable=False)
    id_type: Mapped[str] = mapped_column(String(16), nullable=False)  # email/device/ip/phone
    id_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    first_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    outcomes: Mapped[dict] = mapped_column(JSON, nullable=False, default={})

    __table_args__ = (UniqueConstraint("id_type", "id_hash", name="uq_obs_idtype_hash"),)

class DeviceCapture(Base):
    __tablename__ = "device_captures"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    device_id: Mapped[str] = mapped_column(String(128), nullable=True)
    cart_token: Mapped[str] = mapped_column(String(128), nullable=True)
    email: Mapped[str] = mapped_column(String(256), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderRisk(Base):
    __tablename__ = "order_risk"
    id = Column(Integer, primary_key=True)
    shop_id = Column(String, index=True)
    order_id = Column(String, index=True, unique=True)
    total_price = Column(Float)
    currency = Column(String(8))
    email = Column(String)
    ip = Column(String)
    country = Column(String(4))
    score = Column(Float)        # final combined
    rules_score = Column(Float)  # rules-only
    verdict = Column(String(12)) # green|yellow|red
    reasons = Column(JSON)       # list of strings
    created_at = Column(DateTime, server_default=func.now())

class EvidenceLog(Base):
    __tablename__ = "evidence_log"
    id = Column(Integer, primary_key=True)
    order_id = Column(String, index=True)
    key = Column(String)
    value = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
