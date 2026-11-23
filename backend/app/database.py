"""SQLite engine (WAL mode) and session helpers."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import config


class Base(DeclarativeBase):
    pass


def _make_engine(db_path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_size=20,
        max_overflow=20,
        pool_pre_ping=True,
    )

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.close()

    return eng


engine: Engine = _make_engine(config.db_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def reset_engine() -> None:
    """Re-create the engine (used after a database restore and in tests)."""
    global engine
    engine.dispose()
    engine = _make_engine(config.db_path)
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
