# Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the dashboard frontend in the Grafana style described in the spec, dark by default with a light switch, without changing the API.

**Architecture:** First split `app.js` into native ES modules with no visible change and prove nothing broke. Then add the theme system and the new page frame, restyle the pages one at a time, and finish with cleanup, docs and verification. Every phase ends with a working dashboard.

**Tech Stack:** FastAPI/Starlette static files, plain JavaScript ES modules (no build step), vendored Tailwind Play runtime, vendored Chart.js 4.4.9, pytest, headless Chromium and the Playwright MCP browser for checks.

**Spec:** `docs/superpowers/specs/2026-10-27-frontend-redesign-design.md` (referred to as "spec §n").

---

## Ground rules

- `S` means `dashboard/app/static`. Line numbers refer to `S/js/app.js` as it is today; move functions **by name** and treat the numbers as a guide.
- Moved code is copied verbatim unless a step says otherwise. Keep function names.
- **Commits:** the repo owner's rule applies. Before every commit, ask "**DO YOU WANT TO COMMIT?**" and wait for an explicit yes. Commit points are marked **Checkpoint**.
- **Security hook:** the security-guidance plugin blocks any file whose content contains its trigger strings (code-evaluation calls, HTML-string assignment, the process-spawning call, the Function constructor). Don't write them, not even in comments or tests. Use `textContent`, `createElement`/`createElementNS`, and `String.prototype.match` instead of the RegExp method that runs a pattern.
- No `innerHTML`-style sinks, no inline handlers, no inline scripts (spec §6).

## Verification harness

Used by many tasks. Run from the repo root.

- **H1 tests:** `cd dashboard && .venv/bin/python -m pytest tests/ -q` — everything passes.
- **H2 syntax:** `rg --files -g '*.js' -g '!*.min.js' dashboard/app/static/js | xargs -n1 node --check` — no output, exit 0.
- **H3 preview dashboard:** a throwaway container on the stack's network, with the working tree's `dashboard/app` mounted read-only, temporary state, the real Loki and a known password. Static files are read from disk, so frontend edits show up on reload. Python edits need the container recreated: `--rm` removes it on stop, so run `docker stop kursinis-ui-preview` and then the same `docker run` again.

  ```bash
  docker run -d --rm --name kursinis-ui-preview --network kursinis_lognet -p 127.0.0.1:8098:8080 \
    -v "$PWD/dashboard/app:/app/app:ro" -v kursinis_anomaly-data:/data:ro --tmpfs /state \
    -e LOKI_URL=http://loki:3100 -e ALLOY_READY_URL=http://alloy:12345/-/ready \
    -e ANOMALY_DB_PATH=/data/anomaly_history.json -e DEVICES_DB_PATH=/state/devices.json \
    -e USERS_DB_PATH=/state/users.json -e SECRET_KEY_PATH=/state/secret.key \
    -e SUPPRESSED_DB_PATH=/state/deleted.json -e NOTIFY_CONFIG_PATH=/state/notify.json \
    -e DASHBOARD_ADMIN_USER=admin -e DASHBOARD_ADMIN_PASSWORD=ui-preview-only \
    -e SYNTHETIC_TRAFFIC=false kursinis-dashboard:latest
  ```

  Running a demo attack from the preview sends real syslog into the demo stack and creates real alerts. That's fine on the laptop; don't do it on a production collector. Stop it with `docker stop kursinis-ui-preview`.
- **H4 browser check:** log in at `http://localhost:8098/login` as `admin` / `ui-preview-only`, open `#dashboard`, `#anomalies`, `#devices`, `#attack` and `#messages`, read the console (no errors), and save screenshots to `/tmp/kursinis-ui/<phase>-<page>-<theme>.png`. The Playwright MCP servers need Google Chrome, which isn't installed here, so this runs through a DevTools harness on the system Chromium: `cd /tmp/kursinis-ui && uv run --no-project --with websockets python h4.py --prefix <phase> --themes dark,light --interactions`. It starts with a fresh profile and the cache off, and `--interactions` clicks through the range picker, language, search, dialogs, attack menu, notifications, live stream and reload on a `#page`.
- **H5 banned-function search:** search `S/js` (excluding `*.min.js`) and the two HTML files for the hook's trigger strings and the HTML-string properties from spec §6. Expect no matches. Run it in the shell; it can't be written into a file here.

