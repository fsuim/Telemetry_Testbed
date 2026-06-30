# Architecture

Main flow:

```text
robot_sim -> MQTT broker -> telemetry_gateway -> SQLite/WAL + WebSocket -> UI
```

## Components

- `robot_sim`: simulator executable. It starts simulated sensors, updates the
  shared telemetry cache, publishes raw sensor MQTT topics, and publishes the
  consolidated Protobuf `TelemetryState` snapshot.
- `src/sim/sensors/`: simulated sensor publishers for IMU, tilt, and two motor
  channels.
- `src/sim/telemetry_cache.c`: shared in-memory cache used by sensor threads and
  the state publisher.
- `src/sim/telemetry_state_pub.c`: publishes `TelemetryState` snapshots on
  `/robot/v1/telemetry/state`.
- `telemetry_gateway`: subscribes to the Protobuf snapshot, timestamps reception,
  decodes and queues samples, writes to SQLite/WAL in configurable batches, and
  broadcasts JSON over WebSocket.
- `src/infra/persistence/db_sqlite.c`: schema, PRAGMAs, inserts, and history reads.
- `src/infra/websocket/ws_server.c`: WebSocket live stream and history endpoint.
- `ui/`: static web UI for live monitoring and database-backed replay.
- `state_dump`: CLI Protobuf decoder for the snapshot topic.
- `scripts/`: experiment and analysis automation.

## Dataflow diagram

```text
+-------------+       raw MQTT topics
| robot_sim   | ------------------------------+
| sensors     |                               |
| cache       |       Protobuf snapshot       |
| state pub   | -- /robot/v1/telemetry/state -+
+-------------+                               |
                                              v
                                      +-------------------+
                                      | telemetry_gateway |
                                      | MQTT subscribe    |
                                      | Protobuf decode   |
                                      | gateway timestamp |
                                      | FIFO queue        |
                                      | SQLite writer     |
                                      | WebSocket JSON    |
                                      +---------+---------+
                                                |
                         +----------------------+----------------------+
                         v                                             v
                 +---------------+                             +---------------+
                 | SQLite / WAL  |                             | WebSocket     |
                 | telemetry.db  |                             | JSON live     |
                 | history query |                             | history replay|
                 +---------------+                             +-------+-------+
                                                                        |
                                                                        v
                                                                 +-------------+
                                                                 | ui/         |
                                                                 | browser UI  |
                                                                 +-------------+
```

## Measurement boundary

The current experiments evaluate the local gateway-side path. The gateway
reception timestamp is the temporal reference used for throughput and storage
analysis. The experiments do not measure synchronized end-to-end latency from
publisher to browser.
