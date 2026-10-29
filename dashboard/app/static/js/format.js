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

// Lentelėms: šiandienos įvykiams — tik laikas, senesniems — data ir laikas.
export function shortTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const locale = state.lang === "lt" ? "lt-LT" : "en-GB";
  return d.toDateString() === new Date().toDateString()
    ? d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleString(locale, { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const locale = () => (state.lang === "lt" ? "lt-LT" : "en-GB");

function oneDecimal(n) {
  return Number(n).toLocaleString(locale(), { maximumFractionDigits: 1 });
}

// Procentai su viena dešimtaine („12,5 %").
export function pctFmt(v) {
  return v == null || !isFinite(v) ? "—" : `${oneDecimal(v)} %`;
}

// Kilobaitai -> „1,5 GB" / „812 MB" / „64 KB".
export function sizeFmt(kb) {
  if (kb == null || !isFinite(kb)) return "—";
  if (kb >= 1048576) return `${oneDecimal(kb / 1048576)} GB`;
  if (kb >= 1024) return `${Math.round(kb / 1024)} MB`;
  return `${Math.round(kb)} KB`;
}

// Trukmė sekundėmis -> „3 d. 4 val." / „4 val. 12 min." / „12 min.".
export function durationFmt(sec) {
  if (sec == null || !isFinite(sec)) return "—";
  const u = t("dur_units");
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
  if (d) return `${d} ${u.d} ${h} ${u.h}`;
  if (h) return `${h} ${u.h} ${m} ${u.m}`;
  return `${m} ${u.m}`;
}

// Apkrovos vidurkis su dviem dešimtainėmis („0,52").
export function loadFmt(v) {
  return v == null || !isFinite(v) ? "—"
    : Number(v).toLocaleString(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Žurnalo eilutės kairės juostos spalva pagal lygį (anomalijų ir įrenginio „Visi logai").
export const LOG_SEV_COLOR = {
  emerg: "var(--crit)", alert: "var(--crit)", crit: "var(--crit)", err: "var(--crit)", error: "var(--crit)",
  warning: "var(--warn)", warn: "var(--warn)",
  notice: "var(--ok)", info: "var(--ok)", debug: "var(--text-dim)",
};
