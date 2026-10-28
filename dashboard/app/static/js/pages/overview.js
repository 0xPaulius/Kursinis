// Apžvalgos puslapis: rodikliai, laiko intervalas, srauto grafikas, svarbiausi įvykiai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { alertTitle, t } from "../i18n.js";
import { numFmt, relTime } from "../format.js";
import { navigate } from "../shell.js";

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
    const active = r.h === state.rangeHours;
    btn.className = "w-full text-left px-4 py-2 text-label-md font-label transition-colors " +
      (active
        ? "bg-secondary-container text-on-secondary-container font-bold"
        : "text-on-surface hover:bg-surface-container-high");
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

export function renderMetrics() {
  const total  = state.current ? (state.current.total || 0) : 0;
  const errors = errorCount();
  const rate   = logRate();

  // Logs
  setText("metric-logs-value", state.current ? numFmt(total) : "—");
  setMetricBadge("metric-logs-badge", total > 1000 ? "high" : "normal");
  setBarWidth("metric-logs-bar", Math.min(100, total / 10));

  // Klaidos
  setText("metric-errors-value", state.current ? String(errors) : "—");
  setMetricBadge("metric-errors-badge", errors > 0 ? "error" : "ok");
  const errBar = el("metric-errors-bar");
  if (errBar) {
    errBar.style.width = (total > 0 ? Math.min(100, Math.round(errors / total * 100)) : 0) + "%";
    errBar.className = "h-full rounded-full transition-all " + (errors > 0 ? "bg-error" : "bg-black");
  }

  // Sparta
  setText("metric-rate-value", state.history.length ? numFmt(rate) : "—");
  setMetricBadge("metric-rate-badge", rate > 500 ? "high" : "normal");
  setBarWidth("metric-rate-bar", Math.min(100, rate / 10));
}

function setMetricBadge(id, kind) {
  const e = el(id);
  if (!e) return;
  const cfgs = {
    normal: { cls: "bg-secondary-container text-on-secondary-container", label: t("metric_normal") },
    high:   { cls: "bg-tertiary-fixed text-on-tertiary-container",       label: t("metric_high")   },
    ok:     { cls: "bg-secondary-container text-on-secondary-container", label: t("metric_ok")     },
    error:  { cls: "bg-error-container text-on-error-container",         label: t("metric_high")   },
  };
  const cfg = cfgs[kind] || cfgs.normal;
  e.className = `px-2.5 py-0.5 rounded-full text-[10px] font-bold font-label ${cfg.cls}`;
  e.textContent = cfg.label;
}

function setBarWidth(id, pct) {
  const e = el(id);
  if (e) e.style.width = pct + "%";
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

  if (state.trafficChart) {
    state.trafficChart.data.labels = labels;
    state.trafficChart.data.datasets[0].data = values;
    state.trafficChart.update("none");
    return;
  }

  state.trafficChart = new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Logs",
        data: values,
        borderColor: "#006c4a",
        backgroundColor: (ctx) => {
          const chart = ctx.chart;
          const { ctx: c, chartArea } = chart;
          if (!chartArea) return "rgba(0,108,74,0.12)";
          const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, "rgba(0,108,74,0.22)");
          g.addColorStop(1, "rgba(0,108,74,0)");
          return g;
        },
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointBackgroundColor: "#006c4a",
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
        x: { grid: { color: "rgba(120,118,123,0.12)" }, ticks: { color: "#78767b", maxTicksLimit: 8, font: { size: 11 } } },
        y: { grid: { color: "rgba(120,118,123,0.12)" }, ticks: { color: "#78767b", font: { size: 11 } }, beginAtZero: true },
      },
    },
  });
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

export function renderKeyEvents() {
  const listEl = el("key-events-list");
  if (!listEl) return;

  if (!state.alerts.length) {
    listEl.textContent = "";
    const empty = document.createElement("div");
    empty.className = "text-center py-8 text-on-surface-variant text-sm font-label";

    const icon = document.createElement("span");
    icon.className = "material-symbols-outlined text-4xl block mb-2 text-secondary";
    icon.textContent = "check_circle";
    empty.appendChild(icon);

    const msg = document.createElement("span");
    msg.textContent = t("no_events");
    empty.appendChild(msg);

    listEl.appendChild(empty);
    return;
  }

  const SEV_CFG = {
    critical: { bg: "bg-error-container",     icon_fg: "text-on-error-container"     },
    high:     { bg: "bg-error-container",     icon_fg: "text-on-error-container"     },
    medium:   { bg: "bg-tertiary-fixed",      icon_fg: "text-on-tertiary-container"  },
    low:      { bg: "bg-secondary-container", icon_fg: "text-on-secondary-container" },
  };

  listEl.textContent = "";
  state.alerts.slice(0, 4).forEach(a => {
    const cfg = SEV_CFG[a.severity] || SEV_CFG.low;
    const meta = [a.source_ip || a.source_host || "", relTime(a.timestamp)].filter(Boolean).join(" • ");

    const row = document.createElement("div");
    row.className = "flex items-center gap-3 p-3 rounded-lg hover:bg-surface-container-low transition-colors group cursor-pointer";
    row.addEventListener("click", () => navigate("anomalies"));

    const iconWrap = document.createElement("div");
    iconWrap.className = `w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${cfg.bg}`;
    const icon = document.createElement("span");
    icon.className = `material-symbols-outlined text-lg ${cfg.icon_fg}`;
    icon.textContent = "warning";
    iconWrap.appendChild(icon);

    const info = document.createElement("div");
    info.className = "flex-grow min-w-0";
    const title = document.createElement("h4");
    title.className = "font-body font-semibold text-xs truncate";
    title.textContent = alertTitle(a.alert_type, a.title);
    const metaEl = document.createElement("p");
    metaEl.className = "text-[10px] text-on-surface-variant truncate";
    metaEl.textContent = meta;
    info.appendChild(title);
    info.appendChild(metaEl);

    const time = document.createElement("span");
    time.className = "text-[10px] font-label text-outline whitespace-nowrap";
    time.textContent = relTime(a.timestamp);

    row.appendChild(iconWrap);
    row.appendChild(info);
    row.appendChild(time);
    listEl.appendChild(row);
  });
}

export function init(context) {
  ctx = context;
  el("range-btn")?.addEventListener("click", toggleRangeMenu);
  el("traffic-device-select")?.addEventListener("change", onTrafficDeviceChange);
}

export function render() {
  renderMetrics();
  renderKeyEvents();
  renderTrafficChart();
  populateTrafficDeviceSelect();
  renderTrafficDeviceStats();
}
