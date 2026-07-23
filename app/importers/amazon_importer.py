"""Amazon order-history importer.

Amazon lets you download your purchase history in two ways, and the column
names differ between them:

* The legacy "Order History Report" (Items report) uses columns like
  ``Order Date``, ``Title``, ``Item Total``.
* The newer "Request My Data" export (``Retail.OrderHistory.*.csv``) uses
  ``Order Date``, ``Product Name``, ``Total Owed``.

This importer accepts either. Each line item becomes a spending transaction so
you can see exactly what was bought, not just a lump card charge.
"""
import csv
import io

from app.importers.common import parse_amount, parse_date

_DATE_COLS = ["Order Date", "order date", "Ship Date"]
_ID_COLS = ["Order ID", "order id", "Order Id"]
_TITLE_COLS = ["Title", "Product Name", "product name", "Item Name"]
_AMOUNT_COLS = ["Item Total", "Total Owed", "Item Subtotal", "Purchase Price Per Unit"]
_QTY_COLS = ["Quantity", "quantity"]


def _pick(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and (row[c] or "").strip():
            return row[c].strip()
    return None


def _pick_header(headers: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in headers:
            return c
    return None


def parse_amazon(content: bytes, account_id: int) -> list[dict]:
    """Parse an Amazon order-history CSV into per-item transaction dicts."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []

    date_col = _pick_header(headers, _DATE_COLS)
    amount_col = _pick_header(headers, _AMOUNT_COLS)
    if not date_col or not amount_col:
        return []

    out: list[dict] = []
    for idx, row in enumerate(reader):
        raw_date = (row.get(date_col) or "").strip()
        if not raw_date:
            continue
        try:
            txn_date = parse_date(raw_date)
        except (ValueError, TypeError):
            continue
        try:
            amount = abs(parse_amount(row.get(amount_col)))
        except (ValueError, TypeError):
            continue
        if amount == 0:
            continue

        title = _pick(row, _TITLE_COLS) or "Amazon order"
        order_id = _pick(row, _ID_COLS) or ""
        qty = _pick(row, _QTY_COLS)
        description = f"Amazon: {title}"
        if qty and qty not in ("1", ""):
            description += f" (x{qty})"

        # Amazon spending is negative (money out). Dedup on order id + item index
        # so multiple items in one order stay distinct.
        external = f"amz-{order_id}-{idx}" if order_id else f"amz-row-{idx}-{txn_date.isoformat()}"
        out.append(
            {
                "txn_date": txn_date,
                "amount": -amount,
                "description": description,
                "merchant": "Amazon",
                "external_id": external,
            }
        )
    return out
