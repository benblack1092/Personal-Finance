"""Database engine, session, and base model configuration.

Uses SQLite stored in a local file so the app is entirely self-contained and
no financial data ever leaves the machine.
"""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# The database lives next to the project root by default. Override with the
# FINANCE_DB_PATH environment variable if you want to store it elsewhere.
import os

DB_PATH = os.environ.get("FINANCE_DB_PATH", str(Path(__file__).resolve().parent.parent / "finance.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

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
