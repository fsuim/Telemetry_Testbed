# WebSocket API

Default server for a manual local run:

```text
ws://127.0.0.1:8080
```

The repeated experiment uses `WS_PORT=18080` by default to avoid collisions with
manual UI sessions.

## Live telemetry

The gateway broadcasts JSON telemetry frames to every connected client after a
snapshot has been persisted. The message type is:

```json
{
  "type": "telemetry"
}
```

The full object includes gateway reception metadata, sequence/header fields, IMU,
tilt, and motor summaries. The schema is intentionally browser-friendly JSON even
though the MQTT transport payload is Protobuf.

## History / replay

A client can request the latest stored samples over the same WebSocket connection:

```json
{"type":"history","last":100}
```

The gateway replies with an ordered list of stored samples:

```json
{
  "type": "history",
  "items": []
}
```

Rows are retrieved from SQLite by gateway reception time and returned in
chronological order. The server applies an internal limit to avoid excessive
responses.

## Measurement note

The current experiments evaluate gateway throughput, persistence, and replay data
availability. They do not measure browser rendering latency or end-to-end latency
from publisher to UI.
