"use strict";

/* ------------------------------------------------------------------ *
 * Tiny helpers
 * ------------------------------------------------------------------ */
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c == null) continue;
    node.append(c.nodeType ? c : document.createTextNode(c));
  }
  return node;
};
const money = (n, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency }).format(n || 0);
const fmtDate = (d) => d;

function toast(msg, kind = "") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast ${kind}`;
  setTimeout(() => t.classList.add("hidden"), 3500);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ------------------------------------------------------------------ *
 * App state + routing
 * ------------------------------------------------------------------ */
const state = { accounts: [], categories: [] };
let activeChart = [];

function destroyCharts() {
  activeChart.forEach((c) => c.destroy());
  activeChart = [];
}

async function loadReference() {
  [state.accounts, state.categories] = await Promise.all([
    api("/api/accounts"),
    api("/api/categories"),
  ]);
}

const views = {}; // name -> render fn

function switchView(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.view === name)
  );
  destroyCharts();
  const app = $("#app");
  app.innerHTML = "";
  views[name](app);
}

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => switchView(tab.dataset.view))
);

/* ------------------------------------------------------------------ *
 * Dashboard
 * ------------------------------------------------------------------ */
views.dashboard = async (root) => {
  root.append(el("h2", { class: "view-title" }, "Dashboard"));

  const controls = el("div", { class: "toolbar" });
  const accountSel = accountSelect(true);
  const startInput = el("input", { type: "date" });
  const endInput = el("input", { type: "date" });
  controls.append(
    field("Account", accountSel),
    field("From", startInput),
    field("To", endInput),
    el("button", { class: "btn", onclick: () => refresh() }, "Apply")
  );
  root.append(controls);

  const tiles = el("div", { class: "grid cols-4" });
  const charts = el("div", { class: "grid cols-2" });
  const merchants = el("div", { class: "card" });
  root.append(tiles, charts, merchants);

  async function refresh() {
    const params = new URLSearchParams();
    if (accountSel.value) params.set("account_id", accountSel.value);
    if (startInput.value) params.set("start_date", startInput.value);
    if (endInput.value) params.set("end_date", endInput.value);
    let data;
    try {
      data = await api(`/api/analytics/summary?${params}`);
    } catch (e) {
      toast(e.message, "error");
      return;
    }
    renderTiles(tiles, data);
    renderCharts(charts, data);
    renderMerchants(merchants, data);
  }
  refresh();
};

function renderTiles(root, d) {
  root.innerHTML = "";
  const tile = (label, value, cls = "") =>
    el("div", { class: "card stat" },
      el("span", { class: "label" }, label),
      el("span", { class: `value ${cls}` }, value)
    );
  root.append(
    tile("Total Spending", money(d.total_spending), "neg"),
    tile("Total Income", money(d.total_income), "pos"),
    tile("Net", money(d.net), d.net >= 0 ? "pos" : "neg"),
    tile("Transactions", String(d.transaction_count))
  );
}

function renderCharts(root, d) {
  destroyCharts();
  root.innerHTML = "";

  const catCard = el("div", { class: "card" }, el("h3", {}, "Spending by Category"));
  const catBox = el("div", { class: "chart-box" });
  const catCanvas = el("canvas");
  catBox.append(catCanvas);
  catCard.append(catBox);

  const monthCard = el("div", { class: "card" }, el("h3", {}, "Monthly Spending vs Income"));
  const monthBox = el("div", { class: "chart-box" });
  const monthCanvas = el("canvas");
  monthBox.append(monthCanvas);
  monthCard.append(monthBox);

  root.append(catCard, monthCard);

  if (d.by_category.length) {
    activeChart.push(new Chart(catCanvas, {
      type: "doughnut",
      data: {
        labels: d.by_category.map((c) => c.category_name),
        datasets: [{
          data: d.by_category.map((c) => c.total),
          backgroundColor: d.by_category.map((c) => c.color || "#94a3b8"),
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: "right", labels: { color: cssVar("--text") } } },
      },
    }));
  } else {
    catBox.replaceChildren(emptyNote());
  }

  if (d.by_month.length) {
    activeChart.push(new Chart(monthCanvas, {
      type: "bar",
      data: {
        labels: d.by_month.map((m) => m.month),
        datasets: [
          { label: "Spending", data: d.by_month.map((m) => m.spending), backgroundColor: "#ef4444" },
          { label: "Income", data: d.by_month.map((m) => m.income), backgroundColor: "#22c55e" },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: cssVar("--text-dim") }, grid: { display: false } },
          y: { ticks: { color: cssVar("--text-dim") }, grid: { color: cssVar("--border") } },
        },
        plugins: { legend: { labels: { color: cssVar("--text") } } },
      },
    }));
  } else {
    monthBox.replaceChildren(emptyNote());
  }
}

function renderMerchants(root, d) {
  root.innerHTML = "";
  root.append(el("h3", {}, "Top Merchants"));
  if (!d.by_merchant.length) { root.append(emptyNote()); return; }
  const rows = d.by_merchant.map((m) =>
    el("tr", {},
      el("td", {}, m.merchant),
      el("td", { class: "amount" }, String(m.count)),
      el("td", { class: "amount neg" }, money(m.total))
    )
  );
  root.append(wrapTable(["Merchant", "Txns", "Spent"], rows));
}

/* ------------------------------------------------------------------ *
 * Transactions
 * ------------------------------------------------------------------ */
views.transactions = async (root) => {
  root.append(el("h2", { class: "view-title" }, "Transactions"));

  const accountSel = accountSelect(true);
  const categorySel = categorySelect(true);
  const search = el("input", { type: "search", placeholder: "Search description / merchant" });
  const startInput = el("input", { type: "date" });
  const endInput = el("input", { type: "date" });

  const toolbar = el("div", { class: "toolbar" },
    field("Account", accountSel),
    field("Category", categorySel),
    field("From", startInput),
    field("To", endInput),
    field("Search", search),
    el("button", { class: "btn", onclick: () => load() }, "Filter")
  );
  root.append(toolbar);

  const tableCard = el("div", { class: "card table-wrap" });
  root.append(tableCard);

  async function load() {
    const params = new URLSearchParams();
    if (accountSel.value) params.set("account_id", accountSel.value);
    if (categorySel.value) params.set("category_id", categorySel.value);
    if (startInput.value) params.set("start_date", startInput.value);
    if (endInput.value) params.set("end_date", endInput.value);
    if (search.value.trim()) params.set("search", search.value.trim());
    let txns;
    try { txns = await api(`/api/transactions?${params}`); }
    catch (e) { toast(e.message, "error"); return; }
    renderTxnTable(tableCard, txns, load);
  }
  search.addEventListener("keydown", (e) => { if (e.key === "Enter") load(); });
  load();
};

function renderTxnTable(root, txns, reload) {
  root.innerHTML = "";
  if (!txns.length) { root.append(emptyNote("No transactions match. Import a statement to get started.")); return; }

  const catOptions = state.categories;
  const rows = txns.map((t) => {
    const catCell = el("td");
    const sel = el("select");
    sel.append(el("option", { value: "" }, "—"));
    for (const c of catOptions) {
      const opt = el("option", { value: c.id }, c.name);
      if (c.id === t.category_id) opt.selected = true;
      sel.append(opt);
    }
    sel.addEventListener("change", async () => {
      try {
        await api(`/api/transactions/${t.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ category_id: sel.value ? Number(sel.value) : null }),
        });
        toast("Category updated", "success");
      } catch (e) { toast(e.message, "error"); }
    });
    catCell.append(sel);

    const amtCls = t.amount < 0 ? "neg" : "pos";
    return el("tr", {},
      el("td", {}, t.txn_date),
      el("td", {}, t.account_name || ""),
      el("td", {}, el("div", {}, t.merchant || "—"),
        el("div", { class: "muted", style: "font-size:12px" }, t.description)),
      catCell,
      el("td", { class: `amount ${amtCls}` }, money(t.amount)),
      el("td", {}, el("button", {
        class: "icon", title: "Delete",
        onclick: async () => {
          if (!confirm("Delete this transaction?")) return;
          try { await api(`/api/transactions/${t.id}`, { method: "DELETE" }); reload(); }
          catch (e) { toast(e.message, "error"); }
        },
      }, "🗑"))
    );
  });

  root.append(el("div", { class: "muted", style: "margin-bottom:10px" }, `${txns.length} transactions`));
  root.append(wrapTable(["Date", "Account", "Description", "Category", "Amount", ""], rows));
}

