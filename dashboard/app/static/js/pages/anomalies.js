// Anomalijų puslapis: srauto pulsas, įvykių tipai, chronologija, žali logai.

import { el, setText } from "../dom.js";
import { state } from "../state.js";
import { alertExpl, alertTitle, sevLabel, t } from "../i18n.js";
import { timeLabel } from "../format.js";
import { ANOMALY_CARD_CFG, openAlertInfo } from "../alert-dialog.js";
import { filteredAlerts, updateSearchUI } from "../shell.js";

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
    if (state.pulseChart) { state.pulseChart.destroy(); state.pulseChart = null; }
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
  const pointColors = alertCounts.map(c => (c > 0 ? "#ba1a1a" : "#006c4a"));
  const pointRadii  = alertCounts.map(c => (c > 0 ? 5 : 0));

  if (state.pulseChart) {
    const ch = state.pulseChart;
    ch.data.labels = labels;
    ch.data.datasets[0].data = values;
    ch.data.datasets[0].pointBackgroundColor = pointColors;
    ch.data.datasets[0].pointBorderColor = pointColors;
    ch.data.datasets[0].pointRadius = pointRadii;
    ch._alertCounts = alertCounts;
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
        borderColor: "#006c4a",
        backgroundColor: (ctx) => {
          const { ctx: c, chartArea } = ctx.chart;
          if (!chartArea) return "rgba(0,108,74,0.10)";
          const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, "rgba(0,108,74,0.20)");
          g.addColorStop(1, "rgba(0,108,74,0)");
          return g;
        },
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: pointRadii,
        pointHoverRadius: 6,
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors,
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
        x: { grid: { color: "rgba(120,118,123,0.12)" }, ticks: { color: "#78767b", maxTicksLimit: 8, font: { size: 11 } } },
        y: { grid: { color: "rgba(120,118,123,0.12)" }, ticks: { color: "#78767b", font: { size: 11 } }, beginAtZero: true },
      },
    },
  });
  state.pulseChart._alertCounts = alertCounts;
}

function renderAnomalyCards() {
  const cardsEl = el("anomaly-cards");
  if (!cardsEl) return;
  cardsEl.textContent = "";

  const counts = {};
  for (const a of filteredAlerts()) counts[a.alert_type] = (counts[a.alert_type] || 0) + 1;
  const top3 = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 3);

  if (!top3.length) {
    const empty = document.createElement("div");
    empty.className = "col-span-3 bg-surface-container-lowest rounded-lg p-8 text-center border border-outline-variant";
    const icon = document.createElement("span");
    icon.className = "material-symbols-outlined text-4xl text-secondary block mb-2";
    icon.textContent = "check_circle";
    const msg = document.createElement("p");
    msg.className = "text-on-surface-variant text-sm font-label";
    msg.textContent = t("anomaly_cards_empty");
    empty.appendChild(icon);
    empty.appendChild(msg);
    cardsEl.appendChild(empty);
    return;
  }

  const riskLabels = { critical: t("sev_critical"), medium: t("sev_medium"), warning: t("badge_warning") };

  top3.forEach(([type]) => {
    const cfg = ANOMALY_CARD_CFG[type] || ANOMALY_CARD_CFG.high_error_rate;

    const card = document.createElement("div");
    card.className = "bg-surface-container-lowest rounded-lg p-6 hover:border-outline transition-colors duration-200 group border border-outline-variant" +
      (cfg.risk === "critical" ? " border-t-4 border-t-error/40" : "");

    const iconWrap = document.createElement("div");
    iconWrap.className = `w-12 h-12 rounded-2xl flex items-center justify-center mb-4 group-hover:rotate-6 transition-transform ${cfg.bg}`;
    const icon = document.createElement("span");
    icon.className = `material-symbols-outlined text-2xl ${cfg.fg}`;
    icon.textContent = cfg.icon;
    iconWrap.appendChild(icon);

    const title = document.createElement("h3");
    title.className = "text-base font-bold font-headline mb-2";
    title.textContent = alertTitle(type, type);

    const desc = document.createElement("p");
    desc.className = "text-on-surface-variant text-xs leading-relaxed mb-4";
    desc.textContent = alertExpl(type);

    const badge = document.createElement("div");
    badge.className = `flex items-center gap-2 px-2.5 py-1 w-fit rounded-full text-[10px] font-bold uppercase font-label ${cfg.badge_bg} ${cfg.badge_fg}`;
    badge.textContent = riskLabels[cfg.risk] || cfg.risk;

    card.appendChild(iconWrap);
    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(badge);
    cardsEl.appendChild(card);
  });
}

