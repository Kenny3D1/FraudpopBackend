"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-09-05 00:00:00
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
        "orders",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.String(128), nullable=False),
        sa.Column("shop_order_id", sa.BigInteger, nullable=False),
        sa.Column("name", sa.String(64)),
        sa.Column("email", sa.String(255)),
        sa.Column("total_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(8)),
        sa.Column("source_ip", sa.String(64)),
        sa.Column("raw", JSONB, nullable=False),
        sa.Column("capture_id", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint("shop_id", "shop_order_id", name="uq_order_shop_order"),
    )
    op.create_table(
        "order_risks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.BigInteger, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("score", sa.Integer),                  # 0..100
        sa.Column("verdict", sa.String(16)),            # green|amber|red
        sa.Column("reasons", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metafield_written", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )

def downgrade():
    op.drop_table("risk_vault")
    op.drop_table("order_risks")
    op.drop_table("orders")
