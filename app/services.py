"""Business logic shared across routers (transaction insertion, dedup)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.categorize import categorize_transaction, load_rules
from app.models import ImportBatch, Transaction


def insert_transactions(
    db: Session,
    account_id: int,
    rows: list[dict],
    source: str,
    filename: str | None,
) -> ImportBatch:
    """Insert parsed rows, skipping duplicates and auto-categorizing.

    Deduplication is done against ``(account_id, external_id)`` for rows that
    carry an external id. Rows without one are always inserted.
    """
    batch = ImportBatch(source=source, filename=filename, account_id=account_id, row_count=len(rows))
    db.add(batch)
    db.flush()

    rules = load_rules(db)

    # Pre-load existing external ids for this account to avoid a query per row.
    existing_ids = set(
        db.scalars(
            select(Transaction.external_id).where(
                Transaction.account_id == account_id,
                Transaction.external_id.is_not(None),
            )
        )
    )

    imported = 0
    skipped = 0
    categorized = 0
    seen_this_batch: set[str] = set()

    for row in rows:
        ext = row.get("external_id")
        if ext and (ext in existing_ids or ext in seen_this_batch):
            skipped += 1
            continue
        if ext:
            seen_this_batch.add(ext)

        txn = Transaction(
            account_id=account_id,
            txn_date=row["txn_date"],
            amount=row["amount"],
            description=row.get("description", ""),
            merchant=row.get("merchant"),
            external_id=ext,
            source=source,
            import_batch_id=batch.id,
        )
        if categorize_transaction(txn, rules):
            categorized += 1
        db.add(txn)
        imported += 1

    batch.imported_count = imported
    batch.skipped_count = skipped
    db.commit()
    db.refresh(batch)
    # Stash categorized count on the object (not persisted) for the response.
    batch._categorized_count = categorized  # type: ignore[attr-defined]
    return batch
