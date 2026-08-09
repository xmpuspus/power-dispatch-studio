# Three scripts that take about a minute each

The Python package runs the same engine the browser runs. These scripts are the
first hour with it. They need no account, no key, and no network: a dated
snapshot of the public archive ships inside the wheel.

```bash
pip install power-dispatch-studio
python3 examples/01_replay_a_day.py
```

| Script | What it answers | Runtime |
| --- | --- | --- |
| `01_replay_a_day.py` | What set the price each hour of a recorded day | about 2 seconds |
| `02_add_a_data_center.py` | What 1,500 MW of new flat load does to the Luzon price | about 4 seconds |
| `03_sweep_the_window.py` | How that answer changes across every recorded day | about 1 second per run |

The third script takes a day count, so `python3 examples/03_sweep_the_window.py
out.csv 5` runs the last five days instead of all 118. CI runs it that way.

## Where to go after these

- Your own system, rather than the Philippine one:
  [`docs/data-contract.md`](../docs/data-contract.md) lists the two files the
  engine reads and carries a 30-line system that runs.
- Every scenario key the engine honors: `power_dispatch.OPT_KEYS`, and the table
  in [`src/power_dispatch/README.md`](../src/power_dispatch/README.md).
- The same scenarios with charts:
  [the studio](https://power-dispatch-studio.vercel.app/studio/), which solves
  the same linear program in your browser.

## No script here names a plant, and no price here is a forecast

The engine dispatches fuel blocks per island grid, so no script here names a
plant. Each day solves on its own, so storage resets at midnight. A price from
the cost model is a competitive floor and not a forecast. The method page
carries the error against recorded prices.
