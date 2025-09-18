"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-09-18 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.String(128), nullable=True),
        sa.Column("event_id", sa.String(128), nullable=False, unique=True),
        sa.Column("topic", sa.String(128)),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_webhook_events_shop_id", "webhook_events", ["shop_id"])

    op.create_table(
        "device_captures",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("device_id", sa.String(128)),
        sa.Column("cart_token", sa.String(128)),
        sa.Column("email", sa.String(256)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    op.create_table(
        "order_risk",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.String),
        sa.Column("order_id", sa.String, unique=True),
        sa.Column("total_price", sa.Float),
        sa.Column("currency", sa.String(8)),
        sa.Column("email", sa.String),
        sa.Column("ip", sa.String),
        sa.Column("country", sa.String(4)),
        sa.Column("score", sa.Float),
        sa.Column("rules_score", sa.Float),
        sa.Column("verdict", sa.String(12)),
        sa.Column("reasons", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_order_risk_shop_id", "order_risk", ["shop_id"])
    op.create_index("ix_order_risk_order_id", "order_risk", ["order_id"], unique=True)

    op.create_table(
        "evidence_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.String),
        sa.Column("key", sa.String),
        sa.Column("value", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_evidence_log_order_id", "evidence_log", ["order_id"])

    op.create_table(
        "risk_identity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("hash", sa.String, nullable=False),
        sa.Column("seen_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("kind", "hash", name="uq_kind_hash"),
    )
    op.create_index("ix_risk_identity_hash", "risk_identity", ["hash"])
    op.create_index("ix_risk_identity_kind_hash", "risk_identity", ["kind", "hash"], unique=True)

def downgrade():
    op.drop_index("ix_risk_identity_kind_hash", table_name="risk_identity")
    op.drop_index("ix_risk_identity_hash", table_name="risk_identity")
    op.drop_table("risk_identity")

    op.drop_index("ix_evidence_log_order_id", table_name="evidence_log")
    op.drop_table("evidence_log")

    op.drop_index("ix_order_risk_order_id", table_name="order_risk")
    op.drop_index("ix_order_risk_shop_id", table_name="order_risk")
    op.drop_table("order_risk")

    op.drop_table("device_captures")

    op.drop_index("ix_webhook_events_shop_id", table_name="webhook_events")
    op.drop_table("webhook_events")
