"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-09-05 00:00:00

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'webhook_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('topic', sa.String(length=128), nullable=False),
        sa.Column('event_id', sa.String(length=128), nullable=False, unique=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )
    op.create_table(
        'rv_observations',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('shop_id', sa.String(length=64), nullable=False),
        sa.Column('id_type', sa.String(length=16), nullable=False),
        sa.Column('id_hash', sa.LargeBinary(), nullable=False),
        sa.Column('salt', sa.LargeBinary(), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('seen_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('outcomes', sa.JSON(), nullable=False, server_default=sa.text("'{}'::json"))
    )
    op.create_unique_constraint('uq_obs_idtype_hash', 'rv_observations', ['id_type','id_hash'])

    op.create_table(
        'device_captures',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('shop_id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=128), nullable=False),
        sa.Column('device_id', sa.String(length=128)),
        sa.Column('cart_token', sa.String(length=128)),
        sa.Column('email', sa.String(length=256)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'))
    )

def downgrade():
    op.drop_table('device_captures')
    op.drop_constraint('uq_obs_idtype_hash', 'rv_observations', type_='unique')
    op.drop_table('rv_observations')
    op.drop_table('webhook_events')
