#!/usr/bin/env bash
set -euo pipefail

TARGET_HOST="${TARGET_HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
DURATION="${DURATION:-60s}"

echo "Running load test against $TARGET_HOST"
echo "Users: $USERS | Spawn rate: $SPAWN_RATE | Duration: $DURATION"
echo ""

locust -f tests/performance/locustfile.py \
    --headless \
    --host "$TARGET_HOST" \
    --users "$USERS" \
    --spawn-rate "$SPAWN_RATE" \
    --run-time "$DURATION" \
    --html tests/performance/report.html \
    --csv tests/performance/results \
    --print-stats

echo ""
echo "Report saved to tests/performance/report.html"
