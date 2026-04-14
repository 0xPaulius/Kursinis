#!/bin/bash
# Loads demo alert data into the anomaly-data Docker volume
# so the dashboard shows anomalies, devices, and search results.
#
# Usage: ./seed_demo.sh

set -e
cd "$(dirname "$0")"

VOLUME_NAME="kursinis_anomaly-data"

# Check if volume exists
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo "Volume $VOLUME_NAME does not exist. Start the system first:"
    echo "  docker compose up -d"
    exit 1
fi

# Copy seed data into the volume using a temp container
docker run --rm \
    -v "$VOLUME_NAME":/data \
    -v "$(pwd)/demo_data":/seed:ro \
    alpine cp /seed/anomaly_history.json /data/anomaly_history.json

echo "Demo data loaded. Dashboard will pick it up on next API call."
echo "Open http://localhost:8080 to verify."
