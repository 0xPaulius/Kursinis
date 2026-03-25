/* ============================================================
   Stebėjimo pultas — Alpine.js komponentai
   ============================================================ */

// --- Vertimų žodynai ---

const LT = {
  // Antraštė
  title:            "Stebėjimo pultas",
  subtitle:         "Centralizuota log analizės sistema",
  lang_switch:      "EN",
  checked_at:       "Patikrinta:",

  // Bendra būklė
  badge_ok:         "All OK",
  badge_warning:    "Įspėjimas",
  badge_critical:   "Kritinė būklė",
  badge_unknown:    "Tikrinama...",

  // Sistemos būklė
  system_status:    "Sistemos būklė",
  loading:          "Kraunama...",
  status_error:     "Nepavyko gauti sistemos būklės. Bandoma iš naujo...",

  // Paslaugų pavadinimai
  svc_loki:         "Log saugykla (Loki)",
  svc_syslog:       "Log rinkimas (syslog-ng)",
  svc_promtail:     "Log persiuntimas (Promtail)",
  svc_detector:     "Anomalijų aptikimas",

  // Paslaugų žinutės
  msg_ok:           "Veikia normaliai",
  msg_unreachable:  "Nepasiekiama",
  msg_logs_ok:      "Logs gaunami reguliariai",
  msg_logs_warn5:   "Logų negauta per paskutines 5 min",
  msg_logs_warn1h:  "Nėra logų per paskutinę valandą",
  msg_det_ok:       "Veikia (anomalijų dar neaptikta)",
  msg_det_warn:     "Nepavyko perskaityti duomenų",

  // Log srautas
  log_traffic:      "Log srautas",
  traffic_error:    "Nepavyko gauti srauto duomenų.",
  logs_5min:        "Logs per 5 min",
  logs_per_min:     "Logs per minutę",
  errors_5min:      "Klaidos per 5 min",
  chart_title:      "Log srautas per paskutines 24 val.",
  chart_aria:       "Log srauto grafikas per 24 valandas",
  chart_dataset:    "Logs / val",
  chart_tooltip:    y => `${y} logs`,
  refresh_traffic:  "Atnaujinama automatiškai kas 30 sek.",

  // Įspėjimai
  alerts:           "Įspėjimai",
  alerts_error:     "Nepavyko gauti įspėjimų. Bandoma iš naujo...",
  no_alerts:        "Įspėjimų nėra — sistema veikia normaliai",
  show_history:     "Rodyti visą istoriją",
  loading_hist:     "Kraunama...",
  full_history:     "Visa istorija",
  show_more:        "Rodyti daugiau...",
  refresh_alerts:   "Įspėjimai atnaujinami kas 15 sek.",

  // Rimtingumas
  sev_low:          "Žemas",
  sev_medium:       "Vidutinis",
  sev_high:         "Aukštas",
  sev_critical:     "Kritinis",

  // Santykinis laikas
  rel_just_now:     "ką tik",
  rel_min:          n => `prieš ${n} min`,
  rel_hrs:          n => `prieš ${n} val`,
  rel_days:         n => `prieš ${n} d`,

  // Alert vertimai (sutampa su backend)
  alert_titles: {
    ssh_bruteforce:    "Bandymas įsilaužti per SSH",
    invalid_user_scan: "Nežinomi vartotojai bando jungtis",
    firewall_spike:    "Padidėjęs blokuojamų jungčių kiekis",
    log_volume_spike:  "Neįprastai daug sistemos log",
    high_error_rate:   "Daug sistemos klaidų",
    ml_anomaly:        "Neįprastas sistemos elgesys",
  },
  alert_explanations: {
    ssh_bruteforce:    "Aptikta daug nesėkmingų bandymų prisijungti prie serverio. Tai gali būti bandymas atspėti slaptažodį.",
    invalid_user_scan: "Aptikti bandymai prisijungti su neegzistuojančiais vartotojų vardais. Tai gali reikšti, kad kas nors ieško silpnų vietų jūsų sistemoje.",
    firewall_spike:    "Ugniasienė blokavo neįprastai daug jungčių. Gali būti tinklo ataka arba konfigūracijos problema.",
    log_volume_spike:  "Sistema generuoja žymiai daugiau log nei įprastai. Tai gali reikšti problemą arba padidėjusį apkrovimą.",
    high_error_rate:   "Klaidų kiekis viršija normalų lygį. Kai kurios paslaugos gali veikti netinkamai.",
    ml_anomaly:        "Dirbtinis intelektas aptiko neįprastus sistemos veiklos pokyčius. Tai gali būti ataka, gedimas arba neįprastas naudojimas.",
  },
  alert_recommendations: {
    ssh_bruteforce:    "Rekomenduojama: peržiūrėkite, ar prisijungimas iš nurodyto IP yra leistinas. Jei ne — blokuokite jį ugniasienėje ir pakeiskite slaptažodžius.",
    invalid_user_scan: "Rekomenduojama: patikrinkite, ar nurodyta IP priklausanti jūsų organizacijai. Jei ne — blokuokite ir informuokite IT specialistą.",
    firewall_spike:    "Rekomenduojama: informuokite IT specialistą. Jei sistema dirba lėtai — tai gali būti susiję.",
    log_volume_spike:  "Rekomenduojama: patikrinkite, ar sistema veikia normaliai. Jei lėta ar kyla klaidų — kreipkitės į IT specialistą.",
    high_error_rate:   "Rekomenduojama: patikrinkite, ar visos programos ir paslaugos veikia. Esant problemoms — kreipkitės į IT specialistą.",
    ml_anomaly:        "Rekomenduojama: peržiūrėkite kitus šio laikotarpio įspėjimus. Jei jų daug — nedelsiant informuokite IT specialistą.",
  },
};

