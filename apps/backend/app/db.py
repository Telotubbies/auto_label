"""SQLAlchemy engine/session. SQLite for dev, Postgres in prod (DATABASE_URL)."""
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from .config import DATABASE_URL

_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30} if _sqlite else {},
    pool_pre_ping=True,
)

if _sqlite:
    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("pragma journal_mode=wal")
        cur.execute("pragma foreign_keys=on")
        cur.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@contextmanager
def session_scope() -> Session:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