/* ------------------------------------------------------------------ *
 * Import wizard
 * ------------------------------------------------------------------ */
views.import = async (root) => {
  root.append(el("h2", { class: "view-title" }, "Import Transactions"));

  if (!state.accounts.length) {
    root.append(el("div", { class: "card" },
      el("p", {}, "Create an account first (Accounts tab) so imported transactions have somewhere to live.")));
    return;
  }

  const typeSel = el("select");
  [
    ["csv", "Bank / Credit-card CSV"],
    ["ofx", "OFX / QFX file"],
    ["amazon", "Amazon order history (CSV)"],
  ].forEach(([v, label]) => typeSel.append(el("option", { value: v }, label)));

  const accountSel = accountSelect(false);

  const fileInput = el("input", { type: "file", accept: ".csv,.ofx,.qfx,.txt" });
  const drop = el("div", { class: "dropzone" }, "Click to choose a file, or drag it here");
  drop.addEventListener("click", () => fileInput.click());
  ["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("dragover")));
  drop.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer.files[0]) { fileInput.files = e.dataTransfer.files; onFile(); } });
  fileInput.addEventListener("change", onFile);

  const mappingArea = el("div");
  const resultArea = el("div");

  const card = el("div", { class: "card" },
    el("div", { class: "row" },
      field("What are you importing?", typeSel),
      field("Into account", accountSel)),
    drop, fileInput, mappingArea, resultArea
  );
  fileInput.classList.add("hidden");
  root.append(card);

  root.append(el("div", { class: "card muted" },
    el("h3", {}, "How to get your files"),
    el("p", { html: "<b>Banks &amp; credit cards:</b> log in, open your transactions/statements, and use the “Download” or “Export” option. Choose CSV or OFX/QFX and upload it here." }),
    el("p", { html: "<b>Amazon:</b> Account → <i>Request Your Data</i> → “Your Orders”, or the legacy Order History Report. Upload the CSV — each item becomes its own line so you can see what you bought." }),
    el("p", { html: "Re-importing the same file is safe — duplicates are detected and skipped automatically." })
  ));

  typeSel.addEventListener("change", () => { mappingArea.innerHTML = ""; resultArea.innerHTML = ""; });

  async function onFile() {
    mappingArea.innerHTML = "";
    resultArea.innerHTML = "";
    const file = fileInput.files[0];
    if (!file) return;
    drop.textContent = `📄 ${file.name}`;

    if (typeSel.value === "csv") {
      await showCsvMapping(file, accountSel, mappingArea, resultArea);
    } else {
      await doSimpleImport(typeSel.value, file, accountSel, resultArea);
    }
  }
};

