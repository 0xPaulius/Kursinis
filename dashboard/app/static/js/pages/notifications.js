// Pranešimų (webhook) nustatymų puslapis.

import { el } from "../dom.js";
import { apiSend, fetchJSON } from "../api.js";
import { t } from "../i18n.js";

function setNotifyStatus(msg, kind) {
  const s = el("notify-status");
  if (!s) return;
  s.textContent = msg || "";
  s.className = "text-body-md font-label " +
    (kind === "error" ? "text-error" : kind === "ok" ? "text-secondary" : "text-on-surface-variant");
}

function notifyPayload() {
  const en = el("notify-enabled");
  const wh = el("notify-webhook");
  const ms = el("notify-min-severity");
  return {
    enabled: !!(en && en.checked),
    webhook_url: (wh && wh.value.trim()) || "",
    min_severity: (ms && ms.value) || "medium",
  };
}

async function loadNotificationSettings() {
  try {
    const s = await fetchJSON("/api/notifications/settings");
    const en = el("notify-enabled"); if (en) en.checked = !!s.enabled;
    const wh = el("notify-webhook"); if (wh) wh.value = s.webhook_url || "";
    const ms = el("notify-min-severity"); if (ms) ms.value = s.min_severity || "medium";
    setNotifyStatus("");
  } catch (e) {
    console.error("Notifications:", e);
  }
}

async function saveNotificationSettings() {
  const btn = el("notify-save-btn");
  if (btn) btn.disabled = true;
  setNotifyStatus(t("notify_saving"));
  try {
    await apiSend("/api/notifications/settings", "PUT", notifyPayload());
    setNotifyStatus(t("notify_saved"), "ok");
  } catch (e) {
    setNotifyStatus(e.message || t("notify_save_error"), "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function testNotification() {
  const btn = el("notify-test-btn");
  if (btn) btn.disabled = true;
  setNotifyStatus(t("notify_test_running"));
  try {
    const res = await apiSend("/api/notifications/test", "POST", notifyPayload());
    setNotifyStatus(res.detail || t("notify_test_sent"), "ok");
  } catch (e) {
    setNotifyStatus(e.message || t("notify_test_error"), "error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

export function init() {
  el("notify-save-btn")?.addEventListener("click", saveNotificationSettings);
  el("notify-test-btn")?.addEventListener("click", testNotification);
}

export const load = loadNotificationSettings;
