#!/usr/bin/env bash
set -euo pipefail

DUR=60              # segundos por configuração
SENSOR_RATE=50      # taxa dos sensores RAW (não é o snapshot)
RATES=(20 50 100 200)
BATCHES=(1 50)

mkdir -p logs db results

for B in "${BATCHES[@]}"; do
  for R in "${RATES[@]}"; do
    DB="db/run_b${B}_r${R}.db"
    LOG="logs/gw_b${B}_r${R}.log"

    echo "=== Running batch=$B rate=$R for ${DUR}s ==="

    # gateway em background, log em arquivo
    ./telemetry_gateway --db "$DB" --batch "$B" --stats 2> "$LOG" &
    GW_PID=$!

    # dá um tempo pro gateway subir
    sleep 1

    # simulador por DUR segundos
    timeout "${DUR}" ./robot_sim --rate "${SENSOR_RATE}" --state-rate "${R}" || true

    # encerra gateway
    kill "$GW_PID" 2>/dev/null || true
    wait "$GW_PID" 2>/dev/null || true

    echo "Saved: $DB and $LOG"
    echo
  done
done

# roda análise e gera CSV + figuras
python3 analyze_gwstats.py --log-glob "logs/gw*.log" --db-glob "db/run_*.db" --outdir results

echo "All done. See results/ for CSV and figures."