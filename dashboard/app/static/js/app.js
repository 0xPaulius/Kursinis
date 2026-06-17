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
    th_name:            "Pavadinimas",
    th_os:              "OS",
    th_ip:              "IP / Hostname",
    th_count:           "Įspėjimai",
    th_worst:           "Blogiausia",
    th_actions:         "Veiksmai",
    devices_empty:      "Įrenginių dar nepridėta",
    dev_add_btn:        "Pridėti įrenginį",
    dev_demo_btn:       "Paleisti demonstraciją",
    dev_modal_title:    "Pridėti naują įrenginį",
    dev_name_field:     "Pavadinimas",
    dev_name_ph:        "pvz. Biuro MacBook",
    dev_ip_field:       "IP adresas",
    dev_ip_ph:          "pvz. 192.168.1.50",
    dev_os_field:       "Operacinė sistema",
    dev_os_macos:       "macOS (MacBook)",
    dev_os_windows:     "Windows 11 (PC)",
    dev_cancel:         "Atšaukti",
    dev_save:           "Pridėti",
    dev_saving:         "Pridedama...",
    dev_done:           "Supratau",
    dev_delete:         "Šalinti",
    dev_tutorial:       "Instrukcija",
    dev_delete_confirm: nm => `Pašalinti įrenginį „${nm}“?`,
    dev_worst_none:     "—",
    dev_err_name:       "Įveskite pavadinimą",
    dev_err_ip:         "Įveskite teisingą IPv4 adresą",
    dev_tut_heading:    "Įrenginys pridėtas",
    dev_tut_intro:      nm => `Kad įrenginys „${nm}“ pradėtų siųsti logus, nukreipkite jį į syslog kolektorių (UDP, 514 prievadas). Atlikite šiuos veiksmus:`,
    dev_tut_code_label: "Konfigūracijos pavyzdys",
    dev_demo_running:   "Generuojama demonstracinė ataka...",
    dev_demo_sent:      host => `Demonstracinė ataka prieš „${host}“ išsiųsta. Anomalijos pasirodys po kelių akimirkų.`,
    dev_demo_none:      "Pirma pridėkite įrenginį, tada paleiskite demonstraciją.",
    dev_demo_error:     "Nepavyko paleisti demonstracijos.",
    dev_online_card:    "Aktyvūs dabar",
    dev_all:            "Visi įrenginiai",
    dev_logs5m_card:    "Logai (5 min)",
    map_title:          "Įrenginių žemėlapis",
    map_legend_online:  "Aktyvus",
    map_legend_offline: "Neaktyvus",
    map_legend_alert:   "Su įspėjimais",
    map_collector:      "Kolektorius",
    map_empty:          "Įrenginių dar nėra. Pridėkite įrenginį arba nukreipkite savo serverį į kolektorių (514).",
    th_status:          "Būsena",
    th_logs:            "Logai (5 min)",
    th_lastseen:        "Paskutinis logas",
    dev_status_online:  "Aktyvus",
    dev_status_offline: "Neaktyvus",
    dev_never:          "Negauta",
    dev_info:           "Informacija",
    dev_os_linux:       "Linux",
    dev_os_unknown:     "Nežinoma",
    src_self:           "Šis serveris",
    src_registered:     "Demonstracinis",
    src_discovered:     "Aptiktas",
    info_status_label:  "Būsena",
    info_source_label:  "Tipas",
    info_ip_label:      "IP adresas",
    info_hostname_label:"Hostname",
    info_os_label:      "Operacinė sistema",
    info_version_label: "Versija / branduolys",
    info_lastseen_label:"Paskutinis logas",
    info_logs5m_label:  "Logai (5 min)",
    info_logs1h_label:  "Logai (1 val)",
    info_alerts_label:  "Įspėjimai",
    tut_macos_steps: [
      "Savo „MacBook“ atidarykite programą „Terminal“.",
      "Įdiekite syslog-ng (per Homebrew): brew install syslog-ng",
      "Į konfigūraciją įrašykite paskirties bloką (pavyzdys žemiau), nurodydami {collector}.",
      "Paleiskite paslaugą: sudo brew services start syslog-ng",
      "Po kelių minučių įrenginys pasirodys sraute.",
    ],
    tut_windows_steps: [
      "Atsisiųskite ir įdiekite „nxlog Community Edition“.",
      "Į nxlog.conf įrašykite išvesties bloką (pavyzdys žemiau), nurodydami {collector}.",
      "Maršrute (Route) priskirkite šią išvestį ir nustatykite siuntėjo vardą {hostname}.",
      "Paleiskite „nxlog“ tarnybą per „Services“ valdiklį.",
      "Po kelių minučių įrenginys pasirodys sraute.",
    ],
    tut_macos_code: "destination d_collector {\n  network(\"{collector}\" transport(\"udp\") port(514));\n};\nlog { source(s_local); destination(d_collector); };",
    tut_windows_code: "<Output collector>\n  Module  om_udp\n  Host    {collector}\n  Port    514\n</Output>",
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
    th_name:            "Name",
    th_os:              "OS",
    th_ip:              "IP / Hostname",
    th_count:           "Alerts",
    th_worst:           "Worst",
    th_actions:         "Actions",
    devices_empty:      "No devices added yet",
    dev_add_btn:        "Add device",
    dev_demo_btn:       "Run demo",
    dev_modal_title:    "Add a new device",
    dev_name_field:     "Name",
    dev_name_ph:        "e.g. Office MacBook",
    dev_ip_field:       "IP address",
    dev_ip_ph:          "e.g. 192.168.1.50",
    dev_os_field:       "Operating system",
    dev_os_macos:       "macOS (MacBook)",
    dev_os_windows:     "Windows 11 (PC)",
    dev_cancel:         "Cancel",
    dev_save:           "Add",
    dev_saving:         "Adding...",
    dev_done:           "Got it",
    dev_delete:         "Delete",
    dev_tutorial:       "Setup",
    dev_delete_confirm: nm => `Remove device "${nm}"?`,
    dev_worst_none:     "—",
    dev_err_name:       "Enter a name",
    dev_err_ip:         "Enter a valid IPv4 address",
    dev_tut_heading:    "Device added",
    dev_tut_intro:      nm => `To start receiving logs from "${nm}", point the device at the syslog collector (UDP, port 514). Follow these steps:`,
    dev_tut_code_label: "Configuration example",
    dev_demo_running:   "Generating demo attack...",
    dev_demo_sent:      host => `Demo attack against "${host}" sent. Anomalies will appear shortly.`,
    dev_demo_none:      "Add a device first, then run the demo.",
    dev_demo_error:     "Failed to start the demo.",
    dev_online_card:    "Online now",
    dev_all:            "All devices",
    dev_logs5m_card:    "Logs (5 min)",
    map_title:          "Device map",
    map_legend_online:  "Online",
    map_legend_offline: "Offline",
    map_legend_alert:   "With alerts",
    map_collector:      "Collector",
    map_empty:          "No devices yet. Add one or point your server at the collector (514).",
    th_status:          "Status",
    th_logs:            "Logs (5 min)",
    th_lastseen:        "Last seen",
    dev_status_online:  "Online",
    dev_status_offline: "Offline",
    dev_never:          "Never",
    dev_info:           "Info",
    dev_os_linux:       "Linux",
    dev_os_unknown:     "Unknown",
    src_self:           "This server",
    src_registered:     "Demo",
    src_discovered:     "Discovered",
    info_status_label:  "Status",
    info_source_label:  "Type",
    info_ip_label:      "IP address",
    info_hostname_label:"Hostname",
    info_os_label:      "Operating system",
    info_version_label: "Version / kernel",
    info_lastseen_label:"Last seen",
    info_logs5m_label:  "Logs (5 min)",
    info_logs1h_label:  "Logs (1 h)",
    info_alerts_label:  "Alerts",
    tut_macos_steps: [
      "On your MacBook, open the \"Terminal\" app.",
      "Install syslog-ng (via Homebrew): brew install syslog-ng",
      "Add a destination block to the config (example below), pointing at {collector}.",
      "Start the service: sudo brew services start syslog-ng",
      "Within a few minutes the device will appear in the traffic.",
    ],
    tut_windows_steps: [
      "Download and install \"nxlog Community Edition\".",
      "Add an output block to nxlog.conf (example below), pointing at {collector}.",
      "Assign the output in a Route and set the sender name to {hostname}.",
      "Start the \"nxlog\" service from the Services manager.",
      "Within a few minutes the device will appear in the traffic.",
    ],
    tut_macos_code: "destination d_collector {\n  network(\"{collector}\" transport(\"udp\") port(514));\n};\nlog { source(s_local); destination(d_collector); };",
    tut_windows_code: "<Output collector>\n  Module  om_udp\n  Host    {collector}\n  Port    514\n</Output>",
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
  collector:    null,
  trafficChart: null,
  trafficHost:  "",
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
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

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
  const token = sessionStorage.getItem("auth_token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const r = await fetch(url, { headers });
  if (r.status === 401) {
    sessionStorage.removeItem("auth_token");
    sessionStorage.removeItem("auth_user");
    window.location.replace("/login");
    throw new Error("HTTP 401");
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// POST/DELETE su Bearer tokenu. Klaidos atveju meta Error su serverio `detail`.
async function apiSend(url, method = "POST", body = null) {
  const token = sessionStorage.getItem("auth_token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (body !== null) headers["Content-Type"] = "application/json";
  const r = await fetch(url, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) {
    sessionStorage.removeItem("auth_token");
    sessionStorage.removeItem("auth_user");
    window.location.replace("/login");
    throw new Error("HTTP 401");
  }
  let data = null;
  try { data = await r.json(); } catch (_) { /* tuščias atsakymas */ }
  if (!r.ok) {
    const detail = (data && data.detail) ? data.detail : `HTTP ${r.status}`;
    throw new Error(detail);
  }
  return data;
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
    const q = state.trafficHost ? `&host=${encodeURIComponent(state.trafficHost)}` : "";
    const data = await fetchJSON(`/api/traffic/history?hours=24${q}`);
    state.history = data.points || [];
    renderTrafficChart();
    if (state.page === "anomalies") renderPulseBars();
  } catch (e) {
    console.error("Traffic history:", e);
  }
}

function errorCount() {
  if (!state.current) return 0;
  // Promtail iš syslog-ng išgauna tik standartines syslog severity etiketes:
  // emerg, alert, crit, err, warning, notice, info, debug. Skaičiuojame klaidų lygius.
  const s = state.current.by_severity || {};
  return (s.emerg || 0) + (s.alert || 0) + (s.crit || 0) + (s.err || 0);
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
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Logs",
        data: values,
        borderColor: "#000000",
        backgroundColor: "rgba(0,0,0,0.06)",
        fill: true,
        tension: 0.35,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointBackgroundColor: "#000000",
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
        x: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { color: "#64748b", maxTicksLimit: 8, font: { size: 11 } } },
        y: { grid: { color: "rgba(0,0,0,0.05)" }, ticks: { color: "#64748b", font: { size: 11 } }, beginAtZero: true },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Tinklo aktyvumas — įrenginio pasirinkimas
// ---------------------------------------------------------------------------
function onTrafficDeviceChange() {
  const sel = el("traffic-device-select");
  state.trafficHost = sel ? sel.value : "";
  loadTrafficHistory();
  renderTrafficDeviceStats();
}

function populateTrafficDeviceSelect() {
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

function renderTrafficDeviceStats() {
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

  // Suskaičiuojame realius alertus per kiekvieną valandinį laiko bucket'ą
  // — bar'ai dažomi raudonai tik kai tikrai buvo aptiktas alertas.
  const bucketStart = pts.map(p => new Date(p.time).getTime());
  const bucketEnd = bucketStart.map((s, i) =>
    i + 1 < bucketStart.length ? bucketStart[i + 1] : s + 60 * 60 * 1000
  );
  const alertCounts = bucketStart.map(() => 0);
  for (const a of state.alerts) {
    const ts = new Date(a.timestamp).getTime();
    if (!Number.isFinite(ts)) continue;
    for (let i = 0; i < bucketStart.length; i++) {
      if (ts >= bucketStart[i] && ts < bucketEnd[i]) {
        alertCounts[i]++;
        break;
      }
    }
  }

  const peak = Math.max(...pts.map(p => p.count), 1);
  pts.forEach((p, i) => {
    const pct = Math.max(4, Math.round(p.count / peak * 100));
    const isAnomaly = alertCounts[i] > 0;
    const bar = document.createElement("div");
    bar.className = "flex-1 rounded-t-sm transition-all cursor-default " +
      (isAnomaly ? "bg-error-container/80 hover:bg-error" : "bg-secondary-container/60 hover:bg-secondary");
    bar.style.height = pct + "%";
    bar.title = isAnomaly
      ? `${p.count} logs, ${alertCounts[i]} alert(s)`
      : `${p.count} logs`;
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

  countEl.textContent = state.lang === "lt"
    ? `${count} ${ltResultsWord(count)}`
    : `${count} result${count === 1 ? "" : "s"}`;
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
    const data = await fetchJSON("/api/devices/map");
    state.devices = data.devices || [];
    state.collector = data.collector || null;
    populateTrafficDeviceSelect();
    renderTrafficDeviceStats();
    if (state.page === "devices") renderDevicesPage();
  } catch (e) {
    console.error("Devices:", e);
  }
}

const OS_META = {
  macos:   { icon: "laptop_mac",     label: () => t("dev_os_macos") },
  windows: { icon: "laptop_windows", label: () => t("dev_os_windows") },
  linux:   { icon: "dns",            label: () => t("dev_os_linux") },
  unknown: { icon: "devices_other",  label: () => t("dev_os_unknown") },
};

const SRC_LABEL = {
  self:       () => t("src_self"),
  registered: () => t("src_registered"),
  discovered: () => t("src_discovered"),
};

function renderDevicesPage() {
  const devices = state.devices;
  const online  = devices.filter(d => d.online).length;
  const logs5m  = devices.reduce((s, d) => s + (d.logs_5m || 0), 0);
  setText("devices-total",  String(devices.length));
  setText("devices-online", String(online));
  setText("devices-logs5m", numFmt(logs5m));

  // Demonstracijos mygtukas aktyvus tik jei yra sintetinis (registruotas) įrenginys.
  const demoBtn = el("devices-demo-btn");
  if (demoBtn) demoBtn.disabled = !devices.some(d => d.source === "registered");

  renderDeviceMap();
  renderDeviceTable();
}

function deviceNodeColor(d) {
  if (d.alert_count > 0) return "#ba1a1a";   // su įspėjimais
  if (d.online)         return "#006c49";    // aktyvus
  return "#76777d";                          // neaktyvus
}

function renderDeviceMap() {
  const host    = el("device-map");
  const emptyEl = el("device-map-empty");
  if (!host) return;

  const devices = state.devices;
  if (!devices.length) {
    host.innerHTML = "";
    host.classList.add("hidden");
    if (emptyEl) { emptyEl.classList.remove("hidden"); emptyEl.textContent = t("map_empty"); }
    return;
  }
  host.classList.remove("hidden");
  if (emptyEl) emptyEl.classList.add("hidden");

  const W = 640, H = 340, cx = W / 2, cy = H / 2;
  const n = devices.length;
  const R = Math.min(150, 95 + n * 4);
  const collectorOnline = !!(state.collector && state.collector.online);

  const pos = devices.map((d, i) => {
    const ang = (-Math.PI / 2) + (2 * Math.PI * i / n);
    return { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
  });

  let spokes = "", nodes = "";
  pos.forEach((p, i) => {
    const d = devices[i];
    spokes += `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" ` +
      `stroke="${d.online ? "#c6c6cd" : "#e0e3e5"}" stroke-width="2"` +
      `${d.online ? "" : ' stroke-dasharray="4 4"'}/>`;
  });
  pos.forEach((p, i) => {
    const d = devices[i];
    const r = 22;
    const name = d.name.length > 16 ? d.name.slice(0, 15) + "…" : d.name;
    nodes += `<g class="map-node" data-idx="${i}" style="cursor:pointer">` +
      `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${r}" fill="${deviceNodeColor(d)}" opacity="${d.online ? 1 : 0.55}"/>` +
      `<text x="${p.x.toFixed(1)}" y="${(p.y + 1).toFixed(1)}" text-anchor="middle" dominant-baseline="middle" fill="#fff" font-size="11" font-weight="700">${d.logs_5m}</text>` +
      `<text x="${p.x.toFixed(1)}" y="${(p.y + r + 14).toFixed(1)}" text-anchor="middle" fill="#191c1e" font-size="11" font-weight="600">${esc(name)}</text>` +
      `</g>`;
  });

  const cCol = collectorOnline ? "#000000" : "#76777d";
  const rack = [-8, -1, 6].map(dy =>
    `<rect x="${cx - 10}" y="${cy + dy}" width="20" height="4" rx="1" fill="#fff" opacity="0.9"/>`).join("");

  host.innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;height:auto" font-family="Inter, sans-serif">` +
    spokes +
    `<g><circle cx="${cx}" cy="${cy}" r="30" fill="${cCol}"/>${rack}</g>` +
    `<text x="${cx}" y="${cy + 48}" text-anchor="middle" fill="#191c1e" font-size="11" font-weight="700">${esc(t("map_collector"))}</text>` +
    nodes +
    `</svg>`;

  host.querySelectorAll(".map-node").forEach(g => {
    g.addEventListener("click", () => openDeviceInfo(devices[parseInt(g.dataset.idx, 10)]));
  });
}

function renderDeviceTable() {
  const tbody = el("devices-tbody");
  if (!tbody) return;
  tbody.textContent = "";

  const devs = filteredDevices();
  if (!devs.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 7;
    td.className = "px-6 py-8 text-center text-on-surface-variant text-sm font-label";
    td.textContent = state.devices.length ? `0 ${state.lang === "lt" ? "rezultatų" : "results"}` : t("map_empty");
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  devs.forEach((d, i) => {
    const tr = document.createElement("tr");
    tr.className = "border-b border-outline-variant/20 last:border-0 hover:bg-surface-container-low transition-colors cursor-pointer" +
      (i % 2 === 1 ? " bg-surface-container-low/30" : "");
    tr.addEventListener("click", () => openDeviceInfo(d));

    // Pavadinimas + šaltinio žyma
    const tdName = document.createElement("td");
    tdName.className = "px-6 py-3";
    const nm = document.createElement("div");
    nm.className = "font-semibold";
    nm.textContent = d.name;
    const src = document.createElement("div");
    src.className = "text-[10px] uppercase tracking-wider font-label text-on-surface-variant";
    src.textContent = (SRC_LABEL[d.source] || (() => d.source))();
    tdName.appendChild(nm);
    tdName.appendChild(src);

    // OS
    const tdOs = document.createElement("td");
    tdOs.className = "px-6 py-3";
    const osMeta = OS_META[d.os] || OS_META.unknown;
    const osWrap = document.createElement("span");
    osWrap.className = "inline-flex items-center gap-1.5 text-on-surface-variant";
    const osIcon = document.createElement("span");
    osIcon.className = "material-symbols-outlined text-base";
    osIcon.textContent = osMeta.icon;
    const osText = document.createElement("span");
    osText.className = "text-xs font-label";
    osText.textContent = osMeta.label();
    osWrap.appendChild(osIcon);
    osWrap.appendChild(osText);
    tdOs.appendChild(osWrap);

    // IP / hostname
    const tdId = document.createElement("td");
    tdId.className = "px-6 py-3 font-mono text-sm";
    const ipLine = document.createElement("div");
    ipLine.className = "font-medium";
    ipLine.textContent = d.ip || "—";
    const hostLine = document.createElement("div");
    hostLine.className = "text-[11px] text-on-surface-variant";
    hostLine.textContent = d.hostname;
    tdId.appendChild(ipLine);
    tdId.appendChild(hostLine);

    // Būsena
    const tdStatus = document.createElement("td");
    tdStatus.className = "px-6 py-3";
    const stWrap = document.createElement("span");
    stWrap.className = "inline-flex items-center gap-1.5 text-xs font-label";
    const dot = document.createElement("span");
    dot.className = "w-2 h-2 rounded-full " + (d.online ? "bg-secondary" : "bg-outline");
    const stTxt = document.createElement("span");
    stTxt.textContent = d.online ? t("dev_status_online") : t("dev_status_offline");
    stWrap.appendChild(dot);
    stWrap.appendChild(stTxt);
    tdStatus.appendChild(stWrap);

    // Logai (5 min)
    const tdLogs = document.createElement("td");
    tdLogs.className = "px-6 py-3 font-bold tabular-nums";
    tdLogs.textContent = numFmt(d.logs_5m || 0);

    // Paskutinis logas
    const tdSeen = document.createElement("td");
    tdSeen.className = "px-6 py-3 text-xs text-on-surface-variant font-label";
    tdSeen.textContent = d.last_seen ? relTime(d.last_seen) : t("dev_never");

    // Veiksmai
    const tdActions = document.createElement("td");
    tdActions.className = "px-6 py-3 text-right whitespace-nowrap";
    tdActions.addEventListener("click", e => e.stopPropagation());

    const infoBtn = document.createElement("button");
    infoBtn.className = "inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold text-on-surface-variant hover:bg-surface-container transition font-label";
    infoBtn.title = t("dev_info");
    const infoIcon = document.createElement("span");
    infoIcon.className = "material-symbols-outlined text-base";
    infoIcon.textContent = "info";
    infoBtn.appendChild(infoIcon);
    infoBtn.addEventListener("click", () => openDeviceInfo(d));
    tdActions.appendChild(infoBtn);

    if (d.source === "registered") {
      const tutBtn = document.createElement("button");
      tutBtn.className = "inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold text-on-surface-variant hover:bg-surface-container transition font-label ml-1";
      tutBtn.title = t("dev_tutorial");
      const tutIcon = document.createElement("span");
      tutIcon.className = "material-symbols-outlined text-base";
      tutIcon.textContent = "help";
      tutBtn.appendChild(tutIcon);
      tutBtn.addEventListener("click", () => showDeviceTutorial(d));
      tdActions.appendChild(tutBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-bold text-error hover:bg-error-container transition font-label ml-1";
      delBtn.title = t("dev_delete");
      const delIcon = document.createElement("span");
      delIcon.className = "material-symbols-outlined text-base";
      delIcon.textContent = "delete";
      delBtn.appendChild(delIcon);
      delBtn.addEventListener("click", () => deleteDevice(d.id, d.name));
      tdActions.appendChild(delBtn);
    }

    tr.appendChild(tdName);
    tr.appendChild(tdOs);
    tr.appendChild(tdId);
    tr.appendChild(tdStatus);
    tr.appendChild(tdLogs);
    tr.appendChild(tdSeen);
    tr.appendChild(tdActions);
    tbody.appendChild(tr);
  });
}

// ---------------------------------------------------------------------------
// Devices — informacijos langas
// ---------------------------------------------------------------------------
function openDeviceInfo(d) {
  if (!d) return;
  const modal = el("device-info-modal");
  if (!modal) return;

  setText("device-info-name", d.name);
  const dot = el("device-info-status-dot");
  if (dot) dot.className = "w-2.5 h-2.5 rounded-full " + (d.alert_count > 0 ? "bg-error" : d.online ? "bg-secondary" : "bg-outline");

  setText("info-status", d.online ? t("dev_status_online") : t("dev_status_offline"));
  setText("info-source", (SRC_LABEL[d.source] || (() => d.source))());
  setText("info-ip", d.ip || "—");
  setText("info-hostname", d.hostname);
  setText("info-os", (OS_META[d.os] || OS_META.unknown).label());
  setText("info-version", d.os_version || "—");
  setText("info-lastseen", d.last_seen ? relTime(d.last_seen) : t("dev_never"));
  setText("info-logs5m", numFmt(d.logs_5m || 0));
  setText("info-logs1h", numFmt(d.logs_1h || 0));
  setText("info-alerts", String(d.alert_count || 0));

  modal.classList.remove("hidden");
}

function closeDeviceInfo() {
  const modal = el("device-info-modal");
  if (modal) modal.classList.add("hidden");
}

function onDeviceInfoBackdrop(event) {
  if (event.target === el("device-info-modal")) closeDeviceInfo();
}

// ---------------------------------------------------------------------------
// Devices — modalas, instrukcija, demonstracija
// ---------------------------------------------------------------------------
function openAddDeviceModal() {
  const modal = el("device-modal");
  if (!modal) return;
  el("device-modal-form").classList.remove("hidden");
  el("device-modal-tutorial").classList.add("hidden");
  el("dev-name").value = "";
  el("dev-ip").value = "";
  el("dev-os").value = "macos";
  const err = el("dev-form-error");
  if (err) err.classList.add("hidden");
  modal.classList.remove("hidden");
  el("dev-name").focus();
}

function closeDeviceModal() {
  const modal = el("device-modal");
  if (modal) modal.classList.add("hidden");
}

function onDeviceModalBackdrop(event) {
  if (event.target === el("device-modal")) closeDeviceModal();
}

async function submitAddDevice() {
  const name = el("dev-name").value.trim();
  const ip   = el("dev-ip").value.trim();
  const os   = el("dev-os").value;
  const err  = el("dev-form-error");
  const saveBtn = el("dev-save-btn");

  const showErr = msg => {
    if (err) { err.textContent = msg; err.classList.remove("hidden"); }
  };

  if (!name)              return showErr(t("dev_err_name"));
  if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(ip)) return showErr(t("dev_err_ip"));

  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = t("dev_saving"); }
  try {
    const device = await apiSend("/api/devices", "POST", { name, ip, os });
    await loadDevices();
    navigate("devices");
    showDeviceTutorial(device);
  } catch (e) {
    showErr(e.message || t("dev_err_ip"));
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = t("dev_save"); }
  }
}

function showDeviceTutorial(device) {
  const modal = el("device-modal");
  if (!modal) return;
  el("device-modal-form").classList.add("hidden");
  el("device-modal-tutorial").classList.remove("hidden");

  const collector = window.location.hostname || "<serverio-ip>";

  setText("device-tut-intro", t("dev_tut_intro")(device.name));

  const stepsKey = device.os === "windows" ? "tut_windows_steps" : "tut_macos_steps";
  const codeKey  = device.os === "windows" ? "tut_windows_code"  : "tut_macos_code";
  const steps = (t(stepsKey) || []).map(s =>
    s.replace(/\{collector\}/g, collector).replace(/\{hostname\}/g, device.hostname));

  const ol = el("device-tut-steps");
  ol.textContent = "";
  steps.forEach(s => {
    const li = document.createElement("li");
    li.className = "leading-relaxed";
    li.textContent = s;
    ol.appendChild(li);
  });

  const code = String(t(codeKey) || "")
    .replace(/\{collector\}/g, collector)
    .replace(/\{hostname\}/g, device.hostname);
  setText("device-tut-code", code);

  modal.classList.remove("hidden");
}

async function deleteDevice(id, name) {
  if (!confirm(t("dev_delete_confirm")(name))) return;
  try {
    await apiSend(`/api/devices/${id}`, "DELETE");
    await loadDevices();
    renderDevicesPage();
  } catch (e) {
    console.error("Delete device:", e);
  }
}

function showDemoStatus(msg) {
  const box = el("devices-demo-status");
  if (box) {
    box.classList.remove("hidden");
    setText("devices-demo-status-text", msg);
  }
}

async function runAttackDemo(id) {
  // Ataka taikoma tik sintetiniam (registruotam) įrenginiui — realių host'ų nepaliečiame.
  const registered = state.devices.find(d => d.source === "registered");
  const target = id || (registered && registered.id);
  if (!target) {
    showDemoStatus(t("dev_demo_none"));
    return;
  }
  const demoBtn = el("devices-demo-btn");
  if (demoBtn) demoBtn.disabled = true;
  showDemoStatus(t("dev_demo_running"));
  try {
    const res = await apiSend(`/api/devices/${target}/simulate`, "POST", {});
    showDemoStatus(t("dev_demo_sent")(res.target));
    // Po kelių sekundžių atnaujiname srautą ir įspėjimus, kad demonstracija būtų matoma.
    setTimeout(() => { loadTrafficCurrent(); loadTrafficHistory(); loadAlerts(); loadDevices(); }, 4000);
  } catch (e) {
    showDemoStatus(e.message || t("dev_demo_error"));
  } finally {
    if (demoBtn) demoBtn.disabled = false;
  }
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
  setText("tds-status-label",       t("info_status_label"));
  setText("tds-logs5m-label",       t("info_logs5m_label"));
  setText("tds-lastseen-label",     t("info_lastseen_label"));
  setText("tds-alerts-label",       t("info_alerts_label"));
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
  setText("devices-online-label",   t("dev_online_card"));
  setText("devices-logs5m-label",   t("dev_logs5m_card"));
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
  setText("devices-demo-btn-label", t("dev_demo_btn"));
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
  setPlaceholder("dev-name",        t("dev_name_ph"));
  setPlaceholder("dev-ip",          t("dev_ip_ph"));
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
  populateTrafficDeviceSelect();
  renderTrafficDeviceStats();
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

  // Praleidžiame pollinimą kai tabas paslėptas — taupome resursus.
  const whenVisible = fn => () => {
    if (document.visibilityState === "visible") fn();
  };
  setInterval(whenVisible(loadHealth),          30_000);
  setInterval(whenVisible(loadTrafficCurrent),  30_000);
  setInterval(whenVisible(loadTrafficHistory),  60_000);
  setInterval(whenVisible(loadAlerts),          15_000);
  setInterval(whenVisible(loadDevices),         15_000);

  // Grįžus į tabą — iš karto atnaujiname duomenis.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      loadHealth();
      loadTrafficCurrent();
      loadAlerts();
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