const EN = {
  // Header
  title:            "Monitoring Dashboard",
  subtitle:         "Centralized Log Analysis System",
  lang_switch:      "LT",
  checked_at:       "Checked:",

  // Overall status
  badge_ok:         "All Systems OK",
  badge_warning:    "Warning",
  badge_critical:   "Critical",
  badge_unknown:    "Checking...",

  // System status section
  system_status:    "System Status",
  loading:          "Loading...",
  status_error:     "Failed to retrieve system status. Retrying...",

  // Service names
  svc_loki:         "Log Storage (Loki)",
  svc_syslog:       "Log Collection (syslog-ng)",
  svc_promtail:     "Log Forwarding (Promtail)",
  svc_detector:     "Anomaly Detection",

  // Service messages (mapped from Lithuanian API responses)
  msg_ok:           "Operating normally",
  msg_unreachable:  "Unreachable",
  msg_logs_ok:      "Logs received regularly",
  msg_logs_warn5:   "No logs received in the last 5 min",
  msg_logs_warn1h:  "No logs in the past hour",
  msg_det_ok:       "Running (no anomalies detected yet)",
  msg_det_warn:     "Failed to read data",

  // Log traffic section
  log_traffic:      "Log Traffic",
  traffic_error:    "Failed to retrieve traffic data.",
  logs_5min:        "Logs (5 min)",
  logs_per_min:     "Logs / minute",
  errors_5min:      "Errors (5 min)",
  chart_title:      "Log traffic — last 24 hours",
  chart_aria:       "Log traffic chart for the past 24 hours",
  chart_dataset:    "Logs / hr",
  chart_tooltip:    y => `${y} logs`,
  refresh_traffic:  "Auto-refreshed every 30 sec.",

  // Alerts section
  alerts:           "Alerts",
  alerts_error:     "Failed to retrieve alerts. Retrying...",
  no_alerts:        "No alerts — system operating normally",
  show_history:     "View full history",
  loading_hist:     "Loading...",
  full_history:     "Full history",
  show_more:        "Show more...",
  refresh_alerts:   "Alerts refresh every 15 sec.",

  // Severity labels
  sev_low:          "Low",
  sev_medium:       "Medium",
  sev_high:         "High",
  sev_critical:     "Critical",

  // Relative time
  rel_just_now:     "just now",
  rel_min:          n => `${n} min ago`,
  rel_hrs:          n => `${n} hr ago`,
  rel_days:         n => `${n}d ago`,

  // Alert translations
  alert_titles: {
    ssh_bruteforce:    "SSH Brute-Force Attempt",
    invalid_user_scan: "Unknown Users Attempting to Connect",
    firewall_spike:    "Spike in Blocked Connections",
    log_volume_spike:  "Unusually High Log Volume",
    high_error_rate:   "High Error Rate",
    ml_anomaly:        "Unusual System Behaviour",
  },
  alert_explanations: {
    ssh_bruteforce:    "Many failed login attempts were detected on the server. This may be a password-guessing attack.",
    invalid_user_scan: "Login attempts using non-existent usernames were detected. Someone may be probing for weak points in your system.",
    firewall_spike:    "The firewall blocked an unusually high number of connections. This may indicate a network attack or misconfiguration.",
    log_volume_spike:  "The system is generating significantly more logs than usual. This may indicate a problem or increased load.",
    high_error_rate:   "The error count has exceeded the normal level. Some services may not be functioning correctly.",
    ml_anomaly:        "The AI detected unusual changes in system activity. This could be an attack, a fault, or abnormal usage.",
  },
  alert_recommendations: {
    ssh_bruteforce:    "Recommended: check whether logins from the listed IP are legitimate. If not — block it in the firewall and change passwords.",
    invalid_user_scan: "Recommended: verify whether the listed IP belongs to your organisation. If not — block it and notify your IT team.",
    firewall_spike:    "Recommended: notify your IT team. If the system is running slowly, this may be related.",
    log_volume_spike:  "Recommended: check whether the system is functioning normally. If slow or showing errors — contact your IT team.",
    high_error_rate:   "Recommended: verify that all applications and services are running. If problems persist — contact your IT team.",
    ml_anomaly:        "Recommended: review other alerts from this period. If there are many — notify your IT team immediately.",
  },
};

