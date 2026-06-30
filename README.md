# Telemetry Testbed

A lightweight telemetry platform for measurement and replay in mobile robotics.
The repository contains a local MQTT-based robot simulator, a gateway that stores
consolidated Protobuf telemetry snapshots in SQLite/WAL, a WebSocket replay API,
a static browser UI, and scripts for reproducing the gateway-side experiments used
in the accompanying ISMCR paper.

Repository link: <https://github.com/fsuim/Telemetry_Testbed>

## What this repository provides

The platform is designed to make the telemetry path observable rather than treating
it as opaque infrastructure. It supports:

- raw per-sensor MQTT topics with compact binary payloads;
- a consolidated `robot.v1.TelemetryState` Protobuf snapshot;
- gateway-side reception timestamping;
- FIFO decoupling between MQTT ingestion and SQLite writes;
- SQLite persistence using write-ahead logging (WAL);
- WebSocket JSON streaming for live monitoring;
- database-backed `last N` replay through the same WebSocket channel;
- repeated local experiments for throughput, persistence timing, queue behavior,
  and empirical storage footprint.

The reported experiments are local gateway-side validations. They are not a general
benchmark of MQTT, SQLite, ROS, DDS, cloud deployment, browser rendering latency,
or networked edge-to-cloud performance.

## Architecture at a glance

```text
robot_sim -> MQTT broker -> telemetry_gateway -> SQLite/WAL + WebSocket -> Web UI
```

Main processes:

1. `robot_sim` publishes telemetry to MQTT:
   - raw binary sensor topics under `/robot/sensors/...`;
   - one consolidated Protobuf snapshot on `/robot/v1/telemetry/state`.
2. `telemetry_gateway` subscribes to the snapshot topic, timestamps received
   samples, writes decoded fields plus the raw Protobuf payload to SQLite/WAL,
   and exposes live/replay JSON over WebSocket.
3. `ui/` is a static browser UI for live inspection and `last N` replay.
4. `state_dump` is a small CLI decoder for inspecting the Protobuf snapshot topic.

See also:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/mqtt_topics.md`](docs/mqtt_topics.md)
- [`docs/protobuf.md`](docs/protobuf.md)
- [`docs/database.md`](docs/database.md)
- [`docs/websocket_api.md`](docs/websocket_api.md)

## Repository structure

```text
src/apps/                         binary entry points
src/app/                          gateway orchestration
src/sim/                          simulator, sensors, cache, and state publisher
src/infra/                        MQTT, SQLite, and WebSocket infrastructure
include/                          public headers organized by layer
proto/                            Protobuf contract
generated/protobuf-c/             generated C bindings for Protobuf-C
ui/                               static web interface
scripts/analysis/                 analysis scripts for experiment outputs
scripts/experiments/              repeated-experiment runner
scripts/dev/                      smoke-test helper scripts
docs/                             technical and reproducibility documentation
experiment_repeated/results/      reference outputs from the repeated experiment
```

Compiled binaries (`robot_sim`, `telemetry_gateway`, `state_dump`), SQLite files,
logs, and temporary experiment outputs should be regenerated locally and are ignored
by Git.

## System requirements

Tested target environment:

- Windows 11 + WSL2 + Ubuntu 24.04.3 LTS;
- local Mosquitto broker;
- local simulator, gateway, SQLite database, and UI on the same machine.

The code should also build on a standard Linux distribution with the dependencies
listed below, but performance values are environment-dependent.

### Ubuntu / WSL dependencies

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  mosquitto mosquitto-clients libmosquitto-dev \
  protobuf-c-compiler libprotobuf-c-dev \
  sqlite3 libsqlite3-dev \
  python3 python3-pip
```

Python plotting is optional but recommended for reproducing figures:

```bash
python3 -m pip install --user -r requirements.txt
```

If you prefer not to install Python packages, the analyzers still generate CSV and
Markdown summaries; PNG figures are skipped when `matplotlib` is unavailable.

## Build

From the repository root:

```bash
make clean
make
```

Expected binaries:

```text
./robot_sim
./telemetry_gateway
./state_dump
```

To regenerate Protobuf-C bindings from the `.proto` file:

```bash
make proto
```

To run the lightweight smoke test:

```bash
make smoke-test
```

## Manual local run

Open four terminals in the repository root.

### 1. Start an MQTT broker

```bash
mosquitto -v
```

Alternatively, if your system uses a service manager:

```bash
sudo service mosquitto start
```

### 2. Start the gateway

```bash
./telemetry_gateway \
  --mqtt-host 127.0.0.1 \
  --mqtt-port 1883 \
  --db telemetry.db \
  --ws-port 8080 \
  --batch 50 \
  --stats \
  --stats-ms 1000
```

Expected behavior:

- `telemetry.db` is created;
- `telemetry.db-wal` and `telemetry.db-shm` may exist while the gateway is running;
- the gateway prints `GWSTAT` lines when `--stats` is enabled;
- the WebSocket endpoint listens on `ws://localhost:8080`.

### 3. Start the simulator

```bash
./robot_sim \
  --host 127.0.0.1 \
  --port 1883 \
  --rate 50 \
  --state-rate 20
```

Defaults are `host=127.0.0.1`, `port=1883`, raw sensor `rate=50 Hz`, and snapshot
`state-rate=20 Hz`.

### 4. Serve the UI

```bash
cd ui
python3 -m http.server 8000
```

Open <http://127.0.0.1:8000> and connect the UI to `ws://localhost:8080`.

## Quick sanity checks

Check one raw binary topic:

