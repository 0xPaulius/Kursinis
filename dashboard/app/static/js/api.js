// Prisijungimo tokenas, užklausos į API ir gyvų atnaujinimų jungtis.

import { state } from "./state.js";

export async function fetchJSON(url) {
  const token = sessionStorage.getItem("auth_token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const r = await fetch(url, { headers });
  if (r.status === 401) {
    sessionStorage.removeItem("auth_token");
    sessionStorage.removeItem("auth_user");
    window.location.replace("/login");
    throw new Error("HTTP 401");
  }
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// POST/DELETE su Bearer tokenu. Klaidos atveju meta Error su serverio `detail`.
export async function apiSend(url, method = "POST", body = null) {
  const token = sessionStorage.getItem("auth_token");
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  if (body !== null) headers["Content-Type"] = "application/json";
  const r = await fetch(url, {
    method,
    headers,
    body: body !== null ? JSON.stringify(body) : undefined,
  });
  if (r.status === 401) {
    sessionStorage.removeItem("auth_token");
    sessionStorage.removeItem("auth_user");
    window.location.replace("/login");
    throw new Error("HTTP 401");
  }
  let data = null;
  try { data = await r.json(); } catch (_) { /* tuščias atsakymas */ }
  if (!r.ok) {
    const detail = (data && data.detail) ? data.detail : `HTTP ${r.status}`;
    throw new Error(detail);
  }
  return data;
}

export function logout() {
  if (state.stream) { state.stream.close(); state.stream = null; }
  sessionStorage.removeItem("auth_token");
  sessionStorage.removeItem("auth_user");
  window.location.replace("/login");
}

export function requireAuth() {
  if (!sessionStorage.getItem("auth_token")) {
    window.location.replace("/login");
    return false;
  }
  return true;
}

// Gyvų atnaujinimų jungtis: įvykio vardas -> apdorojimo funkcija (main.js).
export function openStream(handlers) {
  const token = sessionStorage.getItem("auth_token");
  if (!token) return null;
  if (state.stream) state.stream.close();
  const es = new EventSource(`/api/stream?token=${encodeURIComponent(token)}`);
  state.stream = es;
  for (const [name, fn] of Object.entries(handlers)) {
    es.addEventListener(name, e => { try { fn(JSON.parse(e.data)); } catch (_) { /* sugadintas įvykis */ } });
  }
  return es;
}