const TRANSLATIONS = { lt: LT, en: EN };

// Žemėlapis: API grąžina lietuviškas žinutes → jų raktai verčiami
const MSG_KEY_MAP = {
  "Veikia normaliai":                     "msg_ok",
  "Nepasiekiama":                         "msg_unreachable",
  "Žurnalai gaunami reguliariai":         "msg_logs_ok",
  "Logs gaunami reguliariai":             "msg_logs_ok",
  "Žurnalų negauta per paskutines 5 min": "msg_logs_warn5",
  "Logų negauta per paskutines 5 min":    "msg_logs_warn5",
  "Nėra žurnalų per paskutinę valandą":   "msg_logs_warn1h",
  "Nėra logų per paskutinę valandą":      "msg_logs_warn1h",
  "Veikia (anomalijų dar neaptikta)":     "msg_det_ok",
  "Nepavyko perskaityti duomenų":         "msg_det_warn",
};

const SVC_KEY_MAP = {
  "loki":              "svc_loki",
  "syslog-ng":         "svc_syslog",
  "promtail":          "svc_promtail",
  "anomaly-detector":  "svc_detector",
};

// --- Alpine komponentai ---

document.addEventListener("alpine:init", () => {

  // --------------------------------------------------------
  // i18n store — bendras kalbos valdymas
  // --------------------------------------------------------
  Alpine.store("i18n", {
    current: localStorage.getItem("lang") || "lt",

    toggle() {
      this.current = this.current === "lt" ? "en" : "lt";
      localStorage.setItem("lang", this.current);
      document.documentElement.lang = this.current;
      // Pranešame grafiko komponentui, kad jis persipieš
      window.dispatchEvent(new CustomEvent("lang-changed"));
    },

    t(key) {
      const tr = TRANSLATIONS[this.current];
      return (tr && tr[key] !== undefined) ? tr[key] : (TRANSLATIONS.en[key] || key);
    },

    relTime(isoStr) {
      if (!isoStr) return "";
      const tr = TRANSLATIONS[this.current];
      const diff = Date.now() - new Date(isoStr).getTime();
      const sec = Math.floor(diff / 1000);
      if (sec < 60) return tr.rel_just_now;
      const min = Math.floor(sec / 60);
      if (min < 60) return tr.rel_min(min);
      const hrs = Math.floor(min / 60);
      if (hrs < 24) return tr.rel_hrs(hrs);
      return tr.rel_days(Math.floor(hrs / 24));
    },

    sevLabel(s) {
      const tr = TRANSLATIONS[this.current];
      const map = { low: tr.sev_low, medium: tr.sev_medium, high: tr.sev_high, critical: tr.sev_critical };
      return map[s] || s;
    },

    svcLabel(name, fallback) {
      const key = SVC_KEY_MAP[name];
      return key ? this.t(key) : fallback;
    },

    svcMsg(msg) {
      const key = MSG_KEY_MAP[msg];
      return key ? this.t(key) : msg;
    },

    alertTitle(type, fallback) {
      return TRANSLATIONS[this.current].alert_titles[type] || fallback;
    },

    alertExplanation(type, fallback) {
      return TRANSLATIONS[this.current].alert_explanations[type] || fallback;
    },

    alertRecommendation(type, fallback) {
      return TRANSLATIONS[this.current].alert_recommendations[type] || fallback;
    },
  });

  // --------------------------------------------------------
  // Viršutinė antraštė — klauso "health-updated" įvykio,
  // kurį siunčia healthPanel. Neatlieka atskirų fetch užklausų.
  // --------------------------------------------------------
  Alpine.data("headerPanel", () => ({
    overall: "unknown",
    checkedAt: "",

    init() {
      window.addEventListener("health-updated", (e) => {
        this.overall = e.detail.overall;
        this.checkedAt = e.detail.checked_at;
      });
    },

    get badgeLabel() {
      return Alpine.store("i18n").t("badge_" + this.overall) || Alpine.store("i18n").t("badge_unknown");
    },
  }));

  // --------------------------------------------------------
  // Paslaugų sveikatos skydelis — vienintelis fetch šaltinis.
  // Skleidžia "health-updated" įvykį antraštei.
  // --------------------------------------------------------
  Alpine.data("healthPanel", () => ({
    services: [],
    loading: true,
    error: false,

    async init() {
      await this.load();
      setInterval(() => this.load(), 30_000);
    },

    async load() {
      try {
        const data = await fetchJSON("/api/health/status");
        this.services = data.services;
        this.error = false;
        window.dispatchEvent(new CustomEvent("health-updated", { detail: data }));
      } catch {
        this.error = true;
      } finally {
        this.loading = false;
      }
    },
  }));

  // --------------------------------------------------------
  // Srauto skydelis — dabartinis rodiklis + grafikas
  // --------------------------------------------------------
  Alpine.data("trafficPanel", () => ({
    current: null,
    loading: true,
    error: false,
    chart: null,
    lastPoints: [],

    async init() {
      await this.loadCurrent();
      await this.loadChart();
      setInterval(() => this.loadCurrent(), 30_000);
      setInterval(() => this.loadChart(), 60_000);
      // Pergeneruojame grafiką keičiantis kalbai
      window.addEventListener("lang-changed", () => this.rebuildChart());
    },

    async loadCurrent() {
      try {
        this.current = await fetchJSON("/api/traffic/current");
        this.error = false;
      } catch {
        this.error = true;
      } finally {
        this.loading = false;
      }
    },

    async loadChart() {
      try {
        const data = await fetchJSON("/api/traffic/history?hours=24");
        this.lastPoints = data.points;
        this.renderChart(data.points);
      } catch {
        // Chart nebus atnaujintas, bet nerodome klaidos
      }
    },

    rebuildChart() {
      // Sunaikinamas senas grafikas ir piešiamas naujas su nauja kalba
      if (this.chart) {
        this.chart.destroy();
        this.chart = null;
      }
      this.renderChart(this.lastPoints);
    },

    renderChart(points) {
      const canvas = document.getElementById("traffic-chart");
      if (!canvas) return;

      const i18n = Alpine.store("i18n");
      const locale = i18n.current === "lt" ? "lt-LT" : "en-GB";

      const labels = points.map(p => {
        const d = new Date(p.time);
        return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
      });
      const values = points.map(p => p.count);

      // Adaptuojame spalvą pagal dark mode
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const gridColor  = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
      const tickColor  = isDark ? "#94a3b8" : "#64748b";
      const lineColor  = "#6366f1";
      const fillColor  = isDark ? "rgba(99,102,241,0.15)" : "rgba(99,102,241,0.1)";

      if (this.chart) {
        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = values;
        this.chart.data.datasets[0].label = i18n.t("chart_dataset");
        this.chart.update("none");
        return;
      }

      this.chart = new Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [{
            label: i18n.t("chart_dataset"),
            data: values,
            borderColor: lineColor,
            backgroundColor: fillColor,
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 400 },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: ctx => ctx[0].label,
                label: ctx => i18n.t("chart_tooltip")(ctx.parsed.y),
              },
            },
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: tickColor, maxTicksLimit: 8, font: { size: 11 } },
            },
            y: {
              grid: { color: gridColor },
              ticks: { color: tickColor, font: { size: 11 } },
              beginAtZero: true,
            },
          },
        },
      });
    },
  }));

  // --------------------------------------------------------
  // Įspėjimų skydelis
  // --------------------------------------------------------
  Alpine.data("alertPanel", () => ({
    alerts: [],
    total: 0,
    loading: true,
    error: false,
    expanded: new Set(),
    historyPage: 1,
    historyAlerts: [],
    historyTotal: 0,
    historyLoading: false,
    showHistory: false,

    async init() {
      await this.loadRecent();
      setInterval(() => this.loadRecent(), 15_000);
    },

    async loadRecent() {
      try {
        const data = await fetchJSON("/api/alerts/recent?limit=20");
        this.alerts = data.alerts;
        this.total = data.total;
        this.error = false;
      } catch {
        this.error = true;
      } finally {
        this.loading = false;
      }
    },

    async loadHistory() {
      if (this.historyLoading) return;
      this.historyLoading = true;
      try {
        const data = await fetchJSON(`/api/alerts/history?page=${this.historyPage}&size=50`);
        this.historyAlerts = [...this.historyAlerts, ...data.alerts];
        this.historyTotal = data.total;
        this.historyPage = data.page + 1;
        this.showHistory = true;
      } catch {
        // tylu
      } finally {
        this.historyLoading = false;
      }
    },

    toggle(id) {
      const next = new Set(this.expanded);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      this.expanded = next;
    },

    isExpanded(id) { return this.expanded.has(id); },
  }));

});

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}
