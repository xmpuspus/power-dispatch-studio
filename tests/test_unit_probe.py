#!/usr/bin/env python3
"""Pin the named-unit dispatch probe, and the claim it supports.

pipeline/unit_probe.py answers "what does dispatching named units buy" with a
measurement rather than an opinion. The measurement is only worth publishing if
the two runs really do hold the same system, so this checks the controls as well
as the result:

  - the probe dispatched a plausible number of named units per grid,
  - the two runs burn the same daily energy per fuel, which is the claim,
  - the verdict string and the default engine agree with those numbers,
  - the unit shares still sum to one per fuel per grid, which is what keeps the
    two systems the same size.

Plain python, no pytest dependency. Run: python3 tests/test_unit_probe.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


GRIDS = ("luzon", "visayas", "mindanao")
u = json.load(open(os.path.join(ROOT, "web", "data", "unit_probe.json")))

if not u.get("generated_by"):
    print("no unit probe in this build; run python3 pipeline/unit_probe.py --derive")
    sys.exit(0)

n = u["n_units_dispatched"]
check("every grid dispatches named units", all(n[g] > 0 for g in GRIDS))
check("Luzon carries the most named units", n["luzon"] == max(n.values()))
check("the unit count is a fleet, not a handful", sum(n.values()) >= 100)

gap = u["generation_gap"]
check("the two runs burn the same daily energy per fuel", gap["daily_mwh"] < 0.5)
check("the probe measured at least 5 days", u["generation_gap_days"] >= 5)
check(
    "an energy-limited fuel does move between hours",
    gap["hourly_mw"] > 0,
)
check("the verdict follows the daily energy", "same energy" in u["verdict"])
check("the block model stays the default", u["engine_default"] == "block")
check(
    "the probe names what would change the answer",
    "heat rate" in u["what_would_change_it"],
)

# every scored series carries both engines, so no delta is half-measured
for tgt in ("lwap", "mcp"):
    for g in GRIDS:
        d = u["delta"][tgt].get(g)
        if d is None:
            continue
        check(
            f"{g} {tgt} carries both correlations",
            d["block_corr"] is not None and d["unit_corr"] is not None,
        )

# the control: unit shares sum to one per fuel per grid, so the unit run and the
# block run hold the same capacity
import unit_probe as up  # noqa: E402

dispatch = json.load(open(os.path.join(ROOT, "web", "data", "dispatch.json")))
fleet = json.load(open(os.path.join(ROOT, "web", "data", "fleet.json")))
units = up.unit_stacks(dispatch, fleet)
for g in GRIDS:
    per_fuel = {}
    for row in units[g]:
        per_fuel[row["fuel"]] = per_fuel.get(row["fuel"], 0.0) + row["share"]
    check(
        f"{g} unit shares sum to one for every fuel",
        all(abs(v - 1.0) < 1e-9 for v in per_fuel.values()),
    )
    check(
        f"{g} covers every fuel the block model carries",
        set(per_fuel) == set(dispatch["merit_order"][g]["fuel_avail_mw"]),
    )

print()
print(f"unit probe: {len(fails)} failures" if fails else "unit probe: all green")
sys.exit(1 if fails else 0)
