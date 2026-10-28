# Frontend redesign: Grafana-style dashboard

- **Date:** 2026-10-27
- **Status:** design approved in brainstorming; spec awaiting review
- **Branch:** `feature/frontend`
- **Applies to:** `dashboard/app/static/` (plus one serving tweak in `dashboard/app/main.py`, section 4.6)

## 1. Goal

Make the dashboard look and work like a simple, functional monitoring UI in the style of Grafana, for two audiences at once: the thesis defense demo and an office admin's daily use.

## 2. Decisions

| Topic | Decision |
|---|---|
| Look | Grafana-style panels, as in the approved mockups (dark "D", light "E") |
| Theme | Dark by default, light on a switch; the choice is saved per browser |
| Scope | All five pages (Apžvalga, Anomalijos, Įrenginiai, ATT&CK aprėptis, Pranešimai), the login page and the three dialogs |
| Features | Same as today, plus: theme switch, severity bar gauge on the overview, live-status indicator, error banner, Ctrl+K search, current page in the URL hash |
| Backend | No API changes; one serving tweak (no-cache header on static files, section 4.6) |
| Stack | Plain JavaScript, vendored Tailwind runtime and Chart.js 4.4.9, no build step; `app.js` split into native ES modules |

## 3. Non-goals

- No new API endpoints or data. The traffic chart therefore shows log volume only (the API has no error series).
- No framework, bundler or Node build step.
- No role-based hiding of admin controls: viewers still see admin buttons and the backend refuses with 403, as today.
- No Content-Security-Policy or other security headers. Removing inline handlers and scripts makes a CSP possible later.
- No mobile-specific layout beyond the two breakpoints in section 4.4.
- No embedding of Grafana.
- The login page stays Lithuanian-only, as today.

## 4. Architecture

### 4.1 Files

```
dashboard/app/static/
├── index.html              shell, five page sections, three dialogs; no inline handlers or scripts
├── login.html              restyled; no inline scripts
├── css/
│   ├── theme.css           NEW: theme variables (dark default, light) and component classes
│   └── style.css           REMOVED (its few rules move into theme.css)
├── fonts/fonts.css         Manrope @font-face rules and their files removed
└── js/
    ├── theme-boot.js       NEW classic script in <head>: sets data-theme before first paint
    ├── tailwind.config.js  NEW classic script: Tailwind config with colors mapped to CSS variables
    ├── tailwind.min.js     unchanged (vendored runtime)
    ├── chart.min.js        unchanged (vendored Chart.js 4.4.9, global `Chart`)
    ├── main.js             NEW entry module: auth check, data loading, live-stream dispatch, language switch, page wiring
    ├── api.js              NEW: token, fetchJSON, apiSend, openStream, logout
    ├── i18n.js             NEW: I18N dictionary (moved, keys unchanged), t(), label helpers, applyLabels()
    ├── state.js            NEW: shared state object (imports nothing)
    ├── dom.js              NEW: el(), setText(), setPlaceholder() (imports nothing)
    ├── format.js           NEW: numFmt, relTime, timeLabel, fullTime, formatDetailValue
    ├── charts.js           NEW: theme-aware Chart.js helpers, SVG sparkline(), applyTheme()
    ├── shell.js            NEW: navigation and hash routing, top bar, search filters, dialogs, banner
    ├── alert-dialog.js     NEW: alert details dialog, opened from the overview and anomalies pages
    ├── login.js            NEW entry module for login.html
    ├── pages/
    │   ├── overview.js     NEW
    │   ├── anomalies.js    NEW
    │   ├── devices.js      NEW
    │   ├── attack.js       NEW
    │   └── notifications.js NEW
    └── app.js              REMOVED
```

### 4.2 Module boundaries

