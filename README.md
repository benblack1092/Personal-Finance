# 💰 Personal Finance

A private, local-first web app for tracking your spending — what you spent,
which category it falls into, and where the money went. Import statements from
your **bank accounts, credit cards, and Amazon**, and see everything on a
dashboard with category breakdowns, monthly trends, and top merchants.

Everything runs on your own machine and your data is stored in a single local
SQLite file — nothing is ever sent to a third party.

---

## Features

- **Import from anywhere your accounts export to:**
  - **CSV** — any bank or credit-card export. A column-mapping step auto-detects
    the Date / Description / Amount columns (and handles split Debit/Credit
    columns or "purchases as positive" formats).
  - **OFX / QFX** — the richer format most banks offer; imported in one click.
  - **Amazon order history** — turns each purchased *item* into its own line so
    you can see what you actually bought, not just a lump card charge. Works
    with both the "Request My Data" export and the legacy Order History Report.
- **Automatic categorization** — a rules engine tags transactions on import
  (Starbucks → Restaurants, Whole Foods → Groceries, …). Ships with sensible
  defaults; add your own rules and re-apply them anytime.
- **Duplicate-proof** — re-importing the same statement is safe; duplicates are
  detected and skipped.
- **Dashboard** — spending vs. income, spend-by-category doughnut, monthly
  trend bars, and your top merchants, all filterable by account and date range.
- **Editable transactions** — reclassify any transaction's category inline,
  search, filter, add manual entries, and delete.
- **Browser extension** — scan the bank/card/Amazon page you're already viewing
  and import its transactions in one click, no file download needed
  (see [`extension/`](extension/README.md)).

## Why file import instead of auto-login?

Directly automating logins to bank/Amazon sites is fragile (2FA, CAPTCHAs,
frequent site changes) and would mean storing your banking credentials. Every
bank and Amazon already let you **export** your data — this app consumes those
exports, which is reliable, safe, and keeps your credentials out of the picture.

## Getting started

```bash
# 1. Install dependencies (a virtualenv is recommended)
pip install -r requirements.txt

# 2. Run the app
python run.py
# ...or: uvicorn app.main:app --reload

# 3. Open http://127.0.0.1:8000
```

On first launch the app creates `finance.db` and seeds default categories and
categorization rules.

## How to get your statement files

| Source | Where to export |
| --- | --- |
| **Bank / credit card** | Log in → Transactions or Statements → **Download / Export** → choose **CSV** or **OFX/QFX**. |
| **Amazon** | Account → **Request Your Data** → *Your Orders* (or the legacy *Order History Report*) → upload the CSV. |

Then in the app: **Accounts** → add the account, **Import** → pick the type,
choose the account, and drop in the file.

### Or skip the download: use the browser extension

The [`extension/`](extension/README.md) folder contains a Chrome/Edge extension
that scrapes the page you're viewing (bank, credit card, or Amazon **Your
Orders**) and pushes the transactions straight into the app — no export/upload
step. It reads a page only when you click **Scan** and never stores credentials.
Load it unpacked from `chrome://extensions` (Developer mode → Load unpacked →
select `extension/`) while the app is running. See its README for details and
the included test fixtures.

## Project layout

```
app/
  main.py            FastAPI app + static file serving
  database.py        SQLite engine / session
  models.py          ORM models (Account, Transaction, Category, Rule, ...)
  schemas.py         Pydantic request/response models
  categorize.py      Rules engine + default categories
  services.py        Insert-with-dedup + auto-categorize
  importers/         csv / ofx / amazon parsers + shared helpers
  routers/           accounts, categories, transactions, imports, analytics
static/              index.html + styles.css + app.js (vanilla-JS SPA)
extension/           Chrome/Edge MV3 extension (scrape pages -> POST /api/imports/web)
tests/               pytest unit + API tests
```

## Running the tests

```bash
pip install pytest httpx
python -m pytest
```

## Configuration

- `FINANCE_DB_PATH` — override where the SQLite database is stored
  (default: `finance.db` in the project root).

## Roadmap ideas

- Budgets & per-category monthly targets with alerts
- Recurring-charge / subscription detection
- Multi-currency normalization
- CSV/PDF export of reports
- Optional Plaid integration for users who want automated account syncing

## Security & privacy

This is a single-user, local-first app with no authentication — it's meant to
run on your own machine. `finance.db` is git-ignored so your financial data is
never committed. If you deploy it anywhere network-accessible, put it behind
authentication and HTTPS first.

**No external requests.** The app makes zero network calls to third parties.
The server binds to `127.0.0.1` only, the backend never calls out, and the
charting library (Chart.js) is **vendored locally** in `static/vendor/` rather
than loaded from a CDN — so the app runs fully offline and nothing about your
finances (or even a page-load request) ever leaves your device.
