from __future__ import annotations
from logging.config import fileConfig
from pathlib import Path
import os, sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Make 'app' importable ----------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]  # repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import app metadata / models for autogenerate
from app.database import Base
from app import models  # noqa: F401

# --- Alembic config -----------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# --- URL normalization: psycopg v3 driver ------------------------------------
def _normalize_db_url(url: str) -> str:
    if not url:
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url

# Prefer app settings if present; fallback to env
try:
    from app.config import settings
    raw_url = getattr(settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL", "")
except Exception:
    raw_url = os.getenv("DATABASE_URL", "")

normalized_url = _normalize_db_url(raw_url)

# Force Alembic to use normalized URL regardless of alembic.ini
if normalized_url:
    config.set_main_option("sqlalchemy.url", normalized_url)

# --- Migration runners --------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
