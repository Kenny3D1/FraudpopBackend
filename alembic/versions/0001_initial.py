"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-09-18 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- webhook_events ---
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.String(128), nullable=True, index=True),
        sa.Column("event_id", sa.String(128), nullable=False, unique=True),
        sa.Column("topic", sa.String(128)),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # --- device_captures ---
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

    # --- order_risk ---
    op.create_table(
        "order_risk",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.String, index=True),
        sa.Column("order_id", sa.String, unique=True, index=True),
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

    # --- evidence_log ---
    op.create_table(
        "evidence_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.String, index=True),
        sa.Column("key", sa.String),
        sa.Column("value", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

    # --- risk_identity ---
    op.create_table(
        "risk_identity",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String, nullable=False),
        sa.Column("hash", sa.String, nullable=False, index=True),
        sa.Column("seen_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("kind", "hash", name="uq_kind_hash"),
    )

def downgrade():
    op.drop_table("risk_identity")
    op.drop_table("evidence_log")
    op.drop_table("order_risk")
    op.drop_table("device_captures")
    op.drop_table("webhook_events")
