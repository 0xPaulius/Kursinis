// Įrenginio detalių puslapis (#devices/<raktas>): būsena, programos, informacija, veiksmai ir įspėjimai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { fetchJSON } from "../api.js";
import { alertTitle, t } from "../i18n.js";
import { durationFmt, fullTime, loadFmt, LOG_SEV_COLOR, numFmt, pctFmt, relTime, shortTime, sizeFmt } from "../format.js";
import { navigate, setCrumb } from "../shell.js";
import { sparkline, token } from "../charts.js";
import { openAlertInfo, sevBadge } from "../alert-dialog.js";
import { deviceKey, osLabel, sourceLabel } from "./device-meta.js";

// main.js funkcijos (klaidų juosta); puslapiai main.js neimportuoja.
let ctx = {};

const STALE_MS = 3 * 60 * 1000;   // senesnė būsena rodoma kaip pasenusi
const REFRESH_MS = 12000;         // SSE „devices" įvykiai detalių neperkrauna dažniau
const LOG_LIMIT = 100;

// Veiksmo rūšis -> ikona; crit — raudona eilutė.
const KIND_META = {
  login:       { icon: "login" },
  auth_failed: { icon: "lock", crit: true },
  admin:       { icon: "admin_panel_settings" },
  account:     { icon: "manage_accounts" },
  command:     { icon: "terminal" },
  script:      { icon: "code" },
  boot:        { icon: "power_settings_new" },
  log_cleared: { icon: "delete_history", crit: true },
  update:      { icon: "system_update" },
};

function currentDevice() {
  return state.devices.find(d => deviceKey(d) === state.deviceKey) || null;
}

// Detalės rodomos tik to įrenginio, kurio raktas dabar URL'e.
function currentDetail() {
  return state.deviceDetailKey === state.deviceKey ? state.deviceDetail : null;
}

function isStale(status) {
  return Date.now() - new Date(status.time).getTime() > STALE_MS;
}

// -- Duomenys -------------------------------------------------------------------

// Atidarius įrenginį (ar perėjus prie kito) — iš naujo ir nuo viršaus.
export function openDeviceDetail() {
  if (state.deviceDetailKey !== state.deviceKey) {
    state.deviceDetail = null;
    state.deviceDetailKey = "";
    state.deviceLogs = null;
    state.deviceTab = "actions";
    window.scrollTo(0, 0);
  }
  loadDeviceDetail();
}

export async function loadDeviceDetail() {
  const key = state.deviceKey;
  if (!key) return;
  state._lastDeviceDetail = Date.now();
  try {
    const data = await fetchJSON(`/api/devices/${encodeURIComponent(key)}/details`);
    if (state.deviceKey !== key) return;    // kol laukėme, atidarytas kitas puslapis
    state.deviceDetail = data;
    state.deviceDetailKey = key;
  } catch (e) {
    if (state.deviceKey === key) ctx.loadFailed("Device detail:", e);
  }
  if (state.deviceKey === key && state.deviceTab === "logs") await loadDeviceLogs();
  if (state.page === "devices" && state.deviceKey === key) renderDeviceDetail();
}

async function loadDeviceLogs() {
  const d = currentDevice();
  if (!d) return;
  try {
    const data = await fetchJSON(`/api/traffic/logs?limit=${LOG_LIMIT}&host=${encodeURIComponent(d.hostname)}`);
    if (deviceKey(d) === state.deviceKey) state.deviceLogs = data.lines || [];
  } catch (e) {
    ctx.loadFailed("Device logs:", e);
  }
}

// SSE „devices" įvykis (~kas 15 s): detalės perkraunamos ne dažniau nei kas REFRESH_MS.
export function maybeRefreshDeviceDetail() {
  if (state.page !== "devices" || !state.deviceKey) return;
  if (Date.now() - state._lastDeviceDetail >= REFRESH_MS) loadDeviceDetail();
}

function selectTab(tab) {
  if (state.deviceTab === tab) return;
  state.deviceTab = tab;
  renderDeviceDetail();
  if (tab === "logs") loadDeviceLogs().then(renderDeviceDetail);
}

function sortPrograms(by) {
  state.deviceSort = by;
  renderDeviceDetail();
}

// -- Piešimas -------------------------------------------------------------------

export function renderDeviceDetail() {
  const d = currentDevice();
  const missing = state.devicesLoaded && !d;
  el("dd-notfound")?.classList.toggle("hidden", !missing);
  el("dd-body")?.classList.toggle("hidden", missing);
  setCrumb(d ? `${t("nav_devices")} › ${d.name}` : t("nav_devices"));
  const detail = currentDetail();
  renderHeader(d, detail);
  if (!d) return;
  renderTiles(d, detail);
  renderPrograms(detail);
  renderInfo(d, detail);
  renderActivity(detail);
  renderAlerts(detail);
}

