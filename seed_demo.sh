#!/bin/bash
# Loads demo alert data into the anomaly-data Docker volume
# so the dashboard shows anomalies, devices, and search results.
#
# Timestamps are rewritten to "now" at seed time (via python3) so the seeded
# alerts always look recent during a live demo. Falls back to the static
# timestamps if python3 is unavailable.
#
# Usage: ./seed_demo.sh

set -e
cd "$(dirname "$0")"

VOLUME_NAME="kursinis_anomaly-data"
SRC="$(pwd)/demo_data/anomaly_history.json"

# Check if volume exists
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "Volume $VOLUME_NAME does not exist. Start the system first:"
    echo "  docker compose up -d"
    exit 1
fi

# Atnaujiname laiko žymas į „dabar" (kad demo metu alertai atrodytų švieži).
SEED_FILE="$SRC"
TMP_FILE="$(mktemp /tmp/anomaly_history.XXXXXX.json)"
if command -v python3 > /dev/null 2>&1; then
    python3 - "$SRC" "$TMP_FILE" <<'PY'
import datetime
import json
import sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as fh:
    data = json.load(fh)

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
n = len(data)
# Naujausias įrašas (paskutinis sąraše) ~2 min senumo, kiti tolygiai atgal.
for i, alert in enumerate(data):
    minutes = 2 + (n - 1 - i) * 45
    alert["timestamp"] = (now - datetime.timedelta(minutes=minutes)).isoformat()

with open(dst, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=False)
PY
    SEED_FILE="$TMP_FILE"
else
    echo "python3 nerastas — naudojamos statiškos laiko žymos."
fi

# Copy seed data into the volume using a temp container
docker run --rm \
    -v "$VOLUME_NAME":/data \
    -v "$SEED_FILE":/seed.json:ro \
    alpine cp /seed.json /data/anomaly_history.json

rm -f "$TMP_FILE"

echo "Demo data loaded (fresh timestamps). Dashboard will pick it up on next API call."
echo "Open http://localhost:8080 to verify."