---

## Phase 1 — Split `app.js` into modules (no visible change)

### Task 1: Baseline

**Files:** none.

- [ ] Run H1. Expected: `31 passed`.
- [ ] Run `node --version`. Expected: v22 or newer, which checks ES-module syntax.
- [ ] Start H3 with today's code and log in (H4). Save `/tmp/kursinis-ui/before-<page>.png` for all five pages; Phase 1 must look identical.

### Task 2: No-cache header for the frontend (TDD)

**Files:** Modify `dashboard/app/main.py`. Test: `dashboard/tests/test_api.py`.

- [ ] **Step 1: Write the failing test** at the end of `test_api.py`:

```python
def test_frontend_files_are_revalidated(client):
    for path in ("/", "/login", "/static/js/chart.min.js"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.headers.get("cache-control") == "no-cache", path
```

- [ ] **Step 2: Run it.** `cd dashboard && .venv/bin/python -m pytest tests/test_api.py::test_frontend_files_are_revalidated -q`. Expected: FAIL (no header).
- [ ] **Step 3: Implement.** In `main.py`, after the CORS middleware and before the routers:

```python
# Frontend'as — keli ES moduliai be versijų žymų: be šios antraštės naršyklė gali
# po atnaujinimo sujungti senus ir naujus modulius. no-cache = kas kartą tikrinti ETag.
@app.middleware("http")
async def revalidate_frontend(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/login") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response
```

- [ ] **Step 4: Run the test** (PASS), then H1 (all pass).

### Task 3: Static frontend test (fails until Task 8)

**Files:** Create `dashboard/tests/test_frontend_static.py`.

- [ ] **Step 1: Write the test:**

```python
"""Statinio frontend'o taisyklės: be inline handler'ių ir skriptų, importai rodo į esamus failus."""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
HTML_FILES = [STATIC / "index.html", STATIC / "login.html"]
VENDORED = {"tailwind.min.js", "chart.min.js"}

INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
SCRIPT_TAG = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
IMPORT_FROM = re.compile(r"""^\s*import\s[^'"]*['"](\.{1,2}/[^'"]+)['"]""", re.MULTILINE)


def _own_modules() -> list[Path]:
    return [p for p in (STATIC / "js").rglob("*.js") if p.name not in VENDORED]


def test_html_has_no_inline_handlers():
    for page in HTML_FILES:
        assert not INLINE_HANDLER.search(page.read_text(encoding="utf-8")), page.name


def test_html_has_no_inline_scripts():
    for page in HTML_FILES:
        for attrs, body in SCRIPT_TAG.findall(page.read_text(encoding="utf-8")):
            assert "src=" in attrs and not body.strip(), f"{page.name}: inline <script>"


def test_module_imports_resolve():
    for module in _own_modules():
        for target in IMPORT_FROM.findall(module.read_text(encoding="utf-8")):
            assert (module.parent / target).resolve().is_file(), f"{module.name} -> {target}"
```

