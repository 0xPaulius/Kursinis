// Puslapio rėmas: navigacija, sistemos būklė, paieška.

import { el, setText } from "./dom.js";
import { state } from "./state.js";
import { alertTitle, t } from "./i18n.js";
import { applyTheme } from "./charts.js";

const PAGES = ["dashboard", "anomalies", "devices", "attack", "messages"];
let onEnter = () => {};
let liveConnected = false;

// main.js perduoda, ką daryti atidarius puslapį; puslapis laikomas URL #fragmente.
export function initNavigation(enter) {
  onEnter = enter;
  document.querySelectorAll("[data-nav]").forEach(btn =>
    btn.addEventListener("click", () => navigate(btn.dataset.nav)));
  window.addEventListener("hashchange", () => showPage(routeFromHash()));
  showPage(routeFromHash());
}

// route — puslapis („devices") arba įrenginys („devices/self").
export function navigate(route) {
  if (location.hash === "#" + route) showPage(routeFromHash());
  else location.hash = route;
}

// #puslapis arba #devices/<įrenginio raktas>.
function routeFromHash() {
  const [page, ...rest] = location.hash.slice(1).split("/");
  if (!PAGES.includes(page)) return { page: "dashboard", sub: "" };
  let sub = "";
  if (page === "devices" && rest.length) {
    try { sub = decodeURIComponent(rest.join("/")); } catch (_) { sub = ""; }
  }
  return { page, sub };
}

function showPage({ page, sub }) {
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  PAGES.forEach(p => { const b = el("nav-" + p); if (b) b.classList.toggle("active", p === page); });
  state.page = page;
  state.deviceKey = sub;
  setCrumb(t("nav_" + page));
  onEnter(page);
}

// Viršutinės juostos kelias („Įrenginiai" arba „Įrenginiai › MacBook").
export function setCrumb(text) {
  setText("crumb-page", text);
}

// Temos jungiklis: <html data-theme>, išsaugoma naršyklėje; grafikai perpiešiami iš karto.
export function initTheme(onChange = () => {}) {
  el("theme-btn")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
    paintThemeButton();
    applyTheme();
    onChange();
  });
  paintThemeButton();
}

function paintThemeButton() {
  const btn = el("theme-btn");
  if (!btn) return;
  const light = document.documentElement.dataset.theme === "light";
  const icon = btn.querySelector(".material-symbols-outlined");
  if (icon) icon.textContent = light ? "dark_mode" : "light_mode";
  btn.title = t(light ? "theme_dark" : "theme_light");
}

// Ctrl/Cmd+K — į paiešką; Esc paieškoje — išvalyti.
export function initShortcuts(clearSearch) {
  document.addEventListener("keydown", e => {
    const search = el("search-input");
    const dialog = document.querySelector(".dlg-backdrop:not(.hidden)");
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      search?.focus();
    } else if (e.key === "Escape" && dialog) {
      dialog.classList.add("hidden");
    } else if (e.key === "Escape" && document.activeElement === search) {
      clearSearch();
    }
  });
}

export function setLive(connected) {
  liveConnected = connected;
  const box = el("live-status");
  if (!box) return;
  while (box.firstChild) box.removeChild(box.firstChild);
  const dot = document.createElement("span");
  dot.className = "app-dot";
  dot.style.background = connected ? "var(--ok)" : "var(--warn)";
  const label = document.createElement("span");
  label.textContent = t(connected ? "live" : "reconnecting");
  box.append(dot, label);
}

// Po kalbos perjungimo: rėmo užrašai, kurie nėra statiniai data-i18n.
export function refreshFrameLabels() {
  setCrumb(t("nav_" + state.page));
  setLive(liveConnected);
  paintThemeButton();
}

export function setNavCount(n) {
  const badge = el("nav-anomalies-count");
  if (!badge) return;
  badge.textContent = n > 0 ? String(n) : "";
  badge.classList.toggle("hidden", !(n > 0));
}

