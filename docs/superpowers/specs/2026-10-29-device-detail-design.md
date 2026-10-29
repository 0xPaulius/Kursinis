# Device detail page: system status and recent activity

- **Date:** 2026-10-29
- **Status:** design approved in brainstorming; spec awaiting review
- **Branch:** `feature/frontend`
- **Applies to:** this PC's status collector (`config/syslog-ng-host/`, `setup-host-syslog-ng.sh`), one collector filter (`config/syslog-ng/syslog-ng.conf`), the dashboard API and frontend (`dashboard/app/`)

## 1. Goal

On the Devices tab, clicking a device opens a page for that one device. It shows uptime, CPU, memory, disk, the programs running right now, its recent actions (logins, sudo, account changes, commands) and its alerts.

## 2. Decisions

| Topic | Decision |
|---|---|
| Data source | A status heartbeat: once a minute the device sends one JSON status record through the existing log pipeline. No new services, no metrics database |
| Who sends status | Only this PC (the Docker host, map node "Šis serveris") in this version. Every other device shows "no status data" but still gets activity, logs and alerts |
| Layout | A Grafana-style detail page at `#devices/<key>`, replacing the small device info dialog |
| Recent activity | Curated events parsed from the device's logs, plus a raw "All logs" tab |
| Programs | Grouped by process name (Task Manager style), names only, no command lines |
| History | CPU and memory sparklines for the last hour, built from the status records |
| Refresh | Driven by the existing SSE `devices` event, throttled; no new polling timers |

## 3. Non-goals

- Status from the demo devices, Linux endpoints, Windows endpoints or macOS. The record format and the parser are host-agnostic, so the Linux endpoints can later install the same script unchanged.
- Alert rules on status values (CPU or disk thresholds).
- History longer than one hour, or a per-PID process view.
- Any remote action on the device (kill a process, reboot).
- Changes to the anomaly detector or to the thesis text.

## 4. Architecture

### 4.1 Files

```
config/syslog-ng-host/
├── kursinis-status.sh          NEW: prints one status record (JSON) to stdout
├── kursinis-status.service     NEW: oneshot, sandboxed, SyslogIdentifier=kursinis-status
└── kursinis-status.timer       NEW: every 60 s
setup-host-syslog-ng.sh         + installs and starts the script, service and timer
config/syslog-ng/syslog-ng.conf f_security skips program("kursinis-status")

dashboard/app/
├── log_selectors.py            + HOST_RE / valid_host() (moved from routers/traffic.py)
├── routers/traffic.py          uses the shared HOST_RE
├── routers/devices.py          + GET /api/devices/{key}/details
├── dependencies.py             + get_device_details
├── models/schemas.py           + DeviceDetails, HostStatus, ProgramUsage, StatusPoint, ActivityItem
└── services/
    ├── host_status.py          NEW: status record model, line parsing, latest record + 1 h history
    ├── activity.py             NEW: rule table and classifier (pure functions)
    ├── device_details.py       NEW: runs the Loki queries, assembles DeviceDetails
    └── device_monitor.py       alert matching extracted into a reusable helper

dashboard/app/static/
├── index.html                  + detail view markup inside #page-devices; device-info-modal removed
└── js/
    ├── pages/device-detail.js  NEW: detail page (tiles, programs, info, activity/logs tabs, alerts)
    ├── pages/devices.js        map/table clicks navigate to the detail page; dialog code removed
    ├── shell.js                #devices/<key> sub-route, breadcrumb with the device name
    ├── main.js                 throttled detail refresh on `devices` events; info-* label lines removed
    ├── state.js                + deviceKey, deviceDetail, deviceSort, deviceTab, _lastDeviceDetail
    ├── format.js               + duration and size formatters
    └── i18n.js                 + LT/EN strings (dd_* keys)

dashboard/tests/
├── test_host_status.py         NEW
├── test_activity.py            NEW
└── test_api.py                 + details endpoint tests
```

### 4.2 Status record (version 1)

One JSON object per line. Only `v` is required; the script leaves out any field it could not read.

