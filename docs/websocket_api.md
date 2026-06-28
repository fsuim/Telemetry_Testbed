# WebSocket API

Default server: `ws://127.0.0.1:8080`.

## Live telemetry

The gateway sends JSON messages with `type: "telemetry"` containing timestamp, sequence, IDs, IMU, tilt, and motors.

## History

The UI can request history through WebSocket. The server limits the number of samples to avoid excessive responses.

Keeping the live and history JSON formats compatible is important to avoid breaking the UI.
