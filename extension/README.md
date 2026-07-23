# Personal Finance Importer — Browser Extension

A Chrome/Edge (Manifest V3) extension that scrapes the **bank, credit-card, or
Amazon page you're already viewing** and imports the transactions into your local
Personal Finance app — no file downloads, no stored credentials.

It reads the page **only when you click “Scan”** (on-demand injection via
`activeTab`), so it never watches your banking sites in the background.

## Install (load unpacked)

1. Start the app: from the project root, `python run.py` (it must be running on
   `http://127.0.0.1:8000`).
2. Open `chrome://extensions` (or `edge://extensions`).
3. Enable **Developer mode** (top-right).
4. Click **Load unpacked** and select this `extension/` folder.
5. Pin the 💰 icon to your toolbar.

## Usage

1. Log in to your bank / credit card, or open Amazon **Your Orders**, and make
   sure the transactions/orders are visible on screen.
2. Click the 💰 extension icon.
3. Choose the **account** to import into (these come from the app; add accounts
   in the app's Accounts tab first).
4. Click **Scan this page**.
   - **Bank / credit card:** the extension finds the transactions table (pick the
     right one if there are several), auto-suggests a column mapping, and shows a
     preview. Confirm Date / Description / Amount (or Debit + Credit) and click
     **Import into app**.
   - **Amazon:** each order *item* is listed with its price. Click
     **Import N items** — they're imported as spending with merchant “Amazon”.
5. The popup reports how many were imported, skipped as duplicates, and
   auto-categorized. Re-scanning the same page is safe — duplicates are skipped.

## Testing without real bank data

Two fixture pages are included:

- `test-fixtures/bank-table.html` — open it in Chrome (via `file://` or any local
  server) and run **Scan** to exercise the full generic table → mapping → import
  flow.
- `test-fixtures/amazon-like.html` — documents the Amazon order markup the scraper
  targets. The Amazon path only activates on a hostname containing `amazon.`, so
  to test the real Amazon scraper you need to be on amazon.com itself; this
  fixture is for reference.

## How it maps to the app

The extension POSTs scraped rows as JSON to `POST /api/imports/web`, which runs
them through the **same** normalization → deduplication → auto-categorization
pipeline as CSV import. So merchant cleaning, the default category rules, and the
duplicate guard all behave identically to file imports.

## Limitations & notes

- **Generic table scan** handles `<table>` elements and ARIA grids
  (`role=table/grid`), covering most bank/card transaction pages. If a site
  renders transactions in some other custom structure, nothing is detected —
  fall back to the app's CSV/OFX file import.
- **Amazon markup is brittle** and varies by region and page version, so the
  Amazon scraper is best-effort and may miss items after an Amazon redesign.
  Always review the preview before importing.
- Only paginated/visible rows are scraped — scroll or expand “show more” so the
  transactions you want are actually in the page before scanning.
- The extension talks only to `http://127.0.0.1:8000`; the app must be running.
