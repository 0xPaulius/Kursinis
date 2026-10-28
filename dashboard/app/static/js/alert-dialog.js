// Įspėjimo detalių langas (atidaromas iš apžvalgos ir anomalijų puslapių).

import { el, setText } from "./dom.js";
import { alertExpl, alertRec, alertTitle, detailLabel, methodLabel, sevLabel, t } from "./i18n.js";
import { formatDetailValue, fullTime } from "./format.js";

// Anomaly type visual config
export const ANOMALY_CARD_CFG = {
  ssh_bruteforce:    { icon: "login",         bg: "bg-tertiary-fixed",             fg: "text-on-tertiary-container",  badge_bg: "bg-tertiary-fixed",             badge_fg: "text-on-tertiary-container",  risk: "medium"   },
  invalid_user_scan: { icon: "person_off",    bg: "bg-error-container",            fg: "text-on-error-container",     badge_bg: "bg-error-container",            badge_fg: "text-on-error-container",     risk: "critical" },
  firewall_spike:    { icon: "shield",        bg: "bg-error-container",            fg: "text-on-error-container",     badge_bg: "bg-error-container",            badge_fg: "text-on-error-container",     risk: "critical" },
  high_error_rate:   { icon: "error_outline", bg: "bg-surface-container-highest",  fg: "text-on-surface",             badge_bg: "bg-surface-container-high",     badge_fg: "text-on-surface-variant",     risk: "warning"  },
  log_volume_spike:  { icon: "bar_chart",     bg: "bg-tertiary-fixed",             fg: "text-on-tertiary-container",  badge_bg: "bg-tertiary-fixed",             badge_fg: "text-on-tertiary-container",  risk: "medium"   },
};

const _SEV_BADGE = {
  critical: "bg-error-container text-on-error-container",
  high:     "bg-error-container text-on-error-container",
  medium:   "bg-tertiary-fixed text-on-tertiary-container",
  low:      "bg-secondary-container text-on-secondary-container",
};

// Parodo/paslepia eilutę informacijos lange (ir įrašo reikšmę).
function setAlertRow(rowId, valId, val) {
  const row = el(rowId);
  if (!row) return;
  if (val) { row.className = "flex justify-between gap-4"; setText(valId, val); }
  else { row.className = "hidden"; }
}

function renderAlertDetails(details) {
  const wrap = el("alert-info-details-wrap");
  const dl = el("alert-info-details");
  if (!wrap || !dl) return;
  dl.textContent = "";
  const entries = (details && typeof details === "object") ? Object.entries(details) : [];
  if (!entries.length) { wrap.classList.add("hidden"); return; }
  wrap.classList.remove("hidden");
  entries.forEach(([k, v]) => {
    const row = document.createElement("div");
    row.className = "flex justify-between gap-4 py-1.5 border-b border-outline-variant/30 last:border-0";
    const dt = document.createElement("dt");
    dt.className = "text-on-surface-variant font-label shrink-0";
    dt.textContent = detailLabel(k);
    const dd = document.createElement("dd");
    dd.className = "font-medium text-right break-all";
    dd.textContent = formatDetailValue(v);
    row.appendChild(dt);
    row.appendChild(dd);
    dl.appendChild(row);
  });
}

export function openAlertInfo(a) {
  if (!a) return;
  const modal = el("alert-info-modal");
  if (!modal) return;

  const cfg = ANOMALY_CARD_CFG[a.alert_type] ||
    { icon: "warning", bg: "bg-error-container", fg: "text-on-error-container" };

  const iconWrap = el("alert-info-icon-wrap");
  if (iconWrap) iconWrap.className = `w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${cfg.bg}`;
  const icon = el("alert-info-icon");
  if (icon) { icon.className = `material-symbols-outlined text-lg ${cfg.fg}`; icon.textContent = cfg.icon; }

  setText("alert-info-title", alertTitle(a.alert_type, a.title));

  const sev = el("alert-info-severity");
  if (sev) {
    sev.className = `px-2.5 py-1 rounded-full text-[10px] font-bold uppercase font-label ${_SEV_BADGE[a.severity] || _SEV_BADGE.low}`;
    sev.textContent = sevLabel(a.severity);
  }
  setText("alert-info-time", fullTime(a.timestamp));

  setAlertRow("alert-info-ip-row", "alert-info-ip", a.source_ip);
  setAlertRow("alert-info-host-row", "alert-info-host", a.source_host);
  setText("alert-info-method", methodLabel(a.detection_method));

  // ATT&CK technikos (jei yra) — ženkliukai
  const techs = Array.isArray(a.attack_techniques) ? a.attack_techniques : [];
  const techRow = el("alert-info-attack-row");
  const techWrap = el("alert-info-attack");
  setText("alert-info-attack-label", t("alert_techniques"));
  if (techRow && techWrap) {
    techWrap.textContent = "";
    if (techs.length) {
      techRow.classList.remove("hidden");
      techs.forEach(tid => {
        const chip = document.createElement("span");
        chip.className = "font-data-mono text-label-sm px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface";
        chip.textContent = tid;
        techWrap.appendChild(chip);
      });
    } else {
      techRow.classList.add("hidden");
    }
  }

  setText("alert-info-expl", alertExpl(a.alert_type) || a.explanation || "");

  const rec = alertRec(a.alert_type) || a.recommendation || "";
  const recWrap = el("alert-info-rec-wrap");
  if (recWrap) {
    if (rec) { recWrap.className = "bg-surface-container rounded-lg p-3"; setText("alert-info-rec", rec); }
    else { recWrap.className = "hidden"; }
  }

  renderAlertDetails(a.details);

  // Žali log įrašai, sukėlę įspėjimą
  const rawWrap = el("alert-info-raw-wrap");
  const rawPre = el("alert-info-raw");
  const lines = Array.isArray(a.sample_lines) ? a.sample_lines : [];
  if (rawWrap && rawPre) {
    if (lines.length) {
      rawWrap.classList.remove("hidden");
      rawPre.textContent = lines.join("\n");
    } else {
      rawWrap.classList.add("hidden");
    }
  }

  modal.classList.remove("hidden");
}

function closeAlertInfo() {
  const modal = el("alert-info-modal");
  if (modal) modal.classList.add("hidden");
}

function onAlertInfoBackdrop(event) {
  if (event.target === el("alert-info-modal")) closeAlertInfo();
}

export function initAlertDialog() {
  el("alert-info-modal")?.addEventListener("click", onAlertInfoBackdrop);
  document.querySelectorAll('[data-close="alert-info-modal"]').forEach(btn =>
    btn.addEventListener("click", closeAlertInfo));
}
