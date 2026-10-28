// Anomalijų puslapis: srauto pulsas, įvykių tipai, chronologija, žali logai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { alertExpl, alertTitle, t } from "../i18n.js";
import { ANOMALY_CARD_CFG, alertRow } from "../alert-dialog.js";
import { filteredAlerts, updateSearchUI } from "../shell.js";
import { applyAxes, areaFill, forget, themeOptions, token, track } from "../charts.js";

// main.js duomenų įkėlimo funkcijos (puslapiai main.js neimportuoja).
let ctx = {};

export function renderAnomaliesPage() {
  updateSearchUI();
  renderPulseChart();
  renderAnomalyCards();
  renderChronology();
  populateLogsHostSelect();
  renderRawLogs();
}

export function renderPulseChart() {
  const canvas  = el("pulse-chart");
  const emptyEl = el("pulse-empty");
  if (!canvas) return;

  const pts = state.history;
  if (!pts.length) {
    if (state.pulseChart) { forget(state.pulseChart); state.pulseChart.destroy(); state.pulseChart = null; }
    canvas.classList.add("hidden");
    if (emptyEl) { emptyEl.classList.remove("hidden"); emptyEl.textContent = t("no_events"); }
    return;
  }
  canvas.classList.remove("hidden");
  if (emptyEl) emptyEl.classList.add("hidden");

  // Suskaičiuojame realius alertus per kiekvieną laiko bucket'ą — taškas raudonas,
  // kai tame intervale buvo aptiktas alertas (nuokrypis nuo normalaus pulso).
  const bucketStart = pts.map(p => new Date(p.time).getTime());
  const bucketEnd = bucketStart.map((s, i) =>
    i + 1 < bucketStart.length ? bucketStart[i + 1] : s + 60 * 60 * 1000
  );
  const alertCounts = bucketStart.map(() => 0);
  for (const a of state.alerts) {
    const ts = new Date(a.timestamp).getTime();
    if (!Number.isFinite(ts)) continue;
    for (let i = 0; i < bucketStart.length; i++) {
      if (ts >= bucketStart[i] && ts < bucketEnd[i]) { alertCounts[i]++; break; }
    }
  }

  const locale = state.lang === "lt" ? "lt-LT" : "en-GB";
  const labels = pts.map(p => new Date(p.time).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" }));
  const values = pts.map(p => p.count);
  const pointRadii  = alertCounts.map(c => (c > 0 ? 5 : 0));

  if (state.pulseChart) {
    const ch = state.pulseChart;
    ch.data.labels = labels;
    ch.data.datasets[0].data = values;
    ch.data.datasets[0].pointRadius = pointRadii;
    ch._alertCounts = alertCounts;
    restylePulseChart(ch, themeOptions());
    ch.update("none");
    return;
  }

  state.pulseChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Logs",
        data: values,
        backgroundColor: areaFill("--ok", 0.18),
        fill: true,
        tension: 0.35,
        borderWidth: 1.5,
        pointRadius: pointRadii,
        pointHoverRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const ac = (state.pulseChart && state.pulseChart._alertCounts) || [];
              const n = ac[ctx.dataIndex] || 0;
              return n > 0 ? `${ctx.parsed.y} logs · ${n} ⚠` : `${ctx.parsed.y} logs`;
            },
          },
        },
      },
      scales: {
        x: { ticks: { maxTicksLimit: 8 } },
        y: { beginAtZero: true },
      },
    },
  });
  state.pulseChart._alertCounts = alertCounts;
  restylePulseChart(state.pulseChart, themeOptions());
  state.pulseChart.update("none");
  track(state.pulseChart, restylePulseChart);
}

// Taškas raudonas, kai tame intervale buvo alertas; spalvos — iš temos.
function restylePulseChart(chart, o) {
  const ok = token("--ok");
  const crit = token("--crit");
  const colors = (chart._alertCounts || []).map(c => (c > 0 ? crit : ok));
  Object.assign(chart.data.datasets[0], { borderColor: ok, pointBackgroundColor: colors, pointBorderColor: colors });
  applyAxes(chart, o);
}

// Rizikos spalva ir užrašas įvykio tipo skydeliui (pagal ANOMALY_CARD_CFG.risk).
const RISK = {
  critical: { cls: "text-crit", key: "sev_critical" },
  medium:   { cls: "text-warn", key: "sev_medium" },
  warning:  { cls: "text-warn", key: "badge_warning" },
};

