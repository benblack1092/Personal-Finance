"use strict";

const API = "http://127.0.0.1:8000";

/* ------------------------------------------------------------------ *
 * DOM helpers
 * ------------------------------------------------------------------ */
const $ = (sel) => document.querySelector(sel);
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (v != null) n.setAttribute(k, v);
  }
  for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(c));
  return n;
};
function status(msg, kind = "") {
  const s = $("#status");
  s.textContent = msg;
  s.className = `status ${kind}`;
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

/* ------------------------------------------------------------------ *
 * Boot: check connection + load accounts
 * ------------------------------------------------------------------ */
let ACCOUNTS = [];

async function boot() {
  try {
    ACCOUNTS = await api("/api/accounts");
    $("#conn").classList.add("ok");
  } catch (e) {
    $("#conn").classList.add("bad");
    status("Can't reach the app. Start it with `python run.py`, then reopen.", "error");
    $("#scan").disabled = true;
    return;
  }
  const sel = $("#account");
  sel.innerHTML = "";
  if (!ACCOUNTS.length) {
    status("No accounts yet — add one in the app (Accounts tab) first.", "error");
    $("#scan").disabled = true;
    return;
  }
  ACCOUNTS.forEach((a) => sel.append(el("option", { value: a.id }, a.name)));
}

/* ------------------------------------------------------------------ *
 * Scan the active tab
 * ------------------------------------------------------------------ */
$("#scan").addEventListener("click", async () => {
  status("Scanning page…");
  $("#workarea").innerHTML = "";
  let result;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const injections = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content/scrape.js"],
    });
    result = injections[0]?.result;
  } catch (e) {
    status("Couldn't scan this page: " + e.message, "error");
    return;
  }
  if (!result) { status("Nothing readable found on this page.", "error"); return; }

  if (result.amazonOrders && result.amazonOrders.length) {
    status(`Found ${result.amazonOrders.length} Amazon items.`, "success");
    renderAmazon(result.amazonOrders);
  } else if (result.tables && result.tables.length) {
    status(`Found ${result.tables.length} table(s) on the page.`, "success");
    renderTablePicker(result.tables);
  } else {
    status("No transaction tables detected. Make sure the transactions are visible on the page.", "error");
  }
});

/* ------------------------------------------------------------------ *
 * Generic table path: pick table -> map columns -> send
 * ------------------------------------------------------------------ */
function renderTablePicker(tables) {
  const area = $("#workarea");
  area.innerHTML = "";

  const card = el("div", { class: "card" });
  if (tables.length > 1) {
    const sel = el("select", { onchange: () => showMapping(tables[Number(sel.value)]) });
    tables.forEach((t, i) =>
      sel.append(el("option", { value: i }, `Table ${i + 1}: ${t.headers.slice(0, 3).join(", ")}… (${t.rows.length} rows)`))
    );
    card.append(el("label", {}, "Which table holds your transactions?"), sel);
  }
  const mapHost = el("div", { id: "maphost", class: "mt" });
  card.append(mapHost);
  area.append(card);
  showMapping(tables[0]);

  async function showMapping(table) {
    const host = $("#maphost");
    host.innerHTML = "";

    // Ask the backend to suggest a mapping from the headers.
    let sug = {};
    try {
      sug = (await api("/api/imports/suggest-mapping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ headers: table.headers }),
      })) || {};
    } catch (_) { /* suggestion is best-effort */ }

    const opt = (selected) => {
      const s = el("select");
      s.append(el("option", { value: "" }, "—"));
      table.headers.forEach((h) => {
        const o = el("option", { value: h }, h);
        if (h === selected) o.selected = true;
        s.append(o);
      });
      return s;
    };
    const dateSel = opt(sug.date);
    const descSel = opt(sug.description);
    const amountSel = opt(sug.amount);
    const debitSel = opt(sug.debit);
    const creditSel = opt(sug.credit);
    const merchantSel = opt(sug.merchant);
    const flip = el("input", { type: "checkbox" });

    host.append(
      el("div", { class: "map-grid" },
        el("label", {}, "Date"), dateSel,
        el("label", {}, "Description"), descSel,
        el("label", {}, "Amount"), amountSel,
        el("label", {}, "Debit"), debitSel,
        el("label", {}, "Credit"), creditSel,
        el("label", {}, "Merchant"), merchantSel,
        el("label", {}, "Flip sign"), flip
      ),
      el("p", { class: "muted mt" }, "Use a single Amount column OR separate Debit/Credit. Tick “Flip sign” if purchases show as positive."),
      previewTable(table),
      el("button", { class: "btn mt", onclick: send }, "Import into app")
    );

    async function send() {
      if (!dateSel.value || !descSel.value) { status("Map Date and Description first.", "error"); return; }
      if (!amountSel.value && !debitSel.value && !creditSel.value) { status("Map an Amount or Debit/Credit column.", "error"); return; }
      const mapping = {
        date: dateSel.value,
        description: descSel.value,
        amount: amountSel.value || null,
        debit: debitSel.value || null,
        credit: creditSel.value || null,
        merchant: merchantSel.value || null,
        flip_sign: flip.checked,
      };
      const records = table.rows.map((r) => {
        const obj = {};
        table.headers.forEach((h, i) => { obj[h] = r[i] ?? ""; });
        return obj;
      });
      await postImport({ account_id: Number($("#account").value), source: "web", mapping, records });
    }
  }
}