| Field | Type | Source and meaning |
|---|---|---|
| `v` | int, must be 1 | Record format version |
| `uptime_s` | int | Seconds since boot, `/proc/uptime` |
| `cpus` | int | Online CPUs |
| `cpu_pct` | float 0–100 | Share of all CPUs that was busy during a 1-second sample of `/proc/stat` (busy = total − idle − iowait) |
| `load` | 3 floats | 1, 5 and 15 minute load average, `/proc/loadavg` |
| `mem_total_kb`, `mem_avail_kb` | int | `MemTotal`, `MemAvailable` from `/proc/meminfo` |
| `disk_used_kb`, `disk_avail_kb` | int | Root filesystem `/` from `df -Pk /`; used % = used / (used + avail), the same as df's Use% |
| `procs` | int | User-space processes (kernel threads and the script's own processes excluded, as in `top`) |
| `users` | list of strings | Distinct logged-in user names (`loginctl list-users`, falling back to `who`) |
| `top` | list of objects | Programs, see below |

Each `top` entry is `{"name": str, "n": int, "cpu": float, "mem_kb": int}`:

- `name` is the process name (`comm` from `/proc/<pid>/stat`); processes with the same name are grouped into one entry and `n` counts them.
- `cpu` is the group's share of all CPUs during the same 1-second sample, so the entries add up to roughly `cpu_pct`.
- `mem_kb` is the group's summed resident memory (RSS).
- The list is the union of the 10 heaviest groups by `cpu` (ties broken by memory) and the 10 heaviest by `mem_kb`, so it has at most 20 entries.
- Kernel threads (PID 2 and its children) and the script's own processes (its session) are skipped.
- No command lines or arguments: they can carry passwords or tokens.

Example (one line in reality):

```json
{"v":1,"uptime_s":273845,"cpus":16,"cpu_pct":12.3,"load":[0.52,0.61,0.70],
 "mem_total_kb":32617216,"mem_avail_kb":19876543,"disk_used_kb":412345678,"disk_avail_kb":550000000,
 "procs":412,"users":["oxshan"],"top":[{"name":"firefox","n":12,"cpu":8.1,"mem_kb":2400000}]}
```

### 4.3 Status collector on this PC

- `kursinis-status.sh` is bash with awk and coreutils (no Python), reading `/proc`, `df` and `loginctl`. It always prints exactly one valid JSON line, even if a source fails.
- `kursinis-status.service`: `Type=oneshot`, `ExecStart=/usr/local/libexec/kursinis-status`, `SyslogIdentifier=kursinis-status`, `DynamicUser=yes`, `NoNewPrivileges=yes`, `ProtectSystem=strict`, `ProtectHome=yes`, `PrivateTmp=yes`, `PrivateNetwork=yes`. `/proc` stays fully visible (no `ProtectProc`), so all processes are counted.
- `kursinis-status.timer`: `OnBootSec=1min`, `OnUnitActiveSec=1min`, `AccuracySec=1s`, `WantedBy=timers.target`.
- `setup-host-syslog-ng.sh` gains a step that installs the script to `/usr/local/libexec/kursinis-status` (0755), the units to `/etc/systemd/system/`, runs `daemon-reload`, enables the timer and starts the service once so the first record arrives right away. Re-running the setup script stays safe.

### 4.4 Transport and the collector change

The record travels the existing path: stdout → journal → host syslog-ng → collector (514/TCP, or 6514/TLS) → syslog-ng file → Alloy → Loki. Alloy already labels `program`, so the records form their own stream, `{job="syslog", host="<this PC>", program="kursinis-status"}`, and reading them is a cheap label lookup. Volume is about 1 KB per minute, about 1.4 MB per day.

`f_security` in the collector's `syslog-ng.conf` becomes `not program("kursinis-status") and (…existing matches…)`. Otherwise a process name containing "denied", "blocked", "attack" and so on would copy a status line into `security-*.log`. Applying it needs `docker compose restart syslog-ng`.

Side effect: the heartbeat keeps this PC "online" on the device map even when its journal is quiet.

### 4.5 API

`GET /api/devices/{key}/details`, open to any signed-in user (the devices router already requires authentication).

Key resolution:

- `self` → this PC's hostname from `HostInfo` (404 if unknown). This keeps the real hostname out of URLs.
- Otherwise the key must match `^[A-Za-z0-9._-]{1,255}$` (the rule moved from `routers/traffic.py` to `log_selectors.py`) and is used as the hostname. Anything else → 404.
- The device IP for alert matching comes from the registry (registered devices); other devices have none.

Response (`DeviceDetails`):

| Field | Content |
|---|---|
| `status` | `HostStatus` or `null`: the newest valid record, with `time` = its Loki timestamp (the collector's receive time, so the PC's clock does not matter) and `programs: [ProgramUsage{name, processes, cpu_pct, mem_kb}]` |
| `history` | `[StatusPoint{time, cpu_pct, mem_pct}]`, ascending, records from the last hour; `mem_pct` = 100 × (total − avail) / total |
| `activity` | `[ActivityItem{time, kind, user, text}]`, newest first, at most 50, from the last 24 h |
| `alerts` | The device's newest 20 alerts as `AlertItem` |

Loki queries (all over the last 24 h, run concurrently):

1. Status: `{job="syslog", host="<h>", program="kursinis-status"}`, limit 120 (about two hours of records). Latest and history both come from this one query.
2. Activity, syslog family: `{job=~"syslog|linux_endpoint", host="<h>", program!="kursinis-status"} |~ "<prefilter>"`, limit 500 (prefilter in 4.7).
3. Activity, Windows: `{job="windows", host="<h>"} | json event_id | event_id=~"4624|4625|4720|4726|4732|4740|1102|4104|1"`, limit 500.

The "All logs" tab reuses `GET /api/traffic/logs?host=<hostname>&limit=100`.

### 4.6 Status parsing and validation

Status records are untrusted: anyone who can reach UDP 514 can send a line that claims to be any host. `host_status.py`:

- Takes the JSON from the stored line with `kursinis-status\[\d*\]: (\{.*\})$`; lines over 16 KB are skipped.
- Validates it with a strict Pydantic model. A record that fails is skipped (logged at debug), never repaired.

| Rule | Limit |
|---|---|
| `v` | exactly 1 |
| `cpu_pct`, `top[].cpu` | 0–100, finite |
| `uptime_s`, `procs`, `cpus` | ≥ 0 and bounded (`cpus` 1–4096) |
| `*_kb` | 0 to 2^50 |
| `mem_avail_kb` | ≤ `mem_total_kb` when both are present |
| `load` | at most 3 values, each 0 to 10^6 |
| `users` | at most 20 entries, each 1–64 characters |
| `top` | at most 20 entries; `name` 1–64 characters, `n` 1–10^6 |
| Unknown fields | ignored (forward compatible) |

### 4.7 Activity classification

`activity.py` turns a Loki entry into an `ActivityItem` or `None`. Kinds: `login`, `auth_failed`, `admin`, `account`, `command`, `script`, `boot`, `log_cleared`, `update`. `text` is cut to 200 characters.

Syslog-family lines are split into program and message with the collector's template (`<time> <host> <facility>.<level> <program>[<pid>]: <message>`). A line that doesn't fit (a raw auditd line from `linux_endpoint`) is classified on its whole text with an empty program. Program names are compared case-insensitively. Rules are tried in table order and the first match wins (so a sudo line with "incorrect password attempts" is `auth_failed`, not `admin`).

| Program | Message pattern | Kind | User / text |
|---|---|---|---|
| sshd | `Accepted <method> for <user> from <ip>` | login | user; "SSH login from <ip> (<method>)" |
| sshd | `Failed <method> for [invalid user ]<user> from <ip>` | auth_failed | user; "SSH login failed from <ip>" |
| systemd-logind | `New session <id> of user <user>` | login | user; "Session <id> started" |
| sudo | `<user> : <n> incorrect password attempt(s)` | auth_failed | user; "sudo: <n> incorrect password attempts" |
| sudo | `<user> : … COMMAND=<cmd>` | admin | user; "sudo <cmd>" |
| su, su-l | `session opened for user root… by <user>` | admin | user; "su to root" |
| any except sshd | `authentication failure; … user=<user>` | auth_failed | user; "<program>: authentication failure" |
| useradd | `new user: name=<user>` | account | user; "User <user> created" |
| useradd, groupadd | `new group: name=<group>` | account | "Group <group> created" |
| usermod, gpasswd | `add '<user>' to group '<group>'` | account | user; "<user> added to group <group>" |
| userdel | `delete user '<user>'` | account | user; "User <user> deleted" |
| passwd, chpasswd | `password changed for <user>` | account | user; "Password changed for <user>" |
| kernel | `Linux version <ver>` | boot | "System booted (Linux <ver>)" |
| any | `type=EXECVE … a0=… a1=…` | command | the decoded arguments (quoted or hex) joined by spaces |

Demo device lines (`syslog_emitter.py` templates):

| Program | Message pattern | Kind |
|---|---|---|
| loginwindow | `USER_PROCESS: user <user> session opened` | login |
| Security-Auditing | `successfully logged on (Event 4624) for <user>` | login |
| system | `user <user> logged in from <ip> via <method>` | login |
| Kernel-General | `The operating system started` | boot |
| WindowsUpdateClient | `Installation Successful: <update>` | update |

The demo SSH lines are covered by the sshd rules above.

Windows events (Alloy JSON; fields from `event_data` `<Data Name="…">`, and `user_data` for 1102):

| Event | Condition | Kind | User / text |
|---|---|---|---|
| 4624 | `LogonType` 2, 7, 10 or 11 (interactive, unlock, remote, cached) | login | `TargetUserName`; "Logon (<type>) from <IpAddress>" |
| 4625 | always | auth_failed | `TargetUserName`; "Logon failed from <IpAddress>" |
| 4720 / 4726 | always | account | "User <TargetUserName> created / deleted by <SubjectUserName>" |
| 4732 | always | account | "<MemberName or MemberSid> added to group <TargetUserName>" |
| 4740 | always | account | "Account <TargetUserName> locked out" |
| 1102 | always | log_cleared | `SubjectUserName`; "Security log cleared" |
| 4104 | `level` 3 or `levelText` "Warning" (Windows flagged the script as suspicious) | script | "Suspicious PowerShell: <first 120 characters>" |
| 1 | channel contains "Sysmon" | command | `User`; "<image file name>: <CommandLine>" |

Left out on purpose: cron `CMD` (floods the demo web server's feed), sshd `Invalid user` (the "Failed" line follows), pam failures from sshd (duplicate the sshd line), auditd `USER_AUTH` and `ADD_USER` (duplicate the pam and useradd lines), Windows logon types 3 and 5 (network and service noise).

Prefilter for the syslog query (RE2), one alternation of: `Accepted `, `Failed \S+ for `, `New session `, `COMMAND=`, `incorrect password attempt`, `session opened for user root`, `authentication failure`, `new user: `, `new group: `, `to group '`, `delete user '`, `password changed for `, `Linux version `, `type=EXECVE`, `USER_PROCESS: `, `successfully logged on`, `logged in from `, `The operating system started`, `Installation Successful`.

### 4.8 Alerts for a device

The matching in `device_monitor.alert_summary` (alert `source_ip` equals the device IP, or the hostname is one of the comma-separated `source_host` values) moves into a helper that returns the matching alerts. `alert_summary` and the details endpoint both use it. Details return the newest 20, in the `AlertItem` shape the alert dialog already understands.

### 4.9 Frontend

**Routing.** `shell.js` reads `#devices/<key>` as page `devices` plus `state.deviceKey` (URL-decoded); `#devices` clears it. The key is `self` for the self node, otherwise the hostname. A reload keeps the device open. The breadcrumb shows `Įrenginiai › <name>`. A map node click, a table row click and the row's info button all navigate there. `device-info-modal` and its code are removed; its fields move into the page.

**Layout.** `#page-devices` holds two containers: the existing list and a new `#device-detail`; `renderDevicesPage()` shows one of them according to `state.deviceKey`. Static labels use `data-i18n`.

1. **Header:** Back button, device name with status dot, OS and version, IP, "status updated 32 s ago" (amber when the record is older than 3 minutes).
2. **Stat tiles:** Uptime · CPU % (cores and 1-minute load below, 1 h sparkline) · Memory % (used / total GB, sparkline) · Disk `/` % (used / total GB). Sparklines use the existing `sparkline()` helper. Without status the tiles are replaced by a banner: this PC — "No status yet — run `sudo bash setup-host-syslog-ng.sh`"; other devices — "This device doesn't send system status (CPU, memory, programs)".
3. **Programs** (wide) and **Device info** (narrow):
   - Programs: Program · Processes · CPU % · Memory; clicking the CPU or Memory header sorts by it (default CPU). Footer: total process count and logged-in users.
   - Device info: the dialog's old list (status, type, IP, hostname — hidden for this PC, OS, version, last log, logs 5 min / 1 h, alerts) plus cores, load 1/5/15 and processes.
4. **Recent activity** (wide) and **Alerts** (narrow):
   - Activity has two tabs. "Actions": time, kind icon, text, user; `auth_failed` and `log_cleared` rows in the critical color. "All logs": the newest 100 raw lines.
   - Alerts: compact rows (time, severity, title); a click opens the existing dialog through `openAlertInfo()`.

**Refresh.** Each `devices` SSE event (about every 15 s) re-renders the header and the info panel from the map data. The same event triggers `maybeRefreshDeviceDetail()`, which re-fetches details at most once per 12 s (like `maybeRefreshHistory()`), and the raw logs when that tab is open. Returning to the browser tab also refreshes.

**Edge cases.** The page finds its device in `state.devices`: key `self` is the node with `source === "self"`, any other key the node with that hostname. Until the device map has loaded, the page shows skeletons. A key not in the map (a stale link, a deleted device) shows "Device not found" with a Back button. Typing in the global search on the detail page returns to the filtered list.

## 5. Error handling

- Loki down or slow: `AsyncLokiClient` returns `[]`, so each section shows its empty state; the top-frame health indicator already reports Loki down.
- Details request fails (network, 5xx): the page keeps the last data and shows the standard error banner with Retry (`loadFailed`).
- Invalid or forged status records: skipped; with none left the page shows the "no status" banner.
- Script failures on the PC: missing fields are omitted, the rest is still sent; the timer's state is visible in `systemctl status kursinis-status`, and the page shows the record as stale.

## 6. Security

- The key is validated before it reaches LogQL; `self` is resolved on the server.
- Status records are validated with size limits and rendered only through `textContent`; the frontend keeps the "no inline handlers or scripts" rule.
- No command lines in status records. Activity texts (commands that are already in the raw logs) are capped at 200 characters.
- The status service runs as a dynamic unprivileged user in a sandbox without network access.
- No new exposure: viewers can already read raw logs, and the username on the page was already visible in them.

## 7. Testing

Tests are written first (TDD).

- `test_host_status.py`: a valid record is accepted; malformed JSON, `v: 2`, out-of-range numbers, `mem_avail_kb > mem_total_kb`, more than 20 programs and over-long strings are rejected; the latest record and one hour of history are built correctly from a mix of valid, invalid and old lines.
- `test_activity.py`: at least one test per rule in 4.7, using real journal lines, the demo templates, and Windows events in the shape of the detector's golden fixture (logon types 2 and 10 kept, 5 dropped; 4104 counted only with warning level); noise lines return `None`; text is capped.
- `test_api.py`: `/api/devices/self/details` and `/api/devices/web-server-01/details` against a fake Loki; a bad key returns 404; no login returns 401; alerts are matched by hostname.
- Contract test: runs the real `kursinis-status.sh` (Linux only, skipped elsewhere) and feeds its output through the parser, so the script and the parser can't drift apart.
- The existing frontend static checks (no inline handlers or scripts, module imports resolve) cover the new module.
- Coverage for the new Python modules: 80% or more.
- End to end: after `sudo bash setup-host-syslog-ng.sh` is re-run on this PC, check the API with curl and the page with Playwright in both themes, both languages and at phone width.

## 8. Documentation

CLAUDE.md: the new files in Structure, one Key Architecture bullet (status heartbeat, details endpoint, detail route), the setup command note, and the new test counts. The thesis is not changed.

## 9. Risks and open points

- Windows activity can only be checked against fixture-shaped lines here; no Windows endpoint is connected. If Alloy's JSON lacks the numeric `level`, a localized `levelText` won't match and 4104 events are not shown.
- `loginctl` needs the system D-Bus. If it is unavailable in the sandbox the script falls back to `who`, and `users` may be empty on systems without utmp.
- On btrfs (the CachyOS default) `df` numbers are estimates.
- The demo devices' feeds are dominated by repeated synthetic logins; that is expected for generated traffic.
