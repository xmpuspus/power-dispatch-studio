# One scenario file the browser writes and Python runs

A scenario used to exist in two shapes. The command line took a JSON object. The
studio kept its edits in a URL hash. So a scenario built by dragging a slider
could not re-run in Python, and one written in Python could not open in a
browser.

Version `pds-scenario/1` is the one file. The studio writes it from Saved runs.
`power-dispatch run --scenario` reads it. `power-dispatch validate` checks it and
names what is wrong.

```json
{
  "schema": "pds-scenario/1",
  "name": "DICT 1.5 GW on Luzon",
  "date": "2026-06-17",
  "opts": { "demand_delta": { "luzon": 1500 } },
  "meta": { "note": "free text, and the engine never reads it" }
}
```

## The four top-level keys

| Key | Required | Meaning |
| --- | --- | --- |
| `schema` | yes | `pds-scenario/1`. A file without it still runs, as the older shape |
| `date` | yes | `YYYY-MM-DD`, a day the data directory carries |
| `opts` | no | The engine options below. An empty object replays the day as recorded |
| `name`, `meta` | no | For people. The engine reads neither |

## Every option the engine honors

`power_dispatch.OPT_KEYS` is the source of this list, and
`tests/test_scenario_file.py` fails when the two stop matching.

| Option | Value shape | Effect on the run |
| --- | --- | --- |
| `demand_delta` | `{grid: MW}` or `{grid: [24 MW]}` | Adds or removes load. One number is flat around the clock, 24 numbers are an hourly shape |
| `fuel_cost` | `{fuel: PhP/kWh}` | Sets a fuel's marginal cost |
| `fuel_avail_delta` | `{grid: {fuel: MW}}` | Adds or removes capacity of one fuel on one grid |
| `solar_delta_mw` | `{grid: MW}` | Adds installed solar, derated hour by hour |
| `hydrology` | number | Multiplies hydro availability. 1.0 is the recorded day |
| `caps` | `{leyte\|mvip: MW}` or `[24 MW]` | Sets a link's transfer limit |
| `storage` | `[{grid, power_mw, energy_mwh}]` | Adds batteries. An optional `id` names which studio row a battery is |
| `reserve_deduction` | bool | Withholds the day's scheduled reserve from the stack |
| `offer_mode` | bool | Replays the operator's published offer book instead of the cost model |
| `gas_budget` | `{grid: MWh}` | Caps gas energy for the day, for a lower-supply case |

Grids are `luzon`, `visayas`, `mindanao`. Fuels are the keys in
`dispatch.json`'s `fuel_avail_mw`.

## Check a file before you run it

```bash
power-dispatch validate myscenario.json
power-dispatch validate --keys myscenario.json   # print every option first
power-dispatch run --scenario myscenario.json -o out.csv
```

A broken file prints one line per problem and exits 1:

```
myscenario.json: 3 problem(s)
  'date' must be a string shaped YYYY-MM-DD
  unknown option 'demand_delto'. Did you mean 'demand_delta'?
  'fuel_avail_delta' names 'lozon', not a grid
```

From Python:

```python
import power_dispatch as pd

problems = pd.validate_scenario(scenario)   # a list of messages, never raises
scenario = pd.load_scenario("myscenario.json")  # raises ValueError with all of them
result = pd.run_scenario(scenario)
```

## What a round trip through the studio keeps, and what it drops

The studio holds most options as values in its object tables, so they survive a
trip out to a file and back. Three do not, because they are run settings rather
than table values. Loading a file that carries one of them shows a warning that
names it.

| Option | Round trip | Why |
| --- | --- | --- |
| `demand_delta`, `fuel_cost`, `fuel_avail_delta`, `solar_delta_mw`, `caps`, `storage` | kept | Each one maps onto an editable row |
| `demand_delta` as 24 hourly numbers | flattened | The region table holds one number, so the studio takes the mean and says so |
| `hydrology`, `reserve_deduction`, `gas_budget` | dropped, with a warning | These come from controls, not from a table row |

The file's `storage` list is the run's storage. A battery the file does not name
goes to zero on load, so a scenario cannot leave a battery running from the
scenario before it.

## What version 1 cannot carry

No named unit, no contract, no start cost, and no minimum run time. The engine
dispatches fuel blocks per grid, so a file that carried them would describe a run
the engine cannot reproduce. When the engine gains named units, this schema goes
to version 2 and the validator will say so by name.
