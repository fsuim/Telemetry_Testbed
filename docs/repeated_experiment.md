# Repeated Gateway-Side Experiment

The repeated experiment is the recommended path for reproducing the paper-style
local platform validation.

## Quick smoke test

```bash
REPS=1 DUR=15 RUN_LONG=0 ./run_repeated_experiment.sh
```

This checks that the project builds, a private Mosquitto broker can start, the
simulator and gateway can communicate, and the analyzer can generate outputs.

## Full run

```bash
CLEAN_OUTPUT=1 REPS=5 DUR=60 RUN_LONG=1 LONG_DUR=600 ./run_repeated_experiment.sh
```

This runs:

- 5 repetitions for every short-run configuration;
- snapshot rates of 20, 50, 100, and 200 Hz;
- SQLite batch sizes of 1 and 50 rows/transaction;
- two 10 min extended runs at 200 Hz, batch sizes 1 and 50.

## What the script does

`scripts/experiments/run_repeated_experiment.sh`:

1. validates that it is being run from the repository root;
2. optionally builds the project with `make`;
3. starts a private local Mosquitto broker on port 18883 by default;
4. starts `telemetry_gateway` with `--stats` for each run;
5. runs `robot_sim` for the configured duration;
6. records run metadata in `experiment_repeated/run_manifest.csv`;
7. stores gateway logs under `experiment_repeated/logs/`;
8. stores SQLite databases under `experiment_repeated/db/`;
9. calls `scripts/analysis/analyze_repeated_experiments.py`;
10. writes summary CSV, Markdown, and PNG files under `experiment_repeated/results/`.

## Key outputs

```text
experiment_repeated/results/SUMMARY.md
experiment_repeated/results/run_summary.csv
experiment_repeated/results/aggregate_summary.csv
experiment_repeated/results/gwstat_samples.csv
experiment_repeated/results/throughput_batch_1.png
experiment_repeated/results/throughput_batch_50.png
experiment_repeated/results/commit_batch_1.png
experiment_repeated/results/commit_batch_50.png
```

## Analysis-only command

```bash
python3 scripts/analysis/analyze_repeated_experiments.py \
  --manifest experiment_repeated/run_manifest.csv \
  --outdir experiment_repeated/results \
  --warmup-s 3
```

## Important interpretation note

Matched aggregate RX and DB rates show that the local gateway kept up with the
configured workload in aggregate. They do not prove packet-loss-free transport.
The current `telemetry_state.seq` field is not a dedicated snapshot counter.
