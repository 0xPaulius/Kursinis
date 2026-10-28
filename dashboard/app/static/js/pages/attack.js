// MITRE ATT&CK aprėpties puslapis.

import { el } from "../dom.js";
import { state } from "../state.js";
import { t } from "../i18n.js";

function _attackCard(label, value, total, valueCls) {
  const panel = document.createElement("div");
  panel.className = "panel stat col-span-12 sm:col-span-4";
  const head = document.createElement("div");
  head.className = "panel-h";
  const l = document.createElement("span");
  l.textContent = label;
  head.appendChild(l);
  const v = document.createElement("div");
  v.className = "stat-v " + valueCls;
  v.textContent = String(value);
  if (total != null) {
    const of = document.createElement("small");
    of.textContent = `/ ${total}`;
    v.appendChild(of);
  }
  panel.append(head, v);
  return panel;
}

function _attackCell(row) {
  const cell = document.createElement("div");
  cell.className = "attack-cell " + (row.detected ? "is-detected" : row.has_rule ? "is-rule" : "is-none");
  cell.title = row.detected ? t("attack_detected_badge") : row.has_rule ? t("attack_has_rule") : t("attack_no_rule");
  const id = document.createElement("div");
  id.className = "mono text-[11.5px]";
  id.textContent = row.technique;
  const name = document.createElement("div");
  name.className = "text-[12px] leading-snug mt-0.5";
  name.textContent = row.name;
  cell.append(id, name);
  return cell;
}

export function renderAttackCoverage() {
  const data = state.attackCoverage;
  const matrix = el("attack-matrix");
  const summary = el("attack-summary");
  const unavailable = el("attack-unavailable");
  if (!matrix || !summary || !unavailable) return;

  matrix.textContent = "";
  summary.textContent = "";

  const available = !!(data && data.available);
  el("attack-matrix-panel")?.classList.toggle("hidden", !available);
  if (!available) {
    unavailable.classList.remove("hidden");
    unavailable.textContent = t("attack_unavailable");
    return;
  }
  unavailable.classList.add("hidden");

  summary.appendChild(_attackCard(t("attack_total"), data.total, null, "text-strong"));
  summary.appendChild(_attackCard(t("attack_with_rule"), data.with_rule, data.total, "text-accent"));
  summary.appendChild(_attackCard(t("attack_detected"), data.detected, data.total, "text-ok"));

  Object.keys(data.by_tactic).sort().forEach(tactic => {
    const col = document.createElement("div");
    col.className = "attack-col";
    const h = document.createElement("h4");
    h.textContent = tactic;
    col.appendChild(h);
    data.by_tactic[tactic].forEach(row => col.appendChild(_attackCell(row)));
    matrix.appendChild(col);
  });
}

export const render = renderAttackCoverage;
