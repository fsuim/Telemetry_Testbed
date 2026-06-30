# Troubleshooting

## Build fails: `mosquitto.h` or `protobuf-c.h` not found

Install the development packages:

```bash
sudo apt update
sudo apt install -y libmosquitto-dev protobuf-c-compiler libprotobuf-c-dev libsqlite3-dev
```

Then rebuild:

```bash
make clean
make
```

## Mosquitto will not start

Check whether a broker is already running:

```bash
pgrep -a mosquitto || true
ss -ltnp | grep -E '1883|18883' || true
```

For manual runs, start the default broker:

```bash
mosquitto -v
```

For repeated experiments, the script starts a private broker on port 18883 by
default. Change it if the port is in use:

```bash
MQTT_PORT=18884 ./run_repeated_experiment.sh
```

## WebSocket port is already in use

Use another port:

```bash
./telemetry_gateway --ws-port 8081
```

For repeated experiments:

```bash
WS_PORT=18081 ./run_repeated_experiment.sh
```

## UI does not connect

Check that the gateway is running and listening:

```bash
ss -ltnp | grep 8080 || true
```

Use `ws://localhost:8080` for a manual local run. If the gateway uses a different
port, update the UI field accordingly.

## No telemetry appears

Check the snapshot topic:

```bash
mosquitto_sub -t "/robot/v1/telemetry/state" -C 1 | wc -c
```

Check a raw topic:

```bash
mosquitto_sub -t "/robot/sensors/imu0/acc" -C 1 | wc -c
```

Decode snapshots:

```bash
./state_dump 127.0.0.1 1883
```

## Database is locked or stale

Stop old processes:

```bash
pgrep -a telemetry_gateway || true
pgrep -a robot_sim || true
```

Remove local test databases:

```bash
rm -f telemetry.db telemetry.db-wal telemetry.db-shm
```

## Repeated experiment output looks mixed with previous runs

Use a clean output directory:

```bash
CLEAN_OUTPUT=1 ./run_repeated_experiment.sh
```

Or remove outputs manually:

```bash
rm -rf experiment_repeated/logs experiment_repeated/db experiment_repeated/results
```

## Python figures are not generated

Install `matplotlib`:

```bash
python3 -m pip install --user -r requirements.txt
```

CSV and Markdown summaries should still be generated without `matplotlib`.
