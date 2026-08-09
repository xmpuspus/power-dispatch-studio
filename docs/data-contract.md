# The two files the engine reads, and what each one must carry

The engine reads a directory. Point it at your own directory and it models your
own system. Three ways to do that:

```bash
power-dispatch run --data-dir /path/to/your/build --date 2030-01-01
export POWER_DISPATCH_DATA=/path/to/your/build
```

```python
import power_dispatch as pd
pd.run_scenario({"date": "2030-01-01", "opts": {}}, data_dir="/path/to/your/build")
```

The directory needs two files. `dispatch.json` describes the system, and
`profiles.json` describes the days. A third file, `meta.json`, records when the
build ran. The engine never reads it, and the studio shows it.

`tests/test_data_contract.py` checks this page against the engine. It builds a
minimal system with two fuels and one day, runs it, and fails if any key here
stops matching the code.

## Grids and units

Three grid keys, always: `luzon`, `visayas`, `mindanao`. The engine solves them
as a radial path, Luzon to Visayas to Mindanao. Positive flow runs south.

Prices are PhP per kWh. Power is MW. Energy is MWh. Each day has 24 hours, and
every hourly array has 24 entries in clock order.

You can name a grid after your own region. The keys stay the same three strings,
because the linear program builds its rows from them.

## dispatch.json

| Key | Type | Meaning |
| --- | --- | --- |
| `assumptions.wheeling_cost_php_kwh` | float | Cost charged per kWh of flow on a link, in both directions |
| `assumptions.fuel_marginal_cost_php_kwh` | `{fuel: PhP/kWh}` | The marginal cost of each fuel. A fuel missing here costs zero |
| `assumptions.coal_commit_php_kwh` | float | The price of the must-run coal tranche, which keeps committed coal on overnight |
| `assumptions.coal_min_load_frac` | float | Share of available coal that runs as that must-run tranche |
| `coupling.corridors` | list | One entry per link, each `{"id": ..., "limit_mw": ...}` |
| `merit_order.*.fuel_avail_mw` | `{fuel: MW}` | Capacity available per fuel on that grid |
| `merit_order.*.solar_installed_mw` | float | Installed solar on that grid, derated hour by hour by the profile |

The two corridor ids are fixed: `leyte_luzon_hvdc` carries Luzon to Visayas, and
`mvip_hvdc` carries Visayas to Mindanao.

Fuel names are yours to choose, with one exception. A fuel named `coal` splits
into a must-run tranche and a marginal tranche, so a committed plant does not
shut down overnight. Every other fuel is one block at one price. The engine
writes a fuel named `solar` itself each hour, so keep solar out of
`fuel_avail_mw`.

## profiles.json

| Key | Type | Meaning |
| --- | --- | --- |
| `days` | list | One entry per day the engine can replay |
| `days[].date` | string | `YYYY-MM-DD`, and the value `--date` takes |
| `days[].demand` | `{grid: [24 MW]}` | Load per grid per hour |
| `solar_profile` | `[24 fractions]` | Share of installed solar available each hour |

These four are all the engine needs. Everything below is optional, and the
engine falls back when a key is absent.

| Optional key | Fallback | Meaning |
| --- | --- | --- |
| `default_day` | the last day | The day the studio opens on |
| `storage_round_trip_eff` | 0.8 | Round-trip efficiency of added storage |
| `reserve_req_mean_mw` | none | Window-mean reserve per grid, per category |
| `days[].out_dev_mw` | none | That day's outage deviation from the window mean, per fuel |
| `days[].reserve_req_mw` | the window mean | That day's scheduled reserve, per category |
| `days[].hydro_budget_mwh` | unlimited | The day's hydro energy, which caps hydro over 24 hours |
| `days[].corridor_caps` | full limit | Hourly share of each link that was in service |

## A system that runs, in 30 lines

```python
import json, os
GRIDS = ("luzon", "visayas", "mindanao")
hours = range(24)

dispatch = {
    "assumptions": {
        "wheeling_cost_php_kwh": 0.02,
        "fuel_marginal_cost_php_kwh": {"coal": 6.0, "oil": 12.0, "solar": 0.0},
        "coal_commit_php_kwh": 0.5,
        "coal_min_load_frac": 0.4,
    },
    "coupling": {"corridors": [
        {"id": "leyte_luzon_hvdc", "limit_mw": 400.0},
        {"id": "mvip_hvdc", "limit_mw": 450.0},
    ]},
    "merit_order": {g: {
        "fuel_avail_mw": {"coal": 900.0, "oil": 400.0},
        "solar_installed_mw": 200.0,
    } for g in GRIDS},
}
profiles = {
    "default_day": "2030-01-01",
    "solar_profile": [0.0 if h < 6 or h > 18 else 0.6 for h in hours],
    "days": [{"date": "2030-01-01",
              "demand": {g: [800.0 + 10 * h for h in hours] for g in GRIDS}}],
}
os.makedirs("mysystem", exist_ok=True)
json.dump(dispatch, open("mysystem/dispatch.json", "w"))
json.dump(profiles, open("mysystem/profiles.json", "w"))
```

Then run it:

```bash
power-dispatch run --data-dir mysystem --date 2030-01-01
```

## What the contract does not give you

The engine holds fuel blocks per grid, so this file has no place for a named
unit. You can raise `fuel_avail_mw` and you cannot add "Unit 3" and read its
output back. The same limit applies to a contract, a start cost, and a minimum
run time.

Each day solves on its own, with a free terminal storage state, so storage
resets at midnight and the hydro budget caps one day at a time. A year of days
is 365 separate programs, not one 8760-hour program.

Both limits are measured choices rather than oversights. The method page carries
the unit-commitment test that produced the first one.