function renderHeader(d, detail) {
  setText("dd-name", d ? d.name : "—");
  const dot = el("dd-dot");
  if (dot) dot.className = "app-dot" + (d && d.alert_count > 0 ? " bg-crit" : d && d.online ? " bg-ok" : "");
  // Versija (pvz. „Ubuntu Server 22.04 LTS") jau pasako OS; be jos — OS pavadinimas.
  setText("dd-meta", d ? [d.os_version || osLabel(d), d.ip].filter(Boolean).join(" · ") : "");
  const status = detail && detail.status;
  const updated = el("dd-updated");
  if (!updated) return;
  const stale = !!status && isStale(status);
  updated.textContent = status ? t(stale ? "dd_stale" : "dd_updated")(relTime(status.time)) : "";
  updated.classList.toggle("text-warn", stale);
}

function renderTiles(d, detail) {
  const status = detail && detail.status;
  const showTiles = !detail || !!status;          // kol kraunama — tušti langeliai
  document.querySelectorAll("#device-detail .dd-tile").forEach(n => {
    n.classList.toggle("hidden", !showTiles);
    n.classList.toggle("dd-stale", !!status && isStale(status));
  });
  el("dd-nostatus")?.classList.toggle("hidden", showTiles);
  if (!showTiles) {
    setText("dd-nostatus-text", t(d.source === "self" ? "dd_nostatus_self" : "dd_nostatus_other"));
    return;
  }
  const s = status || {};
  // Veikimo laikas „bėga" ir tarp įrašų.
  const age = status ? Math.max(0, (Date.now() - new Date(status.time).getTime()) / 1000) : 0;
  setText("dd-uptime", s.uptime_s != null ? durationFmt(s.uptime_s + age) : "—");
  setText("dd-cpu", pctFmt(s.cpu_pct));
  setText("dd-cpu-sub", s.cpus ? t("dd_cpu_sub")(s.cpus) : "");
  const memUsed = s.mem_total_kb != null && s.mem_avail_kb != null ? s.mem_total_kb - s.mem_avail_kb : null;
  setText("dd-mem", memUsed != null && s.mem_total_kb ? pctFmt(100 * memUsed / s.mem_total_kb) : "—");
  setText("dd-mem-sub", memUsed != null ? t("dd_used_of")(sizeFmt(memUsed), sizeFmt(s.mem_total_kb)) : "");
  const diskTotal = s.disk_used_kb != null && s.disk_avail_kb != null ? s.disk_used_kb + s.disk_avail_kb : 0;
  setText("dd-disk", diskTotal ? pctFmt(100 * s.disk_used_kb / diskTotal) : "—");
  setText("dd-disk-sub", diskTotal ? t("dd_used_of")(sizeFmt(s.disk_used_kb), sizeFmt(diskTotal)) : "");
  const history = (detail && detail.history) || [];
  spark("dd-cpu-spark", history.map(p => p.cpu_pct), "--accent");
  spark("dd-mem-spark", history.map(p => p.mem_pct), "--ok");
}

function spark(id, values, color) {
  const svg = el(id);
  if (svg) sparkline(svg, values.filter(v => v != null), token(color), 100);   // skalė 0–100 %
}

function cell(tr, text, cls) {
  const td = document.createElement("td");
  if (cls) td.className = cls;
  td.textContent = text;
  tr.appendChild(td);
  return td;
}

function emptyRow(tbody, cols, text) {
  const tr = document.createElement("tr");
  cell(tr, text, "empty").colSpan = cols;
  tbody.appendChild(tr);
}

function renderPrograms(detail) {
  const tbody = el("dd-programs-tbody");
  if (!tbody) return;
  ["cpu", "mem"].forEach(k => el(`dd-sort-${k}`)?.classList.toggle("is-sorted", state.deviceSort === k));
  tbody.textContent = "";
  const status = detail && detail.status;
  setText("dd-programs-foot", status && status.procs != null
    ? t("dd_programs_foot")(numFmt(status.procs), status.users.join(", ") || "—") : "");
  if (!detail) return;
  const by = state.deviceSort === "mem" ? "mem_kb" : "cpu_pct";
  const programs = status ? [...status.programs].sort((a, b) => b[by] - a[by] || b.mem_kb - a.mem_kb) : [];
  if (!programs.length) {
    emptyRow(tbody, 4, t("dd_no_programs"));
    return;
  }
  programs.forEach(p => {
    const tr = document.createElement("tr");
    cell(tr, p.name, "mono text-strong");
    cell(tr, numFmt(p.processes), "mono text-muted text-right");
    cell(tr, pctFmt(p.cpu_pct), "mono text-right");
    cell(tr, sizeFmt(p.mem_kb), "mono text-right");
    tbody.appendChild(tr);
  });
}

