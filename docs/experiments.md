# Experiments

This repository contains two experiment drivers:

1. `./run_repeated_experiment.sh` — recommended paper-style repeated validation.
2. `./run_sweep.sh` — simpler exploratory sweep retained for quick checks.

## Recommended: repeated validation

Use this for reproducible paper-style results:

```bash
REPS=1 DUR=15 RUN_LONG=0 ./run_repeated_experiment.sh       # smoke test
CLEAN_OUTPUT=1 REPS=5 DUR=60 RUN_LONG=1 LONG_DUR=600 ./run_repeated_experiment.sh
```

Outputs are written under `experiment_repeated/`.

See [`docs/repeated_experiment.md`](repeated_experiment.md) and
[`docs/reproducibility.md`](reproducibility.md).

## Exploratory sweep

Use this for quick local checks without repeated runs:

```bash
DUR=10 RATES="20 50" BATCHES="1 50" ./run_sweep.sh
```

Default exploratory outputs:

```text
experiments/logs/
experiments/db/
experiments/results/
```

The exploratory sweep is useful for development but should not be used as the
main reproducibility evidence for paper results.
