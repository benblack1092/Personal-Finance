"""File-import endpoints for CSV, OFX/QFX, and Amazon order reports.

Flow for CSV (which needs a column mapping):
1. ``POST /api/imports/preview`` with the file -> headers + suggested mapping.
2. ``POST /api/imports/csv`` with the file, account_id, and confirmed mapping.

OFX/QFX and Amazon files are self-describing so they import in one step.
"""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.importers.amazon_importer import parse_amazon
from app.importers.csv_importer import parse_csv, preview_csv
from app.importers.ofx_importer import parse_ofx
from app.models import Account
from app.schemas import ColumnMapping, CsvPreview, ImportResult
from app.services import insert_transactions

router = APIRouter(prefix="/api/imports", tags=["imports"])


def _require_account(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(400, "account_id does not exist")
    return account


def _result(batch) -> ImportResult:
    return ImportResult(
        batch_id=batch.id,
        source=batch.source,
        row_count=batch.row_count,
        imported_count=batch.imported_count,
        skipped_count=batch.skipped_count,
        categorized_count=getattr(batch, "_categorized_count", 0),
    )


@router.post("/preview", response_model=CsvPreview)
async def preview(file: UploadFile = File(...)):
    """Inspect a CSV and suggest how its columns map to transaction fields."""
    content = await file.read()
    headers, rows, mapping = preview_csv(content)
    if not headers:
        raise HTTPException(400, "Could not read any columns from the file")
    return CsvPreview(headers=headers, sample_rows=rows, suggested_mapping=mapping)


@router.post("/csv", response_model=ImportResult)
async def import_csv(
    account_id: int = Form(...),
    mapping: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import a CSV using a confirmed column mapping (JSON-encoded)."""
    _require_account(db, account_id)
    try:
        mapping_obj = ColumnMapping(**json.loads(mapping))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid mapping: {exc}") from exc

    content = await file.read()
    rows = parse_csv(content, mapping_obj, account_id)
    if not rows:
        raise HTTPException(400, "No valid transactions found with that mapping")
    batch = insert_transactions(db, account_id, rows, "csv", file.filename)
    return _result(batch)


@router.post("/ofx", response_model=ImportResult)
async def import_ofx(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import an OFX or QFX file (self-describing, no mapping needed)."""
    _require_account(db, account_id)
    content = await file.read()
    rows = parse_ofx(content, account_id)
    if not rows:
        raise HTTPException(400, "No transactions found — is this a valid OFX/QFX file?")
    batch = insert_transactions(db, account_id, rows, "ofx", file.filename)
    return _result(batch)


@router.post("/amazon", response_model=ImportResult)
async def import_amazon(
    account_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import an Amazon order-history CSV (one transaction per item)."""
    _require_account(db, account_id)
    content = await file.read()
    rows = parse_amazon(content, account_id)
    if not rows:
        raise HTTPException(
            400,
            "No orders found. Export via Amazon > Account > Request My Data > "
            "Your Orders, or an Order History Report.",
        )
    batch = insert_transactions(db, account_id, rows, "amazon", file.filename)
    return _result(batch)