export function showBanner(kind, text, retry) {
  const box = el("app-banner");
  if (!box) return;
  box.className = `banner is-${kind}`;
  while (box.firstChild) box.removeChild(box.firstChild);
  const icon = document.createElement("span");
  icon.className = "material-symbols-outlined";
  icon.textContent = kind === "error" ? "error" : "info";
  const msg = document.createElement("span");
  msg.className = "flex-1";
  msg.textContent = text;
  box.append(icon, msg);
  if (retry) {
    const again = document.createElement("button");
    again.className = "btn";
    again.textContent = t("retry");
    again.addEventListener("click", () => { hideBanner(); retry(); });
    box.append(again);
  }
  const close = document.createElement("button");
  close.className = "btn btn-icon";
  close.title = t("close");
  const x = document.createElement("span");
  x.className = "material-symbols-outlined";
  x.textContent = "close";
  close.append(x);
  close.addEventListener("click", hideBanner);
  box.append(close);
}

export function hideBanner() {
  el("app-banner")?.classList.add("hidden");
}

const HEALTH_COLOR = { ok: "var(--ok)", warning: "var(--warn)", critical: "var(--crit)", unknown: "var(--text-dim)" };

// Sistemos būklė viršutinėje juostoje; kiekvienos paslaugos būsena — užuominoje (title).
export function renderHealth() {
  const { overall, services } = state.health;
  const badgeEl = el("health-badge");
  if (!badgeEl) return;
  while (badgeEl.firstChild) badgeEl.removeChild(badgeEl.firstChild);
  const dot = document.createElement("span");
  dot.className = "app-dot";
  dot.style.background = HEALTH_COLOR[overall] || HEALTH_COLOR.unknown;
  const label = document.createElement("span");
  label.textContent = t("badge_" + overall) || t("badge_unknown");
  badgeEl.append(dot, label);
  badgeEl.title = (services || []).map(s => `${s.label}: ${s.message}`).join("\n");
}

function alertMatchesQuery(a, q) {
  if (!q) return true;
  const fields = [
    alertTitle(a.alert_type, a.title || ""),
    a.source_ip || "",
    a.source_host || "",
    a.severity || "",
    a.alert_type || "",
  ];
  return fields.some(f => f.toLowerCase().includes(q));
}

// Įspėjimų šaltinis priklauso nuo to, ar įjungtas „Žiūrėti viską" rodinys.
function activeAlerts() {
  return (state.showAllAlerts && state.allAlerts.length) ? state.allAlerts : state.alerts;
}

export function filteredAlerts() {
  const src = activeAlerts();
  const q = state.search;
  return q ? src.filter(a => alertMatchesQuery(a, q)) : src;
}

export function filteredDevices() {
  const q = state.search;
  if (!q) return state.devices;
  return state.devices.filter(d =>
    [d.name, d.ip, d.hostname, d.os].some(f => String(f || "").toLowerCase().includes(q))
  );
}

// Lietuviška daiktavardžių linksniavimas pagal kiekį.
// 1, 21, 31, ... → "rezultatas" (vienaskaita)
// 0, 10-19, 20, ... → "rezultatų" (kilmininkas)
// 2-9, 22-29, ... → "rezultatai" (daugiskaita)
function ltResultsWord(n) {
  const last2 = n % 100;
  const last = n % 10;
  if (last2 >= 11 && last2 <= 19) return "rezultatų";
  if (last === 1) return "rezultatas";
  if (last >= 2 && last <= 9) return "rezultatai";
  return "rezultatų";
}

export function updateSearchUI() {
  const clearBtn  = el("search-clear");
  const countEl   = el("search-count");
  const q         = state.search;

  if (clearBtn) clearBtn.classList.toggle("hidden", !q);

  if (!countEl) return;
  if (!q) {
    countEl.classList.add("hidden");
    return;
  }

  let count = 0;
  if (state.page === "anomalies") count = filteredAlerts().length;
  else if (state.page === "devices") count = filteredDevices().length;
  else count = filteredAlerts().length;

  countEl.textContent = state.lang === "lt"
    ? `${count} ${ltResultsWord(count)}`
    : `${count} result${count === 1 ? "" : "s"}`;
  countEl.classList.remove("hidden");
}
