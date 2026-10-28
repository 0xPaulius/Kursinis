// Įėjimo modulis: duomenų įkėlimas, gyvi atnaujinimai, kalbos perjungimas, puslapių sujungimas.

import { el, setPlaceholder, setText } from "./dom.js";
import { state } from "./state.js";
import { fetchJSON, logout, openStream, requireAuth } from "./api.js";
import { t } from "./i18n.js";
import { initNavigation, navigate, renderHealth, updateSearchUI } from "./shell.js";
import { initAlertDialog } from "./alert-dialog.js";
import { init as initAnomalies, populateLogsHostSelect, renderAnomaliesPage, renderPulseChart, renderRawLogs } from "./pages/anomalies.js";
import { renderAttackCoverage } from "./pages/attack.js";
import { closeAttackMenu, init as initDevices, renderDevicesPage } from "./pages/devices.js";
import { init as initNotifications, load as loadNotificationSettings } from "./pages/notifications.js";
import { closeRangeMenu, init as initOverview, populateTrafficDeviceSelect, renderKeyEvents, renderMetrics, renderRangeMenu, renderTrafficChart, renderTrafficDeviceStats } from "./pages/overview.js";

function applyHealth(data) {
  state.health = data;
  renderHealth();
}

async function loadHealth() {
  try {
    applyHealth(await fetchJSON("/api/health/status"));
  } catch (e) {
    console.error("Health:", e);
  }
}

function applyTrafficCurrent(data) {
  state.current = data;
  renderMetrics();
}

async function loadTrafficCurrent() {
  try {
    applyTrafficCurrent(await fetchJSON("/api/traffic/current"));
  } catch (e) {
    console.error("Traffic current:", e);
  }
}

async function loadTrafficHistory() {
  try {
    const q = state.trafficHost ? `&host=${encodeURIComponent(state.trafficHost)}` : "";
    const data = await fetchJSON(`/api/traffic/history?hours=${state.rangeHours}${q}`);
    state.history = data.points || [];
    renderTrafficChart();
    if (state.page === "anomalies") renderPulseChart();
  } catch (e) {
    console.error("Traffic history:", e);
  }
}

function applyAlerts(data) {
  state.alerts = data.alerts || [];
  renderKeyEvents();
  setText("hero-threats", String(
    state.alerts.filter(a => a.severity === "critical" || a.severity === "high").length
  ));
  if (state.page === "anomalies") {
    // Išplėstame rodinyje atnaujiname ir visą istoriją, kad sąrašas liktų gyvas.
    if (state.showAllAlerts) loadAllAlerts().then(() => renderAnomaliesPage());
    else renderAnomaliesPage();
  }
}

async function loadAlerts() {
  try {
    applyAlerts(await fetchJSON("/api/alerts/recent?limit=20"));
  } catch (e) {
    console.error("Alerts:", e);
  }
}

// Užkrauna visą įspėjimų istoriją (naudojama „Žiūrėti viską" rodinyje).
async function loadAllAlerts() {
  try {
    const data = await fetchJSON("/api/alerts/history?page=1&size=100");
    state.allAlerts = data.alerts || [];
  } catch (e) {
    console.error("All alerts:", e);
  }
}

async function loadAttackCoverage() {
  try {
    state.attackCoverage = await fetchJSON("/api/attack/coverage");
  } catch (e) {
    console.error("ATT&CK:", e);
    state.attackCoverage = null;
  }
  renderAttackCoverage();
}

function applyDevices(data) {
  state.devices = data.devices || [];
  state.collector = data.collector || null;
  populateTrafficDeviceSelect();
  populateLogsHostSelect();
  renderTrafficDeviceStats();
  if (state.page === "devices") renderDevicesPage();
}

async function loadDevices() {
  try {
    applyDevices(await fetchJSON("/api/devices/map"));
  } catch (e) {
    console.error("Devices:", e);
  }
}

function applyRawLogs(lines) {
  state.rawLogs = lines || [];
  renderRawLogs();
}

async function loadRawLogs() {
  try {
    const q = state.logsHost ? `&host=${encodeURIComponent(state.logsHost)}` : "";
    const data = await fetchJSON(`/api/traffic/logs?limit=200${q}`);
    applyRawLogs(data.lines || []);
  } catch (e) {
    console.error("Raw logs:", e);
  }
}

