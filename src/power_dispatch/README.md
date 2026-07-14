# power-dispatch-studio

The PH WESM dispatch engine behind [Power Dispatch
Studio](https://power-dispatch-studio.vercel.app), as an importable, citable
Python module and CLI.

The studio runs this same linear-program merit-order engine in the browser
(wasm HiGHS). This package is the Python reference implementation of one
observed-day replay: it builds per-grid supply stacks from a baked snapshot of
public IEMOP data, applies scenario overrides, and clears a coupled
three-grid LP with corridor limits, storage, reserves, and a hydro water
budget. It is the same engine, same numbers, runnable in a notebook.

## Install

```bash
pip install power-dispatch-studio
```

The only runtime dependency is [`highspy`](https://pypi.org/project/highspy/)
(the HiGHS solver). A dated snapshot of the public data archive ships in the
wheel, so it runs with no network access.

## CLI

```bash
power-dispatch days                              # observed days available
power-dispatch run --date 2026-06-15             # hourly CSV to stdout
power-dispatch run --date 2026-06-15 --offer-mode # replay the market's own bids
power-dispatch run --date 2026-06-15 --demand luzon=1500 -o out.csv
power-dispatch run --scenario scenario.json -o out.csv
```

## Python

```python
import power_dispatch as pd

pd.list_days()[:3]
# ['2026-05-01', '2026-05-02', '2026-05-03']

result = pd.run_scenario({
    "date": "2026-06-15",
    "opts": {"demand_delta": {"luzon": 1500}},  # +1.5 GW data-center load
})
result["summary"]["mean_price"]["luzon"]   # PhP/kWh
```

## The scenario override map

A scenario is `{"date": "YYYY-MM-DD", "opts": {...}}`. The override keys the
engine honors:

| key | type | meaning |
| --- | --- | --- |
| `demand_delta` | `{grid: MW}` | load added or removed |
| `fuel_cost` | `{fuel: PhP/kWh}` | marginal-cost override |
| `fuel_avail_delta` | `{grid: {fuel: MW}}` | availability edit |
| `solar_delta_mw` | `{grid: MW}` | installed solar edit |
| `hydrology` | `float` | water multiplier (1.0 = observed) |
| `caps` | `{leyte\|mvip: MW or [24]}` | corridor limits |
| `storage` | `[{grid, power_mw, energy_mwh}]` | added BESS |
| `reserve_deduction` | `bool` | withhold scheduled reserve |
| `offer_mode` | `bool` | replay the observed offer book, not the cost proxy |

`grid` is one of `luzon`, `visayas`, `mindanao`.

## The data snapshot

The bundled data is a dated snapshot of the public archive at build time (see
`power_dispatch/data/meta.json`). To run against a fresher bake, point the
engine at a copy of the deployed `web/data/`:

```bash
power-dispatch run --date 2026-07-01 --data-dir /path/to/web/data
# or: export POWER_DISPATCH_DATA=/path/to/web/data
```

## What this is and is not

This replays OBSERVED days with scenario what-ifs on a defensible engine. It is
not a price forecast, and offer-mode is a replay of the market's own published
bids, not a bid-strategy simulator. Every number traces to a primary IEMOP
source; the studio's Backcast view and methodology publish the engine's error
rather than tuning it. Full methodology:
<https://power-dispatch-studio.vercel.app/methodology.html>.

MIT licensed.
