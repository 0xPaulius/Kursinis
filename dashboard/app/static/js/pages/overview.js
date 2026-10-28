// Apžvalgos puslapis: rodikliai, laiko intervalas, srauto grafikas, svarbiausi įvykiai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { sevLabel, t } from "../i18n.js";
import { numFmt, relTime } from "../format.js";
import { alertRow } from "../alert-dialog.js";
import { applyAxes, areaFill, sparkline, themeOptions, token, track } from "../charts.js";

// main.js duomenų įkėlimo funkcijos (puslapiai main.js neimportuoja).
let ctx = {};

const TIME_RANGES = [
  { h: 1,   key: "range_1h"  },
  { h: 6,   key: "range_6h"  },
  { h: 12,  key: "range_12h" },
  { h: 24,  key: "range_24h" },
  { h: 48,  key: "range_2d"  },
  { h: 168, key: "range_7d"  },
];

function currentRangeLabel() {
  const r = TIME_RANGES.find(x => x.h === state.rangeHours) || TIME_RANGES[3];
  return t(r.key);
}

export function renderRangeMenu() {
  const menu = el("range-menu");
  if (!menu) return;
  menu.textContent = "";
  TIME_RANGES.forEach(r => {
    const btn = document.createElement("button");
    btn.className = "menu-item" + (r.h === state.rangeHours ? " is-active" : "");
    btn.textContent = t(r.key);
    btn.addEventListener("click", () => setRange(r.h));
    menu.appendChild(btn);
  });
  setText("range-label", currentRangeLabel());
  setText("last-24h-label", currentRangeLabel());
}

function toggleRangeMenu(ev) {
  if (ev) ev.stopPropagation();
  const menu = el("range-menu");
  if (menu) menu.classList.toggle("hidden");
}

export function closeRangeMenu() {
  const menu = el("range-menu");
  if (menu) menu.classList.add("hidden");
}

function setRange(hours) {
  state.rangeHours = hours;
  localStorage.setItem("range_hours", String(hours));
  closeRangeMenu();
  renderRangeMenu();
  ctx.loadTrafficHistory();
}

function errorCount() {
  if (!state.current) return 0;
  // Alloy iš syslog-ng išgauna tik standartines syslog severity etiketes:
  // emerg, alert, crit, err, warning, notice, info, debug. Skaičiuojame klaidų lygius.
  const s = state.current.by_severity || {};
  return (s.emerg || 0) + (s.alert || 0) + (s.crit || 0) + (s.err || 0);
}

function logRate() {
  if (!state.history.length) return 0;
  const recent = state.history.slice(-6);
  return Math.round(recent.reduce((a, p) => a + p.count, 0) / recent.length);
}

// Reikšmės spalva pagal slenkstį (tos pačios ribos kaip ankstesnių ženklelių).
const STAT_COLORS = ["text-ok", "text-warn", "text-crit"];

function setStat(id, text, colorCls) {
  const e = el(id);
  if (!e) return;
  e.textContent = text;
  e.classList.remove(...STAT_COLORS);
  if (colorCls) e.classList.add(colorCls);
}

export function renderMetrics() {
  const total  = state.current ? (state.current.total || 0) : 0;
  const errors = errorCount();
  const rate   = logRate();
  const hasNow = !!state.current;
  const hasHistory = state.history.length > 0;
  const logsColor = total > 1000 ? "warn" : "ok";
  const rateColor = rate > 500 ? "warn" : "ok";

  setStat("metric-logs-value", hasNow ? numFmt(total) : "—", hasNow ? `text-${logsColor}` : "");
  setStat("metric-errors-value", hasNow ? String(errors) : "—", hasNow ? (errors > 0 ? "text-crit" : "text-ok") : "");
  const share = (errors / total * 100).toLocaleString(state.lang === "lt" ? "lt-LT" : "en-GB", { maximumFractionDigits: 1 });
  setText("metric-errors-pct", hasNow && total > 0 ? `${share} %` : "");
  setStat("metric-rate-value", hasHistory ? numFmt(rate) : "—", hasHistory ? `text-${rateColor}` : "");

  const recent = state.history.slice(-12).map(p => p.count);
  const logsSpark = el("metric-logs-spark");
  const rateSpark = el("metric-rate-spark");
  if (logsSpark) sparkline(logsSpark, recent, token(`--${logsColor}`));
  if (rateSpark) sparkline(rateSpark, recent, token(`--${rateColor}`));
}

