"""Shared test fixtures.

The database path is set via ``FINANCE_DB_PATH`` *before* the app is imported so
the whole suite runs against a throwaway SQLite file. Tables are recreated fresh
for each test that needs the API, keeping tests isolated without reloading
modules (which breaks SQLAlchemy's shared ``Base`` metadata).
"""
import os
import tempfile

import pytest

_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["FINANCE_DB_PATH"] = _TMP_DB.name


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.categorize import seed_defaults
    from app.database import Base, SessionLocal, engine, init_db
    from app.main import app

    # Fresh schema per test.
    Base.metadata.drop_all(bind=engine)
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)

    with TestClient(app) as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_TMP_DB.name)
    except OSError:
        pass
