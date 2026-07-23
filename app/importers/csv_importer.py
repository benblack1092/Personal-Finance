"""Generic, mapping-driven CSV importer.

Works with any bank / credit-card CSV export. The frontend first asks for a
:class:`~app.schemas.ColumnMapping` (auto-suggested from the headers), then the
rows are parsed into transaction dicts.
"""
import csv
import hashlib
import io

from app.importers.common import clean_merchant, parse_amount, parse_date
from app.schemas import ColumnMapping

# Header keywords used to auto-suggest a mapping.
_DATE_HINTS = ["date", "posted", "transaction date", "post date"]
_AMOUNT_HINTS = ["amount", "value"]
_DEBIT_HINTS = ["debit", "withdrawal", "charges", "money out"]
_CREDIT_HINTS = ["credit", "deposit", "payments", "money in"]
_DESC_HINTS = ["description", "name", "memo", "payee", "details", "merchant", "narrative"]


def _find(headers: list[str], hints: list[str]) -> str | None:
    lowered = {h.lower().strip(): h for h in headers}
    # Exact-ish match first.
    for hint in hints:
        for low, original in lowered.items():
            if low == hint:
                return original
    # Then substring.
    for hint in hints:
        for low, original in lowered.items():
            if hint in low:
                return original
    return None


def suggest_mapping(headers: list[str]) -> ColumnMapping | None:
    """Guess how the columns map to transaction fields."""
    date_col = _find(headers, _DATE_HINTS)
    desc_col = _find(headers, _DESC_HINTS)
    if not date_col or not desc_col:
        return None
    amount_col = _find(headers, _AMOUNT_HINTS)
    debit_col = _find(headers, _DEBIT_HINTS)
    credit_col = _find(headers, _CREDIT_HINTS)
    return ColumnMapping(
        date=date_col,
        amount=amount_col if not (debit_col or credit_col) else None,
        debit=debit_col,
        credit=credit_col,
        description=desc_col,
    )


def preview_csv(content: bytes, sample_size: int = 5):
    """Return headers + a few sample rows and a suggested mapping."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = []
    for i, row in enumerate(reader):
        if i >= sample_size:
            break
        rows.append(row)
    return headers, rows, suggest_mapping(headers)


def _external_id(account_id: int, txn_date, amount: float, description: str) -> str:
    raw = f"{account_id}|{txn_date.isoformat()}|{amount:.2f}|{description.strip().lower()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def rows_from_records(records: list[dict], mapping: ColumnMapping, account_id: int) -> list[dict]:
    """Normalize a list of ``{header: value}`` records into transaction dicts.

    Shared by the CSV importer and the browser-extension web importer so both
    paths get identical date/amount parsing, merchant cleaning, and dedup ids.
    """
    out: list[dict] = []
    for row in records:
        raw_date = (row.get(mapping.date) or "").strip()
        description = (row.get(mapping.description) or "").strip()
        if not raw_date and not description:
            continue  # skip blank lines
        try:
            txn_date = parse_date(raw_date, mapping.date_format)
        except (ValueError, TypeError):
            continue  # skip rows without a valid date (e.g. trailing totals)

        amount = _extract_amount(row, mapping)
        if amount is None:
            continue

        # Prefer an explicit merchant column when the mapping names one
        # (e.g. Amazon sends "Amazon", some bank tables have a payee column);
        # otherwise derive a clean merchant from the description.
        merchant = ""
        if mapping.merchant:
            merchant = (row.get(mapping.merchant) or "").strip()
        if not merchant:
            merchant = clean_merchant(description)

        out.append(
            {
                "txn_date": txn_date,
                "amount": amount,
                "description": description,
                "merchant": merchant,
                "external_id": _external_id(account_id, txn_date, amount, description),
            }
        )
    return out


def parse_csv(content: bytes, mapping: ColumnMapping, account_id: int) -> list[dict]:
    """Parse CSV bytes into a list of transaction dicts ready for insertion."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return rows_from_records(list(reader), mapping, account_id)


def _extract_amount(row: dict, mapping: ColumnMapping) -> float | None:
    """Resolve a signed amount from either a single column or debit/credit pair."""
    if mapping.debit or mapping.credit:
        debit = (row.get(mapping.debit) or "").strip() if mapping.debit else ""
        credit = (row.get(mapping.credit) or "").strip() if mapping.credit else ""
        try:
            if debit:
                return -abs(parse_amount(debit))
            if credit:
                return abs(parse_amount(credit))
        except ValueError:
            return None
        return None

    if not mapping.amount:
        return None
    raw = (row.get(mapping.amount) or "").strip()
    if not raw:
        return None
    try:
        amount = parse_amount(raw)
    except ValueError:
        return None
    return -amount if mapping.flip_sign else amount
