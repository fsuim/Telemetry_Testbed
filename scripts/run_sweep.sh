#!/usr/bin/env bash
set -euo pipefail

DUR="${DUR:-60}"                  # segundos por configuração
SENSOR_RATE="${SENSOR_RATE:-50}"  # taxa dos sensores RAW
RATES_STR="${RATES:-20 50 100 200}"
BATCHES_STR="${BATCHES:-1 50}"
OUT_ROOT="${OUT_ROOT:-experiments}"

read -r -a RATES_ARR <<< "$RATES_STR"
read -r -a BATCHES_ARR <<< "$BATCHES_STR"

mkdir -p "$OUT_ROOT/logs" "$OUT_ROOT/db" "$OUT_ROOT/results"

for B in "${BATCHES_ARR[@]}"; do
  for R in "${RATES_ARR[@]}"; do
    DB="$OUT_ROOT/db/run_b${B}_r${R}.db"
    LOG="$OUT_ROOT/logs/gw_b${B}_r${R}.log"

    echo "=== Running batch=$B rate=$R for ${DUR}s ==="

    ./telemetry_gateway --db "$DB" --batch "$B" --stats 2> "$LOG" &
    GW_PID=$!

    sleep 1
    timeout "${DUR}" ./robot_sim --rate "${SENSOR_RATE}" --state-rate "${R}" || true

    kill "$GW_PID" 2>/dev/null || true
    wait "$GW_PID" 2>/dev/null || true

    echo "Saved: $DB and $LOG"
    echo
  done
done

python3 scripts/analysis/analyze_gwstats.py \
  --log-glob "$OUT_ROOT/logs/gw*.log" \
  --db-glob "$OUT_ROOT/db/run_*.db" \
  --outdir "$OUT_ROOT/results"

echo "All done. See $OUT_ROOT/results/ for CSV and figures."
