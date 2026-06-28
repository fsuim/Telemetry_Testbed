#!/usr/bin/env bash
set -euo pipefail

DB="${DB:-/tmp/telemetry_testbed_smoke.db}"
LOG="${LOG:-/tmp/telemetry_testbed_smoke_gateway.log}"
DUR="${DUR:-5}"

rm -f "$DB" "$DB-wal" "$DB-shm" "$LOG"

if ! command -v mosquitto >/dev/null 2>&1; then
  echo "[SMOKE] mosquitto not found; install Mosquitto or start an external broker." >&2
  exit 2
fi

if ! pgrep -x mosquitto >/dev/null 2>&1; then
  mosquitto -p 1883 >/tmp/telemetry_testbed_smoke_mosquitto.log 2>&1 &
  MOSQ_PID=$!
  sleep 1
else
  MOSQ_PID=""
fi

cleanup() {
  if [ -n "${GW_PID:-}" ]; then kill "$GW_PID" 2>/dev/null || true; fi
  if [ -n "${MOSQ_PID:-}" ]; then kill "$MOSQ_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

./telemetry_gateway --db "$DB" --ws-port 18080 --batch 10 --stats 2> "$LOG" &
GW_PID=$!
sleep 1

timeout "$DUR" ./robot_sim --rate 20 --state-rate 10 >/tmp/telemetry_testbed_smoke_robot.log 2>&1 || true
kill "$GW_PID" 2>/dev/null || true
wait "$GW_PID" 2>/dev/null || true
GW_PID=""

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "[SMOKE] sqlite3 not found; DB was created at $DB, but row count was not checked." >&2
  exit 0
fi

ROWS=$(sqlite3 "$DB" 'select count(*) from telemetry_state;' 2>/dev/null || echo 0)
if [ "${ROWS:-0}" -le 0 ]; then
  echo "[SMOKE] expected telemetry rows, got $ROWS" >&2
  echo "[SMOKE] gateway log: $LOG" >&2
  exit 1
fi

echo "[SMOKE] ok: $ROWS telemetry rows written to $DB"
