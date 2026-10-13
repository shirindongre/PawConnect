/* PawConnect frontend — thin presentation layer. Vanilla JS + Fetch.
 * All business rules and authorization live in the Flask backend.
 * Every endpoint path used by this file is listed in ENDPOINTS below.
 */
"use strict";

/* ---------- Configuration (single place to change) ---------- */
const CONFIG = {
  // "" = same origin (frontend/dev_server.py proxies /api to Flask).
  // Override before app.js loads: window.PAWCONNECT_API_BASE = "https://api.example.com"
  // NOTE: a different origin requires CORS on the backend, which does not exist today.
  API_BASE: (typeof window !== "undefined" && window.PAWCONNECT_API_BASE) || "",
  ANIMALS_PER_PAGE: 12,
  CASES_PER_PAGE: 10,
  FEATURED_COUNT: 3,
};

const ENDPOINTS = {
  animals: "/api/animals",                       // GET public  ?page&per_page
  animal: (id) => `/api/animals/${encodeURIComponent(id)}`, // GET public
  rescueCases: "/api/rescue-cases",              // POST / GET (Cognito + local user)
  rescueCase: (id) => `/api/rescue-cases/${encodeURIComponent(id)}`, // GET (Cognito + local user)
  me: "/api/users/me",                           // GET / PATCH (Cognito + local user)
  myNgo: "/api/ngos/me",                         // GET (NGO role)
};

/* Field limits mirror docs/API.md §6 — for UX only; the backend remains authoritative. */
const URGENCY_LEVELS = ["Low", "Medium", "High", "Critical"];

/* ---------- Auth (integration point) ----------
 * No sign-in endpoint or Cognito hosted-UI config exists in the repository, so this
 * frontend cannot obtain tokens itself. It only holds a Cognito token supplied by the
 * user, in memory, and sends it as "Authorization: Bearer <token>".
 * Replace Auth.getToken()/setToken() with a real Cognito flow later. */
const Auth = (() => {
  let token = null;
  return {
    getToken: () => token,
    setToken: (t) => { token = (t || "").trim() || null; renderAuthStatus(); },
    clear: () => { token = null; renderAuthStatus(); },
    isSignedIn: () => !!token,
  };
})();

