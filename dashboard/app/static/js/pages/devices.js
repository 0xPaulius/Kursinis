// Įrenginių puslapis: žemėlapis, lentelė, įrenginių langai, demonstracinės atakos;
// #devices/<raktas> — vieno įrenginio puslapis (pages/device-detail.js).

import { closeDialog, el, openDialog, setText } from "../dom.js";
import { state } from "../state.js";
import { apiSend } from "../api.js";
import { t } from "../i18n.js";
import { numFmt, relTime } from "../format.js";
import { filteredDevices, navigate } from "../shell.js";
import { token } from "../charts.js";
import { openDeviceDetail, renderDeviceDetail } from "./device-detail.js";
import { deviceKey, OS_META, sourceLabel } from "./device-meta.js";

// main.js duomenų įkėlimo funkcijos (puslapiai main.js neimportuoja).
let ctx = {};

export function renderDevicesPage() {
  // #devices/<raktas> — vieno įrenginio puslapis vietoje sąrašo.
  const detail = !!state.deviceKey;
  el("devices-list")?.classList.toggle("hidden", detail);
  el("device-detail")?.classList.toggle("hidden", !detail);
  if (detail) {
    renderDeviceDetail();
    return;
  }

  const devices = state.devices;
  const online  = devices.filter(d => d.online).length;
  setText("devices-total",  String(devices.length));
  setText("devices-online", String(online));

  // Atakų ir ML testo mygtukai aktyvūs tik jei yra sintetinis (registruotas) įrenginys.
  const hasSynthetic = devices.some(d => d.source === "registered");
  const demoBtn = el("devices-demo-btn");
  if (demoBtn) demoBtn.disabled = !hasSynthetic;
  const attackBtn = el("attack-btn");
  if (attackBtn) attackBtn.disabled = !hasSynthetic;

  renderDeviceMap();
  renderDeviceTable();
}

function deviceNodeColor(d) {
  if (d.alert_count > 0) return token("--crit");   // su įspėjimais
  if (d.online)         return token("--ok");      // aktyvus
  return token("--text-dim");                      // neaktyvus
}

