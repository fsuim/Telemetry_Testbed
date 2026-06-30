# Reproducibility Guide

This document describes how to reproduce the local gateway-side experiment and
how to record enough metadata for a paper artifact or archival release.

## Scope

The experiment validates the local telemetry platform path:

```text
robot_sim -> MQTT broker -> telemetry_gateway -> SQLite/WAL + WebSocket
```

It measures gateway-side throughput, persistence behavior, queue occupancy, and
empirical storage footprint. It does not claim synchronized end-to-end latency,
network loss, cloud performance, browser rendering latency, or packet-loss-free
transport.

## Recommended environment

The paper experiments were designed for a local Ubuntu/WSL-style environment.
Record your actual environment before running:

```bash
{
  date -Iseconds
  uname -a
  gcc --version | head -n 1
  mosquitto -h 2>&1 | head -n 1 || true
  sqlite3 --version
  protoc-c --version
  python3 --version
  git rev-parse HEAD 2>/dev/null || true
} | tee experiment_environment.txt
```

Install dependencies on Ubuntu/WSL:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  mosquitto mosquitto-clients libmosquitto-dev \
  protobuf-c-compiler libprotobuf-c-dev \
  sqlite3 libsqlite3-dev \
  python3 python3-pip
python3 -m pip install --user -r requirements.txt
```

## Build

```bash
make clean
make
```

Expected binaries:

```text
robot_sim
telemetry_gateway
state_dump
```

## Smoke test

```bash
REPS=1 DUR=15 RUN_LONG=0 ./run_repeated_experiment.sh
```

Confirm that the analysis report exists:

```bash
cat experiment_repeated/results/SUMMARY.md
```

## Full repeated experiment

```bash
CLEAN_OUTPUT=1 REPS=5 DUR=60 RUN_LONG=1 LONG_DUR=600 ./run_repeated_experiment.sh
```

Default matrix:

| Parameter | Values |
|---|---|
| Short-run repetitions | 5 |
| Short-run duration | 60 s |
| Snapshot rates | 20, 50, 100, 200 Hz |
| SQLite batch sizes | 1, 50 rows/transaction |
| Raw sensor rate | 50 Hz |
| Extended runs | 200 Hz, batch 1 and 50 |
| Extended-run duration | 600 s |
| GWSTAT interval | 1000 ms |
| Warm-up excluded by analyzer | 3 s |
| MQTT broker | private local Mosquitto on port 18883 |
| WebSocket port during experiment | 18080 |

Expected outputs:

```text
experiment_repeated/run_manifest.csv
experiment_repeated/logs/*.log
experiment_repeated/db/*.db
experiment_repeated/results/SUMMARY.md
experiment_repeated/results/run_summary.csv
experiment_repeated/results/aggregate_summary.csv
experiment_repeated/results/gwstat_samples.csv
experiment_repeated/results/*.png
```

## Re-run analysis only

```bash
python3 scripts/analysis/analyze_repeated_experiments.py \
  --manifest experiment_repeated/run_manifest.csv \
  --outdir experiment_repeated/results \
  --warmup-s 3
```

## Configurable experiment variables

The experiment runner reads environment variables:

| Variable | Default | Meaning |
|---|---:|---|
| `OUT_ROOT` | `experiment_repeated` | Output root directory |
| `REPS` | `5` | Number of short-run repetitions |
| `DUR` | `60` | Short-run duration in seconds |
| `RUN_LONG` | `1` | Whether to run extended tests |
| `LONG_DUR` | `600` | Extended-run duration in seconds |
| `RATES` | `20 50 100 200` | Snapshot rates for short runs |
| `BATCHES` | `1 50` | SQLite batch sizes for short runs |
| `LONG_RATES` | `200` | Snapshot rates for extended runs |
| `LONG_BATCHES` | `1 50` | Batch sizes for extended runs |
| `SENSOR_RATE` | `50` | Raw sensor publish rate |
| `STATS_MS` | `1000` | Gateway statistics interval |
| `WARMUP_S` | `3` | Warm-up removed from analysis |
| `MQTT_HOST` | `127.0.0.1` | MQTT host |
| `MQTT_PORT` | `18883` | MQTT port for private broker |
| `WS_PORT` | `18080` | Gateway WebSocket port |
| `USE_PRIVATE_BROKER` | `1` | Start/stop a private local Mosquitto broker |
| `BUILD_FIRST` | `1` | Run `make` before experiments |
| `CLEAN_OUTPUT` | `0` | Remove previous output root before running |
| `ANALYZE_AFTER` | `1` | Run analysis after experiments |

## Plot typography

Use these optional variables to tune figure readability:

| Variable | Default |
|---|---:|
| `PLOT_BASE_FONT` | 10 |
| `PLOT_TITLE_FONT` | 12 |
| `PLOT_LABEL_FONT` | 12 |
| `PLOT_TICK_FONT` | 10 |
| `PLOT_LEGEND_FONT` | 10 |
| `PLOT_FIG_W` | 5.2 |
| `PLOT_FIG_H` | 3.8 |
| `PLOT_DPI` | 300 |

Example:

```bash
PLOT_LABEL_FONT=11 PLOT_TITLE_FONT=11 \
python3 scripts/analysis/analyze_repeated_experiments.py \
  --manifest experiment_repeated/run_manifest.csv \
  --outdir experiment_repeated/results \
  --warmup-s 3
```

## Measurement caveat about `seq`

The current `TelemetryState.seq` value is a simulator cache-update counter, not a
dedicated snapshot-publication sequence number. The analyzer can report duplicate,
decreasing, and span-related sequence indicators, but these are not packet-loss
proof. A strict loss/reordering/replay-completeness analysis requires a dedicated
monotonically increasing snapshot counter emitted once per snapshot.

## Reference outputs

Reference analysis outputs may be kept under `experiment_repeated/results/` to
support paper figure regeneration and sanity checking. The authoritative result
for a new machine should be generated by rerunning the experiment and recording
that machine's environment metadata.
