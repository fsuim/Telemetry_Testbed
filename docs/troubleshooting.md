# Troubleshooting

## Mosquitto does not connect

Check whether the broker is active on port 1883:

```bash
mosquitto -v
```

or, on systems with a service manager:

```bash
sudo service mosquitto start
```

## WebSocket port is already in use

Use another port:

```bash
./telemetry_gateway --ws-port 8081
```

## Database is locked or stale

Stop old processes and remove local artifacts:

```bash
rm -f telemetry.db telemetry.db-wal telemetry.db-shm
```

## UI has no data

Confirm that:

- the MQTT broker is running;
- `robot_sim` is publishing;
- `telemetry_gateway` is connected;
- the UI points to the correct WebSocket port.