async function showCsvMapping(file, accountSel, mappingArea, resultArea) {
  const fd = new FormData();
  fd.append("file", file);
  let preview;
  try { preview = await api("/api/imports/preview", { method: "POST", body: fd }); }
  catch (e) { toast(e.message, "error"); return; }

  const headers = preview.headers;
  const sug = preview.suggested_mapping || {};
  const headerOptions = (selected) => {
    const s = el("select");
    s.append(el("option", { value: "" }, "—"));
    headers.forEach((h) => {
      const o = el("option", { value: h }, h);
      if (h === selected) o.selected = true;
      s.append(o);
    });
    return s;
  };

  const dateSel = headerOptions(sug.date);
  const descSel = headerOptions(sug.description);
  const amountSel = headerOptions(sug.amount);
  const debitSel = headerOptions(sug.debit);
  const creditSel = headerOptions(sug.credit);
  const flip = el("input", { type: "checkbox" });
  if (sug.flip_sign) flip.checked = true;

  const grid = el("div", { class: "mapping-grid" },
    el("label", {}, "Date column"), dateSel,
    el("label", {}, "Description"), descSel,
    el("label", {}, "Amount (signed)"), amountSel,
    el("label", {}, "Debit column"), debitSel,
    el("label", {}, "Credit column"), creditSel,
    el("label", {}, "Flip amount sign"), flip
  );

  const note = el("p", { class: "muted", style: "font-size:12px" },
    "Use a single signed Amount column, OR separate Debit/Credit columns. " +
    "Tick “Flip sign” if your export lists purchases as positive numbers.");

  const importBtn = el("button", { class: "btn", onclick: run }, "Import CSV");

  mappingArea.innerHTML = "";
  mappingArea.append(el("h3", {}, "Map your columns"), grid, note, importBtn);

  async function run() {
    if (!accountSel.value) { toast("Choose an account first", "error"); return; }
    const mapping = {
      date: dateSel.value,
      description: descSel.value,
      amount: amountSel.value || null,
      debit: debitSel.value || null,
      credit: creditSel.value || null,
      flip_sign: flip.checked,
    };
    if (!mapping.date || !mapping.description) { toast("Date and Description are required", "error"); return; }
    if (!mapping.amount && !mapping.debit && !mapping.credit) { toast("Map an Amount, or Debit/Credit columns", "error"); return; }

    const fd2 = new FormData();
    fd2.append("account_id", accountSel.value);
    fd2.append("mapping", JSON.stringify(mapping));
    fd2.append("file", file);
    importBtn.disabled = true;
    try {
      const r = await api("/api/imports/csv", { method: "POST", body: fd2 });
      showResult(resultArea, r);
    } catch (e) { toast(e.message, "error"); }
    finally { importBtn.disabled = false; }
  }
}