- [ ] **Step 2: Run it.** Expected: the first two tests FAIL (today's inline `onclick` and inline scripts); the import test passes. They must pass at the end of Task 8.

### Task 4: Leaf modules

**Files:** Create `S/js/state.js`, `S/js/dom.js`, `S/js/i18n.js`, `S/js/format.js`, `S/js/api.js`.

- [ ] `state.js`: move `const state = {…}` (553–573); export it. No imports.
- [ ] `dom.js`: move `el`, `setText`, `setPlaceholder` (669–679); export them. No imports.
- [ ] `i18n.js`: move `const I18N = {…}` (8–539) and `t`, `alertTitle`, `alertExpl`, `alertRec`, `methodLabel`, `detailLabel`, `sevLabel` (596–633, without `formatDetailValue`); export all. `import { state } from "./state.js";`
- [ ] `format.js`: move `formatDetailValue`, `relTime`, `timeLabel`, `fullTime`, `numFmt` (623–667); export them. Import `state` and `t`.
- [ ] `api.js`: move `fetchJSON`, `apiSend` (681–718), `logout`, `requireAuth` (578–591); export them. Import `state`. Add the stream helper that replaces `openStream`'s hard-wired handlers:

```js
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
```

- [ ] Run H2.

### Task 5: Shell and alert dialog

**Files:** Create `S/js/shell.js`, `S/js/alert-dialog.js`.

- [ ] `shell.js`: move `renderHealth` (756–787) and the search helpers `alertMatchesQuery`, `activeAlerts`, `filteredAlerts`, `filteredDevices`, `ltResultsWord`, `updateSearchUI` (1415–1482); export them. Replace `navigate` with hash routing:

```js
const PAGES = ["dashboard", "anomalies", "devices", "attack", "messages"];
let onEnter = () => {};

// main.js perduoda, ką daryti atidarius puslapį; puslapis laikomas URL #fragmente.
export function initNavigation(enter) {
  onEnter = enter;
  document.querySelectorAll("[data-nav]").forEach(btn =>
    btn.addEventListener("click", () => navigate(btn.dataset.nav)));
  window.addEventListener("hashchange", () => showPage(pageFromHash()));
  showPage(pageFromHash());
}

export function navigate(page) {
  if (location.hash === "#" + page) showPage(page);
  else location.hash = page;
}

function pageFromHash() {
  const page = location.hash.slice(1);
  return PAGES.includes(page) ? page : "dashboard";
}

function showPage(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === "page-" + page));
  PAGES.forEach(p => { const b = el("nav-" + p); if (b) b.classList.toggle("active", p === page); });
  state.page = page;
  onEnter(page);
}
```

- [ ] `alert-dialog.js`: move `ANOMALY_CARD_CFG` (542–548), `_SEV_BADGE`, `setAlertRow`, `renderAlertDetails`, `openAlertInfo`, `closeAlertInfo` (1547–1665). Export `ANOMALY_CARD_CFG` and `openAlertInfo`. Add `initAlertDialog()`, which binds the close button and the backdrop click that `onAlertInfoBackdrop` handles today.
- [ ] Run H2.

### Task 6: Page modules

**Files:** Create `S/js/pages/overview.js`, `anomalies.js`, `devices.js`, `attack.js`, `notifications.js`.

Each page exports `init(ctx)` (bind DOM events once) and `render()`. `ctx` is passed by `main.js` and holds the loaders: `loadTrafficHistory`, `loadTrafficCurrent`, `loadAlerts`, `loadAllAlerts`, `loadRawLogs`, `loadDevices` (the devices page reloads alerts and traffic after a demo attack).

- [ ] `overview.js`: move `TIME_RANGES` … `renderTrafficChart` (820–993), `onTrafficDeviceChange`, `populateTrafficDeviceSelect`, `renderTrafficDeviceStats` (997–1036) and `renderKeyEvents` (1174–1240). `setRange` and `onTrafficDeviceChange` call `ctx.loadTrafficHistory()` instead of the global. Export `render` (calls `renderMetrics`, `renderKeyEvents`, `renderTrafficChart`, `populateTrafficDeviceSelect`, `renderTrafficDeviceStats`), `renderRangeMenu` and `closeRangeMenu`.
- [ ] `anomalies.js`: move `renderAnomaliesPage`, `renderPulseChart`, `renderAnomalyCards` (1244–1411), `renderChronology` (1483–1543), `toggleShowAllAlerts` (1072–1076, calling `ctx.loadAllAlerts`), and `_LOG_SEV_DOT`, `onLogsHostChange`, `populateLogsHostSelect`, `logMatchesQuery`, `renderRawLogs` (1670–1753, without `applyRawLogs`/`loadRawLogs`). Export `render` (= `renderAnomaliesPage`), `renderPulseChart` and `renderRawLogs`.
- [ ] `devices.js`: move `OS_META`, `SRC_LABEL`, `renderDevicesPage`, `deviceNodeColor`, `renderDeviceMap`, `renderDeviceTable` (1774–2042), the device dialog (2046–2077) and the add-device, tutorial, connect, delete and demo functions (2081–2236). Calls to `loadDevices()` become `ctx.loadDevices()`. Export `render` (= `renderDevicesPage`) and `closeAttackMenu`.
- [ ] `attack.js`: move `_attackCard`, `_attackCell`, `renderAttackCoverage` (1091–1172). Export `render` (= `renderAttackCoverage`).
- [ ] `notifications.js`: move 2364–2422. Export `load` (= `loadNotificationSettings`).
- [ ] Each page imports only what it uses from `state`, `dom`, `i18n`, `format`, `api`, `shell` and `alert-dialog`. A page never imports another page.
- [ ] Run H2.

### Task 7: Entry module

**Files:** Create `S/js/main.js`.

- [ ] Move the loaders `applyHealth`, `loadHealth` (743–754), `applyTrafficCurrent`, `loadTrafficCurrent`, `loadTrafficHistory` (792–815), `applyAlerts`, `loadAlerts`, `loadAllAlerts` (1041–1070), `loadAttackCoverage` (1081–1090), `applyDevices`, `loadDevices` (1757–1772), `applyRawLogs`, `loadRawLogs` (1676–1689), `applyI18n`, `toggleLang` (2240–2359), `maybeRefreshHistory` (2426–2435) and `init` (2457–2528).
- [ ] Rewrite the cross-page calls in the moved loaders to call page exports: for example, `loadTrafficHistory` calls `overview.render()` and, when `state.page === "anomalies"`, `anomalies.renderPulseChart()`.
- [ ] Replace `openStream()` with `openStream({ health: applyHealth, alerts: applyAlerts, devices: applyDevices, traffic: d => { applyTrafficCurrent(d); maybeRefreshHistory(); } })`.
- [ ] Replace `navigate` with `initNavigation(enterPage)`, where `enterPage` holds today's per-page work from `navigate`: on `anomalies` render and `loadRawLogs()`, on `devices` render, on `attack` `loadAttackCoverage()`, on `messages` `notifications.load()`.
- [ ] Call each page's `init(ctx)` and `initAlertDialog()` before the first loads. The document click handler that closes the range and attack menus stays in `init`, using the exported close functions.
- [ ] End the file with `init();`. Module scripts run after parsing, so `DOMContentLoaded` isn't needed.
- [ ] Run H2.

### Task 8: Wire `index.html` and `login.html`

**Files:** Modify `S/index.html`, `S/login.html`. Create `S/js/tailwind.config.js`, `S/js/login.js`. Delete `S/js/app.js`.

- [ ] Move the inline `tailwind.config = {…}` script from `index.html` to `S/js/tailwind.config.js` unchanged, and load it right after `tailwind.min.js`. `login.html`'s inline config is a subset of it with identical values, so `login.html` loads the same file.
- [ ] Replace `<script src="/static/js/app.js">` with `<script type="module" src="/static/js/main.js"></script>`.
- [ ] Remove every inline handler and bind it in the owning module's `init`:

| Inline handler today | Becomes |
|---|---|
| `navigate('…')` on the 5 menu buttons and "Žiūrėti visus" | `data-nav="…"` (shell) |
| `toggleLang()`, `logout()` | listeners in `main.js` |
| `toggleRangeMenu(event)`, `onTrafficDeviceChange()` | `overview.init` |
| `onLogsHostChange()`, `loadRawLogs()` | `anomalies.init` (refresh calls `ctx.loadRawLogs`) |
| attack menu, `runAttack(…)`, `runAttackDemo()`, `openConnectComputer()`, `openAddDeviceModal()`, `submitAddDevice()`, `closeDeviceModal()` ×3, `onDeviceModalBackdrop`, `renderTutorial(this.value)`, `closeDeviceInfo()`, `onDeviceInfoBackdrop` | `devices.init`; buttons without ids get `data-action="…"` |
| `saveNotificationSettings()`, `testNotification()` | `notifications.init` |
| `closeAlertInfo()`, `onAlertInfoBackdrop` | `initAlertDialog()` |

- [ ] `login.html`: move the inline login script to `S/js/login.js` (module) unchanged, apart from binding listeners instead of inline handlers.
- [ ] Delete `S/js/app.js`.
- [ ] Run H1 (the Task 3 tests now pass too), H2 and H5.
- [ ] Run H4 against the preview and compare with the Task 1 screenshots: same look, no console errors, menus, range picker, search, dialogs, language switch, live updates and reload on each `#page` all work.
- [ ] **Checkpoint:** "Split app.js into ES modules, add no-cache header and frontend tests".

---

## Phase 2 — Theme system and page frame

### Task 9: Theme files

**Files:** Create `S/css/theme.css`, `S/js/theme-boot.js`. Modify `S/js/tailwind.config.js`, `S/fonts/fonts.css`, `S/index.html`, `S/login.html`. Delete `S/css/style.css`.

- [ ] `theme-boot.js` (classic script, first in `<head>` of both HTML files):

```js
// Tema nustatoma prieš pirmą piešimą, kad nesimatytų baltas blyksnis.
document.documentElement.dataset.theme = localStorage.getItem("theme") === "light" ? "light" : "dark";
```

- [ ] `theme.css`: the variables exactly as in the spec §4.3 table on `:root` and `[data-theme="light"]`, then base styles (`body` uses `--bg`, `--text`, Inter, 13px/1.4; `.mono` uses the system monospace stack; `:focus-visible` gets a 2 px `--accent` outline), then the component classes from spec §4.4: `.panel`, `.panel-h`, `.panel-b`, `.stat`, `.stat-v`, `.stat-threat`, `.tbl`, `.logs`, `.dlg`, `.dlg-backdrop`, `.btn`, `.btn-primary`, `.btn-danger`, `.input`, `.switch`, `.banner` (`.is-info`, `.is-ok`, `.is-error`), `.skeleton`, `.empty`, `.nav-item` (with `.active` and the 3 px bar), `.sev-critical`/`.sev-high`/`.sev-medium`/`.sev-low` (color only), and `.page`/`.page.active`. Move the 7 lines of `style.css` and the inline `<style>` rules of both HTML files here.
- [ ] `tailwind.config.js`: add the variable colors (`bg`, `panel`, `line`, `line-weak`, `hover`, `fg`, `strong`, `muted`, `dim`, `accent`, `ok`, `warn`, `high`, `crit`) as `"var(--…)"`, and set `fontFamily.sans` to Inter and `fontFamily.mono` to the system stack. Keep the old Material color, spacing and font-size names as **temporary aliases** pointing at the nearest variable (for example `surface-container-lowest` to `var(--panel)`, `on-surface` to `var(--text)`, `outline-variant` to `var(--line)`, `secondary` to `var(--ok)`, `error` to `var(--crit)`), so the unconverted pages still render in the new theme. Task 18 removes the aliases.
- [ ] `fonts.css`: delete the Manrope `@font-face` rules and their `.woff2` files. Keep Inter and Material Symbols.
- [ ] Both HTML files load, in order: `theme-boot.js`, `theme.css`, `fonts.css`, `tailwind.min.js`, `tailwind.config.js`.
- [ ] H2, then H4 in dark only: pages still render (imperfectly) with no console errors.

### Task 10: Theme-aware charts

**Files:** Create `S/js/charts.js`. Modify `S/js/pages/overview.js`, `S/js/pages/anomalies.js`.

- [ ] `charts.js`:

```js
const live = new Set();

export function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function withAlpha(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// Bendros ašių/tinklelio spalvos pagal temą; kviečiama kuriant ir perjungus temą.
export function themeOptions() {
  return {
    color: token("--text-muted"),
    borderColor: token("--line-weak"),
    font: { family: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", size: 10.5 },
    tooltipBg: token("--panel"),
    tooltipText: token("--text"),
  };
}

export function track(chart, restyle) {
  live.add({ chart, restyle });
  return chart;
}

export function forget(chart) {
  for (const item of live) if (item.chart === chart) live.delete(item);
}

export function applyTheme() {
  for (const { chart, restyle } of live) { restyle(chart, themeOptions()); chart.update("none"); }
}

export function sparkline(svg, values, color) {
  const NS = "http://www.w3.org/2000/svg";
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  if (values.length < 2) return;
  const [, , w, h] = svg.getAttribute("viewBox").split(" ").map(Number);
  const max = Math.max(...values) || 1;
  const pts = values.map((v, i) => `${(i * w / (values.length - 1)).toFixed(1)},${(h - h * v / max).toFixed(1)}`);
  const area = document.createElementNS(NS, "polygon");
  area.setAttribute("points", `0,${h} ${pts.join(" ")} ${w},${h}`);
  area.setAttribute("fill", withAlpha(color, 0.18));
  const line = document.createElementNS(NS, "polyline");
  line.setAttribute("points", pts.join(" "));
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", color);
  line.setAttribute("stroke-width", "1.5");
  line.setAttribute("vector-effect", "non-scaling-stroke");
  svg.append(area, line);
}
```

- [ ] `renderTrafficChart` and `renderPulseChart`: take every color from `token()`/`themeOptions()` instead of hard-coded hex values. Register each chart with `track(chart, restyleFn)`, where `restyleFn` re-applies dataset colors, grid, tick and tooltip colors. Call `forget` before destroying a chart.
- [ ] H2, then H4 after setting `localStorage.theme = "light"` in the browser and reloading: both charts use the light colors. Switching without a reload is checked in Task 11.

### Task 11: Page frame

**Files:** Modify `S/index.html`, `S/css/theme.css`, `S/js/shell.js`, `S/js/main.js`, `S/js/i18n.js`.

- [ ] Replace the sidebar and top bar markup with the spec §4.4 frame: 40 px top bar (logo, breadcrumb with `id="crumb-page"`, search `#search-input` + `#search-clear`, `#health-badge`, `#lang-btn`, `#theme-btn`, user name `#user-name`, `#logout-btn`), a 200 px left menu with the five `data-nav` items (`#nav-<page>`, count `#nav-anomalies-count`), and a `<main>` holding the five `.page` sections. Page contents stay unchanged in this task.
- [ ] `theme.css` breakpoints: under 1024 px the menu becomes a 56 px icon rail (labels hidden, each item keeps a `title`); under 768 px the panel grids collapse to one column.
- [ ] `shell.js` additions:
  - `initTheme()`: binds `#theme-btn`, which toggles `document.documentElement.dataset.theme`, stores `localStorage.theme`, swaps the icon (`dark_mode`/`light_mode`) and calls `applyTheme()` from `charts.js`.
  - `initShortcuts()`: Ctrl/Cmd+K focuses `#search-input`; Esc in the search clears it (reuse the clear-button handler).
  - `renderHealth()`: dot and label colored per the spec §4.3 health colors; `title` lists each service as `label: message`.
  - `setLive(connected)`: shows `● Gyvai`/`● Live` in `--ok` or `Jungiamasi…`/`Reconnecting…` in `--warn` in `#live-status`.
  - `showBanner(kind, text, retry)` / `hideBanner()`: one dismissible banner under the top bar; `retry` adds a button.
  - The breadcrumb follows the page in `showPage`; the anomaly count follows `activeAlerts().length` (called from `main.js` after alerts change).
- [ ] `main.js`: wrap each initial load so a failure calls `showBanner("error", t("load_failed"), retryAll)`; listen to the EventSource `open`/`error` events and call `setLive`; show the user name stored at login (`sessionStorage.auth_user`).
- [ ] `i18n.js`: add `applyLabels(root = document)`, which sets `textContent` from `t(el.dataset.i18n)` for every `[data-i18n]` and the `placeholder` for every `[data-i18n-placeholder]`. Add new keys in both `lt` and `en`: `theme_dark`, `theme_light`, `live`, `reconnecting`, `load_failed`, `retry`, `no_data`, `legend_avg`, `legend_max`, `legend_last`, `sev_breakdown`, `last_20`, `matrix_legend_detected`, `matrix_legend_rule`, `matrix_legend_none`.
- [ ] New markup uses `data-i18n`. `applyI18n` in `main.js` calls `applyLabels()` first and keeps its `setText` lines only for elements not converted yet.
- [ ] H2, then H4 in dark and light: frame correct in both, the theme button recolors both charts without a reload, the theme is kept after a reload, Ctrl+K works, the icon rail appears in a 900 px wide window, no console errors.
- [ ] **Checkpoint:** "Theme system, page frame and theme-aware charts".

---

## Phase 3 — Pages

Each task replaces one page section's markup with panels from spec §4.4–4.5 (mockup D/E is the visual reference), adapts that page's render functions to the new markup (same data, same function names), uses `data-i18n` for static labels, and ends with H2 and H4 in both themes.

### Task 12: Overview (`#page-dashboard`)

**Files:** Modify `S/index.html`, `S/js/pages/overview.js`, `S/js/i18n.js`.

- [ ] Controls row: device select `#traffic-device-select`, range button `#range-btn` + `#range-menu`, refresh `#refresh-btn` (calls `ctx.loadTrafficHistory()` and `ctx.loadTrafficCurrent()`), live status `#live-status`.
- [ ] Row of four `.stat` panels: `#metric-logs-value`, `#metric-errors-value` (+ `#metric-errors-pct`), `#metric-rate-value`, `#hero-threats`. `renderMetrics` sets each value's color class by today's thresholds (spec §4.4) and draws `sparkline()` into `#metric-logs-spark` and `#metric-rate-spark` from the last 12 `state.history` counts. The Threats panel toggles `.stat-threat` (background `--threat-bg`) when the count is above 0. Drop `setMetricBadge`/`setBarWidth` and their badge elements.
- [ ] Time-series panel (8 columns): canvas `#traffic-chart`, legend table `#traffic-legend` (average, maximum, last of `state.history`, filled with `textContent`), the `#traffic-device-stats` strip under it, plus totals `#chart-total` and `#chart-peak`.
- [ ] **New** bar-gauge panel (4 columns) `#sev-breakdown`: `renderSeverityBreakdown()` counts `state.alerts` by severity and draws one row per severity (label, bar width relative to the largest count, count) with the `.sev-*` colors. Subtitle `data-i18n="last_20"`. Called from `render()`.
- [ ] Key-events table panel `#key-events-table`: `renderKeyEvents` builds `<tr>` rows for the 4 newest alerts with columns time, severity, event, source IP, host and ATT&CK; a row click calls `openAlertInfo(a)`.
- [ ] H2, H4.

### Task 13: Anomalies (`#page-anomalies`)

**Files:** Modify `S/index.html`, `S/js/pages/anomalies.js`.

- [ ] Pulse time-series panel (12 columns) with canvas `#pulse-chart` and the normal/deviation legend.
- [ ] `renderAnomalyCards` produces up to 3 `.stat` panels in `#anomaly-cards` (one per alert type, count as the value, colored by the type's risk).
- [ ] `renderChronology` produces table rows in `#chronology-table` (same columns as key events); `#view-all-chrono` keeps toggling the full history.
- [ ] `renderRawLogs` produces `.logs` lines with the 3 px severity bar; `#logs-host-select` and `#logs-refresh-btn` keep their behavior.
- [ ] H2, H4.

### Task 14: Devices (`#page-devices`)

**Files:** Modify `S/index.html`, `S/js/pages/devices.js`.

- [ ] Controls row: `#attack-btn` (`.btn-danger`) with `#attack-menu`, `#devices-demo-btn`, `#devices-connect-btn`, `#devices-add-btn` (`.btn-primary`).
- [ ] `#devices-demo-status` becomes a `.banner.is-info`.
- [ ] Device-map panel (9 columns) and two stacked `.stat` panels `#devices-total` and `#devices-online` (3 columns). `renderDeviceMap` takes node, line and label colors from `token()` instead of hex values, and `deviceNodeColor` returns token values.
- [ ] Devices table panel: `renderDeviceTable` keeps its columns and the delete action, restyled with `.tbl` and `.btn`.
- [ ] H2, H4 (add a device in the preview, open its info, delete it).

### Task 15: ATT&CK (`#page-attack`)

**Files:** Modify `S/index.html`, `S/js/pages/attack.js`.

- [ ] Three `.stat` panels from `_attackCard` (Techniques, With a rule, Detected).
- [ ] Matrix panel: `renderAttackCoverage` builds one column per tactic (sorted). `_attackCell` produces a compact cell (technique ID, name) colored `--ok` if detected, `--accent` if rule only, `--text-dim` if no rule. Add a legend from the new `matrix_legend_*` keys.
- [ ] The `#attack-unavailable` notice becomes a `.banner.is-info`.
- [ ] H2, H4.

### Task 16: Notifications and dialogs

**Files:** Modify `S/index.html`, `S/js/pages/notifications.js`, `S/js/pages/devices.js`, `S/js/alert-dialog.js`.

- [ ] Notifications: one settings panel; `#notify-enabled` becomes a `.switch`; inputs use `.input`; Save is `.btn-primary`, Send test is `.btn`; `#notify-status` keeps its messages.
- [ ] The three dialogs (`#device-modal`, `#device-info-modal`, `#alert-info-modal`) get `.dlg-backdrop` + `.dlg`. Esc closes the open dialog, and focus moves to its first focusable element on open. Fields and ids stay the same.
- [ ] H2, H4 (open every dialog in both themes).

### Task 17: Login page

**Files:** Modify `S/login.html`, `S/js/login.js`.

- [ ] Centered `.panel` with logo, username, password with the show/hide button, Sign in (`.btn-primary`) and the error banner; Lithuanian text as today. The page loads `theme-boot.js` and `theme.css`, so it follows the saved theme.
- [ ] H1, H2, H5; log in and out in both themes.
- [ ] **Checkpoint:** "Restyle all pages, dialogs and login in the Grafana style".

---

## Phase 4 — Cleanup, docs, final verification

### Task 18: Remove transition leftovers

**Files:** Modify `S/js/tailwind.config.js`, `S/js/main.js`, `S/index.html`.

- [ ] Delete the temporary Material aliases from `tailwind.config.js`. Search the HTML and JS for the old class names (`surface-container`, `on-surface`, `outline-variant`, `primary-container`, `secondary-container`, `tertiary-fixed`, `error-container`, `font-headline`, `text-label-md`, `stack_`) and replace any left.
- [ ] Remove the `setText` lines in `applyI18n` that target elements that no longer exist (for example the old `hero-*` labels).
- [ ] H1, H2, H5, then H4 in both themes.

### Task 19: Docs

**Files:** Modify `CLAUDE.md`, `README.md`.

- [ ] CLAUDE.md structure section: replace the `dashboard/app/static/` line with the module layout (spec §4.1). In the architecture section, note the theme variables, `theme-boot.js`, the hash routing and the no-cache header. Update the dashboard test count (31 plus the new tests).
- [ ] README dashboard paragraph: Grafana-style UI, dark/light switch.
- [ ] Remind the author that thesis line 1365 should say "HTML, JS modules, CSS (Tailwind + Chart.js)".

### Task 20: Final verification and review

**Files:** none.

- [ ] H1, H2, H5.
- [ ] Rebuild the real dashboard: `docker compose up -d --build dashboard`. Log in at `http://localhost:8080` and work through spec §7's manual checklist, including a demo attack and watching the alert arrive live.
- [ ] Save final screenshots of every page in both themes to `/tmp/kursinis-ui/final-*.png` and show them to the author.
- [ ] `docker stop kursinis-ui-preview`.
- [ ] **Checkpoint:** "Docs for the redesigned frontend".
