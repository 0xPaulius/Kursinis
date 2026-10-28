// Puslapio rėmas: navigacija, sistemos būklė, paieška.

import { el, setText } from "./dom.js";
import { state } from "./state.js";
import { alertTitle, t } from "./i18n.js";

const PAGES = ["dashboard", "anomalies", "devices", "attack", "messages"];
let onEnter = () => {};

// main.js perduoda, ką daryti atidarius puslapį; puslapis laikomas URL #fragmente.
export function initNavigation(enter) {
  onEnter = enter;
  document.querySelectorAll("[data-nav]").forEach(btn =>
    btn.addEventListener("click", () => navigate(btn.dataset.nav)));
  window.addEventListener("hashchange", () => showPage(pageFromHash()));
  showPage(pageFromHash());
}

export function navigate(page) {
  if (location.hash === "#" + page) showPage(page);
  else location.hash = page;
}

function pageFromHash() {
  const page = location.hash.slice(1);
  return PAGES.includes(page) ? page : "dashboard";
}

function showPage(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  PAGES.forEach(p => { const b = el("nav-" + p); if (b) b.classList.toggle("active", p === page); });
  state.page = page;
  onEnter(page);
}

export function renderHealth() {
  const { overall, services } = state.health;
  const badgeEl = el("health-badge");
  if (!badgeEl) return;

  const cfgMap = {
    ok:       { dot: "bg-secondary animate-pulse", bg: "bg-secondary-container",  text: "text-on-secondary-container" },
    warning:  { dot: "bg-yellow-500",              bg: "bg-tertiary-fixed",        text: "text-on-tertiary-container"  },
    critical: { dot: "bg-error animate-pulse",     bg: "bg-error-container",       text: "text-on-error-container"     },
    unknown:  { dot: "bg-outline",                 bg: "bg-surface-container",     text: "text-on-surface-variant"     },
  };
  const cfg = cfgMap[overall] || cfgMap.unknown;

  // Build badge using safe DOM methods
  badgeEl.className = `flex items-center gap-2 px-3 py-1.5 rounded-full ${cfg.bg}`;
  while (badgeEl.firstChild) badgeEl.removeChild(badgeEl.firstChild);

  const dot = document.createElement("div");
  dot.className = `w-2 h-2 rounded-full ${cfg.dot}`;
  badgeEl.appendChild(dot);

  const label = document.createElement("span");
  label.className = `text-[10px] font-bold tracking-wide uppercase font-label ${cfg.text}`;
  label.textContent = t("badge_" + overall) || t("badge_unknown");
  badgeEl.appendChild(label);

  // Hero
  const titleKey = { ok: "hero_safe", warning: "hero_warning", critical: "hero_critical" };
  setText("hero-title", t(titleKey[overall] || "hero_safe"));
  setText("hero-desc",  t(overall === "ok" ? "hero_desc_safe" : "hero_desc_warn"));
  setText("hero-uptime", (services || []).every(s => s.status === "ok") ? "100%" : "—");
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