function previewTable(table) {
  const wrap = el("div", { class: "scroll mt" });
  const t = el("table", { class: "mini-table" });
  t.append(el("thead", {}, el("tr", {}, ...table.headers.map((h) => el("th", {}, h)))));
  const body = el("tbody");
  table.rows.slice(0, 6).forEach((r) => body.append(el("tr", {}, ...r.map((c) => el("td", {}, c)))));
  t.append(body);
  wrap.append(t);
  return wrap;
}

/* ------------------------------------------------------------------ *
 * Amazon path: preview items -> send (records pre-normalized)
 * ------------------------------------------------------------------ */
function renderAmazon(orders) {
  const area = $("#workarea");
  area.innerHTML = "";
  const card = el("div", { class: "card" }, el("h3", {}, "Amazon items"));

  const wrap = el("div", { class: "scroll" });
  const t = el("table", { class: "mini-table" });
  t.append(el("thead", {}, el("tr", {}, el("th", {}, "Date"), el("th", {}, "Item"), el("th", {}, "Price"))));
  const body = el("tbody");
  orders.forEach((o) => body.append(el("tr", {},
    el("td", {}, o.date || "?"), el("td", {}, o.title.slice(0, 48)), el("td", {}, o.price))));
  t.append(body);
  wrap.append(t);

  card.append(wrap,
    el("p", { class: "muted mt" }, "Each item becomes one transaction (merchant “Amazon”). Rows without a readable date are skipped."),
    el("button", { class: "btn mt", onclick: send }, `Import ${orders.length} items`));
  area.append(card);

  async function send() {
    const records = orders.map((o) => ({
      date: o.date,
      description: `Amazon: ${o.title}` + (o.qty && o.qty !== "1" ? ` (x${o.qty})` : ""),
      amount: String(-Math.abs(parsePrice(o.price))),
      merchant: "Amazon",
    }));
    const mapping = { date: "date", description: "description", amount: "amount", merchant: "merchant" };
    await postImport({ account_id: Number($("#account").value), source: "amazon", mapping, records });
  }
}

function parsePrice(s) {
  const n = parseFloat(String(s).replace(/[^0-9.\-]/g, ""));
  return isNaN(n) ? 0 : n;
}

/* ------------------------------------------------------------------ *
 * Send to the app
 * ------------------------------------------------------------------ */
async function postImport(payload) {
  status("Importing…");
  try {
    const r = await api("/api/imports/web", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    status(`Imported ${r.imported_count} (${r.skipped_count} duplicates skipped, ${r.categorized_count} auto-categorized).`, "success");
    $("#workarea").innerHTML = "";
  } catch (e) {
    status("Import failed: " + e.message, "error");
  }
}

boot();
