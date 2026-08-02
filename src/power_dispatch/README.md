# power-dispatch-studio

The PH WESM dispatch engine behind [Power Dispatch
Studio](https://power-dispatch-studio.vercel.app), as an importable, citable
Python module and CLI.

The studio runs the same linear optimization and lowest-cost-first dispatch
(merit order) in the browser with HiGHS compiled to WebAssembly. This package is
the Python reference code for replaying one recorded day. It builds a
supply stack for each island grid from a calculated snapshot of public IEMOP data,
applies scenario changes, and clears the three connected grids with inter-grid
limits, storage, reserves, and a daily hydro-energy limit. The same calculation
and numbers can run in a notebook.

## Install

```bash
pip install power-dispatch-studio
```

The only runtime dependency is [`highspy`](https://pypi.org/project/highspy/)
(the HiGHS solver). A dated snapshot of the public data archive ships in the
wheel, so it runs with no network access.

## CLI

```bash
power-dispatch days                              # recorded days available
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

A scenario is `{"date": "YYYY-MM-DD", "opts": {...}}`. The engine accepts
the following override keys.

| key | type | meaning |
| --- | --- | --- |
| `demand_delta` | `{grid: MW}` or `{grid: [24 MW]}` | load added or removed, flat or with an hourly shape |
| `fuel_cost` | `{fuel: PhP/kWh}` | marginal-cost override |
| `fuel_avail_delta` | `{grid: {fuel: MW}}` | availability edit |
| `solar_delta_mw` | `{grid: MW}` | installed solar edit |
| `hydrology` | `float` | water multiplier (1.0 = observed) |
| `caps` | `{leyte\|mvip: MW or [24]}` | link limits |
| `storage` | `[{grid, power_mw, energy_mwh}]` | added BESS |
| `reserve_deduction` | `bool` | withhold scheduled reserve |
| `offer_mode` | `bool` | replay the recorded offer book. False uses the cost calculation |

`grid` is one of `luzon`, `visayas`, `mindanao`.

## The data snapshot

The bundled data is a dated snapshot of the public archive at build time (see
`power_dispatch/data/meta.json`). To run against newer calculated data, point the
engine at a copy of the deployed `web/data/`.

```bash
power-dispatch run --date 2026-07-01 --data-dir /path/to/web/data
# or: export POWER_DISPATCH_DATA=/path/to/web/data
```

## What this is and is not

This replays recorded days with scenario what-ifs on a documented calculation. It is
not a price forecast, and offer mode replays the market's published bids rather
than simulating bidding strategy. Recorded market inputs trace to the Independent
Electricity Market Operator of the Philippines (IEMOP). Fleet and cost inputs cite
their own sources. Caller inputs and model assumptions have separate labels. The
Historical replay view and method page report the calculation error. Read the
[full method](https://power-dispatch-studio.vercel.app/methodology.html).

MIT licensed.
