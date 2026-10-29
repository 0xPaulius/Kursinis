// Įspėjimų lentelės eilutė ir detalių langas (naudoja apžvalgos, anomalijų ir įrenginio puslapiai).

import { closeDialog, el, openDialog, setText } from "./dom.js";
import { alertExpl, alertRec, alertTitle, detailLabel, methodLabel, sevLabel, t } from "./i18n.js";
import { formatDetailValue, fullTime, shortTime } from "./format.js";

export function sevBadge(severity) {
  const badge = document.createElement("span");
  badge.className = `sev-badge sev-${severity}`;
  const dot = document.createElement("i");
  dot.className = `bg-sev-${severity}`;
  const label = document.createElement("span");
  label.textContent = sevLabel(severity);
  badge.append(dot, label);
  return badge;
}

// Lentelės eilutė: laikas, lygis, įvykis, šaltinis, įrenginys, ATT&CK; paspaudus — detalės.
export function alertRow(a) {
  const tr = document.createElement("tr");
  tr.className = "is-click";
  tr.addEventListener("click", () => openAlertInfo(a));
  const cell = (text, cls) => {
    const td = document.createElement("td");
    if (cls) td.className = cls;
    td.textContent = text;
    tr.appendChild(td);
  };
  cell(shortTime(a.timestamp), "mono text-muted whitespace-nowrap");
  const sevTd = document.createElement("td");
  sevTd.appendChild(sevBadge(a.severity));
  tr.appendChild(sevTd);
  cell(alertTitle(a.alert_type, a.title));
  cell(a.source_ip || "—", "mono text-muted");
  cell(a.source_host || "—");
  cell((a.attack_techniques || []).join(", ") || "—", "mono text-accent whitespace-nowrap");
  return tr;
}

// Įvykio tipo ikona (detalių lange) ir rizika (anomalijų puslapio skydeliuose)
export const ANOMALY_CARD_CFG = {
  ssh_bruteforce:    { icon: "login",         risk: "medium"   },
  invalid_user_scan: { icon: "person_off",    risk: "critical" },
  firewall_spike:    { icon: "shield",        risk: "critical" },
  high_error_rate:   { icon: "error_outline", risk: "warning"  },
  log_volume_spike:  { icon: "bar_chart",     risk: "medium"   },
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
    row.className = "flex justify-between gap-4";
    const dt = document.createElement("dt");
    dt.textContent = detailLabel(k);
    const dd = document.createElement("dd");
    dd.className = "break-all";
    dd.textContent = formatDetailValue(v);
    row.appendChild(dt);
    row.appendChild(dd);
    dl.appendChild(row);
  });
}

export function openAlertInfo(a) {
  if (!a) return;
  if (!el("alert-info-modal")) return;

  const icon = el("alert-info-icon");
  if (icon) {
    icon.className = `material-symbols-outlined text-[20px] shrink-0 sev-${a.severity}`;
    icon.textContent = (ANOMALY_CARD_CFG[a.alert_type] || { icon: "warning" }).icon;
  }

  setText("alert-info-title", alertTitle(a.alert_type, a.title));

  el("alert-info-severity")?.replaceChildren(sevBadge(a.severity));
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
        chip.className = "mono text-[11.5px] px-1.5 py-0.5 rounded bg-hover text-accent";
        chip.textContent = tid;
        techWrap.appendChild(chip);
      });
    } else {
      techRow.classList.add("hidden");
    }
  }

  setText("alert-info-expl", alertExpl(a.alert_type) || a.explanation || "");

  const rec = alertRec(a.alert_type) || a.recommendation || "";
  el("alert-info-rec-wrap")?.classList.toggle("hidden", !rec);
  setText("alert-info-rec", rec);

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

  openDialog("alert-info-modal");
}

function closeAlertInfo() {
  closeDialog("alert-info-modal");
}

function onAlertInfoBackdrop(event) {
  if (event.target === el("alert-info-modal")) closeAlertInfo();
}

export function initAlertDialog() {
  el("alert-info-modal")?.addEventListener("click", onAlertInfoBackdrop);
  document.querySelectorAll('[data-close="alert-info-modal"]').forEach(btn =>
    btn.addEventListener("click", closeAlertInfo));
}
