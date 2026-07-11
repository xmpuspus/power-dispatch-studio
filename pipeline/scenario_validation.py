#!/usr/bin/env python3
"""Battle-test harness: run analyst what-if scenarios through the real dispatch
engine (run_chronology_lp) and check the tool reproduces the expected direction
and rough magnitude. A mismatch means the engine is wrong, not the analyst.

    python3 pipeline/scenario_validation.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # pipeline/
ROOT = os.path.abspath(os.path.join(HERE, ".."))           # repo root
sys.path.insert(0, HERE)

import lp_dispatch  # noqa: E402

DISPATCH = json.load(open(os.path.join(ROOT, "web", "data", "dispatch.json")))
PROFILES = json.load(open(os.path.join(ROOT, "web", "data", "profiles.json")))
GRIDS = ["luzon", "visayas", "mindanao"]

TYPICAL = "2026-06-20"   # profiles default_day
STRESS = "2026-05-28"    # highest observed Luzon peak in the window


def run(date, opts=None):
    return lp_dispatch.run_chronology_lp(DISPATCH, PROFILES, date, opts or {})


def summ(res):
    """Collapse an engine run to the metrics an analyst reads."""
    hrs = res["hours"]
    n = len(hrs)
    out = {"n": n}
    for g in GRIDS:
        pr = [h["price"][g] for h in hrs]
        out[f"{g}_mean_price"] = round(sum(pr) / n, 3)
        out[f"{g}_peak_price"] = round(hrs[19]["price"][g], 3)   # 7pm
        out[f"{g}_mid_price"] = round(hrs[12]["price"][g], 3)    # noon
        out[f"{g}_shed_mwh"] = round(sum(h["shortfall"][g] for h in hrs), 1)
    # fuel energy over the day (MWh), summed across grids
    fuels = {}
    for h in hrs:
        for g in GRIDS:
            for f, mw in h["fuel_gen"][g].items():
                fuels[f] = fuels.get(f, 0.0) + mw
    out["fuel_mwh"] = {f: round(v) for f, v in sorted(fuels.items())}
    # Leyte-Luzon corridor: hours saturated + congestion rent
    out["leyte_sat_hours"] = sum(1 for h in hrs if h["leyte"]["sat"])
    out["leyte_flow_peak"] = round(hrs[19]["flow_lv"], 1)
    out["vis_luz_spread_peak"] = round(
        hrs[19]["price"]["visayas"] - hrs[19]["price"]["luzon"], 3)
    return out


def delta(base, scen, key):
    return round(scen[key] - base[key], 3)


# ---- the scenario battery -------------------------------------------------
# each: (id, title, day, opts, expectation-check(base, scen) -> (verdict, note))

def _co2_proxy(s):
    """coal+gas MWh as a dirty-generation proxy (no emissions factor baked)."""
    fm = s["fuel_mwh"]
    return fm.get("coal", 0) + fm.get("natural_gas", 0) + fm.get("oil", 0)


SCENARIOS = []


def scen(id, title, day, opts, check):
    SCENARIOS.append((id, title, day, opts, check))


scen("1", "+1,000 MW solar, Luzon", TYPICAL,
     {"solar_delta_mw": {"luzon": 1000}},
     lambda b, s: (
         "PASS" if delta(b, s, "luzon_mid_price") < -0.001
         and abs(delta(b, s, "luzon_peak_price")) < 0.05
         and _co2_proxy(s) < _co2_proxy(b) else "CHECK",
         f"midday {delta(b,s,'luzon_mid_price'):+.3f}, "
         f"peak {delta(b,s,'luzon_peak_price'):+.3f}, "
         f"coal+gas MWh {_co2_proxy(s)-_co2_proxy(b):+.0f}"))

scen("2a", "+300 MW AI DC, Pampanga (Luzon)", TYPICAL,
     {"demand_delta": {"luzon": 300}},
     lambda b, s: (
         "PASS" if delta(b, s, "luzon_peak_price") >= -0.001
         and s["leyte_sat_hours"] <= b["leyte_sat_hours"] + 0 else "CHECK",
         f"Luzon peak {delta(b,s,'luzon_peak_price'):+.3f}, "
         f"leyte sat hrs {b['leyte_sat_hours']}->{s['leyte_sat_hours']}"))

scen("2b", "+1,000 MW AI DC, Cebu (Visayas)", TYPICAL,
     {"demand_delta": {"visayas": 1000}},
     lambda b, s: (
         "PASS" if s["leyte_sat_hours"] >= b["leyte_sat_hours"]
         and delta(b, s, "visayas_peak_price") > 0.001 else "CHECK",
         f"Visayas peak {delta(b,s,'visayas_peak_price'):+.3f}, "
         f"leyte sat hrs {b['leyte_sat_hours']}->{s['leyte_sat_hours']}, "
         f"vis-luz spread@peak {b['vis_luz_spread_peak']:.2f}->"
         f"{s['vis_luz_spread_peak']:.2f}, shed {delta(b,s,'visayas_shed_mwh'):+.1f}"))

scen("3", "+50 MW small hydro, Luzon (downstream Angat)", TYPICAL,
     {"fuel_avail_delta": {"luzon": {"hydro": 50}}},
     lambda b, s: (
         "PASS" if s["fuel_mwh"].get("hydro", 0) >= b["fuel_mwh"].get("hydro", 0)
         and delta(b, s, "luzon_mean_price") <= 0.001 else "CHECK",
         f"hydro MWh {b['fuel_mwh'].get('hydro',0)}->{s['fuel_mwh'].get('hydro',0)}, "
         f"Luzon mean {delta(b,s,'luzon_mean_price'):+.3f}"))

scen("4", "+600 MW gas, Visayas", TYPICAL,
     {"fuel_avail_delta": {"visayas": {"natural_gas": 600}}},
     lambda b, s: (
         "PASS" if delta(b, s, "visayas_mean_price") <= 0.001
         and s["leyte_sat_hours"] <= b["leyte_sat_hours"] else "CHECK",
         f"Visayas mean {delta(b,s,'visayas_mean_price'):+.3f}, "
         f"leyte sat hrs {b['leyte_sat_hours']}->{s['leyte_sat_hours']}"))

scen("5", "Malampaya depletes -> imported LNG (gas 4.8->10.3)", TYPICAL,
     {"fuel_cost": {"natural_gas": 10.3}},
     lambda b, s: (
         "PASS" if delta(b, s, "luzon_mean_price") > 0.001 else "CHECK",
         f"Luzon mean {delta(b,s,'luzon_mean_price'):+.3f}, "
         f"peak {delta(b,s,'luzon_peak_price'):+.3f}"))

scen("6", "Trip both Sual units (2x647 MW coal, Luzon)", STRESS,
     {"fuel_avail_delta": {"luzon": {"coal": -1294}}},
     lambda b, s: (
         "PASS" if delta(b, s, "luzon_peak_price") > 0.001
         or delta(b, s, "luzon_shed_mwh") > 0.1 else "CHECK",
         f"Luzon peak {delta(b,s,'luzon_peak_price'):+.3f}, "
         f"shed {b['luzon_shed_mwh']}->{s['luzon_shed_mwh']} MWh"))

scen("7", "Dry year (hydro x0.344) + DICT 1.5 GW wave, Luzon", STRESS,
     {"hydrology": 0.344, "demand_delta": {"luzon": 1500}},
     lambda b, s: (
         "PASS" if delta(b, s, "luzon_peak_price") > 0.001
         or delta(b, s, "luzon_shed_mwh") > 0.1 else "CHECK",
         f"Luzon peak {delta(b,s,'luzon_peak_price'):+.3f}, "
         f"shed {b['luzon_shed_mwh']}->{s['luzon_shed_mwh']} MWh, "
         f"hydro MWh {b['fuel_mwh'].get('hydro',0)}->{s['fuel_mwh'].get('hydro',0)}"))


def main():
    print(f"engine: run_chronology_lp | typical={TYPICAL} stress={STRESS}\n")
    results = {}
    for id, title, day, opts, check in SCENARIOS:
        base = summ(run(day))
        scenr = summ(run(day, opts))
        verdict, note = check(base, scenr)
        results[id] = {"title": title, "day": day, "opts": opts,
                       "verdict": verdict, "note": note,
                       "base": base, "scen": scenr}
        print(f"[{verdict}] {id}  {title}")
        print(f"        {note}")
    if "--json" in sys.argv:
        json.dump(results, open(os.path.join(ROOT, "tmp",
                  "scenario-validation-results.json"), "w"), indent=1)
    npass = sum(1 for r in results.values() if r["verdict"] == "PASS")
    print(f"\n{npass}/{len(results)} reproduced the analyst prior")


if __name__ == "__main__":
    main()