async function doSimpleImport(kind, file, accountSel, resultArea) {
  if (!accountSel.value) { toast("Choose an account first", "error"); return; }
  const fd = new FormData();
  fd.append("account_id", accountSel.value);
  fd.append("file", file);
  try {
    const r = await api(`/api/imports/${kind}`, { method: "POST", body: fd });
    showResult(resultArea, r);
  } catch (e) { toast(e.message, "error"); }
}

function showResult(root, r) {
  root.innerHTML = "";
  root.append(el("div", { class: "card", style: "border-left:4px solid var(--success);margin-top:16px" },
    el("h3", {}, "Import complete"),
    el("p", {}, `Imported ${r.imported_count} of ${r.row_count} rows ` +
      `(${r.skipped_count} duplicates skipped, ${r.categorized_count} auto-categorized).`),
    el("button", { class: "btn secondary", onclick: () => switchView("dashboard") }, "View dashboard")
  ));
  toast(`Imported ${r.imported_count} transactions`, "success");
}

/* ------------------------------------------------------------------ *
 * Categories & Rules
 * ------------------------------------------------------------------ */
views.rules = async (root) => {
  root.append(el("h2", { class: "view-title" }, "Categories & Rules"));
  const cols = el("div", { class: "grid cols-2" });
  root.append(cols);

  const catCard = el("div", { class: "card" });
  const ruleCard = el("div", { class: "card" });
  cols.append(catCard, ruleCard);

  await renderCategories(catCard);
  await renderRules(ruleCard);
};

async function renderCategories(root) {
  root.innerHTML = "";
  root.append(el("h3", {}, "Categories"));

  const name = el("input", { placeholder: "e.g. Coffee" });
  const color = el("input", { type: "color", value: "#6366f1" });
  const add = el("button", { class: "btn", onclick: async () => {
    if (!name.value.trim()) return;
    try {
      await api("/api/categories", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.value.trim(), color: color.value }) });
      await loadReference();
      renderCategories(root);
      toast("Category added", "success");
    } catch (e) { toast(e.message, "error"); }
  }}, "Add");
  root.append(el("div", { class: "row", style: "align-items:flex-end;margin-bottom:14px" },
    field("New category", name), field("Colour", color), add));

  const rows = state.categories.map((c) =>
    el("tr", {},
      el("td", {}, el("span", { class: "category-dot", style: `background:${c.color || "#94a3b8"}` }), c.name),
      el("td", {}, el("button", { class: "icon", onclick: async () => {
        if (!confirm(`Delete category "${c.name}"?`)) return;
        try { await api(`/api/categories/${c.id}`, { method: "DELETE" }); await loadReference(); renderCategories(root); }
        catch (e) { toast(e.message, "error"); }
      }}, "🗑"))
    )
  );
  root.append(wrapTable(["Name", ""], rows));
}

async function renderRules(root) {
  root.innerHTML = "";
  root.append(el("h3", {}, "Auto-categorization Rules"));
  root.append(el("p", { class: "muted", style: "font-size:12px" },
    "When a transaction's text contains the pattern, it gets the chosen category. Applied on import."));

  const pattern = el("input", { placeholder: "text to match, e.g. starbucks" });
  const catSel = categorySelect(false);
  const add = el("button", { class: "btn", onclick: async () => {
    if (!pattern.value.trim() || !catSel.value) { toast("Pattern and category required", "error"); return; }
    try {
      await api("/api/rules", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pattern: pattern.value.trim(), category_id: Number(catSel.value), priority: 20 }) });
      pattern.value = "";
      renderRules(root);
      toast("Rule added", "success");
    } catch (e) { toast(e.message, "error"); }
  }}, "Add");
  root.append(el("div", { class: "row", style: "align-items:flex-end;margin-bottom:14px" },
    field("Pattern", pattern), field("Category", catSel), add));

  const applyBtn = el("button", { class: "btn secondary", style: "margin-bottom:14px", onclick: async () => {
    try {
      const r = await api("/api/rules/apply?only_uncategorized=false", { method: "POST" });
      toast(`Re-categorized ${r.changed} transactions`, "success");
    } catch (e) { toast(e.message, "error"); }
  }}, "Re-apply rules to all transactions");
  root.append(applyBtn);

  let rules;
  try { rules = await api("/api/rules"); } catch (e) { toast(e.message, "error"); return; }
  const catById = Object.fromEntries(state.categories.map((c) => [c.id, c]));
  const rows = rules.map((rl) => {
    const c = catById[rl.category_id];
    return el("tr", {},
      el("td", {}, el("code", {}, rl.pattern)),
      el("td", {}, c ? el("span", { class: "pill", style: `background:${c.color || "#64748b"}` }, c.name) : "?"),
      el("td", {}, el("button", { class: "icon", onclick: async () => {
        try { await api(`/api/rules/${rl.id}`, { method: "DELETE" }); renderRules(root); }
        catch (e) { toast(e.message, "error"); }
      }}, "🗑"))
    );
  });
  root.append(wrapTable(["Pattern", "Category", ""], rows));
}