function renderChronology() {
  const listEl = el("chronology-list");
  if (!listEl) return;
  listEl.textContent = "";

  setText("view-all-chrono", state.showAllAlerts ? t("show_less") : t("view_all_chrono"));

  const alerts = filteredAlerts();

  if (!alerts.length) {
    const msg = document.createElement("p");
    msg.className = "text-center py-6 text-on-surface-variant text-sm font-label";
    msg.textContent = t("no_events");
    listEl.appendChild(msg);
    return;
  }

  const SEV_DOT = {
    critical: "bg-error ring-error-container/30",
    high:     "bg-error ring-error-container/30",
    medium:   "bg-tertiary-fixed-dim ring-tertiary-fixed/30",
    low:      "bg-secondary ring-secondary-container/30",
  };

  (state.showAllAlerts ? alerts : alerts.slice(0, 20)).forEach(a => {
    const dot = SEV_DOT[a.severity] || "bg-outline ring-outline-variant/30";

    const row = document.createElement("div");
    row.className = "flex items-center gap-5 p-3 hover:bg-surface-container-low transition-colors rounded-lg group cursor-pointer";
    row.addEventListener("click", () => openAlertInfo(a));

    const timeEl = document.createElement("div");
    timeEl.className = "text-[10px] font-bold text-on-surface-variant w-12 tabular-nums font-label";
    timeEl.textContent = timeLabel(a.timestamp);

    const dotEl = document.createElement("div");
    dotEl.className = `w-1.5 h-1.5 rounded-full ring-2 shrink-0 ${dot}`;

    const info = document.createElement("div");
    info.className = "flex-1 min-w-0";
    const titleEl = document.createElement("p");
    titleEl.className = "text-sm font-semibold truncate";
    titleEl.textContent = alertTitle(a.alert_type, a.title);
    const meta = document.createElement("p");
    meta.className = "text-[10px] text-on-surface-variant";
    meta.textContent = (a.source_ip || a.source_host ? (a.source_ip || a.source_host) + " • " : "") + sevLabel(a.severity);
    info.appendChild(titleEl);
    info.appendChild(meta);

    const arrow = document.createElement("span");
    arrow.className = "material-symbols-outlined text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity text-xl";
    arrow.textContent = "arrow_forward";

    row.appendChild(timeEl);
    row.appendChild(dotEl);
    row.appendChild(info);
    row.appendChild(arrow);
    listEl.appendChild(row);
  });
}

async function toggleShowAllAlerts() {
  state.showAllAlerts = !state.showAllAlerts;
  if (state.showAllAlerts) await ctx.loadAllAlerts();
  renderAnomaliesPage();
}

const _LOG_SEV_DOT = {
  emerg: "bg-error", alert: "bg-error", crit: "bg-error", err: "bg-error", error: "bg-error",
  warning: "bg-tertiary-fixed-dim", warn: "bg-tertiary-fixed-dim",
  notice: "bg-secondary", info: "bg-secondary", debug: "bg-outline",
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
    row.className = "flex items-start gap-2 px-2 py-1 rounded hover:bg-surface-container-low transition-colors";

    const dot = document.createElement("span");
    dot.className = "w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 " + (_LOG_SEV_DOT[l.severity] || "bg-outline");

    const text = document.createElement("span");
    text.className = "text-on-surface break-all whitespace-pre-wrap min-w-0 leading-relaxed";
    text.textContent = l.line || "";

    row.appendChild(dot);
    row.appendChild(text);
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
