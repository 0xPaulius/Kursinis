#!/usr/bin/env bash
# Kursinis: vienas šio kompiuterio būsenos įrašas (JSON eilutė) į stdout — veikimo laikas, CPU,
# atmintis, diskas, prisijungę vartotojai ir sunkiausios programos.
#
# Kas minutę paleidžia kursinis-status.timer; stdout patenka į journal (SyslogIdentifier=
# kursinis-status), iš ten per host syslog-ng — į kolektorių. Įrašą tikrina dashboard
# (app/services/host_status.py); formatas — docs/superpowers/specs/2026-10-29-device-detail-design.md.
# Komandų eilučių nesiunčiame (jose gali būti slaptažodžių) — tik procesų vardus.
# Nepavykęs šaltinis praleidžiamas: JSON visada teisingas, trūksta tik to lauko.
set -uo pipefail
export LC_ALL=C

SAMPLE_SECONDS="${SAMPLE_SECONDS:-1}"   # CPU matavimo langas
TOP_N="${TOP_N:-10}"                    # programų pagal CPU ir pagal atmintį (iš viso <= 2*TOP_N)

# JSON eilutė: kabutės ir \ ekranuojami, valdymo ir ne ASCII baitai -> „?".
JS='function js(s) { gsub(/\\/, "\\\\", s); gsub(/"/, "\\\"", s); gsub(/[\001-\037\177-\377]/, "?", s); return "\"" s "\"" }'

# /proc/stat „cpu" eilutė -> "total busy" tick'ai (guest jau įskaičiuotas į user).
cpu_ticks() {
  awk '/^cpu / { t = 0; for (i = 2; i <= 9; i++) t += $i; print t, t - $5 - $6; exit }' /proc/stat
}

# Procesai: pid, sesija, ppid, utime+stime, rss (puslapiais), vardas. Vardas (comm) gali
# turėti tarpų ir „)", todėl laukai skaitomi nuo paskutinio „)".
proc_snapshot() {
  cat /proc/[0-9]*/stat 2>/dev/null | awk '{
    l = index($0, " ("); r = 0
    for (i = length($0); i > l; i--) if (substr($0, i, 1) == ")") { r = i; break }
    if (!l || !r) next
    name = substr($0, l + 2, r - l - 2); gsub(/\t/, " ", name)
    split(substr($0, r + 2), f, " ")
    printf "%s\t%s\t%s\t%d\t%d\t%s\n", substr($0, 1, l - 1), f[4], f[2], f[12] + f[13], f[22], name
  }'
}

read -r t0 b0 < <(cpu_ticks)
snap0=$(proc_snapshot)
sleep "$SAMPLE_SECONDS"
read -r t1 b1 < <(cpu_ticks)
snap1=$(proc_snapshot)
dt=$(( ${t1:-0} - ${t0:-0} ))

self_sid=$(awk '{ for (i = length($0); i > 0; i--) if (substr($0, i, 1) == ")") break
                  split(substr($0, i + 2), f, " "); print f[4] }' /proc/self/stat)
page_kb=$(( $(getconf PAGESIZE 2>/dev/null || echo 4096) / 1024 ))

# Programos: procesai sugrupuoti pagal vardą -> "tick'ai  atmintis_kb  procesai  vardas".
# Praleidžiamos branduolio gijos (PID 2 ir jo vaikai) ir paties skripto procesai (jo sesija).
groups=$(awk -F'\t' -v sid="$self_sid" -v page_kb="$page_kb" '
  FNR == NR { before[$1] = $4; next }
  $1 == 2 || $3 == 2 || $2 == sid { next }
  { d = $4 - (($1 in before) ? before[$1] : 0); if (d < 0) d = 0
    cpu[$6] += d; mem[$6] += $5 * page_kb; cnt[$6]++ }
  END { for (n in cnt) printf "%d\t%d\t%d\t%s\n", cpu[n], mem[n], cnt[n], n }
' <(printf '%s\n' "$snap0") <(printf '%s\n' "$snap1"))

fields=('"v":1')
add() { [[ -n "$2" ]] && fields+=("\"$1\":$2"); }

add uptime_s "$(awk '{ printf "%d", $1 }' /proc/uptime 2>/dev/null)"
add cpus "$(nproc 2>/dev/null)"
if (( dt > 0 )); then
  add cpu_pct "$(awk -v b=$(( b1 - b0 )) -v t="$dt" 'BEGIN { v = 100 * b / t; if (v < 0) v = 0; if (v > 100) v = 100; printf "%.1f", v }')"
fi
add load "$(awk '{ printf "[%s,%s,%s]", $1, $2, $3 }' /proc/loadavg 2>/dev/null)"
add mem_total_kb "$(awk '/^MemTotal:/ { print $2 }' /proc/meminfo 2>/dev/null)"
add mem_avail_kb "$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo 2>/dev/null)"
read -r disk_used disk_avail < <(df -Pk / 2>/dev/null | awk 'NR == 2 { print $3, $4 }')
add disk_used_kb "${disk_used:-}"
add disk_avail_kb "${disk_avail:-}"
add procs "$(printf '%s\n' "$groups" | awk -F'\t' 'NF { s += $3 } END { print s + 0 }')"

users=$(loginctl list-users --no-legend 2>/dev/null | awk '{ print $2 }')
[[ -n "$users" ]] || users=$(who 2>/dev/null | awk '{ print $1 }')
add users "[$(printf '%s\n' "$users" | sort -u | head -n 20 | awk "$JS"' NF { printf "%s%s", (n++ ? "," : ""), js($0) }')]"

if (( dt > 0 )); then
  add top "[$( { printf '%s\n' "$groups" | sort -t $'\t' -k1,1nr -k2,2nr | head -n "$TOP_N"
                 printf '%s\n' "$groups" | sort -t $'\t' -k2,2nr | head -n "$TOP_N"; } |
              awk -F'\t' 'NF && !seen[$4]++' | sort -t $'\t' -k1,1nr -k2,2nr |
              awk -F'\t' -v t="$dt" "$JS"' { c = 100 * $1 / t; if (c > 100) c = 100
                printf "%s{\"name\":%s,\"n\":%d,\"cpu\":%.1f,\"mem_kb\":%d}", (NR > 1 ? "," : ""), js($4), $3, c, $2 }')]"
fi

(IFS=,; printf '{%s}\n' "${fields[*]}")