- Each page module exports `init()`, which binds its DOM events once, and `render()`, which redraws the page from `state` and is safe to call repeatedly.
- Pages never import each other. They read `state`, call `api`, and use `charts`, `format`, `i18n`, `dom`, `shell` (dialogs, banner, search filters) and `alert-dialog`.
- Imports form a tree with no cycles: `state.js` and `dom.js` import nothing; `i18n.js` imports `state`; `format.js` imports `state` and `i18n`; `api.js` imports `state`; `shell.js`, `charts.js` and `alert-dialog.js` sit above those; pages sit above them; `main.js` imports everything.
- `main.js` owns the data flow: the `load*`/`apply*` functions, initial loads and live-stream events update `state`, then it calls `render()` for the visible page and the shell parts (health indicator, alert count). Pages that change data (adding or deleting a device) receive the reload functions they need through `init(ctx)`.
- The language switch lives in `main.js`, because it re-renders every page.
- Load order: `theme-boot.js`, Tailwind runtime and config, `chart.min.js` (classic scripts), then `main.js` as `<script type="module">`.
- Function names from `app.js` are kept where the function survives, so the port can be checked side by side.

### 4.3 Theming

CSS variables on `:root` (dark) and `[data-theme="light"]`:

| Variable | Dark | Light |
|---|---|---|
| `--bg` | `#111217` | `#F4F5F5` |
| `--panel` | `#181B1F` | `#FFFFFF` |
| `--line` | `rgba(204,204,220,.12)` | `rgba(36,41,46,.12)` |
| `--line-weak` | `rgba(204,204,220,.07)` | `rgba(36,41,46,.07)` |
| `--hover` | `rgba(204,204,220,.08)` | `rgba(36,41,46,.06)` |
| `--text` | `#CCCCDC` | `#24292E` |
| `--text-strong` | `#E4E5EA` | `#111418` |
| `--text-muted` | `rgba(204,204,220,.65)` | `rgba(36,41,46,.72)` |
| `--text-dim` | `rgba(204,204,220,.45)` | `rgba(36,41,46,.5)` |
| `--accent` | `#5794F2` | `#1F62E0` |
| `--ok` | `#73BF69` | `#2E8540` |
| `--warn` | `#FADE2A` | `#B7870F` |
| `--high` | `#FF9830` | `#D4610F` |
| `--crit` | `#F2495C` | `#D0244B` |
| `--threat-bg` | `#C4162A` | `#D0244B` |

- **Severity colors:** critical `--crit`, high `--high`, medium `--warn`, low `--accent`.
- **Health colors:** ok `--ok`, warning `--warn`, critical `--crit`, unknown `--text-dim`.
- **Tailwind:** `tailwind.config.js` maps color names to the variables (`bg`, `panel`, `line`, `line-weak`, `hover`, `fg`, `strong`, `muted`, `dim`, `accent`, `ok`, `warn`, `high`, `crit`), so one class such as `bg-panel` works in both themes. Opacity modifiers (`bg-panel/50`) are not used; they don't work with `var()` colors.
- **Switch:** a top-bar button toggles `data-theme` on `<html>`, saves `localStorage.theme` (default `dark`) and calls `charts.applyTheme()`.
- **No flash:** `theme-boot.js` runs in `<head>` before the stylesheet applies; `login.html` loads it too.
- **Charts** read the variables with `getComputedStyle` when they render and again in `applyTheme()`.
- **Fonts:** Inter (bundled) for all text; the system monospace stack (`ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace`) for numbers, IPs and logs; Material Symbols (bundled) for icons. Manrope is removed.

### 4.4 Layout and components

