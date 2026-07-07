#!/usr/bin/env python3
"""Property and cross-oracle checks on the HiGHS LP engine (pipeline side).

The browser parity lives in the studio suite (byte-identical LP text hashes
plus golden outputs). This file pins the Python engine itself:
  - determinism: two runs of the same day produce identical text and outputs
  - physics: energy balance, storage never creates energy, SoC inside bounds
  - optimality against the old coordinate-descent clear as a second oracle:
    the LP's system cost may never exceed the heuristic's on the same day
Plain python + highspy, no pytest dependency. Run: python3 tests/test_lp_parity.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

from chrono import GRID_KEYS, run_chronology  # noqa: E402
from lp_dispatch import run_chronology_lp  # noqa: E402

WEB = os.path.join(HERE, "..", "web", "data")
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


dispatch = json.load(open(os.path.join(WEB, "dispatch.json")))
profiles = json.load(open(os.path.join(WEB, "profiles.json")))
date = profiles["default_day"]
storage = [{"grid": s["grid"], "power_mw": s["power_mw"],
            "energy_mwh": s["energy_mwh"]}
           for s in profiles["storage_defaults"]]

CASES = [
    ("base", {}),
    ("dict wave", {"demand_delta": {"luzon": 1500}}),
    ("dict wave + storage", {"demand_delta": {"luzon": 1500},
                             "storage": storage}),
    ("reserve co-opt", {"reserve_deduction": True}),
    ("sual out", {"fuel_avail_delta": {"luzon": {"coal": -1294}}}),
]

# determinism: identical text hash and identical outputs across two runs
a = run_chronology_lp(dispatch, profiles, date, {"storage": storage})
b = run_chronology_lp(dispatch, profiles, date, {"storage": storage})
check("deterministic lp text hash", a["lp_sha256"] == b["lp_sha256"])
check("deterministic outputs",
      all(a["hours"][h] == b["hours"][h] for h in range(24)))

eff = profiles["storage_round_trip_eff"]
for label, opts in CASES:
    res = run_chronology_lp(dispatch, profiles, date, opts)
    hrs = res["hours"]
    check(f"{label}: prices finite and positive", all(
        0 < o["price"][g] < 100 for o in hrs for g in GRID_KEYS))
    check(f"{label}: shortfall never negative", all(
        o["shortfall"][g] >= 0 for o in hrs for g in GRID_KEYS))
    # energy balance per hour: fuel_gen + storage discharge + shed covers
    # demand plus exports (0.5 MW slack for the rounded reads)
    ok = True
    for o in hrs:
        gen_l = sum(o["fuel_gen"]["luzon"].values())
        need_l = o["demand"]["luzon"] + o["flow_lv"] - o["shortfall"]["luzon"]
        if abs(gen_l - need_l) > 0.5 + 1e-6:
            ok = False
    check(f"{label}: luzon hourly energy balance", ok)
    # storage physics over the day
    soc = 0.0
    ok = True
    for o in hrs:
        soc += o["charge_mw"] * eff - o["discharge_mw"]
        if soc < -0.51 or o["soc_mwh"] < -1e-6:
            ok = False
    check(f"{label}: storage never creates energy", ok)

# cost dominance: the LP system cost may never exceed the heuristic clear's
# cost on the same inputs (the LP is the optimum of the same problem)
def dispatch_cost(res) -> float:
    a = dispatch["assumptions"]
    costs = dict(a["fuel_marginal_cost_php_kwh"])
    wheel = a["wheeling_cost_php_kwh"]
    total = 0.0
    for o in res["hours"]:
        for g in GRID_KEYS:
            for fuel, mw in o["fuel_gen"][g].items():
                if fuel == "coal":
                    # cost the coal energy at the marginal price: an upper
                    # bound (the commit tranche is cheaper), same for both
                    total += mw * costs["coal"]
                elif fuel == "storage":
                    total += 0.0
                else:
                    total += mw * costs.get(fuel, 0.0)
        total += wheel * (abs(o["flow_lv"]) + abs(o["flow_vm"]))
    return total


for label, opts in (("base", {}), ("dict wave",
                                   {"demand_delta": {"luzon": 1500}})):
    old = run_chronology(dispatch, profiles, date, opts)
    new = run_chronology_lp(dispatch, profiles, date, opts)
    check(f"{label}: LP dispatch cost <= heuristic clear cost",
          dispatch_cost(new) <= dispatch_cost(old) + 1.0)
    # both engines agree on unserved energy for the base model
    check(f"{label}: unserved energy agrees with the old clear", all(
        abs(old["summary"]["unserved_mwh"][g]
            - new["summary"]["unserved_mwh"][g]) <= 5.0 for g in GRID_KEYS))

# a reserve requirement beyond a grid's capable capacity must clamp, not
# blow up the solve (the infeasible-row defect the adversarial review found)
kill = {f: -1e6 for f in ("coal", "oil", "hydro", "geothermal",
                          "natural_gas", "biomass")}
res = run_chronology_lp(dispatch, profiles, date,
                        {"reserve_deduction": True,
                         "fuel_avail_delta": {"mindanao": kill}})
check("reserve requirement beyond capable capacity still solves", all(
    0 < o["price"][g] < 100 for o in res["hours"] for g in GRID_KEYS))
check("the gutted grid sheds instead of going infeasible",
      res["summary"]["unserved_mwh"]["mindanao"] > 0)

# the baked goldens must be reproducible from the current pipeline
golden = profiles["chrono_golden"]
res = run_chronology_lp(dispatch, profiles, golden["date"],
                        {k: v for k, v in golden["cases"][0]["input"].items()
                         if k != "date"})
check("baked golden case 0 reproduces (hash)",
      res["lp_sha256"] == golden["cases"][0]["lp_sha256"])

print(f"\n{len(fails)} failures" if fails else "\nall green")
sys.exit(1 if fails else 0)
