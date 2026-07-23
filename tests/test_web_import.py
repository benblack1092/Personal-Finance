"""Tests for the browser-extension web-import endpoint and shared normalizer."""
import pytest

from app.importers.csv_importer import rows_from_records
from app.schemas import ColumnMapping


def test_rows_from_records_uses_explicit_merchant():
    records = [{"d": "01/15/2024", "desc": "Amazon: USB Cable", "amt": "-9.99", "m": "Amazon"}]
    mapping = ColumnMapping(date="d", description="desc", amount="amt", merchant="m")
    rows = rows_from_records(records, mapping, account_id=1)
    assert len(rows) == 1
    assert rows[0]["merchant"] == "Amazon"
    assert rows[0]["amount"] == -9.99


def test_rows_from_records_falls_back_to_cleaned_merchant():
    records = [{"d": "01/15/2024", "desc": "POS PURCHASE STARBUCKS #123 CA", "amt": "-4.50"}]
    mapping = ColumnMapping(date="d", description="desc", amount="amt")
    rows = rows_from_records(records, mapping, account_id=1)
    assert "Starbucks" in rows[0]["merchant"]


def test_suggest_mapping_endpoint(client):
    r = client.post("/api/imports/suggest-mapping", json={"headers": ["Post Date", "Payee", "Amount"]})
    assert r.status_code == 200
    m = r.json()
    assert m["date"] == "Post Date"
    assert m["amount"] == "Amount"


def test_web_import_generic_table(client):
    acct = client.post("/api/accounts", json={"name": "Card", "type": "credit_card"}).json()
    payload = {
        "account_id": acct["id"],
        "source": "web",
        "mapping": {"date": "Date", "description": "Description", "amount": "Amount"},
        "records": [
            {"Date": "07/01/2026", "Description": "STARBUCKS #1", "Amount": "-5.75"},
            {"Date": "07/02/2026", "Description": "WHOLE FOODS", "Amount": "-64.20"},
        ],
    }
    r = client.post("/api/imports/web", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported_count"] == 2
    assert body["categorized_count"] == 2  # default rules catch both

    # Re-posting the identical payload skips duplicates.
    r2 = client.post("/api/imports/web", json=payload)
    assert r2.json()["skipped_count"] == 2
    assert r2.json()["imported_count"] == 0


def test_web_import_amazon_shape(client):
    acct = client.post("/api/accounts", json={"name": "Amazon", "type": "amazon"}).json()
    payload = {
        "account_id": acct["id"],
        "source": "amazon",
        "mapping": {"date": "date", "description": "description", "amount": "amount", "merchant": "merchant"},
        "records": [
            {"date": "July 3, 2026", "description": "Amazon: USB-C Cable", "amount": "-12.99", "merchant": "Amazon"},
        ],
    }
    r = client.post("/api/imports/web", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["imported_count"] == 1
    txns = client.get(f"/api/transactions?account_id={acct['id']}").json()
    assert txns[0]["merchant"] == "Amazon"
    assert txns[0]["category_name"] == "Shopping"


def test_web_import_rejects_empty(client):
    acct = client.post("/api/accounts", json={"name": "Card", "type": "credit_card"}).json()
    r = client.post("/api/imports/web", json={
        "account_id": acct["id"], "source": "web",
        "mapping": {"date": "Date", "description": "Description", "amount": "Amount"},
        "records": [],
    })
    assert r.status_code == 400
