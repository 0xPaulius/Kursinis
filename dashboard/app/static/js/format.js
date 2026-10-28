// Laiko, skaičių ir detalių formatavimas pagal pasirinktą kalbą.

import { state } from "./state.js";
import { t } from "./i18n.js";

export function formatDetailValue(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (v && typeof v === "object") return JSON.stringify(v);
  if (typeof v === "number" && Number.isInteger(v)) return numFmt(v);
  return String(v);
}

export function relTime(iso) {
  if (!iso) return "";
  const sec = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (sec < 60)  return t("just_now");
  const min = Math.floor(sec / 60);
  if (min < 60)  return t("min_ago")(min);
  const hr = Math.floor(min / 60);
  if (hr < 24)   return t("hr_ago")(hr);
  return t("day_ago")(Math.floor(hr / 24));
}

export function timeLabel(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(
    state.lang === "lt" ? "lt-LT" : "en-GB",
    { hour: "2-digit", minute: "2-digit" }
  );
}

// Pilna data ir laikas + santykinis laikas (naudojama detalės lange).
export function fullTime(iso) {
  if (!iso) return "";
  const full = new Date(iso).toLocaleString(
    state.lang === "lt" ? "lt-LT" : "en-GB",
    { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }
  );
  const rel = relTime(iso);
  return rel ? `${full} · ${rel}` : full;
}

export function numFmt(n) {
  return Number(n).toLocaleString(state.lang === "lt" ? "lt-LT" : "en-GB");
}
