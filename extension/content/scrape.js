/*
 * Injected on demand (never runs passively) when the user clicks "Scan".
 * Reads the already-rendered, logged-in page and returns structured data.
 *
 * Returns: { hostname, tables: [{headers, rows}], amazonOrders: [{date, title, price, qty}] }
 *
 * This runs as the last expression of an executeScript injection, so the final
 * value is what chrome.scripting hands back to the popup.
 */
(function scrapePage() {
  "use strict";

  const text = (node) => (node ? node.textContent.replace(/\s+/g, " ").trim() : "");

  /* ---------------------------------------------------------------- *
   * Generic table extraction
   * Handles real <table> elements AND ARIA grids (role=table/row/cell),
   * which many modern bank UIs use instead of <table>.
   * ---------------------------------------------------------------- */
  function extractHtmlTables() {
    const out = [];
    for (const table of document.querySelectorAll("table")) {
      const rows = Array.from(table.rows);
      if (rows.length < 2) continue;

      // Header row: prefer a <thead>, else the first row.
      let headerCells, bodyRows;
      const thead = table.querySelector("thead");
      if (thead && thead.rows.length) {
        headerCells = Array.from(thead.rows[thead.rows.length - 1].cells);
        bodyRows = rows.filter((r) => !thead.contains(r));
      } else {
        headerCells = Array.from(rows[0].cells);
        bodyRows = rows.slice(1);
      }
      const headers = headerCells.map((c, i) => text(c) || `Column ${i + 1}`);
      if (headers.length < 2) continue;

      const data = [];
      for (const r of bodyRows) {
        const cells = Array.from(r.cells).map(text);
        if (cells.every((c) => c === "")) continue;
        data.push(cells);
      }
      if (data.length) out.push({ headers, rows: data });
    }
    return out;
  }

  function extractAriaGrids() {
    const out = [];
    const grids = document.querySelectorAll('[role="table"], [role="grid"], [role="treegrid"]');
    for (const grid of grids) {
      const rowEls = grid.querySelectorAll('[role="row"]');
      if (rowEls.length < 2) continue;
      const rowsCells = Array.from(rowEls).map((row) =>
        Array.from(row.querySelectorAll('[role="columnheader"], [role="cell"], [role="gridcell"], [role="rowheader"]')).map(text)
      );
      const widths = rowsCells.map((c) => c.length).filter((n) => n > 0);
      if (!widths.length) continue;
      const width = Math.max(...widths);
      if (width < 2) continue;

      // First row with column headers becomes the header; else synthesize.
      let headers = rowsCells.find((_, i) =>
        rowEls[i].querySelector('[role="columnheader"]')
      );
      let start = 0;
      if (headers && headers.length) {
        start = rowsCells.indexOf(headers) + 1;
      } else {
        headers = Array.from({ length: width }, (_, i) => `Column ${i + 1}`);
      }
      const data = rowsCells.slice(start).filter((c) => c.length && c.some((v) => v !== ""));
      if (data.length) out.push({ headers, rows: data });
    }
    return out;
  }

  function extractTables() {
    // De-duplicate by a cheap signature so an ARIA grid that also uses <table>
    // isn't listed twice.
    const all = [...extractHtmlTables(), ...extractAriaGrids()];
    const seen = new Set();
    const unique = [];
    for (const t of all) {
      const sig = t.headers.join("|") + "#" + t.rows.length;
      if (seen.has(sig)) continue;
      seen.add(sig);
      unique.push(t);
    }
    return unique;
  }

  /* ---------------------------------------------------------------- *
   * Amazon order extraction (best-effort; markup varies by region/page).
   * Falls back to the generic table scan when nothing is found.
   * ---------------------------------------------------------------- */
  function extractAmazonOrders() {
    if (!/amazon\./i.test(location.hostname)) return [];
    const orders = [];

    // Order containers across the various order-history layouts.
    const cards = document.querySelectorAll(
      ".order, .order-card, .a-box-group.order, [class*='order-card'], .js-order-card"
    );
    for (const card of cards) {
      // Order date: look for the "Order placed" label's sibling value.
      let dateStr = "";
      const infoCells = card.querySelectorAll(".a-column, .a-row, span, div");
      for (const cell of infoCells) {
        const label = text(cell).toLowerCase();
        if (label === "order placed" || label === "ordered on") {
          const val = cell.nextElementSibling || cell.parentElement;
          dateStr = text(val).replace(/order placed|ordered on/i, "").trim();
          if (dateStr) break;
        }
      }
      // Fallback: any date-looking string in the card header.
      if (!dateStr) {
        const m = text(card).match(
          /\b(?:\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},\s*\d{4}|\d{4}-\d{2}-\d{2})\b/
        );
        if (m) dateStr = m[0];
      }

      // Each item: product title link + its price.
      const items = card.querySelectorAll(
        ".yohtmlc-item, .a-fixed-left-grid, .item-box, [class*='item-view']"
      );
      const itemEls = items.length ? items : [card];
      for (const item of itemEls) {
        const titleEl = item.querySelector(
          ".yohtmlc-product-title, a.a-link-normal[href*='/gp/product'], a.a-link-normal[href*='/dp/'], .a-link-normal .a-text-bold"
        );
        const title = text(titleEl);
        if (!title || title.length < 3) continue;
        const priceEl = item.querySelector(".a-color-price, .a-price .a-offscreen, .yohtmlc-item-price");
        const price = text(priceEl);
        if (!price) continue;
        orders.push({ date: dateStr, title, price, qty: "1" });
      }
    }
    return orders;
  }

  return {
    hostname: location.hostname,
    tables: extractTables(),
    amazonOrders: extractAmazonOrders(),
  };
})();
