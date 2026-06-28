# Experiments

Main script:

```bash
./run_sweep.sh
```

The root wrapper calls `scripts/run_sweep.sh`.

Useful variables:

```bash
DUR=10 RATES="20 50" BATCHES="1 50" ./run_sweep.sh
```

Default outputs:

- `experiments/logs/`
- `experiments/db/`
- `experiments/results/`

These directories should not be versioned.
