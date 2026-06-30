# Protobuf Contract

Source contract:

```text
proto/robot_telemetry.proto
```

Generated Protobuf-C files:

```text
generated/protobuf-c/robot_telemetry.pb-c.c
generated/protobuf-c/robot_telemetry.pb-c.h
```

Regenerate bindings with:

```bash
make proto
```

## Snapshot topic

The consolidated snapshot is published on:

```text
/robot/v1/telemetry/state
```

The message type is:

```text
robot.v1.TelemetryState
```

It contains a header, IMU values, tilt values, and two motor state submessages.
The gateway stores both decoded fields and the raw Protobuf payload.

## Sequence-field caveat

The current `TelemetryState.header.seq` value is a simulator cache-update counter.
It is useful for debugging monotonicity but is not a dedicated snapshot-publication
sequence number. Do not use gaps in this field as packet-loss proof. A strict
loss/reordering/replay-completeness study should add a snapshot-level sequence
counter that increments exactly once per emitted snapshot.

## Evolution rules

- Keep the package versioned; the current package is `robot.v1`.
- Add new fields in a backward-compatible way.
- Do not reuse numeric tags from removed fields.
- Document schema changes here and regenerate the Protobuf-C bindings.