function applyI18n() {
  setText("sidebar-title",          t("title"));
  setText("nav-label-dashboard",    t("nav_dashboard"));
  setText("nav-label-anomalies",    t("nav_anomalies"));
  setText("nav-label-devices",      t("nav_devices"));
  setText("nav-label-attack",       t("nav_attack"));
  setText("nav-label-messages",     t("nav_messages"));
  setText("attack-page-title",      t("attack_page_title"));
  setText("attack-desc",            t("attack_desc"));
  if (state.page === "attack") renderAttackCoverage();
  setText("lang-btn",               t("lang_switch"));
  setPlaceholder("search-input",    t("search_placeholder"));
  setText("hero-label",             t("hero_label"));
  setText("hero-uptime-label",      t("hero_uptime"));
  setText("hero-threats-label",     t("hero_threats"));
  setText("hero-threats-sub",        t("metric_threats_sub"));
  setText("metric-logs-label",      t("metric_logs"));
  setText("metric-errors-label",    t("metric_errors"));
  setText("metric-rate-label",      t("metric_rate"));
  setText("key-events-title",       t("key_events"));
  setText("view-all-label",         t("view_all"));
  setText("network-activity-title", t("network_activity"));
  renderRangeMenu();   // nustato range-label ir last-24h-label pagal pasirinktą intervalą
  setText("total-label",            t("total"));
  setText("peak-label",             t("peak"));
  setText("incoming-label",         t("incoming"));
  setText("tds-status-label",       t("info_status_label"));
  setText("tds-logs5m-label",       t("info_logs5m_label"));
  setText("tds-lastseen-label",     t("info_lastseen_label"));
  setText("tds-alerts-label",       t("info_alerts_label"));
  setText("pulse-monitor-label",    t("pulse_monitor"));
  setText("pulse-title",            t("pulse_title"));
  setText("pulse-normal-label",     t("pulse_normal"));
  setText("pulse-deviation-label",  t("pulse_deviation"));
  setText("chronology-title",       t("chronology"));
  setText("view-all-chrono",        state.showAllAlerts ? t("show_less") : t("view_all_chrono"));
  setText("alert-info-ip-label",     t("info_ip_label"));
  setText("alert-info-host-label",   t("info_hostname_label"));
  setText("alert-info-method-label", t("ad_method"));
  setText("alert-info-expl-label",   t("ad_explanation"));
  setText("alert-info-rec-label",    t("ad_recommendation"));
  setText("alert-info-details-label",t("ad_details"));
  setText("alert-info-raw-label",    t("ad_raw_lines"));
  setText("logs-title",              t("logs_title"));
  setText("logs-subtitle",           t("logs_subtitle"));
  const logsRefreshBtn = el("logs-refresh-btn");
  if (logsRefreshBtn) logsRefreshBtn.title = t("logs_refresh");
  setText("devices-page-title",     t("devices_page"));
  setText("devices-total-label",    t("map_total"));
  setText("devices-online-label",   t("map_online"));
  setText("map-title",              t("map_title"));
  setText("map-legend-online",      t("map_legend_online"));
  setText("map-legend-offline",     t("map_legend_offline"));
  setText("map-legend-alert",       t("map_legend_alert"));
  setText("th-name",                t("th_name"));
  setText("th-os",                  t("th_os"));
  setText("th-ip",                  t("th_ip"));
  setText("th-status",              t("th_status"));
  setText("th-logs",                t("th_logs"));
  setText("th-lastseen",            t("th_lastseen"));
  setText("th-actions",             t("th_actions"));
  setText("devices-add-btn-label",  t("dev_add_btn"));
  setText("devices-connect-btn-label", t("dev_connect_btn"));
  setText("attack-btn-label",       t("dev_attack_btn"));
  setText("attack-ssh-label",       t("dev_attack_ssh"));
  setText("attack-firewall-label",  t("dev_attack_firewall"));
  setText("devices-demo-btn-label", t("dev_mltest_btn"));
  setText("info-status-label",      t("info_status_label"));
  setText("info-source-label",      t("info_source_label"));
  setText("info-ip-label",          t("info_ip_label"));
  setText("info-hostname-label",    t("info_hostname_label"));
  setText("info-os-label",          t("info_os_label"));
  setText("info-version-label",     t("info_version_label"));
  setText("info-lastseen-label",    t("info_lastseen_label"));
  setText("info-logs5m-label",      t("info_logs5m_label"));
  setText("info-logs1h-label",      t("info_logs1h_label"));
  setText("info-alerts-label",      t("info_alerts_label"));
  setText("device-modal-title",     t("dev_modal_title"));
  setText("dev-name-label",         t("dev_name_field"));
  setText("dev-ip-label",           t("dev_ip_field"));
  setText("dev-os-label",           t("dev_os_field"));
  setText("dev-os-macos",           t("dev_os_macos"));
  setText("dev-os-windows",         t("dev_os_windows"));
  setText("dev-cancel-btn",         t("dev_cancel"));
  setText("dev-save-btn",           t("dev_save"));
  setText("dev-done-btn",           t("dev_done"));
  setText("device-tut-title-text",  t("dev_tut_heading"));
  setText("device-tut-code-label",  t("dev_tut_code_label"));
  setText("device-tut-os-label",    t("dev_os_field"));
  setPlaceholder("dev-name",        t("dev_name_ph"));
  setPlaceholder("dev-ip",          t("dev_ip_ph"));
  setText("messages-page-title",     t("messages_page"));
  setText("messages-desc",           t("messages_desc"));
  setText("notify-enabled-label",    t("notify_enabled_label"));
  setText("notify-enabled-hint",     t("notify_enabled_hint"));
  setText("notify-webhook-label",    t("notify_webhook_label"));
  setText("notify-severity-label",   t("notify_severity_label"));
  setText("notify-sev-low",          t("sev_low"));
  setText("notify-sev-medium",       t("sev_medium"));
  setText("notify-sev-high",         t("sev_high"));
  setText("notify-sev-critical",     t("sev_critical"));
  setText("notify-save-btn",         t("notify_save"));
  setText("notify-test-btn",         t("notify_test"));
  setPlaceholder("notify-webhook",   t("notify_webhook_ph"));
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
  populateTrafficDeviceSelect();
  renderTrafficDeviceStats();
  if (state.page === "anomalies") renderAnomaliesPage();
  if (state.page === "devices")   renderDevicesPage();
}

