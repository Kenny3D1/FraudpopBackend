from typing import Generator, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

def _normalize_db_url(url: str) -> str:
    # Use psycopg v3 driver with SQLAlchemy
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url

_DB_URL = _normalize_db_url(settings.DATABASE_URL)

_engine = None  # lazy-init to avoid C-extension import at module import time
_SessionLocal: Optional[sessionmaker] = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _DB_URL,
            pool_pre_ping=True,
            future=True,  # explicit 2.0-style
        )
    return _engine

def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            future=True,
        )
    return _SessionLocal

class Base(DeclarativeBase):
    pass

def get_db() -> Generator:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
