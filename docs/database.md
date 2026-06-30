# SQLite Persistence

Gateway persistence is implemented in `src/infra/persistence/db_sqlite.c`.

## Runtime configuration

The gateway opens the database path provided by:

```bash
./telemetry_gateway --db telemetry.db
```

SQLite is configured with:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
```

WAL mode allows reads for history replay while writes continue.

## Main table

The gateway stores one consolidated snapshot per row in `telemetry_state`.
The table includes:

- gateway reception time: `received_at_ns`;
- MQTT topic;
- robot ID, message timestamp, and sequence field from the snapshot header;
- decoded IMU, tilt, and motor values used by the UI and analysis;
- `raw BLOB`, the original Protobuf payload for archival and later re-decoding.

Indexes:

- `idx_state_received` on `received_at_ns`;
- `idx_state_robot_received` on `(robot_id, received_at_ns)`.

## Local artifacts

Do not treat `.db`, `.db-wal`, or `.db-shm` files as source files. They are
runtime artifacts. Experiment databases are written under:

```text
experiment_repeated/db/
experiments/db/
```

## Storage-footprint metric

The analysis scripts report empirical bytes per sample as database file size
divided by stored rows. This is a practical footprint for the tested SQLite
configuration and run duration, not a format-intrinsic constant. SQLite page
allocation, indexes, WAL behavior, and run duration can all affect the result.