export function renderTrafficChart() {
  const canvas = el("traffic-chart");
  if (!canvas || !state.history.length) return;

  const locale = state.lang === "lt" ? "lt-LT" : "en-GB";
  const labels = state.history.map(p =>
    new Date(p.time).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })
  );
  const values = state.history.map(p => p.count);
  const total  = values.reduce((a, b) => a + b, 0);
  const peak   = Math.max(...values, 0);

  setText("chart-total", numFmt(total) + " " + t("logs_unit"));
  setText("chart-peak",  numFmt(peak));
  setText("traffic-avg",  numFmt(Math.round(total / values.length)));
  setText("traffic-max",  numFmt(peak));
  setText("traffic-last", numFmt(values[values.length - 1]));

  if (state.trafficChart) {
    state.trafficChart.data.labels = labels;
    state.trafficChart.data.datasets[0].data = values;
    state.trafficChart.update("none");
    return;
  }

  const chart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Logs",
        data: values,
        backgroundColor: areaFill("--ok"),
        fill: true,
        tension: 0.35,
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y} logs` } },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8 } },
        y: { beginAtZero: true },
      },
    },
  });
  restyleTrafficChart(chart, themeOptions());
  chart.update("none");
  state.trafficChart = track(chart, restyleTrafficChart);
}

function restyleTrafficChart(chart, o) {
  const color = token("--ok");
  Object.assign(chart.data.datasets[0], { borderColor: color, pointBackgroundColor: color });
  applyAxes(chart, o);
}

function onTrafficDeviceChange() {
  const sel = el("traffic-device-select");
  state.trafficHost = sel ? sel.value : "";
  ctx.loadTrafficHistory();
  renderTrafficDeviceStats();
}

export function populateTrafficDeviceSelect() {
  const sel = el("traffic-device-select");
  if (!sel) return;
  const cur = state.trafficHost;
  sel.textContent = "";
  const optAll = document.createElement("option");
  optAll.value = "";
  optAll.textContent = t("dev_all");
  sel.appendChild(optAll);
  state.devices.forEach(d => {
    const o = document.createElement("option");
    o.value = d.hostname;
    o.textContent = d.ip ? `${d.name} (${d.ip})` : d.name;
    sel.appendChild(o);
  });
  sel.value = cur;
  if (sel.value !== cur) {            // anksčiau pasirinktas įrenginys dingo iš sąrašo
    state.trafficHost = "";
    sel.value = "";
  }
}

export function renderTrafficDeviceStats() {
  const box = el("traffic-device-stats");
  if (!box) return;
  const d = state.trafficHost ? state.devices.find(x => x.hostname === state.trafficHost) : null;
  if (!d) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  setText("tds-status",   d.online ? t("dev_status_online") : t("dev_status_offline"));
  setText("tds-logs5m",   numFmt(d.logs_5m || 0));
  setText("tds-lastseen", d.last_seen ? relTime(d.last_seen) : t("dev_never"));
  setText("tds-alerts",   String(d.alert_count || 0));
}

function emptyRow(tbody, cols, text) {
  const tr = document.createElement("tr");
  const td = document.createElement("td");
  td.colSpan = cols;
  td.className = "empty";
  td.textContent = text;
  tr.appendChild(td);
  tbody.appendChild(tr);
}

function renderKeyEvents() {
  const tbody = el("key-events-table");
  if (!tbody) return;
  tbody.textContent = "";
  if (!state.alerts.length) { emptyRow(tbody, 6, t("no_events")); return; }
  state.alerts.slice(0, 4).forEach(a => tbody.appendChild(alertRow(a)));
}

function renderThreats() {
  const n = state.alerts.filter(a => a.severity === "critical" || a.severity === "high").length;
  setText("hero-threats", String(n));
  el("threat-panel")?.classList.toggle("stat-threat", n > 0);
}

const SEVERITIES = ["critical", "high", "medium", "low"];

// Tie patys 20 naujausių įspėjimų, suskirstyti pagal lygį.
function renderSeverityBreakdown() {
  const box = el("sev-breakdown");
  if (!box) return;
  box.textContent = "";
  if (!state.alerts.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = t("no_events");
    box.appendChild(empty);
    return;
  }
  const counts = Object.fromEntries(SEVERITIES.map(s => [s, 0]));
  state.alerts.forEach(a => { if (a.severity in counts) counts[a.severity]++; });
  const max = Math.max(1, ...Object.values(counts));
  SEVERITIES.forEach(s => {
    const row = document.createElement("div");
    row.className = "gauge-row";
    const label = document.createElement("span");
    label.textContent = sevLabel(s);
    const trackEl = document.createElement("div");
    trackEl.className = "gauge-track";
    const fill = document.createElement("div");
    fill.className = `gauge-fill bg-sev-${s}`;
    fill.style.width = `${counts[s] / max * 100}%`;
    trackEl.appendChild(fill);
    const count = document.createElement("b");
    count.className = `sev-${s}`;
    count.textContent = String(counts[s]);
    row.append(label, trackEl, count);
    box.appendChild(row);
  });
}

// Viskas, kas priklauso nuo įspėjimų sąrašo (kviečiama ir gavus naujus įspėjimus).
export function renderAlertPanels() {
  renderKeyEvents();
  renderThreats();
  renderSeverityBreakdown();
}

export function init(context) {
  ctx = context;
  el("range-btn")?.addEventListener("click", toggleRangeMenu);
  el("traffic-device-select")?.addEventListener("change", onTrafficDeviceChange);
  el("refresh-btn")?.addEventListener("click", () => { ctx.loadTrafficHistory(); ctx.loadTrafficCurrent(); });
}

export function render() {
  renderMetrics();
  renderAlertPanels();
  renderTrafficChart();
  populateTrafficDeviceSelect();
  renderTrafficDeviceStats();
}