function renderInfo(d, detail) {
  const dl = el("dd-info");
  if (!dl) return;
  const rows = [
    [t("info_status_label"),   d.online ? t("dev_status_online") : t("dev_status_offline")],
    [t("info_source_label"),   sourceLabel(d)],
    [t("info_ip_label"),       d.ip || "—", "mono"],
    // Savo serverio realaus hostname nerodome (privatumas).
    [t("info_hostname_label"), d.source === "self" ? "—" : d.hostname, "mono"],
    [t("info_os_label"),       osLabel(d)],
    [t("info_version_label"),  d.os_version || "—"],
    [t("info_lastseen_label"), d.last_seen ? relTime(d.last_seen) : t("dev_never")],
    [t("info_logs5m_label"),   numFmt(d.logs_5m || 0), "mono"],
    [t("info_logs1h_label"),   numFmt(d.logs_1h || 0), "mono"],
    [t("info_alerts_label"),   numFmt(d.alert_count || 0), "mono"],
  ];
  const s = detail && detail.status;
  if (s) {
    if (s.cpus != null) rows.push([t("dd_cores"), numFmt(s.cpus), "mono"]);
    if (s.load.length) rows.push([t("dd_load"), s.load.map(loadFmt).join(" / "), "mono"]);
    if (s.procs != null) rows.push([t("dd_procs"), numFmt(s.procs), "mono"]);
    rows.push([t("dd_users"), s.users.join(", ") || "—"]);
  }
  dl.textContent = "";
  rows.forEach(([label, value, cls]) => {
    const row = document.createElement("div");
    row.className = "flex justify-between gap-4";
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    if (cls) dd.className = cls;
    dd.textContent = value;
    row.append(dt, dd);
    dl.appendChild(row);
  });
}

function emptyBox(text) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = text;
  return p;
}

function skeleton() {
  const div = document.createElement("div");
  div.className = "skeleton h-4 w-1/2 mx-auto my-4";
  return div;
}

function renderActivity(detail) {
  el("dd-tab-actions")?.classList.toggle("is-active", state.deviceTab === "actions");
  el("dd-tab-logs")?.classList.toggle("is-active", state.deviceTab === "logs");
  const feed = el("dd-activity");
  const logs = el("dd-logs");
  if (!feed || !logs) return;
  feed.classList.toggle("hidden", state.deviceTab !== "actions");
  logs.classList.toggle("hidden", state.deviceTab !== "logs");
  if (state.deviceTab === "logs") renderLogs(logs);
  else renderFeed(feed, detail ? detail.activity : null);
}

function renderFeed(feed, items) {
  feed.textContent = "";
  if (!items) {
    feed.appendChild(skeleton());
    return;
  }
  if (!items.length) {
    feed.appendChild(emptyBox(t("dd_no_activity")));
    return;
  }
  const kinds = t("dd_kind");
  items.forEach(a => {
    const meta = KIND_META[a.kind] || { icon: "info" };
    const row = document.createElement("div");
    row.className = "dd-item" + (meta.crit ? " is-crit" : "");
    const time = document.createElement("span");
    time.className = "mono text-muted";
    time.textContent = shortTime(a.time);
    time.title = fullTime(a.time);
    const icon = document.createElement("span");
    icon.className = "material-symbols-outlined";
    icon.textContent = meta.icon;
    const body = document.createElement("div");
    body.className = "dd-text";
    const head = document.createElement("div");
    head.className = "dd-kind font-medium text-strong";
    const label = kinds[a.kind] || a.kind;
    head.textContent = a.user ? `${label} · ${a.user}` : label;
    const text = document.createElement("div");
    text.className = "text-muted";
    text.textContent = a.text;
    body.append(head, text);
    row.append(time, icon, body);
    feed.appendChild(row);
  });
}

function renderLogs(box) {
  box.textContent = "";
  if (state.deviceLogs === null) {
    box.appendChild(skeleton());
    return;
  }
  if (!state.deviceLogs.length) {
    box.appendChild(emptyBox(t("logs_empty")));
    return;
  }
  state.deviceLogs.forEach(l => {
    const row = document.createElement("div");
    row.className = "ln";
    row.style.borderLeftColor = LOG_SEV_COLOR[l.severity] || "var(--text-dim)";
    row.textContent = l.line || "";
    box.appendChild(row);
  });
}

function renderAlerts(detail) {
  const tbody = el("dd-alerts-tbody");
  if (!tbody) return;
  tbody.textContent = "";
  if (!detail) return;
  if (!detail.alerts.length) {
    emptyRow(tbody, 3, t("dd_no_alerts"));
    return;
  }
  detail.alerts.forEach(a => {
    const tr = document.createElement("tr");
    tr.className = "is-click";
    tr.addEventListener("click", () => openAlertInfo(a));
    cell(tr, shortTime(a.timestamp), "mono text-muted whitespace-nowrap");
    cell(tr, "").appendChild(sevBadge(a.severity));
    cell(tr, alertTitle(a.alert_type, a.title));
    tbody.appendChild(tr);
  });
}

export function init(context) {
  ctx = context;
  document.querySelectorAll("[data-dd-back]").forEach(b => b.addEventListener("click", () => navigate("devices")));
  el("dd-tab-actions")?.addEventListener("click", () => selectTab("actions"));
  el("dd-tab-logs")?.addEventListener("click", () => selectTab("logs"));
  el("dd-sort-cpu")?.addEventListener("click", () => sortPrograms("cpu"));
  el("dd-sort-mem")?.addEventListener("click", () => sortPrograms("mem"));
}
