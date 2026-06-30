#!/usr/bin/env bash
set -Eeuo pipefail

# Repeated telemetry experiment runner for Telemetry_Testbed.
# Run from the repository root:
#   bash scripts/experiments/run_repeated_experiment.sh
# or use the root wrapper:
#   ./run_repeated_experiment.sh
#
# This script does not modify source code. It builds the existing binaries,
# starts a private Mosquitto broker by default, runs repeated local gateway-side
# experiments, and calls scripts/analysis/analyze_repeated_experiments.py.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# ------------------------- configurable parameters -------------------------
OUT_ROOT="${OUT_ROOT:-experiment_repeated}"
REPS="${REPS:-5}"
DUR="${DUR:-60}"
RUN_LONG="${RUN_LONG:-1}"
LONG_DUR="${LONG_DUR:-600}"
RATES_STR="${RATES:-20 50 100 200}"
BATCHES_STR="${BATCHES:-1 50}"
LONG_RATES_STR="${LONG_RATES:-200}"
LONG_BATCHES_STR="${LONG_BATCHES:-1 50}"
SENSOR_RATE="${SENSOR_RATE:-50}"
STATS_MS="${STATS_MS:-1000}"
WARMUP_S="${WARMUP_S:-3}"
POST_WAIT="${POST_WAIT:-2}"
MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-18883}"
WS_PORT="${WS_PORT:-18080}"
USE_PRIVATE_BROKER="${USE_PRIVATE_BROKER:-1}"
BUILD_FIRST="${BUILD_FIRST:-1}"
CLEAN_OUTPUT="${CLEAN_OUTPUT:-0}"
ANALYZE_AFTER="${ANALYZE_AFTER:-1}"

read -r -a RATES_ARR <<< "$RATES_STR"
read -r -a BATCHES_ARR <<< "$BATCHES_STR"
read -r -a LONG_RATES_ARR <<< "$LONG_RATES_STR"
read -r -a LONG_BATCHES_ARR <<< "$LONG_BATCHES_STR"

LOG_DIR="$OUT_ROOT/logs"
DB_DIR="$OUT_ROOT/db"
RESULTS_DIR="$OUT_ROOT/results"
MANIFEST="$OUT_ROOT/run_manifest.csv"
BROKER_LOG="$LOG_DIR/mosquitto_${MQTT_PORT}.log"

GW_PID=""
SIM_PID=""
BROKER_PID=""

cleanup_run_processes(){
  if [[ -n "${SIM_PID:-}" ]] && kill -0 "$SIM_PID" 2>/dev/null; then
    kill "$SIM_PID" 2>/dev/null || true
    wait "$SIM_PID" 2>/dev/null || true
  fi
  if [[ -n "${GW_PID:-}" ]] && kill -0 "$GW_PID" 2>/dev/null; then
    kill "$GW_PID" 2>/dev/null || true
    wait "$GW_PID" 2>/dev/null || true
  fi
}

cleanup_all(){
  cleanup_run_processes
  if [[ -n "${BROKER_PID:-}" ]] && kill -0 "$BROKER_PID" 2>/dev/null; then
    kill "$BROKER_PID" 2>/dev/null || true
    wait "$BROKER_PID" 2>/dev/null || true
  fi
}
trap cleanup_all EXIT INT TERM

require_cmd(){
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found: $1" >&2
    exit 2
  fi
}

check_repo(){
  local missing=0
  for f in Makefile src/apps/robot_main.c src/apps/telemetry_gateway_main.c scripts/analysis/analyze_repeated_experiments.py; do
    if [[ ! -e "$f" ]]; then
      echo "[ERROR] Missing expected repository file: $f" >&2
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    echo "[ERROR] Run this script from the Telemetry_Testbed repository root or install it into the repository first." >&2
    exit 2
  fi
}

start_broker(){
  if [[ "$USE_PRIVATE_BROKER" == "1" ]]; then
    require_cmd mosquitto
    echo "[INFO] Starting private Mosquitto broker on ${MQTT_HOST}:${MQTT_PORT}"
    # Bind to localhost to avoid exposing the broker accidentally.
    mosquitto -h >/dev/null 2>&1 || true
    mosquitto -p "$MQTT_PORT" -v > "$BROKER_LOG" 2>&1 &
    BROKER_PID=$!
    sleep 1
    if ! kill -0 "$BROKER_PID" 2>/dev/null; then
      echo "[ERROR] Mosquitto broker failed to start. See: $BROKER_LOG" >&2
      exit 3
    fi
  else
    echo "[INFO] USE_PRIVATE_BROKER=0; assuming MQTT broker is already running at ${MQTT_HOST}:${MQTT_PORT}"
  fi
}

init_output(){
  if [[ "$CLEAN_OUTPUT" == "1" && -d "$OUT_ROOT" ]]; then
    echo "[INFO] Removing previous output directory: $OUT_ROOT"
    rm -rf "$OUT_ROOT"
  fi
  mkdir -p "$LOG_DIR" "$DB_DIR" "$RESULTS_DIR"
  if [[ ! -f "$MANIFEST" ]]; then
    echo "run_id,kind,rep,rate_hz,batch,duration_s,sensor_rate_hz,mqtt_host,mqtt_port,ws_port,db_path,gw_log,sim_log,start_epoch,end_epoch,exit_code" > "$MANIFEST"
  fi
}

