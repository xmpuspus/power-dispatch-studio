#!/usr/bin/env python3
"""Mark one worked contract book against a Sual trip, for the README and the map.

The README carries a worked position case, and every figure in it moves with the
archive window: the day rolls, the spot price moves, and the peso figures move
with it. So the case derives here rather than sitting hand-typed, and
scripts/verify_claims.py rewrites the prose from this file every night.

Both runs carry the existing storage fleet, because the studio's object model
does and a published figure has to be one a reader can reproduce in the browser.

The book is deliberately plain and stated in full: a 250 MW power supply
agreement struck at P6.40/kWh across the day, a 100 MW block struck at
P9.00/kWh over the evening peak, and a declared Luzon load of 400 MW. The
scenario is both 647 MW Sual units out, which is the contingency the rest of the
project already uses.

    python3 pipeline/position_probe.py --derive
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "derived", "position_probe.json")
sys.path.insert(0, os.path.join(ROOT, "src"))

import power_dispatch as pdx  # noqa: E402

# both units of the largest coal plant, the same contingency the N-1 view uses
SUAL_BOTH_MW = 1294
BOOK = [
    {
        "name": "Power supply agreement",
        "grid": "luzon",
        "mw": 250,
        "strike_php_kwh": 6.4,
        "side": "buy",
    },
    {
        "name": "Evening peak block",
        "grid": "luzon",
        "mw": 100,
        "strike_php_kwh": 9.0,
        "side": "buy",
        "hours": [18, 19, 20, 21],
    },
]
LOAD_MW = {"luzon": 400}


def derive(data_dir: str | None = None) -> dict:
    day = pdx.list_days(data_dir)[-1]
    # The studio carries the existing storage fleet in every run, because its
    # object model holds those rows. A probe that leaves them out publishes a
    # number the browser will not reproduce: without them the evening peak
    # prices at P12.00 instead of P7.50, and the position moves by more.
    _, profiles = pdx.load_data(data_dir)
    storage = [
        {"grid": s["grid"], "power_mw": s["power_mw"], "energy_mwh": s["energy_mwh"]}
        for s in profiles.get("storage_defaults") or []
    ]
    base = pdx.run_scenario(
        {"date": day, "opts": {"storage": storage}}, data_dir=data_dir
    )
    trip = pdx.run_scenario(
        {
            "date": day,
            "opts": {
                "storage": storage,
                "fuel_avail_delta": {"luzon": {"coal": -SUAL_BOTH_MW}},
            },
        },
        data_dir=data_dir,
    )
    cmp = pdx.compare_position(base, trip, BOOK, LOAD_MW)
    return {
        "generated_by": "pipeline/position_probe.py",
        "date": day,
        "scenario": f"both Sual units out, {SUAL_BOTH_MW} MW of Luzon coal",
        "storage_mw": sum(s["power_mw"] for s in storage),
        "storage_note": (
            "the existing storage fleet is in both runs, the same way the "
            "studio carries it, so the browser reproduces these figures"
        ),
        "book": BOOK,
        "load_mw": LOAD_MW,
        "contracted_mw": sum(c["mw"] for c in BOOK if not c.get("hours")),
        "book_mw": sum(c["mw"] for c in BOOK),
        "covered_share_pct": cmp["base"]["open"][0]["covered_share_pct"],
        "base_mean_spot_php_kwh": cmp["contracts"][0]["base_mean_spot"],
        "scenario_mean_spot_php_kwh": cmp["contracts"][0]["scenario_mean_spot"],
        "position_change_php": cmp["position_change_php"],
        "open_cost_change_php": cmp["open_cost_change_php"],
        "net_change_php": cmp["net_change_php"],
        "note": cmp["note"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true", help="remeasure and write")
    args = ap.parse_args()
    out = derive()
    print(f"{out['date']}: {out['scenario']}")
    print(f"  cover {out['covered_share_pct']}%")
    print(
        f"  mean Luzon spot P{out['base_mean_spot_php_kwh']} -> "
        f"P{out['scenario_mean_spot_php_kwh']}"
    )
    print(f"  contracts   {out['position_change_php']:+,.0f}")
    print(f"  open load   {out['open_cost_change_php']:+,.0f}")
    print(f"  net         {out['net_change_php']:+,.0f}")
    if args.derive:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