// Vienas skydelis kiekvienam iš 3 dažniausių įvykio tipų: skaičius ir rizika.
function renderAnomalyCards() {
  const cardsEl = el("anomaly-cards");
  if (!cardsEl) return;
  cardsEl.textContent = "";

  const counts = {};
  for (const a of filteredAlerts()) counts[a.alert_type] = (counts[a.alert_type] || 0) + 1;
  const top3 = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);

  if (!top3.length) {
    const empty = document.createElement("div");
    empty.className = "panel col-span-12 empty";
    empty.textContent = t("anomaly_cards_empty");
    cardsEl.appendChild(empty);
    return;
  }

  top3.forEach(([type, n]) => {
    const cfg = ANOMALY_CARD_CFG[type] || ANOMALY_CARD_CFG.high_error_rate;
    const risk = RISK[cfg.risk] || { cls: "text-muted", key: "" };
    const panel = document.createElement("div");
    panel.className = "panel stat col-span-12 md:col-span-4";
    panel.title = alertExpl(type);
    const head = document.createElement("div");
    head.className = "panel-h";
    const name = document.createElement("span");
    name.textContent = alertTitle(type, type);
    const label = document.createElement("span");
    label.className = `panel-sub ${risk.cls}`;
    label.textContent = risk.key ? t(risk.key) : "";
    head.append(name, label);
    const value = document.createElement("div");
    value.className = `stat-v ${risk.cls}`;
    value.textContent = String(n);
    panel.append(head, value);
    cardsEl.appendChild(panel);
  });
}

function renderChronology() {
  const tbody = el("chronology-table");
  if (!tbody) return;
  tbody.textContent = "";
  setText("view-all-chrono", state.showAllAlerts ? t("show_less") : t("view_all_chrono"));

  const alerts = filteredAlerts();
  if (!alerts.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.className = "empty";
    td.textContent = t("no_events");
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }
  (state.showAllAlerts ? alerts : alerts.slice(0, 20)).forEach(a => tbody.appendChild(alertRow(a)));
}

async function toggleShowAllAlerts() {
  state.showAllAlerts = !state.showAllAlerts;
  if (state.showAllAlerts) await ctx.loadAllAlerts();
  renderAnomaliesPage();
}

// Kairiosios juostelės spalva pagal syslog lygį.
const LOG_SEV_COLOR = {
  emerg: "var(--crit)", alert: "var(--crit)", crit: "var(--crit)", err: "var(--crit)", error: "var(--crit)",
  warning: "var(--warn)", warn: "var(--warn)",
  notice: "var(--ok)", info: "var(--ok)", debug: "var(--text-dim)",
};

function onLogsHostChange() {
  const sel = el("logs-host-select");
  state.logsHost = sel ? sel.value : "";
  ctx.loadRawLogs();
}

export function populateLogsHostSelect() {
  const sel = el("logs-host-select");
  if (!sel) return;
  const cur = state.logsHost;
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
  if (sel.value !== cur) { state.logsHost = ""; sel.value = ""; }
}

function logMatchesQuery(l, q) {
  if (!q) return true;
  return [l.line, l.host, l.program, l.severity]
    .some(f => String(f || "").toLowerCase().includes(q));
}

export function renderRawLogs() {
  const listEl = el("logs-list");
  const emptyEl = el("logs-empty");
  if (!listEl) return;
  listEl.textContent = "";

  const q = state.search;
  const logs = q ? state.rawLogs.filter(l => logMatchesQuery(l, q)) : state.rawLogs;

  if (!logs.length) {
    if (emptyEl) { emptyEl.classList.remove("hidden"); emptyEl.textContent = t("logs_empty"); }
    return;
  }
  if (emptyEl) emptyEl.classList.add("hidden");

  logs.forEach(l => {
    const row = document.createElement("div");
    row.className = "ln";
    row.style.borderLeftColor = LOG_SEV_COLOR[l.severity] || "var(--text-dim)";
    row.textContent = l.line || "";
    listEl.appendChild(row);
  });
}

export function init(context) {
  ctx = context;
  el("view-all-chrono")?.addEventListener("click", toggleShowAllAlerts);
  el("logs-host-select")?.addEventListener("change", onLogsHostChange);
  el("logs-refresh-btn")?.addEventListener("click", () => ctx.loadRawLogs());
}

export const render = renderAnomaliesPage;
