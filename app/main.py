"""FastAPI application entry point.

Serves the JSON API under ``/api`` and the single-page dashboard from
``/static``. Run with::

    uvicorn app.main:app --reload

or simply ``python run.py``.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import SessionLocal, init_db
from app.categorize import seed_defaults
from app.paths import resource_path
from app.routers import accounts, analytics, categories, imports, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables and seed default categories/rules on startup."""
    init_db()
    with SessionLocal() as db:
        seed_defaults(db)
    yield


app = FastAPI(title="Personal Finance", version="0.1.0", lifespan=lifespan)

# The browser extension runs on a chrome-extension:// origin and the dashboard
# on localhost; both need CORS to reach the API. Scoped to those origins only —
# the app still binds to 127.0.0.1 (see run.py), so it isn't network-exposed.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://.*$|^http://(127\.0\.0\.1|localhost):8000$",
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(imports.router)
app.include_router(analytics.router)

STATIC_DIR = resource_path("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
