/* ============================================================
   Stebėjimo pultas — Alpine.js komponentai
   ============================================================ */

// --- Pagalbinės funkcijos ---

/**
 * Grąžina santykinį laiką lietuviškai, pvz. "prieš 5 min".
 */
function relativeTime(isoStr) {
  if (!isoStr) return "";
  const diff = Date.now() - new Date(isoStr).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "ką tik";
  const min = Math.floor(sec / 60);
  if (min < 60) return `prieš ${min} min`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `prieš ${hrs} val`;
  const days = Math.floor(hrs / 24);
  return `prieš ${days} d`;
}

/**
 * Grąžina lietuvišką rimtingumo pavadinimą.
 */
function severityLabel(s) {
  const map = { low: "Žemas", medium: "Vidutinis", high: "Aukštas", critical: "Kritinis" };
  return map[s] || s;
}

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// --- Alpine komponentai ---

document.addEventListener("alpine:init", () => {

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
      const map = { ok: "Veikia gerai", warning: "Įspėjimas", critical: "Kritinė būklė", unknown: "Tikrinama..." };
      return map[this.overall] || "Nežinoma";
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

    async init() {
      await this.loadCurrent();
      await this.loadChart();
      setInterval(() => this.loadCurrent(), 30_000);
      setInterval(() => this.loadChart(), 60_000);
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
        this.renderChart(data.points);
      } catch {
        // Chart nebus atnaujintas, bet nerodome klaidos
      }
    },

    renderChart(points) {
      const canvas = document.getElementById("traffic-chart");
      if (!canvas) return;

      const labels = points.map(p => {
        const d = new Date(p.time);
        return d.toLocaleTimeString("lt-LT", { hour: "2-digit", minute: "2-digit" });
      });
      const values = points.map(p => p.count);

      // Adaptuojame spalvą pagal dark mode
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const gridColor = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
      const tickColor = isDark ? "#94a3b8" : "#64748b";
      const lineColor = "#6366f1";
      const fillColor = isDark ? "rgba(99,102,241,0.15)" : "rgba(99,102,241,0.1)";

      if (this.chart) {
        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = values;
        this.chart.update("none");
        return;
      }

      this.chart = new Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [{
            label: "Žurnalai / val",
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
                label: ctx => `${ctx.parsed.y} žurnalų`,
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

    relTime: relativeTime,
    sevLabel: severityLabel,
  }));

});