function renderDeviceMap() {
  const host    = el("device-map");
  const emptyEl = el("device-map-empty");
  if (!host) return;

  const clear = (node) => { while (node.firstChild) node.removeChild(node.firstChild); };

  const devices = state.devices;
  if (!devices.length) {
    clear(host);
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

  // SVG kuriamas saugiais DOM metodais; tekstas dedamas per textContent
  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };

  const svg = svgEl("svg", {
    viewBox: `0 0 ${W} ${H}`, width: "100%",
    style: `max-width:${W}px;height:auto`, "font-family": "Inter, sans-serif",
  });

  // Linijos iki kolektoriaus
  pos.forEach((p, i) => {
    const d = devices[i];
    const line = svgEl("line", {
      x1: cx, y1: cy, x2: p.x.toFixed(1), y2: p.y.toFixed(1),
      stroke: token(d.online ? "--text-dim" : "--line"), "stroke-width": "1.5",
    });
    if (!d.online) line.setAttribute("stroke-dasharray", "4 4");
    svg.appendChild(line);
  });

  // Kolektorius (centras)
  const cCol = token(collectorOnline ? "--accent" : "--text-dim");
  const cg = svgEl("g", {});
  cg.appendChild(svgEl("circle", { cx, cy, r: "30", fill: cCol }));
  [-8, -1, 6].forEach(dy => {
    cg.appendChild(svgEl("rect", { x: cx - 10, y: cy + dy, width: "20", height: "4", rx: "1", fill: "#fff", opacity: "0.9" }));
  });
  svg.appendChild(cg);

  const cLabel = svgEl("text", {
    x: cx, y: cy + 48, "text-anchor": "middle", fill: token("--text-strong"), "font-size": "11", "font-weight": "600",
  });
  cLabel.textContent = t("map_collector");
  svg.appendChild(cLabel);

  // Įrenginių mazgai
  pos.forEach((p, i) => {
    const d = devices[i];
    const r = 22;
    const name = d.name.length > 16 ? d.name.slice(0, 15) + "…" : d.name;
    const g = svgEl("g", { class: "map-node", "data-idx": String(i), style: "cursor:pointer" });
    g.appendChild(svgEl("circle", {
      cx: p.x.toFixed(1), cy: p.y.toFixed(1), r: String(r),
      fill: deviceNodeColor(d),
    }));
    const countT = svgEl("text", {
      x: p.x.toFixed(1), y: (p.y + 1).toFixed(1), "text-anchor": "middle",
      "dominant-baseline": "middle", fill: "#fff", "font-size": "11", "font-weight": "700",
    });
    countT.textContent = String(d.logs_5m);
    g.appendChild(countT);
    const nameT = svgEl("text", {
      x: p.x.toFixed(1), y: (p.y + r + 14).toFixed(1), "text-anchor": "middle",
      fill: token("--text"), "font-size": "11", "font-weight": "500",
    });
    nameT.textContent = name;
    g.appendChild(nameT);
    g.addEventListener("click", () => openDevice(d));
    svg.appendChild(g);
  });

  clear(host);
  host.appendChild(svg);
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
    td.className = "empty";
    td.textContent = state.devices.length ? `0 ${state.lang === "lt" ? "rezultatų" : "results"}` : t("map_empty");
    tr.appendChild(td);
    tbody.appendChild(tr);
    return;
  }

  devs.forEach(d => {
    const tr = document.createElement("tr");
    tr.className = "is-click";
    tr.addEventListener("click", () => openDevice(d));

    // Pavadinimas + šaltinio žyma
    const tdName = document.createElement("td");
    const nm = document.createElement("div");
    nm.className = "font-medium text-strong";
    nm.textContent = d.name;
    const src = document.createElement("div");
    src.className = "text-[11px] text-dim";
    src.textContent = sourceLabel(d);
    tdName.appendChild(nm);
    tdName.appendChild(src);

    // OS
    const tdOs = document.createElement("td");
    const osMeta = OS_META[d.os] || OS_META.unknown;
    const osWrap = document.createElement("span");
    osWrap.className = "inline-flex items-center gap-1.5 text-muted";
    const osIcon = document.createElement("span");
    osIcon.className = "material-symbols-outlined text-[16px]";
    osIcon.textContent = osMeta.icon;
    const osText = document.createElement("span");
    osText.textContent = osMeta.label();
    osWrap.appendChild(osIcon);
    osWrap.appendChild(osText);
    tdOs.appendChild(osWrap);

    // IP / hostname
    const tdId = document.createElement("td");
    tdId.className = "mono";
    const ipLine = document.createElement("div");
    ipLine.textContent = d.ip || "—";
    const hostLine = document.createElement("div");
    hostLine.className = "text-[11px] text-dim";
    // Savo serverio realaus hostname nerodome (privatumas).
    hostLine.textContent = d.source === "self" ? "" : d.hostname;
    tdId.appendChild(ipLine);
    tdId.appendChild(hostLine);

    // Būsena
    const tdStatus = document.createElement("td");
    const stWrap = document.createElement("span");
    stWrap.className = "inline-flex items-center gap-1.5";
    const dot = document.createElement("span");
    dot.className = "app-dot" + (d.online ? " bg-ok" : "");
    const stTxt = document.createElement("span");
    stTxt.textContent = d.online ? t("dev_status_online") : t("dev_status_offline");
    stWrap.appendChild(dot);
    stWrap.appendChild(stTxt);
    tdStatus.appendChild(stWrap);

    // Logai (5 min)
    const tdLogs = document.createElement("td");
    tdLogs.className = "mono";
    tdLogs.textContent = numFmt(d.logs_5m || 0);

    // Paskutinis logas
    const tdSeen = document.createElement("td");
    tdSeen.className = "text-muted";
    tdSeen.textContent = d.last_seen ? relTime(d.last_seen) : t("dev_never");

    // Veiksmai
    const tdActions = document.createElement("td");
    tdActions.className = "text-right whitespace-nowrap";
    tdActions.addEventListener("click", e => e.stopPropagation());

    const infoBtn = document.createElement("button");
    infoBtn.className = "btn btn-icon btn-ghost";
    infoBtn.title = t("dev_info");
    const infoIcon = document.createElement("span");
    infoIcon.className = "material-symbols-outlined";
    infoIcon.textContent = "info";
    infoBtn.appendChild(infoIcon);
    infoBtn.addEventListener("click", () => openDevice(d));
    tdActions.appendChild(infoBtn);

    if (d.source === "registered") {
      const tutBtn = document.createElement("button");
      tutBtn.className = "btn btn-icon btn-ghost";
      tutBtn.title = t("dev_tutorial");
      const tutIcon = document.createElement("span");
      tutIcon.className = "material-symbols-outlined";
      tutIcon.textContent = "help";
      tutBtn.appendChild(tutIcon);
      tutBtn.addEventListener("click", () => showDeviceTutorial(d));
      tdActions.appendChild(tutBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "btn btn-icon btn-ghost text-crit";
      delBtn.title = t("dev_delete");
      const delIcon = document.createElement("span");
      delIcon.className = "material-symbols-outlined";
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

function openDevice(d) {
  navigate(`devices/${encodeURIComponent(deviceKey(d))}`);
}

// Atidarius puslapį (main.js enterPage): įrenginio detalės kraunamos iš naujo.
export function enterDevicesPage() {
  if (state.deviceKey) openDeviceDetail();
  renderDevicesPage();
}

function openAddDeviceModal() {
  if (!el("device-modal")) return;
  el("device-modal-form").classList.remove("hidden");
  el("device-modal-tutorial").classList.add("hidden");
  el("dev-name").value = "";
  el("dev-ip").value = "";
  el("dev-os").value = "macos";
  const err = el("dev-form-error");
  if (err) err.classList.add("hidden");
  openDialog("device-modal");
}

function closeDeviceModal() {
  closeDialog("device-modal");
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
    await ctx.loadDevices();
    navigate("devices");
    showDeviceTutorial(device);
  } catch (e) {
    showErr(e.message || t("dev_err_ip"));
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = t("dev_save"); }
  }
}

// Instrukcijos žingsniai ir kodas pagal OS: windows, linux, kitaip — macOS.
function renderTutorial(os, hostname = "") {
  const key = os === "windows" || os === "linux" ? os : "macos";
  const collector = window.location.hostname || "<serverio-ip>";
  const fill = s => String(s).replace(/\{collector\}/g, collector).replace(/\{hostname\}/g, hostname);

  const ol = el("device-tut-steps");
  ol.textContent = "";
  (t(`tut_${key}_steps`) || []).forEach(s => {
    const li = document.createElement("li");
    li.className = "leading-relaxed";
    li.textContent = fill(s);
    ol.appendChild(li);
  });

  setText("device-tut-code-label", t(key === "macos" ? "dev_tut_code_label" : "dev_tut_cmd_label"));
  setText("device-tut-code", fill(t(`tut_${key}_code`) || ""));
}

function openTutorialPanel(icon, title, intro, pickOs) {
  el("device-modal-form").classList.add("hidden");
  el("device-modal-tutorial").classList.remove("hidden");
  el("device-tut-os-wrap").classList.toggle("hidden", !pickOs);
  setText("device-tut-icon", icon);
  setText("device-tut-title-text", title);
  setText("device-tut-intro", intro);
  openDialog("device-modal");
}

function showDeviceTutorial(device) {
  if (!el("device-modal")) return;
  openTutorialPanel("check_circle", t("dev_tut_heading"), t("dev_tut_intro")(device.name), false);
  renderTutorial(device.os, device.hostname);
}

// Tikram kompiuteriui įrašo nekuriame: prisijungęs jis pats atsiras žemėlapyje kaip aptiktas.
function openConnectComputer() {
  if (!el("device-modal")) return;
  openTutorialPanel("computer", t("dev_connect_btn"), t("dev_connect_intro"), true);
  el("device-tut-os").value = "windows";
  renderTutorial("windows");
}

async function deleteDevice(id, name) {
  if (!confirm(t("dev_delete_confirm")(name))) return;
  try {
    await apiSend(`/api/devices/${id}`, "DELETE");
    await ctx.loadDevices();
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

function toggleAttackMenu(ev) {
  if (ev) ev.stopPropagation();
  const menu = el("attack-menu");
  if (menu) menu.classList.toggle("hidden");
}

export function closeAttackMenu() {
  const menu = el("attack-menu");
  if (menu) menu.classList.add("hidden");
}

// Bendras demonstracinės atakos paleidimas (atakų meniu ir ML testo mygtukas).
async function runDemoAttack(attack, btnId) {
  // Scenarijus taikomas tik registruotiems (sintetiniams) įrenginiams — realių host'ų nepaliečiame.
  if (!state.devices.some(d => d.source === "registered")) {
    showDemoStatus(t("dev_demo_none"));
    return;
  }
  const btn = el(btnId);
  if (btn) btn.disabled = true;
  showDemoStatus(t("dev_demo_running"));
  try {
    const res = await apiSend("/api/devices/demo/scenario", "POST", { attack });
    showDemoStatus(t("dev_demo_sent")(res.target));
    // Po kelių sekundžių atnaujiname srautą ir įspėjimus, kad demonstracija būtų matoma.
    setTimeout(() => { ctx.loadTrafficCurrent(); ctx.loadTrafficHistory(); ctx.loadAlerts(); ctx.loadDevices(); }, 4000);
  } catch (e) {
    showDemoStatus(e.message || t("dev_demo_error"));
  } finally {
    if (btn) btn.disabled = false;
  }
}

// Atakų meniu pasirinkimas (SSH brute-force / ugniasienės banga).
function runAttack(attack) {
  closeAttackMenu();
  runDemoAttack(attack, "attack-btn");
}

// „Testuoti ML detektorių" — pilnas daugiapakopis scenarijus.
function runAttackDemo() {
  runDemoAttack("full", "devices-demo-btn");
}

export function init(context) {
  ctx = context;
  el("attack-btn")?.addEventListener("click", toggleAttackMenu);
  document.querySelectorAll("[data-attack]").forEach(btn =>
    btn.addEventListener("click", () => runAttack(btn.dataset.attack)));
  el("devices-demo-btn")?.addEventListener("click", runAttackDemo);
  el("devices-connect-btn")?.addEventListener("click", openConnectComputer);
  el("devices-add-btn")?.addEventListener("click", openAddDeviceModal);
  el("dev-save-btn")?.addEventListener("click", submitAddDevice);
  el("device-tut-os")?.addEventListener("change", e => renderTutorial(e.target.value));
  el("device-modal")?.addEventListener("click", onDeviceModalBackdrop);
  document.querySelectorAll('[data-close="device-modal"]').forEach(btn =>
    btn.addEventListener("click", closeDeviceModal));
}

export const render = renderDevicesPage;
