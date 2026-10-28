// Bendra kliento būsena — vienas objektas, kurį skaito visi moduliai.

export const state = {
  lang:         localStorage.getItem("lang") || "lt",
  page:         "dashboard",
  search:       "",
  health:       { overall: "unknown", services: [] },
  current:      null,
  history:      [],
  alerts:       [],
  allAlerts:    [],      // visa istorija — užkraunama paspaudus „Žiūrėti viską"
  showAllAlerts:false,   // ar chronologijoje rodome visą istoriją
  rawLogs:      [],      // žali log įrašai iš Loki („Visi logai" rodinys)
  logsHost:     "",      // pasirinktas įrenginys logų rodiniui
  devices:      [],
  collector:    null,
  trafficChart: null,
  pulseChart:   null,
  trafficHost:  "",
  rangeHours:   parseInt(localStorage.getItem("range_hours") || "24", 10) || 24,
  stream:       null,   // EventSource gyviems atnaujinimams
  _lastHistory: 0,      // grafiko atnaujinimo throttle žyma
};
