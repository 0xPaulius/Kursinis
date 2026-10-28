// MITRE ATT&CK aprėpties puslapis.

import { el } from "../dom.js";
import { state } from "../state.js";
import { t } from "../i18n.js";

function _attackCard(label, value, valueCls) {
  const card = document.createElement("div");
  card.className = "bg-surface-container-lowest border border-outline-variant rounded-lg p-stack_md";
  const v = document.createElement("div");
  v.className = "text-display-sm font-headline " + valueCls;
  v.textContent = value;
  const l = document.createElement("div");
  l.className = "text-label-md font-label text-on-surface-variant mt-1";
  l.textContent = label;
  card.appendChild(v);
  card.appendChild(l);
  return card;
}

function _attackCell(row) {
  const cell = document.createElement("div");
  const style = row.detected
    ? "bg-secondary-container border-secondary text-on-secondary-container"
    : row.has_rule
      ? "bg-surface-container-high border-outline-variant text-on-surface"
      : "bg-surface-container-lowest border-dashed border-outline-variant text-on-surface-variant";
  cell.className = "border rounded-lg p-3 text-left " + style;

  const head = document.createElement("div");
  head.className = "flex items-center justify-between gap-2";
  const id = document.createElement("span");
  id.className = "font-data-mono text-label-md";
  id.textContent = row.technique;
  const badge = document.createElement("span");
  if (row.detected) {
    badge.className = "text-label-sm font-label px-1.5 py-0.5 rounded bg-secondary text-on-secondary";
    badge.textContent = t("attack_detected_badge");
  } else {
    badge.className = "text-label-sm font-label text-on-surface-variant";
    badge.textContent = row.has_rule ? t("attack_has_rule") : t("attack_no_rule");
  }
  head.appendChild(id);
  head.appendChild(badge);

  const name = document.createElement("div");
  name.className = "text-body-sm mt-1 leading-snug";
  name.textContent = row.name;

  cell.appendChild(head);
  cell.appendChild(name);
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

  if (!data || !data.available) {
    unavailable.classList.remove("hidden");
    unavailable.textContent = t("attack_unavailable");
    return;
  }
  unavailable.classList.add("hidden");

  summary.appendChild(_attackCard(t("attack_total"), String(data.total), "text-on-surface"));
  summary.appendChild(_attackCard(t("attack_with_rule"), `${data.with_rule} / ${data.total}`, "text-primary"));
  summary.appendChild(_attackCard(t("attack_detected"), `${data.detected} / ${data.total}`, "text-secondary"));

  Object.keys(data.by_tactic).sort().forEach(tactic => {
    const group = document.createElement("div");
    const h = document.createElement("h3");
    h.className = "text-title-md font-headline text-on-surface mb-2";
    h.textContent = tactic;
    const grid = document.createElement("div");
    grid.className = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-stack_sm";
    data.by_tactic[tactic].forEach(row => grid.appendChild(_attackCell(row)));
    group.appendChild(h);
    group.appendChild(grid);
    matrix.appendChild(group);
  });
}

export const render = renderAttackCoverage;
