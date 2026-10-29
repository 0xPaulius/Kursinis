// Įrenginių OS ir šaltinio užrašai bei maršruto raktas (sąrašas ir detalių puslapis).

import { t } from "../i18n.js";

export const OS_META = {
  macos:   { icon: "laptop_mac",     label: () => t("dev_os_macos") },
  windows: { icon: "laptop_windows", label: () => t("dev_os_windows") },
  linux:   { icon: "dns",            label: () => t("dev_os_linux") },
  router:  { icon: "router",         label: () => t("dev_os_router") },
  server:  { icon: "dns",            label: () => t("dev_os_server") },
  unknown: { icon: "devices_other",  label: () => t("dev_os_unknown") },
};

const SRC_LABEL = {
  self:       () => t("src_self"),
  registered: () => t("src_registered"),
  discovered: () => t("src_discovered"),
};

export function osLabel(d) {
  return (OS_META[d.os] || OS_META.unknown).label();
}

export function sourceLabel(d) {
  return (SRC_LABEL[d.source] || (() => d.source))();
}

// #devices/<raktas>: savo serveris — „self" (tikras hostname URL'e nerodomas), kiti — hostname.
export function deviceKey(d) {
  return d.source === "self" ? "self" : d.hostname;
}
