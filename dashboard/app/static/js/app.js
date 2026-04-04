/* ============================================================
   Logų analizės pultas — Vanilla JS
   ============================================================ */

// ---------------------------------------------------------------------------
// i18n
// ---------------------------------------------------------------------------
const I18N = {
  lt: {
    title:              "Logų analizė",
    hero_label:         "Sistemos būklė",
    hero_safe:          "Sistemos būklė: Saugi",
    hero_warning:       "Sistemos būklė: Įspėjimas",
    hero_critical:      "Sistemos būklė: Kritinė",
    hero_desc_safe:     "Visi mazgai veikia stabiliai. Kritinių incidentų neužfiksuota.",
    hero_desc_warn:     "Aptikti įspėjimai. Peržiūrėkite anomalijų puslapį.",
    hero_uptime:        "Veikimo laikas",
    hero_threats:       "Grėsmės",
    badge_ok:           "Saugi",
    badge_warning:      "Įspėjimas",
    badge_critical:     "Kritinė",
    badge_unknown:      "Tikrinama...",
    metric_logs:        "Logs (5 min)",
    metric_errors:      "Klaidos (5 min)",
    metric_rate:        "Logs / val",
    metric_normal:      "Normalus",
    metric_high:        "Padidėjęs",
    metric_ok:          "Gerai",
    key_events:         "Svarbiausi įvykiai",
    view_all:           "Žiūrėti visus",
    network_activity:   "Tinklo aktyvumas",
    last_24h:           "Paskutinės 24 valandos",
    total:              "Iš viso",
    peak:               "Pikas",
    logs_unit:          "įrašų",
    incoming:           "Įeinantis",
    pulse_monitor:      "Tinklo monitoringas",
    pulse_title:        "Statistinis srauto pulsas",
    pulse_normal:       "Normalus",
    pulse_deviation:    "Nuokrypis",
    rule_violation:     "Taisyklės pažeidimas",
    rule_desc:          "Aptikti kritiniai įspėjimai. Peržiūrėkite sąrašą.",
    rule_btn:           "Peržiūrėti",
    density_label:      "Kritinių įvykių dalis",
    anomaly_cards_empty:"Anomalijų nėra",
    chronology:         "Naujausia chronologija",
    view_all_chrono:    "Žiūrėti viską",
    no_events:          "Įvykių nėra",
    devices_page:       "Įrenginiai",
    devices_total:      "Iš viso įrenginių",
    devices_critical:   "Kritiniai",
    devices_warning:    "Įspėjimai",
    th_ip:              "IP / Hostname",
    th_count:           "Įspėjimai",
    th_worst:           "Blogiausia",
    devices_empty:      "Įrenginių nerasta",
    messages_page:      "Pranešimų nustatymai",
    messages_soon:      "Pranešimų nustatymai bus pridėti netrukus",
    messages_desc:      "Šiame skyriuje galėsite konfigūruoti el. pašto ir webhook pranešimus apie anomalijas.",
    nav_dashboard:      "Apžvalga",
    nav_anomalies:      "Anomalijos",
    nav_devices:        "Įrenginiai",
    nav_messages:       "Pranešimai",
    lang_switch:        "EN",
    search_placeholder: "Ieškoti įvykių ar įrenginių...",
    just_now:           "ką tik",
    min_ago:            n => `prieš ${n} min`,
    hr_ago:             n => `prieš ${n} val`,
    day_ago:            n => `prieš ${n} d`,
    sev_low:            "Žemas",
    sev_medium:         "Vidutinis",
    sev_high:           "Aukštas",
    sev_critical:       "Kritinis",
    alert_titles: {
      ssh_bruteforce:    "Bandymas įsilaužti per SSH",
      invalid_user_scan: "Nežinomi vartotojai bando jungtis",
      firewall_spike:    "Padidėjęs blokuojamų jungčių kiekis",
      log_volume_spike:  "Neįprastai daug sistemos log",
      high_error_rate:   "Daug sistemos klaidų",
      ml_anomaly:        "Neįprastas sistemos elgesys",
    },
    alert_explanations: {
      ssh_bruteforce:    "Aptikta daug nesėkmingų bandymų prisijungti. Gali būti slaptažodžio atspėjimo ataka.",
      invalid_user_scan: "Bandymai jungtis su neegzistuojančiais vartotojų vardais.",
      firewall_spike:    "Ugniasienė blokavo neįprastai daug jungčių.",
      log_volume_spike:  "Sistema generuoja žymiai daugiau log nei įprastai.",
      high_error_rate:   "Klaidų kiekis viršija normalų lygį.",
      ml_anomaly:        "ML aptiko neįprastus sistemos veiklos pokyčius.",
    },
  },
  en: {
    title:              "Log Analysis",
    hero_label:         "System Status",
    hero_safe:          "System Status: Healthy",
    hero_warning:       "System Status: Warning",
    hero_critical:      "System Status: Critical",
    hero_desc_safe:     "All nodes operating stably. No critical incidents recorded.",
    hero_desc_warn:     "Alerts detected. Review the anomalies page.",
    hero_uptime:        "Uptime",
    hero_threats:       "Threats",
    badge_ok:           "Healthy",
    badge_warning:      "Warning",
    badge_critical:     "Critical",
    badge_unknown:      "Checking...",
    metric_logs:        "Logs (5 min)",
    metric_errors:      "Errors (5 min)",
    metric_rate:        "Logs / hr",
    metric_normal:      "Normal",
    metric_high:        "Elevated",
    metric_ok:          "Good",
    key_events:         "Key Events",
    view_all:           "View all",
    network_activity:   "Network Activity",
    last_24h:           "Last 24 hours",
    total:              "Total",
    peak:               "Peak",
    logs_unit:          "records",
    incoming:           "Incoming",
    pulse_monitor:      "Network Monitoring",
    pulse_title:        "Statistical Traffic Pulse",
    pulse_normal:       "Normal",
    pulse_deviation:    "Deviation",
    rule_violation:     "Rule Violation",
    rule_desc:          "Critical alerts detected. Review the list.",
    rule_btn:           "Review",
    density_label:      "Critical event rate",
    anomaly_cards_empty:"No anomalies",
    chronology:         "Latest Chronology",
    view_all_chrono:    "View all",
    no_events:          "No events",
    devices_page:       "Devices",
    devices_total:      "Total Devices",
    devices_critical:   "Critical",
    devices_warning:    "Warnings",
    th_ip:              "IP / Hostname",
    th_count:           "Alerts",
    th_worst:           "Worst",
    devices_empty:      "No devices found",
    messages_page:      "Notification Settings",
    messages_soon:      "Notification settings coming soon",
    messages_desc:      "Configure email and webhook notifications for anomaly alerts here.",
    nav_dashboard:      "Dashboard",
    nav_anomalies:      "Anomalies",
    nav_devices:        "Devices",
    nav_messages:       "Notifications",
    lang_switch:        "LT",
    search_placeholder: "Search events or devices...",
    just_now:           "just now",
    min_ago:            n => `${n} min ago`,
    hr_ago:             n => `${n} hr ago`,
    day_ago:            n => `${n}d ago`,
    sev_low:            "Low",
    sev_medium:         "Medium",
    sev_high:           "High",
    sev_critical:       "Critical",
    alert_titles: {
      ssh_bruteforce:    "SSH Brute-Force Attempt",
      invalid_user_scan: "Unknown Users Attempting to Connect",
      firewall_spike:    "Spike in Blocked Connections",
      log_volume_spike:  "Unusually High Log Volume",
      high_error_rate:   "High Error Rate",
      ml_anomaly:        "Unusual System Behaviour",
    },
    alert_explanations: {
      ssh_bruteforce:    "Many failed login attempts detected. May be a password-guessing attack.",
      invalid_user_scan: "Login attempts using non-existent usernames detected.",
      firewall_spike:    "The firewall blocked an unusually high number of connections.",
      log_volume_spike:  "The system is generating significantly more logs than usual.",
      high_error_rate:   "The error count has exceeded the normal level.",
      ml_anomaly:        "ML detected unusual changes in system activity.",
    },
  },
};