```bash
mosquitto_sub -t "/robot/sensors/imu0/acc" -C 1 | wc -c
```

Check the consolidated Protobuf snapshot topic:

```bash
mosquitto_sub -t "/robot/v1/telemetry/state" -C 1 | wc -c
```

Decode snapshots with the CLI consumer:

```bash
./state_dump 127.0.0.1 1883
```

Check the WebSocket port:

```bash
ss -ltnp | grep 8080 || true
```

## Reproducing the repeated gateway-side experiment

The main reproducibility path is the repeated experiment runner:

```bash
./run_repeated_experiment.sh
```

By default it performs the paper-style local validation:

- 5 repeated short runs per configuration;
- short-run duration: 60 s;
- snapshot rates: 20, 50, 100, and 200 Hz;
- SQLite batch sizes: 1 and 50 rows/transaction;
- raw sensor rate: 50 Hz;
- private Mosquitto broker on port 18883;
- gateway WebSocket port 18080;
- 3 s GWSTAT warm-up excluded by the analyzer;
- two extended 10 min runs at 200 Hz, batch sizes 1 and 50.

For a fast smoke test before running the full experiment:

```bash
REPS=1 DUR=15 RUN_LONG=0 ./run_repeated_experiment.sh
```

For the full paper-style run:

```bash
REPS=5 DUR=60 RUN_LONG=1 LONG_DUR=600 ./run_repeated_experiment.sh
```

Default outputs:

```text
experiment_repeated/run_manifest.csv
experiment_repeated/logs/
experiment_repeated/db/
experiment_repeated/results/SUMMARY.md
experiment_repeated/results/run_summary.csv
experiment_repeated/results/aggregate_summary.csv
experiment_repeated/results/gwstat_samples.csv
experiment_repeated/results/throughput_batch_1.png
experiment_repeated/results/throughput_batch_50.png
experiment_repeated/results/commit_batch_1.png
experiment_repeated/results/commit_batch_50.png
```

The repository includes reference `experiment_repeated/results/` files from a
completed run. To regenerate them from scratch, use a clean output directory:

```bash
CLEAN_OUTPUT=1 REPS=5 DUR=60 RUN_LONG=1 LONG_DUR=600 ./run_repeated_experiment.sh
```

The experiment runner and analyzer are documented in:

- [`docs/repeated_experiment.md`](docs/repeated_experiment.md)
- [`docs/reproducibility.md`](docs/reproducibility.md)

## Re-running analysis only

If logs, databases, and `run_manifest.csv` already exist:

```bash
python3 scripts/analysis/analyze_repeated_experiments.py \
  --manifest experiment_repeated/run_manifest.csv \
  --outdir experiment_repeated/results \
  --warmup-s 3
```

The analysis uses only standard Python libraries for CSV/Markdown summaries.
`matplotlib` is used only for PNG figures.

## Figure font adjustment

The plotting scripts read optional environment variables for figure typography:

```bash
PLOT_BASE_FONT=10 \
PLOT_LABEL_FONT=12 \
PLOT_TITLE_FONT=12 \
PLOT_TICK_FONT=10 \
PLOT_LEGEND_FONT=10 \
PLOT_FIG_W=5.2 \
PLOT_FIG_H=3.8 \
python3 scripts/analysis/analyze_repeated_experiments.py \
  --manifest experiment_repeated/run_manifest.csv \
  --outdir experiment_repeated/results \
  --warmup-s 3
```

These defaults are intended for figures that may be placed side-by-side in a paper.

## Important measurement notes

The experiment reports local gateway-side metrics:

- mean MQTT snapshot reception rate;
- mean SQLite insertion rate;
- Protobuf payload size;
- SQLite commit-time summaries;
- FIFO queue occupancy indicators;
- stored row counts;
- empirical database bytes per sample.

Matched aggregate reception and insertion rates do not prove packet-loss-free
transport. The current `TelemetryState.seq` field is a simulator cache-update
counter, not a dedicated snapshot-publication counter. A sample-level packet-loss
or replay-completeness claim requires adding a dedicated monotonically increasing
snapshot counter.

The current experiment also does not measure synchronized end-to-end latency,
network jitter, packet loss, reconnection behavior, cloud performance, browser
rendering latency, multi-host deployment, encryption overhead, or physical sensor
uncertainty.

## Legacy sweep script

A simpler non-repeated sweep is still available for quick exploratory runs:

```bash
DUR=10 RATES="20 50" BATCHES="1 50" ./run_sweep.sh
```

This writes to `experiments/` and is useful for quick checks, but the repeated
experiment above is the recommended reproducibility path for paper results.

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md). Common quick checks:

```bash
pgrep -a mosquitto || true
pgrep -a telemetry_gateway || true
pgrep -a robot_sim || true
ss -ltnp | grep -E '1883|18883|8080|18080' || true
```

If a local database appears stale:

```bash
rm -f telemetry.db telemetry.db-wal telemetry.db-shm
```

If repeated-experiment outputs should be regenerated from scratch:

```bash
rm -rf experiment_repeated/logs experiment_repeated/db experiment_repeated/results
CLEAN_OUTPUT=1 ./run_repeated_experiment.sh
```

## Citation and release metadata

Before public archival or paper submission, record:

- the Git commit hash used for the experiment;
- the operating system and hardware;
- dependency versions (`mosquitto`, `sqlite3`, `protoc-c`, compiler, Python);
- the exact command used to run the experiment;
- the repository license, if the project is released publicly;
- an archival DOI or release tag, if required by the venue.

A minimal environment capture command is:

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