function maybeRefreshHistory() {
  // Grafiko srautas priklauso nuo kliento intervalo/įrenginio, tad jį atnaujina
  // pats klientas (throttle ~12s), kai serveris atsiunčia naują srauto įvykį.
  const now = Date.now();
  if (now - state._lastHistory > 12000) {
    state._lastHistory = now;
    loadTrafficHistory();
    if (state.page === "anomalies") loadRawLogs();
  }
}

// Ką padaryti atidarius puslapį (anksčiau — navigate()).
function enterPage(page) {
  if (page === "anomalies") { renderAnomaliesPage(); loadRawLogs(); }
  if (page === "devices")   renderDevicesPage();
  if (page === "attack")    loadAttackCoverage();
  if (page === "messages")  loadNotificationSettings();
}

const streamHandlers = {
  health:  applyHealth,
  alerts:  applyAlerts,
  devices: applyDevices,
  traffic: data => { applyTrafficCurrent(data); maybeRefreshHistory(); },
};

async function init() {
  if (!requireAuth()) return;

  applyI18n();

  const ctx = { loadTrafficHistory, loadTrafficCurrent, loadAlerts, loadAllAlerts, loadRawLogs, loadDevices };
  initOverview(ctx);
  initAnomalies(ctx);
  initDevices(ctx);
  initNotifications();
  initAlertDialog();
  el("lang-btn")?.addEventListener("click", toggleLang);
  el("logout-btn")?.addEventListener("click", logout);
  initNavigation(enterPage);

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

  // Laiko intervalo meniu uždaromas paspaudus kitur
  document.addEventListener("click", (ev) => {
    const btn = el("range-btn");
    const menu = el("range-menu");
    if (menu && !menu.classList.contains("hidden") &&
        btn && !btn.contains(ev.target) && !menu.contains(ev.target)) {
      closeRangeMenu();
    }
    const aBtn = el("attack-btn");
    const aMenu = el("attack-menu");
    if (aMenu && !aMenu.classList.contains("hidden") &&
        aBtn && !aBtn.contains(ev.target) && !aMenu.contains(ev.target)) {
      closeAttackMenu();
    }
  });

  await Promise.allSettled([
    loadHealth(),
    loadTrafficCurrent(),
    loadTrafficHistory(),
    loadAlerts(),
    loadDevices(),
  ]);

  // Gyvi atnaujinimai per SSE — serveris pushina pokyčius viena jungtimi
  // (vietoj periodinio pollinimo).
  openStream(streamHandlers);

  // Grįžus į matomą tabą — atnaujiname grafiką ir, jei reikia, atkuriame srautą.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    loadTrafficHistory();
    if (!state.stream || state.stream.readyState === 2) openStream(streamHandlers);
  });
}

init();