// Anomaly type visual config
const ANOMALY_CARD_CFG = {
  ssh_bruteforce:    { icon: "login",         bg: "bg-tertiary-fixed",             fg: "text-on-tertiary-container",  badge_bg: "bg-tertiary-fixed",             badge_fg: "text-on-tertiary-container",  risk: "medium"   },
  invalid_user_scan: { icon: "person_off",    bg: "bg-error-container",            fg: "text-on-error-container",     badge_bg: "bg-error-container",            badge_fg: "text-on-error-container",     risk: "critical" },
  firewall_spike:    { icon: "shield",        bg: "bg-error-container",            fg: "text-on-error-container",     badge_bg: "bg-error-container",            badge_fg: "text-on-error-container",     risk: "critical" },
  high_error_rate:   { icon: "error_outline", bg: "bg-surface-container-highest",  fg: "text-on-surface",             badge_bg: "bg-surface-container-high",     badge_fg: "text-on-surface-variant",     risk: "warning"  },
  log_volume_spike:  { icon: "bar_chart",     bg: "bg-tertiary-fixed",             fg: "text-on-tertiary-container",  badge_bg: "bg-tertiary-fixed",             badge_fg: "text-on-tertiary-container",  risk: "medium"   },
  ml_anomaly:        { icon: "psychology",    bg: "bg-error-container",            fg: "text-on-error-container",     badge_bg: "bg-error-container",            badge_fg: "text-on-error-container",     risk: "critical" },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  lang:         localStorage.getItem("lang") || "lt",
  page:         "dashboard",
  search:       "",
  health:       { overall: "unknown", services: [] },
  current:      null,
  history:      [],
  alerts:       [],
  devices:      [],
  trafficChart: null,
};

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
function logout() {
  sessionStorage.removeItem("auth_token");
  sessionStorage.removeItem("auth_user");
  window.location.replace("/login");
}

