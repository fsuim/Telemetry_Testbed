# SQLite

Gateway persistence is implemented in `src/infra/persistence/db_sqlite.c`.

Recommendations:

- Keep WAL enabled for continuous writes.
- Do not version `.db`, `.db-wal`, or `.db-shm` database files.
- Use experiment databases under `experiments/db/`.
- Document any future schema migration here.