- **Top bar (40 px):** logo, breadcrumb (`Logų analizė › <page>`), search (Ctrl+K or Cmd+K focuses it, Esc clears), health indicator (overall status; the per-service list is in its tooltip), LT/EN, theme switch, user name and logout.
- **Left menu (200 px):** the five pages, active-alert count on Anomalijos, 3 px accent bar on the active item. Under 1024 px it shrinks to a 56 px icon rail.
- **Controls row (30 px)** under the top bar, contents per page.
- **Grid:** 12 columns, 8 px gap. Under 768 px panels stack in one column.
- **Panel:** 1 px `--line` border, 4 px radius, `--panel` background, 28 px header (13 px title, muted subtitle, optional actions), 8 px body padding.
- **Stat panel:** 30 px value, colored by threshold, optional SVG sparkline of the last 12 history points. Thresholds are today's badge rules: logs over 1,000 in 5 min is `--warn`, any errors is `--crit`, a rate over 500 is `--warn`, otherwise `--ok`. The Threats panel uses `--threat-bg` when the count is above 0 and stays neutral at 0.
- **Time series:** Chart.js line, 1.5 px stroke, 12–16 % fill, `--line-weak` grid, monospace ticks. A legend table under the chart shows average, maximum and last, computed in the browser.
- **Bar gauge:** one row per severity with label, bar (width relative to the largest count) and count.
- **Table:** 11.5 px muted header, 12.5 px rows, `--hover` on hover; clickable rows open the matching dialog.
- **Logs panel:** 12 px monospace lines with a 3 px left bar colored by syslog severity; scrolls inside the panel (max about 420 px, as today).
- **Dialog:** panel style, max 520 px wide, dimmed backdrop; Esc and a backdrop click close it; focus moves into it when it opens.
- **Controls:** primary button (accent), secondary (outlined), danger (`--crit`, used for "Run attack"), inputs and selects (28–32 px high, 4 px radius), switch (notifications), banner (info, success, error), skeleton loaders, and a "Nėra duomenų" empty state.

### 4.5 Pages

Content and data sources stay as today unless marked **new**.

