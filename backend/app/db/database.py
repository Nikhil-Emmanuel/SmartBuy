"""Database engine, session factory and FastAPI dependency.

One DATABASE_URL drives everything: SQLite locally, PostgreSQL (Neon) in prod.
No dialect-specific SQL anywhere in the codebase -- see docs/DATA_MODEL.md.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class IdMixin:
    """UUID4 string primary key.

    Deliberately not autoincrement: seed data and runtime-generated rows must
    never collide, and ids need to be stable across a database rebuild.
    """

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_connect_args: dict = {}
if settings.is_sqlite:
    # FastAPI may touch a session from a different thread than the one that
    # created it. Safe here because each request gets its own Session.
    _connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        """SQLite ignores foreign keys unless asked, and WAL avoids the
        'database is locked' errors that show up the moment two developers
        hit the API at once."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency. Commits on success, rolls back on exception."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. No Alembic -- 48 hours, and the schema is frozen."""
    from app import models  # noqa: F401  (registers every model on Base.metadata)

    Base.metadata.create_all(bind=engine)