csv_escape(){
  # Minimal CSV escape for paths/strings.
  local s="$1"
  s="${s//\"/\"\"}"
  printf '"%s"' "$s"
}

run_one(){
  local kind="$1"
  local rep="$2"
  local rate="$3"
  local batch="$4"
  local duration="$5"

  local run_id="${kind}_rep${rep}_r${rate}_b${batch}"
  local db="$DB_DIR/${run_id}.db"
  local gw_log="$LOG_DIR/gw_${run_id}.log"
  local sim_log="$LOG_DIR/sim_${run_id}.log"
  local start_epoch end_epoch exit_code

  rm -f "$db" "$db-wal" "$db-shm" "$gw_log" "$sim_log"

  echo
  echo "===================================================================="
  echo "[RUN] $run_id  duration=${duration}s  sensor_rate=${SENSOR_RATE}Hz"
  echo "===================================================================="

  start_epoch="$(date +%s)"

  ./telemetry_gateway \
    --mqtt-host "$MQTT_HOST" \
    --mqtt-port "$MQTT_PORT" \
    --db "$db" \
    --ws-port "$WS_PORT" \
    --batch "$batch" \
    --stats \
    --stats-ms "$STATS_MS" \
    > "$gw_log" 2>&1 &
  GW_PID=$!

  sleep 1
  if ! kill -0 "$GW_PID" 2>/dev/null; then
    echo "[ERROR] telemetry_gateway exited early. See: $gw_log" >&2
    exit_code=20
    end_epoch="$(date +%s)"
  else
    set +e
    timeout --preserve-status "${duration}s" ./robot_sim \
      --host "$MQTT_HOST" \
      --port "$MQTT_PORT" \
      --rate "$SENSOR_RATE" \
      --state-rate "$rate" \
      > "$sim_log" 2>&1
    local sim_rc=$?
    set -e

    # timeout returns 143/124 depending on signal behavior; both are acceptable here.
    sleep "$POST_WAIT"
    if kill -0 "$GW_PID" 2>/dev/null; then
      kill "$GW_PID" 2>/dev/null || true
      wait "$GW_PID" 2>/dev/null || true
    fi
    GW_PID=""
    end_epoch="$(date +%s)"

    if [[ "$sim_rc" -eq 0 || "$sim_rc" -eq 124 || "$sim_rc" -eq 143 ]]; then
      exit_code=0
    else
      echo "[WARN] robot_sim returned code $sim_rc. See: $sim_log" >&2
      exit_code="$sim_rc"
    fi
  fi

  {
    printf '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,' "$run_id" "$kind" "$rep" "$rate" "$batch" "$duration" "$SENSOR_RATE" "$MQTT_HOST" "$MQTT_PORT" "$WS_PORT"
    csv_escape "$db"; printf ','
    csv_escape "$gw_log"; printf ','
    csv_escape "$sim_log"; printf ',%s,%s,%s\n' "$start_epoch" "$end_epoch" "$exit_code"
  } >> "$MANIFEST"

  echo "[DONE] $run_id"
  echo "       DB:  $db"
  echo "       GW:  $gw_log"
  echo "       SIM: $sim_log"
}

main(){
  check_repo
  require_cmd timeout
  require_cmd python3

  init_output

  if [[ "$BUILD_FIRST" == "1" ]]; then
    echo "[INFO] Building project with make"
    make
  fi

  start_broker

  echo "[INFO] Short repeated experiment: REPS=$REPS DUR=$DUR RATES=[$RATES_STR] BATCHES=[$BATCHES_STR]"
  for rep in $(seq 1 "$REPS"); do
    for batch in "${BATCHES_ARR[@]}"; do
      for rate in "${RATES_ARR[@]}"; do
        run_one "short" "$rep" "$rate" "$batch" "$DUR"
      done
    done
  done

  if [[ "$RUN_LONG" == "1" ]]; then
    echo "[INFO] Extended experiment: LONG_DUR=$LONG_DUR LONG_RATES=[$LONG_RATES_STR] LONG_BATCHES=[$LONG_BATCHES_STR]"
    for batch in "${LONG_BATCHES_ARR[@]}"; do
      for rate in "${LONG_RATES_ARR[@]}"; do
        run_one "long" "1" "$rate" "$batch" "$LONG_DUR"
      done
    done
  fi

  if [[ "$ANALYZE_AFTER" == "1" ]]; then
    echo "[INFO] Running analyzer"
    python3 scripts/analysis/analyze_repeated_experiments.py \
      --manifest "$MANIFEST" \
      --outdir "$RESULTS_DIR" \
      --warmup-s "$WARMUP_S"
  fi

  echo
  echo "[OK] Experiment complete. Results: $RESULTS_DIR"
  echo "     Main report: $RESULTS_DIR/SUMMARY.md"
}

main "$@"
