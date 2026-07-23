"""End-to-end API tests. The ``client`` fixture lives in conftest.py."""
import pytest


def test_seed_creates_categories(client):
    cats = client.get("/api/categories").json()
    names = {c["name"] for c in cats}
    assert "Groceries" in names and "Restaurants" in names


def test_account_and_import_flow(client):
    acct = client.post("/api/accounts", json={"name": "Test Card", "type": "credit_card"}).json()

    csv = "Date,Description,Amount\n01/15/2024,STARBUCKS STORE,-4.50\n01/16/2024,WHOLE FOODS,-30\n"
    mapping = '{"date":"Date","description":"Description","amount":"Amount"}'
    r = client.post(
        "/api/imports/csv",
        data={"account_id": acct["id"], "mapping": mapping},
        files={"file": ("stmt.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["imported_count"] == 2
    # Both rows should auto-categorize via default rules.
    assert result["categorized_count"] == 2

    # Re-importing the same file skips duplicates.
    r2 = client.post(
        "/api/imports/csv",
        data={"account_id": acct["id"], "mapping": mapping},
        files={"file": ("stmt.csv", csv, "text/csv")},
    )
    assert r2.json()["skipped_count"] == 2
    assert r2.json()["imported_count"] == 0

    # Summary reflects the spending.
    summary = client.get("/api/analytics/summary").json()
    assert summary["total_spending"] == pytest.approx(34.5)
    assert summary["transaction_count"] == 2
    assert any(c["category_name"] == "Groceries" for c in summary["by_category"])


def test_amazon_import(client):
    acct = client.post("/api/accounts", json={"name": "Amazon", "type": "amazon"}).json()
    csv = "Order Date,Order ID,Product Name,Total Owed\n2024-03-01,111-1,Book,15.00\n"
    r = client.post(
        "/api/imports/amazon",
        data={"account_id": acct["id"]},
        files={"file": ("orders.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported_count"] == 1
    txns = client.get("/api/transactions").json()
    assert txns[0]["merchant"] == "Amazon"
    assert txns[0]["category_name"] == "Shopping"  # amazon default rule