- **Apžvalga.**
  - *Controls:* device filter (today's traffic device select), time range menu (1 h, 6 h, 12 h, 24 h, 2 d, 7 d), refresh, live status.
  - *Stats:* Logs (5 min) is the `/api/traffic/current` total. Errors (5 min) is today's `errorCount()`, shown with its share of the total. Logs / hour is today's `logRate()`. Threats is today's "Grėsmės" count: high and critical alerts among the 20 most recent (`/api/alerts/recent?limit=20`).
  - *Sparklines:* Logs and Logs / hour use the history points. Threats gets no sparkline: with only the 20 most recent alerts loaded, a trend line would silently drop older alerts.
  - *Time series:* log volume from `/api/traffic/history` for the selected range and device, with the legend table. The selected device's stats sit under it, as today.
  - **New** bar gauge "Įvykiai pagal lygį" (subtitle "paskutiniai 20"): the same 20 most recent alerts counted by severity. It is not a count over the selected range, which would need more alert data than the overview loads.
  - *Key events table:* the 4 newest alerts (as today), with columns time, severity, event, source IP, host and ATT&CK. A click opens the alert dialog.
- **Anomalijos.** Traffic pulse chart (normal vs deviation, as today). One stat per alert type for the top 3 types by count (today's cards). Timeline table: 20 newest, and "Žiūrėti viską" toggles the full history, as today. Raw logs panel with host filter, refresh and colored level bar.
- **Įrenginiai.**
  - *Controls:* Run attack ▾ (SSH brute force, firewall spike), Test ML detector (full scenario), Connect a computer (tutorial dialog with OS selector), Add device (form dialog, then tutorial).
  - *Demo status banner.*
  - *Device map panel:* SVG ring with node colors from the theme variables and a legend; Devices and Active stats beside it.
  - *Devices table:* as today, including delete with confirmation. A node or row click opens the device dialog.
- **ATT&CK aprėptis.** Stats for Techniques, With a rule and Detected. The "unavailable" notice stays as today. The matrix has one column per tactic (sorted), with technique cells colored detected (`--ok`), rule only (`--accent`) or no rule (`--text-dim`), plus a legend.
- **Pranešimai.** Settings panel with enable switch, webhook URL, minimum severity, Save, Send test and a status line. These endpoints stay admin-only, as today.
- **Login.** Centered panel with logo, username, password (show/hide), Sign in and an error line. It follows the saved theme; its logic moves to `login.js`.
- **Dialogs.** Add device with tutorial, device details and alert details keep their fields and get the panel styling.

### 4.6 Navigation and serving

- **New:** the current page is kept in the URL hash, using today's page ids (`#dashboard`, `#anomalies`, `#devices`, `#attack`, `#messages`). A reload keeps the page, back and forward work, and tests can open a page directly.
- **New, the only backend-side change:** `main.py` sends `Cache-Control: no-cache` for `/static/*` and the two HTML routes. Browsers then revalidate with the existing ETag on every load and never mix old and new modules after an update. The API is untouched.

## 5. Data flow, errors and languages

- **Data flow (unchanged):** auth check, initial loads (health, current traffic, history, alerts, devices, ATT&CK coverage; notification settings when that page opens), live stream (health, traffic, alerts and devices events), `apply*()` into `state`, then render the visible page. The history refresh throttle and the 401 handling (log out) stay as they are.
- **Errors:** a failed load shows a dismissible error banner with a retry button. Today such errors only reach the browser console.
- **Live status:** green when the stream is connected, `--warn` while the browser reconnects, based on the EventSource open and error events.
- **Languages:** the dictionary moves unchanged. Static labels get `data-i18n` attributes that `applyLabels()` in `i18n.js` fills in one loop, replacing today's long list of `setText()` calls; after a switch `main.js` re-renders the pages. New keys (theme, legend headers, severity panel, live status, empty and error states) exist in both LT and EN.

## 6. Security constraints

- Frontend scripts in `static/js` (the vendored `tailwind.min.js` and `chart.min.js` excluded) never turn strings into markup or code: no properties or methods that parse HTML strings, no runtime code evaluation, no string-argument timers. Text goes in through `textContent`; SVG is built with `createElementNS` and fixed attribute names. These are checked with a search during verification (section 7).
- No inline event handlers or inline scripts in `index.html` and `login.html`.
- Token handling stays as today: `sessionStorage`, the `Authorization` header, and `?token=` for the live stream.

## 7. Testing and verification

- The existing dashboard tests (31) pass unchanged.
- **New** `dashboard/tests/test_frontend_static.py` fails on inline `on*` attributes or inline `<script>` bodies in the HTML files, and on module imports that point at missing files.
- **New** test in `test_api.py`: `/`, `/login` and `/static/*` answer with `Cache-Control: no-cache` (section 4.6).
- The banned functions from section 6 are checked with a search during verification rather than in a test: the security-guidance plugin's hook blocks any file that names them.
- `node --check` passes for every module.
- **Browser smoke test:** a throwaway dashboard (temporary state, seeded alert history) loads every page in dark and light with no console errors. Screenshots go to the author for review.
- **Manual checklist:**
  - login and logout;
  - every page and dialog;
  - theme and language kept across reloads;
  - live updates during demo attacks;
  - search and Ctrl+K;
  - adding and deleting a device;
  - notification save and test;
  - range and device filters;
  - a viewer account getting the same refusals as today.
- **Docs:** CLAUDE.md (structure, theme, modules, no-cache) and the README dashboard paragraph are updated. Thesis line 1365 ("HTML, `app.js`, CSS …") is left for the author.

## 8. Risks

- **Tailwind runtime with CSS-variable colors:** opacity modifiers don't work, so component styles live in `theme.css` and utilities use whole tokens.
- **Porting 2,530 lines:** behavior could get lost. Mitigation: port page by page, keep function names, and work through the section 7 checklist.
- **Theme switch and charts:** Chart.js keeps colors per chart, so `applyTheme()` must update every live chart.
- **Caching after an upgrade:** handled by the no-cache header in section 4.6.
