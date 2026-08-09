#!/usr/bin/env python3
"""The bring-your-own-data contract is a test, not a promise.

`power-dispatch --data-dir` and `POWER_DISPATCH_DATA` already point the engine
at any directory holding dispatch.json and profiles.json. Nothing checked what
those two files must carry, so docs/data-contract.md could drift from the engine
in either direction. This file pins three things:

  1. the shipped build satisfies the contract (web/data and the bundled wheel
     snapshot both run),
  2. docs/data-contract.md names every required key, so a reader building their
     own system is not missing one,
  3. a minimal hand-written system, with two fuels and one day, actually solves.

Item 3 is the real proof. It is what an analyst does on their first afternoon.

Plain python + highspy, no pytest dependency. Run: python3 tests/test_data_contract.py
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import power_dispatch as pdx  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


GRIDS = ("luzon", "visayas", "mindanao")

# Every key the engine reads, as a dotted path. `*` stands for each of the three
# grid names. Derived from engine/lp_dispatch.py:_assemble and
# engine/chrono.py:build_stack; a key added there belongs here and in the doc.
REQUIRED_DISPATCH = [
    "assumptions.wheeling_cost_php_kwh",
    "assumptions.fuel_marginal_cost_php_kwh",
    "assumptions.coal_commit_php_kwh",
    "assumptions.coal_min_load_frac",
    "coupling.corridors",
    "merit_order.*.fuel_avail_mw",
    "merit_order.*.solar_installed_mw",
]
REQUIRED_PROFILES = [
    "days",
    "days[].date",
    "days[].demand",
    "solar_profile",
]
OPTIONAL_PROFILES = [
    "default_day",
    "storage_round_trip_eff",
    "reserve_req_mean_mw",
    "days[].out_dev_mw",
    "days[].reserve_req_mw",
    "days[].hydro_budget_mwh",
    "days[].corridor_caps",
]


def dig(obj, path):
    """Follow a dotted path, expanding `*` over the three grids and `[]` over
    the first list element. Returns (found, value)."""
    cur = obj
    for part in path.split("."):
        if part.endswith("[]"):
            part = part[:-2]
            if not isinstance(cur, dict) or part not in cur:
                return False, None
            cur = cur[part]
            if not isinstance(cur, list) or not cur:
                return False, None
            cur = cur[0]
            continue
        if part == "*":
            if not isinstance(cur, dict):
                return False, None
            for g in GRIDS:
                if g not in cur:
                    return False, None
            cur = cur[GRIDS[0]]
            continue
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def check_dir(label, root):
    d = json.load(open(os.path.join(root, "dispatch.json")))
    p = json.load(open(os.path.join(root, "profiles.json")))
    for path in REQUIRED_DISPATCH:
        found, _ = dig(d, path)
        check(f"{label}: dispatch.json carries {path}", found)
    for path in REQUIRED_PROFILES:
        found, _ = dig(p, path)
        check(f"{label}: profiles.json carries {path}", found)
    ids = {c.get("id") for c in d["coupling"]["corridors"]}
    check(
        f"{label}: both corridors are named",
        {"leyte_luzon_hvdc", "mvip_hvdc"} <= ids,
    )
    check(f"{label}: the solar profile is 24 hours", len(p["solar_profile"]) == 24)
    day = p["days"][0]
    check(
        f"{label}: every grid's demand is 24 hours",
        all(len(day["demand"][g]) == 24 for g in GRIDS),
    )


# 1. the shipped builds
check_dir("web/data", os.path.join(ROOT, "web", "data"))
bundled = os.path.join(ROOT, "src", "power_dispatch", "data")
if os.path.isfile(os.path.join(bundled, "dispatch.json")):
    check_dir("bundled snapshot", bundled)

# 2. the document names every required key
doc = open(os.path.join(ROOT, "docs", "data-contract.md")).read()
for path in REQUIRED_DISPATCH + REQUIRED_PROFILES:
    check(f"docs/data-contract.md names {path}", f"`{path}`" in doc)
for path in OPTIONAL_PROFILES:
    check(f"docs/data-contract.md names the optional {path}", f"`{path}`" in doc)


# 3. a minimal hand-written system solves
def minimal_system(tmp):
    hours = list(range(24))
    dispatch = {
        "assumptions": {
            "wheeling_cost_php_kwh": 0.02,
            "fuel_marginal_cost_php_kwh": {"coal": 6.0, "oil": 12.0, "solar": 0.0},
            "coal_commit_php_kwh": 0.5,
            "coal_min_load_frac": 0.4,
        },
        "coupling": {
            "corridors": [
                {"id": "leyte_luzon_hvdc", "limit_mw": 400.0},
                {"id": "mvip_hvdc", "limit_mw": 450.0},
            ]
        },
        "merit_order": {
            g: {
                "fuel_avail_mw": {"coal": 900.0, "oil": 400.0},
                "solar_installed_mw": 200.0,
            }
            for g in GRIDS
        },
    }
    profiles = {
        "default_day": "2030-01-01",
        "solar_profile": [0.0 if h < 6 or h > 18 else 0.6 for h in hours],
        "days": [
            {
                "date": "2030-01-01",
                "demand": {g: [800.0 + 10 * h for h in hours] for g in GRIDS},
            }
        ],
    }
    with open(os.path.join(tmp, "dispatch.json"), "w") as fh:
        json.dump(dispatch, fh)
    with open(os.path.join(tmp, "profiles.json"), "w") as fh:
        json.dump(profiles, fh)


with tempfile.TemporaryDirectory() as tmp:
    minimal_system(tmp)
    check("a minimal system lists its one day", pdx.list_days(tmp) == ["2030-01-01"])
    res = pdx.run_scenario({"date": "2030-01-01", "opts": {}}, data_dir=tmp)
    check("a minimal system solves 24 hours", len(res["hours"]) == 24)
    prices = [h["price"]["luzon"] for h in res["hours"]]
    check("every hour prices", all(v > 0 for v in prices))
    check(
        "the cheap fuel sets the price while it lasts",
        res["hours"][0]["marginal"]["luzon"] == "coal",
    )
    # 3,000 MW on a fleet that peaks near 1,500 must show unserved load
    short = pdx.run_scenario(
        {"date": "2030-01-01", "opts": {"demand_delta": {"luzon": 3000}}},
        data_dir=tmp,
    )
    check(
        "load past the fleet shows as a shortfall, not a silent clip",
        any(h["shortfall"]["luzon"] > 0 for h in short["hours"]),
    )
    check_dir("a minimal system", tmp)

print()
print(f"data contract: {len(fails)} failures" if fails else "data contract: all green")
sys.exit(1 if fails else 0)
