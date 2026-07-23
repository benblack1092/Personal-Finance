"""Transaction listing, filtering, and editing."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.categorize import categorize_transaction, load_rules
from app.database import get_db
from app.models import Account, Transaction
from app.schemas import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _to_out(txn: Transaction) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        account_id=txn.account_id,
        txn_date=txn.txn_date,
        amount=txn.amount,
        description=txn.description,
        merchant=txn.merchant,
        category_id=txn.category_id,
        notes=txn.notes,
        pending=txn.pending,
        source=txn.source,
        external_id=txn.external_id,
        category_name=txn.category.name if txn.category else None,
        account_name=txn.account.name if txn.account else None,
    )


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    account_id: int | None = None,
    category_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    search: str | None = None,
    limit: int = Query(500, le=5000),
    offset: int = 0,
):
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category), selectinload(Transaction.account))
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if start_date is not None:
        stmt = stmt.where(Transaction.txn_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Transaction.txn_date <= end_date)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            (Transaction.description.ilike(like)) | (Transaction.merchant.ilike(like))
        )
    stmt = stmt.limit(limit).offset(offset)
    return [_to_out(t) for t in db.scalars(stmt)]


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    if not db.get(Account, payload.account_id):
        raise HTTPException(400, "account_id does not exist")
    txn = Transaction(**payload.model_dump(), source="manual")
    if txn.category_id is None:
        categorize_transaction(txn, load_rules(db))
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return _to_out(txn)


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, payload: TransactionUpdate, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    return _to_out(txn)


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