/* ---------- API helper ---------- */
async function api(path, { method = "GET", body, auth = false } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && Auth.getToken()) headers["Authorization"] = `Bearer ${Auth.getToken()}`;

  let res;
  try {
    res = await fetch(CONFIG.API_BASE + path, {
      method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    return { ok: false, status: 0, network: true, message: "Could not reach the PawConnect server. Check that the backend is running.", data: null };
  }

  let payload = null;
  const text = await res.text();               // handles 204 / empty bodies
  if (text) { try { payload = JSON.parse(text); } catch (_) { payload = null; } }

  if (res.ok) {
    return { ok: true, status: res.status, data: payload ? payload.data : null, message: payload && payload.message };
  }
  return {
    ok: false, status: res.status, data: null,
    message: (payload && payload.message) || `Request failed (HTTP ${res.status}).`,
    details: payload && payload.details,
  };
}

/* ---------- Tiny DOM helpers (textContent only: no innerHTML with API data) ---------- */
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (id) => document.getElementById(id);
const isNil = (v) => v === null || v === undefined || v === "";
const isHttpUrl = (s) => { try { const u = new URL(s); return u.protocol === "http:" || u.protocol === "https:"; } catch (_) { return false; } };

function showLoading(host, label = "Loading…") { host.replaceChildren(h("div", { class: "state", role: "status" }, h("span", { class: "spinner", "aria-hidden": "true" }), label)); }
function showEmpty(host, msg) { host.replaceChildren(h("div", { class: "state" }, msg)); }
function showError(host, msg, retry) {
  host.replaceChildren(h("div", { class: "state error", role: "alert" }, msg, retry ? [" ", h("button", { type: "button", class: "btn btn-small", onclick: retry }, "Try again")] : null));
}
function fmtDate(iso) { if (!iso) return null; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString(); }

/* Gate for protected views. Returns true when a request may be attempted. */
function gateAuth(host, what) {
  if (Auth.isSignedIn()) return true;
  host.replaceChildren(h("div", { class: "notice" },
    h("p", {}, `Sign-in is required to ${what}. This frontend has no sign-in screen yet; you can supply a Cognito token to continue.`),
    h("button", { type: "button", class: "btn btn-small", onclick: openAuthDialog }, "Add token")));
  return false;
}
/* Translate an auth-related failure into a clear message. */
function authAwareError(host, res, retry) {
  if (res.status === 401) { Auth.clear(); showError(host, `${res.message} Please add a valid token again.`); return; }
  if (res.status === 403) { showError(host, `Not permitted: ${res.message}`); return; }
  if (res.status === 503) { showError(host, `Authentication service unavailable: ${res.message}`); return; }
  showError(host, res.message, retry);
}

/* ---------- Animals ---------- */
function animalCard(a) {
  const name = isNil(a.name) ? "Unnamed animal" : a.name;
  const sub = [a.species, a.breed].filter((x) => !isNil(x)).join(" · ");
  const meta = [!isNil(a.age) ? `Age ${a.age}` : null, a.gender, a.location].filter((x) => !isNil(x)).join(" · ");
  const img = !isNil(a.image_url) && isHttpUrl(a.image_url)
    ? h("img", { class: "card-img", src: a.image_url, alt: `Photo of ${name}`, loading: "lazy", referrerpolicy: "no-referrer" })
    : h("div", { class: "card-img-ph", "aria-hidden": "true" }, "No photo");
  img.addEventListener("error", () => img.replaceWith(h("div", { class: "card-img-ph", "aria-hidden": "true" }, "Photo unavailable")), { once: true });
  return h("li", {}, h("article", { class: "card" }, img,
    h("div", { class: "card-body" },
      h("h3", {}, name),
      sub ? h("p", { class: "card-meta" }, sub) : h("p", { class: "card-meta na" }, "Species not provided"),
      meta ? h("p", { class: "card-meta" }, meta) : null,
      !isNil(a.status) ? h("span", { class: "badge" }, a.status) : null,
      h("a", { class: "btn btn-small", href: `#animal/${a.animal_id}`, "aria-label": `View details for ${name}` }, "View details"))));
}
function animalGrid(items) { return h("ul", { class: "grid" }, items.map(animalCard)); }

async function loadFeatured() {
  const host = $("home-featured");
  showLoading(host, "Loading animals…");
  const res = await api(`${ENDPOINTS.animals}?page=1&per_page=${CONFIG.FEATURED_COUNT}`);
  if (!res.ok) return showError(host, res.message, loadFeatured);
  const items = (res.data && res.data.items) || [];
  if (!items.length) return showEmpty(host, "No animals are listed for adoption right now.");
  host.replaceChildren(animalGrid(items), h("p", {}, h("a", { href: "#adopt" }, "See all animals →")));
}

const adoptState = { page: 1, items: [], total: 0, perPage: CONFIG.ANIMALS_PER_PAGE };

async function loadAnimals(page = adoptState.page) {
  const host = $("adopt-list");
  showLoading(host, "Loading animals…");
  $("adopt-pager").hidden = true;
  const res = await api(`${ENDPOINTS.animals}?page=${page}&per_page=${adoptState.perPage}`);
  if (!res.ok) return showError(host, res.message, () => loadAnimals(page));
  const d = res.data || {};
  adoptState.page = d.page || page;
  adoptState.items = d.items || [];
  adoptState.total = typeof d.total === "number" ? d.total : adoptState.items.length;
  adoptState.perPage = d.per_page || adoptState.perPage;
  populateSpecies();
  renderAnimals();
}
function populateSpecies() {
  const sel = $("animal-species"), current = sel.value;
  const species = [...new Set(adoptState.items.map((a) => a.species).filter((s) => !isNil(s)))].sort();
  sel.replaceChildren(h("option", { value: "" }, "All species"), ...species.map((s) => h("option", { value: s }, s)));
  sel.value = species.includes(current) ? current : "";
}
function renderAnimals() {
  const host = $("adopt-list");
  const q = $("animal-search").value.trim().toLowerCase();
  const sp = $("animal-species").value;
  const shown = adoptState.items.filter((a) =>
    (!sp || a.species === sp) &&
    (!q || [a.name, a.species, a.breed, a.location, a.description].some((v) => !isNil(v) && String(v).toLowerCase().includes(q))));
  const pages = Math.max(1, Math.ceil(adoptState.total / adoptState.perPage));
  const hint = $("adopt-hint");
  hint.hidden = !(adoptState.total > adoptState.items.length);
  hint.textContent = `Search and species filters apply only to the ${adoptState.items.length} animals loaded on this page (${adoptState.total} available in total).`;

  if (!adoptState.items.length) showEmpty(host, "No animals are listed for adoption right now.");
  else if (!shown.length) showEmpty(host, "No animals on this page match your search.");
  else host.replaceChildren(animalGrid(shown));

  $("adopt-pager").hidden = pages <= 1;
  $("adopt-page-label").textContent = `Page ${adoptState.page} of ${pages}`;
  $("adopt-prev").disabled = adoptState.page <= 1;
  $("adopt-next").disabled = adoptState.page >= pages;
}

async function loadAnimalDetail(id) {
  const host = $("animal-detail");
  showLoading(host, "Loading animal…");
  const res = await api(ENDPOINTS.animal(id));
  if (res.status === 404) return showEmpty(host, "This animal could not be found.");
  if (!res.ok) return showError(host, res.message, () => loadAnimalDetail(id));
  const a = res.data;
  const name = isNil(a.name) ? "Unnamed animal" : a.name;
  const hasImg = !isNil(a.image_url) && isHttpUrl(a.image_url);
  const row = (label, v) => [h("dt", {}, label), h("dd", v === null || v === undefined || v === "" ? { class: "na" } : {}, isNil(v) ? "Not provided" : String(v))];
  const img = hasImg ? h("img", { src: a.image_url, alt: `Photo of ${name}`, referrerpolicy: "no-referrer" }) : null;
  if (img) img.addEventListener("error", () => img.remove(), { once: true });
  host.replaceChildren(h("article", { class: "detail" + (hasImg ? " has-img" : "") }, img,
    h("div", {},
      h("h1", { id: "animal-title" }, name),
      !isNil(a.status) ? h("p", {}, h("span", { class: "badge" }, a.status)) : null,
      h("dl", { class: "kv" },
        row("Species", a.species), row("Breed", a.breed), row("Age", a.age), row("Gender", a.gender),
        row("Location", a.location), row("Description", a.description), row("Listed", fmtDate(a.created_at))),
      h("p", { class: "notice" }, "Adoption applications are not yet available in PawConnect."))));
  document.title = `${name} · PawConnect`;
}

/* ---------- Report form ---------- */
const REPORT_FIELDS = ["location", "animal_type", "urgency", "condition", "description", "image_url"];
const REPORT_RULES = {
  location: { max: 255, required: true, label: "Location" },
  animal_type: { max: 100, label: "Animal type" },
  condition: { max: 2000, label: "Condition" },
  description: { max: 2000, label: "Description" },
  image_url: { max: 2048, label: "Image URL" },
};
function setFieldError(name, msg) {
  const input = $(`r-${name}`), err = $(`r-${name}-err`);
  err.textContent = msg || "";
  if (msg) input.setAttribute("aria-invalid", "true"); else input.removeAttribute("aria-invalid");
}
function readReport() {
  const out = {};
  for (const f of REPORT_FIELDS) { const v = $(`r-${f}`).value.trim(); if (v) out[f] = v; }  // omit empty optionals
  return out;
}
function validateReport(p) {
  const errors = {};
  for (const [f, r] of Object.entries(REPORT_RULES)) {
    const v = p[f];
    if (r.required && !v) errors[f] = `${r.label} is required.`;
    else if (v && v.length > r.max) errors[f] = `${r.label} must not exceed ${r.max} characters.`;
  }
  if (p.urgency && !URGENCY_LEVELS.includes(p.urgency)) errors.urgency = `Urgency must be one of: ${URGENCY_LEVELS.join(", ")}.`;
  if (p.image_url && !errors.image_url && !isHttpUrl(p.image_url)) errors.image_url = "Image URL must be an absolute http:// or https:// link.";
  return errors;
}
function resultMsg(kind, text) { const el = $("report-result"); el.className = `notice ${kind}`; el.textContent = text; el.hidden = !text; }

async function submitReport(ev) {
  ev.preventDefault();
  resultMsg("", "");
  REPORT_FIELDS.forEach((f) => setFieldError(f, ""));
  const payload = readReport();
  const errors = validateReport(payload);
  const first = Object.keys(errors)[0];
  if (first) { Object.entries(errors).forEach(([f, m]) => setFieldError(f, m)); $(`r-${first}`).focus(); return; }
  if (!Auth.isSignedIn()) {
    resultMsg("error", "Sign-in is required to submit a report. Nothing was sent. Add a Cognito token (top right) and try again.");
    return;
  }
  const btn = $("report-submit");
  btn.disabled = true; btn.textContent = "Submitting…";
  const res = await api(ENDPOINTS.rescueCases, { method: "POST", body: payload, auth: true });
  btn.disabled = false; btn.textContent = "Submit report";
  if (res.ok && res.status === 201 && res.data && !isNil(res.data.case_id)) {
    $("report-form").reset();
    $("report-result").className = "notice success"; $("report-result").hidden = false;
    $("report-result").replaceChildren(`Report submitted. Case #${res.data.case_id} was created with status “${res.data.status}”. `, h("a", { href: `#case/${res.data.case_id}` }, "View case"));
    return;
  }
  if (res.status === 401) Auth.clear();
  if (res.details) for (const [f, m] of Object.entries(res.details)) if (REPORT_FIELDS.includes(f)) setFieldError(f, m);
  resultMsg("error", res.ok ? "The server responded unexpectedly; the report may not have been saved." : res.message);
}
function renderReportAuthNotice() {
  const n = $("report-auth");
  n.hidden = Auth.isSignedIn();
  n.textContent = "Submitting a report requires sign-in. You can fill in the form now; it will not be sent until a token is added.";
}

/* ---------- Rescue cases ---------- */
const casesState = { page: 1, perPage: CONFIG.CASES_PER_PAGE, total: 0 };

function caseCard(c) {
  const urgent = c.urgency === "High" || c.urgency === "Critical";
  return h("li", {}, h("article", { class: "card" }, h("div", { class: "card-body" },
    h("h3", {}, `Case #${c.case_id}`),
    h("p", {}, !isNil(c.status) ? h("span", { class: "badge" }, c.status) : null, " ", !isNil(c.urgency) ? h("span", { class: "badge" + (urgent ? " badge-urgent" : "") }, `Urgency: ${c.urgency}`) : null),
    h("p", { class: "card-meta" }, [c.animal_type, c.location].filter((x) => !isNil(x)).join(" · ") || "No details"),
    c.created_at ? h("p", { class: "card-meta" }, `Reported ${fmtDate(c.created_at)}`) : null,
    h("a", { class: "btn btn-small", href: `#case/${c.case_id}` }, "View case"))));
}
async function loadCases(page = casesState.page) {
  const host = $("cases-list");
  $("cases-pager").hidden = true;
  if (!gateAuth(host, "view your rescue cases")) return;
  showLoading(host, "Loading cases…");
  const res = await api(`${ENDPOINTS.rescueCases}?page=${page}&per_page=${casesState.perPage}`, { auth: true });
  if (!res.ok) return authAwareError(host, res, () => loadCases(page));
  const d = res.data || {}, items = d.items || [];
  casesState.page = d.page || page; casesState.total = typeof d.total === "number" ? d.total : items.length; casesState.perPage = d.per_page || casesState.perPage;
  if (!items.length) return showEmpty(host, casesState.page > 1 ? "No cases on this page." : "No rescue cases to show yet. Cases you report will appear here.");
  host.replaceChildren(h("ul", { class: "grid" }, items.map(caseCard)));
  const pages = Math.max(1, Math.ceil(casesState.total / casesState.perPage));
  $("cases-pager").hidden = pages <= 1;
  $("cases-page-label").textContent = `Page ${casesState.page} of ${pages}`;
  $("cases-prev").disabled = casesState.page <= 1;
  $("cases-next").disabled = casesState.page >= pages;
}
async function loadCaseDetail(id) {
  const host = $("case-detail");
  if (!gateAuth(host, "view this rescue case")) return;
  showLoading(host, "Loading case…");
  const res = await api(ENDPOINTS.rescueCase(id), { auth: true });
  if (res.status === 404) return showEmpty(host, "This rescue case could not be found.");
  if (!res.ok) return authAwareError(host, res, () => loadCaseDetail(id));
  const c = res.data;
  const row = (label, v) => [h("dt", {}, label), h("dd", isNil(v) ? { class: "na" } : {}, isNil(v) ? "Not provided" : String(v))];
  const hasImg = !isNil(c.image_url) && isHttpUrl(c.image_url);
  const img = hasImg ? h("img", { src: c.image_url, alt: "Photo submitted with this report", referrerpolicy: "no-referrer" }) : null;
  if (img) img.addEventListener("error", () => img.remove(), { once: true });
  host.replaceChildren(h("article", { class: "detail" + (hasImg ? " has-img" : "") }, img, h("div", {},
    h("h1", { id: "case-title" }, `Case #${c.case_id}`),
    h("dl", { class: "kv" },
      row("Status", c.status), row("Urgency", c.urgency), row("Animal type", c.animal_type), row("Location", c.location),
      row("Condition", c.condition), row("Description", c.description),
      row("Assigned NGO", isNil(c.assigned_ngo) ? "Not yet assigned" : `NGO #${c.assigned_ngo}`),
      row("Reported", fmtDate(c.created_at)), row("Last updated", fmtDate(c.updated_at))))));
}

/* ---------- Profile ---------- */
async function loadProfile() {
  const host = $("profile-body");
  if (!gateAuth(host, "view your profile")) return;
  showLoading(host, "Loading profile…");
  const res = await api(ENDPOINTS.me, { auth: true });
  if (!res.ok) return authAwareError(host, res, loadProfile);
  const u = res.data;
  const row = (label, v) => [h("dt", {}, label), h("dd", isNil(v) ? { class: "na" } : {}, isNil(v) ? "Not provided" : String(v))];
  const form = h("form", { id: "profile-form", novalidate: true },
    h("h2", {}, "Edit profile"),
    profileField("name", "Name", u.name, 100), profileField("phone", "Phone", u.phone, 20), profileField("location", "Location", u.location, 255),
    h("p", { id: "profile-result", role: "status", "aria-live": "polite" }),
    h("button", { type: "submit", class: "btn", id: "profile-save" }, "Save changes"));
  form.addEventListener("submit", (e) => saveProfile(e, u));
  const ngoHost = h("div", { id: "ngo-body" });
  host.replaceChildren(
    h("div", { class: "detail" }, h("dl", { class: "kv" }, row("Name", u.name), row("Email", u.email), row("Phone", u.phone), row("Location", u.location), row("Role", u.role))),
    form, ngoHost);
  if (u.role === "NGO") loadNgo(ngoHost);
}
function profileField(name, label, value, max) {
  return h("div", { class: "field" }, h("label", { for: `p-${name}` }, label),
    h("input", { id: `p-${name}`, type: "text", maxlength: String(max), value: value || "", "aria-describedby": `p-${name}-err` }),
    h("p", { class: "err", id: `p-${name}-err`, role: "alert" }));
}
async function saveProfile(ev, original) {
  ev.preventDefault();
  const result = $("profile-result"); result.className = ""; result.textContent = "";
  const payload = {};
  let bad = false;
  for (const [f, max] of [["name", 100], ["phone", 20], ["location", 255]]) {
    const el = $(`p-${f}`), err = $(`p-${f}-err`); err.textContent = ""; el.removeAttribute("aria-invalid");
    const v = el.value.trim();
    if (f === "name" && !v) { err.textContent = "Name must not be empty."; bad = true; }
    else if (v.length > max) { err.textContent = `Must not exceed ${max} characters.`; bad = true; }
    if (bad && err.textContent) el.setAttribute("aria-invalid", "true");
    if (v !== (original[f] || "")) payload[f] = v === "" && f !== "name" ? null : v;   // empty optional → null
  }
  if (bad) return;
  if (!Object.keys(payload).length) { result.className = "notice"; result.textContent = "No changes to save."; return; }
  const btn = $("profile-save"); btn.disabled = true;
  const res = await api(ENDPOINTS.me, { method: "PATCH", body: payload, auth: true });
  btn.disabled = false;
  if (res.ok) { result.className = "notice success"; result.textContent = "Profile updated."; loadProfile(); return; }
  if (res.status === 401) Auth.clear();
  if (res.details) for (const [f, m] of Object.entries(res.details)) { const e = $(`p-${f}-err`); if (e) e.textContent = m; }
  result.className = "notice error"; result.textContent = res.message;
}
async function loadNgo(host) {
  host.replaceChildren(h("h2", {}, "NGO profile"), h("p", { role: "status" }, "Loading NGO profile…"));
  const res = await api(ENDPOINTS.myNgo, { auth: true });
  if (res.status === 404) return host.replaceChildren(h("h2", {}, "NGO profile"), h("p", { class: "notice" }, res.message));
  if (!res.ok) return host.replaceChildren(h("h2", {}, "NGO profile"), h("p", { class: "notice error" }, res.message));
  const n = res.data || {};
  host.replaceChildren(h("h2", {}, "NGO profile"), h("div", { class: "detail" }, h("dl", { class: "kv" },
    Object.entries(n).map(([k, v]) => [h("dt", {}, k.replace(/_/g, " ")), h("dd", isNil(v) ? { class: "na" } : {}, isNil(v) ? "Not provided" : String(v))]))));
}

/* ---------- Auth dialog / header ---------- */
function renderAuthStatus() {
  $("auth-status").textContent = Auth.isSignedIn() ? "Token added" : "Not signed in";
  $("auth-btn").textContent = Auth.isSignedIn() ? "Change token" : "Add token";
  if (typeof renderReportAuthNotice === "function" && $("report-auth")) renderReportAuthNotice();
}
function openAuthDialog() { $("auth-token").value = ""; $("auth-dialog").showModal(); }

/* ---------- Router ---------- */
const VIEWS = ["home", "adopt", "animal", "report", "cases", "case", "profile"];
function route() {
  const [name = "home", arg] = (location.hash.replace(/^#/, "") || "home").split("/");
  const view = VIEWS.includes(name) ? name : "home";
  VIEWS.forEach((v) => { $(`view-${v}`).hidden = v !== view; });
  const navKey = view === "animal" ? "adopt" : view === "case" ? "cases" : view;
  document.querySelectorAll("[data-nav]").forEach((a) => a.toggleAttribute("aria-current", a.dataset.nav === navKey));
  document.querySelectorAll("[data-nav]").forEach((a) => { if (a.dataset.nav === navKey) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  document.title = "PawConnect";
  if (view === "home") loadFeatured();
  else if (view === "adopt") loadAnimals(1);
  else if (view === "animal") loadAnimalDetail(arg);
  else if (view === "report") renderReportAuthNotice();
  else if (view === "cases") loadCases(1);
  else if (view === "case") loadCaseDetail(arg);
  else if (view === "profile") loadProfile();
  $("main").focus({ preventScroll: true });
  window.scrollTo(0, 0);
}

/* ---------- Init ---------- */
function init() {
  $("animal-search").addEventListener("input", renderAnimals);
  $("animal-species").addEventListener("change", renderAnimals);
  $("adopt-prev").addEventListener("click", () => loadAnimals(adoptState.page - 1));
  $("adopt-next").addEventListener("click", () => loadAnimals(adoptState.page + 1));
  $("cases-prev").addEventListener("click", () => loadCases(casesState.page - 1));
  $("cases-next").addEventListener("click", () => loadCases(casesState.page + 1));
  $("report-form").addEventListener("submit", submitReport);
  $("auth-btn").addEventListener("click", openAuthDialog);
  $("auth-clear").addEventListener("click", () => { Auth.clear(); $("auth-dialog").close(); route(); });
  $("auth-dialog").addEventListener("close", () => {
    if ($("auth-dialog").returnValue === "save" && $("auth-token").value.trim()) { Auth.setToken($("auth-token").value); route(); }
    $("auth-token").value = "";
  });
  window.addEventListener("hashchange", route);
  renderAuthStatus();
  route();
}
document.addEventListener("DOMContentLoaded", init);
