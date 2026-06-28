# Architecture

Main flow:

```text
robot_sim -> MQTT -> telemetry_gateway -> SQLite/WebSocket -> UI
```

## Components

- `robot_sim`: simulator executable. Initializes sensors, the telemetry cache, and the consolidated Protobuf publisher.
- `src/sim/sensors`: simulated sensors that publish RAW payloads to separate MQTT topics.
- `src/sim/telemetry_cache.c`: in-memory cache shared by the sensors and the state publisher.
- `src/sim/telemetry_state_pub.c`: publishes `TelemetryState` snapshots in Protobuf on the `/robot/v1/telemetry/state` topic.
- `telemetry_gateway`: gateway executable. Consumes Protobuf via MQTT, persists data to SQLite/WAL, and broadcasts JSON through WebSocket.
- `src/infra/persistence/db_sqlite.c`: schema, PRAGMAs, writes, and history reads.
- `src/infra/websocket/ws_server.c`: WebSocket server for the UI and history replay.
- `ui/`: static web interface.
- `scripts/`: experiment and analysis automation.

## Diagram

```text
+-------------+       MQTT RAW topics
| robot_sim   | ------------------------------+
| sensors     |                               |
| cache       |       MQTT Protobuf snapshot  |
| state pub   | -- /robot/v1/telemetry/state -+
+-------------+                               |
                                              v
                                      +-------------------+
                                      | telemetry_gateway |
                                      | MQTT subscribe    |
                                      | Protobuf decode   |
                                      | queue/batch       |
                                      | SQLite writer     |
                                      | WS JSON stream    |
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

## Organization decision

- `src/apps`: entrypoints and CLI.
- `src/app`: application orchestration.
- `src/sim`: simulator and sensors.
- `src/infra`: external dependencies and infrastructure, such as MQTT, SQLite, and WebSocket.
- `include`: headers organized by layer.
- `proto`: Protobuf contracts.
- `generated`: generated code.
- `scripts`: operational automation.
- `experiments`: local databases, logs, and results, ignored by Git.
