"""Database engine, session, and base model configuration.

Uses SQLite stored in a local file so the app is entirely self-contained and
no financial data ever leaves the machine.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.paths import default_db_path

# Where the SQLite database lives: FINANCE_DB_PATH env var if set, a per-user
# data directory when packaged as an executable, else the project root.
DB_PATH = default_db_path()
# as_posix() keeps the sqlite URL valid on Windows (forward slashes).
DATABASE_URL = f"sqlite:///{Path(DB_PATH).as_posix()}"

# check_same_thread=False is required because FastAPI may access the session
# from different threads within a single request lifecycle.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db():
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call repeatedly."""
    # Import models so they are registered on Base.metadata before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