/* ------------------------------------------------------------------ *
 * Accounts
 * ------------------------------------------------------------------ */
views.accounts = async (root) => {
  root.append(el("h2", { class: "view-title" }, "Accounts"));
  const card = el("div", { class: "card" });
  root.append(card);

  const name = el("input", { placeholder: "e.g. Chase Sapphire" });
  const typeSel = el("select");
  [["credit_card", "Credit card"], ["checking", "Checking"], ["savings", "Savings"],
   ["amazon", "Amazon"], ["cash", "Cash"], ["other", "Other"]]
    .forEach(([v, l]) => typeSel.append(el("option", { value: v }, l)));
  const inst = el("input", { placeholder: "Institution (optional)" });

  const add = el("button", { class: "btn", onclick: async () => {
    if (!name.value.trim()) { toast("Name required", "error"); return; }
    try {
      await api("/api/accounts", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.value.trim(), type: typeSel.value, institution: inst.value.trim() || null }) });
      name.value = ""; inst.value = "";
      await loadReference();
      views.accounts(document.querySelector("#app").replaceChildren() || $("#app"));
      switchView("accounts");
      toast("Account created", "success");
    } catch (e) { toast(e.message, "error"); }
  }}, "Add account");

  card.append(el("div", { class: "row", style: "align-items:flex-end;margin-bottom:16px" },
    field("Name", name), field("Type", typeSel), field("Institution", inst), add));

  if (!state.accounts.length) {
    card.append(emptyNote("No accounts yet. Add your first credit card or bank account above."));
    return;
  }
  const rows = state.accounts.map((a) =>
    el("tr", {},
      el("td", {}, a.name),
      el("td", {}, a.type.replace("_", " ")),
      el("td", {}, a.institution || "—"),
      el("td", {}, el("button", { class: "icon", onclick: async () => {
        if (!confirm(`Delete "${a.name}" and all its transactions?`)) return;
        try { await api(`/api/accounts/${a.id}`, { method: "DELETE" }); await loadReference(); switchView("accounts"); }
        catch (e) { toast(e.message, "error"); }
      }}, "🗑"))
    )
  );
  card.append(wrapTable(["Name", "Type", "Institution", ""], rows));
};

/* ------------------------------------------------------------------ *
 * Reusable UI bits
 * ------------------------------------------------------------------ */
function field(labelText, control) {
  return el("div", { class: "field" }, el("label", {}, labelText), control);
}
function accountSelect(includeAll) {
  const s = el("select");
  if (includeAll) s.append(el("option", { value: "" }, "All accounts"));
  state.accounts.forEach((a) => s.append(el("option", { value: a.id }, a.name)));
  return s;
}
function categorySelect(includeAll) {
  const s = el("select");
  if (includeAll) s.append(el("option", { value: "" }, "All categories"));
  else s.append(el("option", { value: "" }, "Choose…"));
  state.categories.forEach((c) => s.append(el("option", { value: c.id }, c.name)));
  return s;
}
function wrapTable(headers, rows) {
  const table = el("table");
  table.append(el("thead", {}, el("tr", {}, ...headers.map((h) => el("th", {}, h)))));
  table.append(el("tbody", {}, ...rows));
  return table;
}
function emptyNote(msg = "No data yet.") {
  return el("p", { class: "muted", style: "text-align:center;padding:24px" }, msg);
}
function cssVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim() || "#94a3b8";
}

/* ------------------------------------------------------------------ *
 * Boot
 * ------------------------------------------------------------------ */
(async function boot() {
  try {
    await loadReference();
  } catch (e) {
    toast("Failed to load data: " + e.message, "error");
  }
  switchView("dashboard");
})();