function requireAuth() {
  if (!sessionStorage.getItem("auth_token")) {
    window.location.replace("/login");
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function t(key) {
  const d = I18N[state.lang];
  return (d && d[key] !== undefined) ? d[key] : (I18N.en[key] || key);
}

function alertTitle(type, fallback) {
  return ((I18N[state.lang] || {}).alert_titles || {})[type] || fallback || type;
}

function alertExpl(type) {
  return ((I18N[state.lang] || {}).alert_explanations || {})[type] || "";
}

function sevLabel(s) {
  const m = { low: t("sev_low"), medium: t("sev_medium"), high: t("sev_high"), critical: t("sev_critical") };
  return m[s] || s;
}

function relTime(iso) {
  if (!iso) return "";
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60)  return t("just_now");
  const min = Math.floor(sec / 60);
  if (min < 60)  return t("min_ago")(min);
  const hr = Math.floor(min / 60);
  if (hr < 24)   return t("hr_ago")(hr);
  return t("day_ago")(Math.floor(hr / 24));
}

function timeLabel(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(
    state.lang === "lt" ? "lt-LT" : "en-GB",
    { hour: "2-digit", minute: "2-digit" }
  );
}

function numFmt(n) {
  return Number(n).toLocaleString(state.lang === "lt" ? "lt-LT" : "en-GB");
}

// Safe text escape — prevent XSS when inserting server strings into HTML
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function el(id) { return document.getElementById(id); }

function setText(id, val) {
  const e = el(id);
  if (e) e.textContent = val;
}

function setPlaceholder(id, val) {
  const e = el(id);
  if (e) e.placeholder = val;
}

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function navigate(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  const target = el("page-" + page);
  if (target) target.classList.add("active");

  ["dashboard", "anomalies", "devices", "messages"].forEach(p => {
    const btn = el("nav-" + p);
    if (btn) btn.classList.toggle("active", p === page);
  });

  state.page = page;
  if (page === "anomalies") renderAnomaliesPage();
  if (page === "devices")   renderDevicesPage();
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
async function loadHealth() {
  try {
    const data = await fetchJSON("/api/health/status");
    state.health = data;
    renderHealth();
  } catch (e) {
    console.error("Health:", e);
  }
}

function renderHealth() {
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

// ---------------------------------------------------------------------------
// Traffic
// ---------------------------------------------------------------------------
async function loadTrafficCurrent() {
  try {
    state.current = await fetchJSON("/api/traffic/current");
    renderMetrics();
  } catch (e) {
    console.error("Traffic current:", e);
  }
}

async function loadTrafficHistory() {
  try {
    const data = await fetchJSON("/api/traffic/history?hours=24");
    state.history = data.points || [];
    renderTrafficChart();
    if (state.page === "anomalies") renderPulseBars();
  } catch (e) {
    console.error("Traffic history:", e);
  }
}

function errorCount() {
  if (!state.current) return 0;
  const s = state.current.by_severity || {};
  return (s.err || 0) + (s.error || 0) + (s.crit || 0) + (s.critical || 0);
}

function logRate() {
  if (!state.history.length) return 0;
  const recent = state.history.slice(-6);
  return Math.round(recent.reduce((a, p) => a + p.count, 0) / recent.length);
}

function renderMetrics() {
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

function renderTrafficChart() {
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
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Logs",
        data: values,
        backgroundColor: "rgba(0,0,0,0.75)",
        borderRadius: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y} logs` } },
      },
      scales: {
        x: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { color: "#64748b", maxTicksLimit: 8, font: { size: 11 } } },
        y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { color: "#64748b", font: { size: 11 } }, beginAtZero: true },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
async function loadAlerts() {
  try {
    const data = await fetchJSON("/api/alerts/recent?limit=20");
    state.alerts = data.alerts || [];
    renderKeyEvents();
    setText("hero-threats", String(
      state.alerts.filter(a => a.severity === "critical" || a.severity === "high").length
    ));
    if (state.page === "anomalies") renderAnomaliesPage();
  } catch (e) {
    console.error("Alerts:", e);
  }
}

function renderKeyEvents() {
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

// ---------------------------------------------------------------------------
// Anomalies page
// ---------------------------------------------------------------------------
function renderAnomaliesPage() {
  updateSearchUI();
  renderPulseBars();
  renderRuleViolation();
  renderAnomalyCards();
  renderChronology();
}

function renderPulseBars() {
  const barsEl  = el("pulse-bars");
  const timesEl = el("pulse-times");
  if (!barsEl) return;

  const pts = state.history.slice(-24);
  barsEl.textContent = "";

  if (!pts.length) {
    const msg = document.createElement("div");
    msg.className = "flex-1 flex items-center justify-center text-on-surface-variant text-sm";
    msg.textContent = t("no_events");
    barsEl.appendChild(msg);
    return;
  }

  const peak = Math.max(...pts.map(p => p.count), 1);
  pts.forEach(p => {
    const pct = Math.max(4, Math.round(p.count / peak * 100));
    const isAnomaly = p.count > peak * 0.7;
    const bar = document.createElement("div");
    bar.className = "flex-1 rounded-t-sm transition-all cursor-default " +
      (isAnomaly ? "bg-error-container/80 hover:bg-error" : "bg-secondary-container/60 hover:bg-secondary");
    bar.style.height = pct + "%";
    bar.title = p.count + " logs";
    barsEl.appendChild(bar);
  });

  if (timesEl) {
    timesEl.textContent = "";
    const idxs = [0, Math.floor(pts.length / 4), Math.floor(pts.length / 2), Math.floor(pts.length * 3 / 4), pts.length - 1];
    idxs.forEach(i => {
      const span = document.createElement("span");
      span.textContent = pts[i] ? timeLabel(pts[i].time) : "";
      timesEl.appendChild(span);
    });
  }
}

function renderRuleViolation() {
  const critical = state.alerts.find(a => a.severity === "critical" || a.severity === "high");
  setText("rule-violation-desc", critical
    ? alertTitle(critical.alert_type, critical.title)
    : t("rule_desc"));

  const total    = state.alerts.length;
  const critCnt  = state.alerts.filter(a => a.severity === "critical" || a.severity === "high").length;
  const pct      = total > 0 ? Math.min(100, Math.round(critCnt / total * 100)) : 0;
  setText("density-pct", pct + "%");
  setBarWidth("density-bar", pct);
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
    empty.className = "col-span-3 bg-surface-container-lowest rounded-xl p-8 text-center shadow-sm";
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
    card.className = "bg-surface-container-lowest rounded-xl p-6 hover:-translate-y-0.5 transition-all duration-300 group shadow-sm" +
      (cfg.risk === "critical" ? " border-t-4 border-error/20" : "");

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

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
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

function filteredAlerts() {
  const q = state.search;
  return q ? state.alerts.filter(a => alertMatchesQuery(a, q)) : state.alerts;
}

function filteredDevices() {
  const q = state.search;
  return q ? state.devices.filter(d => d.id.toLowerCase().includes(q)) : state.devices;
}

function updateSearchUI() {
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

  countEl.textContent = `${count} rezultat${count === 1 ? "as" : "ų"}`;
  countEl.classList.remove("hidden");
}

function renderChronology() {
  const listEl = el("chronology-list");
  if (!listEl) return;
  listEl.textContent = "";

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

  alerts.slice(0, 20).forEach(a => {
    const dot = SEV_DOT[a.severity] || "bg-outline ring-outline-variant/30";

    const row = document.createElement("div");
    row.className = "flex items-center gap-5 p-3 hover:bg-surface-container-low transition-colors rounded-lg group";

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

// ---------------------------------------------------------------------------
// Devices
// ---------------------------------------------------------------------------
async function loadDevices() {
  try {
    const data = await fetchJSON("/api/alerts/history?page=1&size=100");
    const raw  = data.alerts || [];
    const SEV_RANK = { low: 1, medium: 2, high: 3, critical: 4 };
    const map  = new Map();
    for (const a of raw) {
      const key = a.source_ip || a.source_host || "unknown";
      if (!map.has(key)) map.set(key, { id: key, count: 0, worstSeverity: "low" });
      const d = map.get(key);
      d.count++;
      if ((SEV_RANK[a.severity] || 0) > (SEV_RANK[d.worstSeverity] || 0)) d.worstSeverity = a.severity;
    }
    state.devices = [...map.values()].sort((a, b) => b.count - a.count);
    if (state.page === "devices") renderDevicesPage();
  } catch (e) {
    console.error("Devices:", e);
  }
}

function renderDevicesPage() {
  const devs = filteredDevices();
  setText("devices-total",    String(state.devices.length));
  setText("devices-critical", String(state.devices.filter(d => d.worstSeverity === "critical" || d.worstSeverity === "high").length));
  setText("devices-warning",  String(state.devices.filter(d => d.worstSeverity === "medium").length));

  const empty = el("devices-empty");
  const wrap  = el("devices-table-wrap");

  if (!devs.length) {
    if (empty) empty.classList.remove("hidden");
    if (wrap)  wrap.classList.add("hidden");
    return;
  }
  if (empty) empty.classList.add("hidden");
  if (wrap)  wrap.classList.remove("hidden");

  const SEV_BADGE = {
    low:      "bg-secondary-container text-on-secondary-container",
    medium:   "bg-tertiary-fixed text-on-tertiary-container",
    high:     "bg-error-container text-on-error-container",
    critical: "bg-error-container text-on-error-container",
  };

  const tbody = el("devices-tbody");
  if (!tbody) return;
  tbody.textContent = "";

  devs.forEach((d, i) => {
    const tr = document.createElement("tr");
    tr.className = "border-b border-outline-variant/20 last:border-0 hover:bg-surface-container-low transition-colors" +
      (i % 2 === 1 ? " bg-surface-container-low/30" : "");

    const tdId = document.createElement("td");
    tdId.className = "px-6 py-3 font-mono text-sm font-medium";
    tdId.textContent = d.id;

    const tdCount = document.createElement("td");
    tdCount.className = "px-6 py-3 font-bold";
    tdCount.textContent = d.count;

    const tdWorst = document.createElement("td");
    tdWorst.className = "px-6 py-3";
    const badge = document.createElement("span");
    badge.className = "px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase font-label " +
      (SEV_BADGE[d.worstSeverity] || "bg-surface-container text-on-surface-variant");
    badge.textContent = sevLabel(d.worstSeverity);
    tdWorst.appendChild(badge);

    tr.appendChild(tdId);
    tr.appendChild(tdCount);
    tr.appendChild(tdWorst);
    tbody.appendChild(tr);
  });
}

// ---------------------------------------------------------------------------
// i18n — update all static labels
// ---------------------------------------------------------------------------
function applyI18n() {
  setText("sidebar-title",          t("title"));
  setText("nav-label-dashboard",    t("nav_dashboard"));
  setText("nav-label-anomalies",    t("nav_anomalies"));
  setText("nav-label-devices",      t("nav_devices"));
  setText("nav-label-messages",     t("nav_messages"));
  setText("lang-btn",               t("lang_switch"));
  setPlaceholder("search-input",    t("search_placeholder"));
  setText("hero-label",             t("hero_label"));
  setText("hero-uptime-label",      t("hero_uptime"));
  setText("hero-threats-label",     t("hero_threats"));
  setText("metric-logs-label",      t("metric_logs"));
  setText("metric-errors-label",    t("metric_errors"));
  setText("metric-rate-label",      t("metric_rate"));
  setText("key-events-title",       t("key_events"));
  setText("view-all-label",         t("view_all"));
  setText("network-activity-title", t("network_activity"));
  setText("last-24h-label",         t("last_24h"));
  setText("total-label",            t("total"));
  setText("peak-label",             t("peak"));
  setText("incoming-label",         t("incoming"));
  setText("pulse-monitor-label",    t("pulse_monitor"));
  setText("pulse-title",            t("pulse_title"));
  setText("pulse-normal-label",     t("pulse_normal"));
  setText("pulse-deviation-label",  t("pulse_deviation"));
  setText("rule-violation-title-label", t("rule_violation"));
  setText("rule-violation-btn",     t("rule_btn"));
  setText("density-label",          t("density_label"));
  setText("chronology-title",       t("chronology"));
  setText("view-all-chrono",        t("view_all_chrono"));
  setText("devices-page-title",     t("devices_page"));
  setText("devices-total-label",    t("devices_total"));
  setText("devices-critical-label", t("devices_critical"));
  setText("devices-warning-label",  t("devices_warning"));
  setText("th-ip",                  t("th_ip"));
  setText("th-count",               t("th_count"));
  setText("th-worst",               t("th_worst"));
  setText("devices-empty-label",    t("devices_empty"));
  setText("messages-page-title",    t("messages_page"));
  setText("messages-soon-title",    t("messages_soon"));
  setText("messages-soon-desc",     t("messages_desc"));
  document.documentElement.lang = state.lang;
}

function toggleLang() {
  state.lang = state.lang === "lt" ? "en" : "lt";
  localStorage.setItem("lang", state.lang);
  applyI18n();
  renderHealth();
  renderMetrics();
  renderKeyEvents();
  renderTrafficChart();
  if (state.page === "anomalies") renderAnomaliesPage();
  if (state.page === "devices")   renderDevicesPage();
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
async function init() {
  if (!requireAuth()) return;

  applyI18n();

  // Search
  const searchInput = el("search-input");
  const clearBtn    = el("search-clear");

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      state.search = searchInput.value.trim().toLowerCase();
      updateSearchUI();
      if (state.search && state.page === "dashboard") {
        navigate("anomalies");
      } else if (state.page === "anomalies") {
        renderAnomaliesPage();
      } else if (state.page === "devices") {
        renderDevicesPage();
      }
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      state.search = "";
      if (searchInput) searchInput.value = "";
      updateSearchUI();
      if (state.page === "anomalies") renderAnomaliesPage();
      else if (state.page === "devices") renderDevicesPage();
    });
  }

  await Promise.allSettled([
    loadHealth(),
    loadTrafficCurrent(),
    loadTrafficHistory(),
    loadAlerts(),
    loadDevices(),
  ]);
  setInterval(loadHealth,          30_000);
  setInterval(loadTrafficCurrent,  30_000);
  setInterval(loadTrafficHistory,  60_000);
  setInterval(loadAlerts,          15_000);
  setInterval(loadDevices,         60_000);
}

document.addEventListener("DOMContentLoaded", init);
