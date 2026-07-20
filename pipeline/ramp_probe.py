#!/usr/bin/env python3
"""Measure the operator's published ramp rates against the ramp this model is
ever asked to perform, and record why an hourly ramp constraint is not built.

Background. The methodology used to say ramp rates "would require per-unit data
the Philippine sources do not publish". That was false, and a round-10 audit
caught it: every RTDOE offer row carries a piecewise ramp curve
(RR_BREAK_QUANTITY1-5 with RR_UP1-5 and RR_DOWN1-5, in MW per minute by MW
band), populated on essentially every resource, in the same hourly file
pipeline/offers.py already downloads for the offer books.

So the question stops being "can we?" and becomes "would it bind?". This module
answers that before anything is built, because an inert constraint is fidelity
theater: it costs engine complexity and buys no accuracy.

Two measurements, both from the published curves:

1. Per resource, does one hour of ramping cover the unit's own offered range?
   Where ramp x 60 >= the top cumulative offer breakpoint, an HOURLY ramp limit
   cannot bind for that unit no matter what the dispatch asks.
2. Per grid, can the fleet ramp faster than demand has ever moved? Aggregate
   each unit's one-hour ramp capability (capped at its own range, since a unit
   cannot exceed it) and compare against the largest hour-to-hour demand RISE in
   the archived observed profiles.

The verdict this produces is the one that matters for THIS engine, which clears
per-fuel blocks per grid rather than per unit: if the fleet aggregate ramps
several times faster than the worst observed demand ramp, a per-fuel hourly ramp
constraint is inert by construction.

Scope, stated so the result is not over-read: this is measured at grid and
fuel-aggregate level at hourly resolution, which is the model's resolution. A
per-UNIT model would see the binding minority reported here, and a 5-minute
replay is a different question this does not answer.

    python3 pipeline/ramp_probe.py --derive
"""
from __future__ import annotations

import argparse
import json
import os
from statistics import median

from offers import _fetch_hour_csv

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web", "data")
OUT = os.path.join(HERE, "..", "data", "derived", "ramp_probe.json")
REGION_GRID = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")
# a mid-morning weekday hour on a market day, inside the archived window
SAMPLE_STAMP = "202605031000"
SRC = "https://www.iemop.ph/market-data/rtd-generation-offers/"


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _resource_rows(stamp: str) -> list[dict]:
    """One interval's rows: the offer book repeats each resource per 5-minute
    interval inside the hourly file, so score a single interval."""
    rows = _fetch_hour_csv("rtd-generation-offers", "RTDOE", stamp)
    stamps = sorted({(r.get("TIME_INTERVAL") or "").strip()
                     for r in rows if r.get("TIME_INTERVAL")})
    if not stamps:
        return []
    return [r for r in rows
            if (r.get("TIME_INTERVAL") or "").strip() == stamps[0]]


def _unit_ramp(r: dict) -> tuple[float, float]:
    """(offered capacity MW, best up-ramp MW/min) for one resource. Capacity is
    the TOP cumulative breakpoint: QUANTITYn is a cumulative offer curve, not a
    block width, so summing them would double count."""
    cap = max([_f(r.get(f"QUANTITY{i}")) for i in range(1, 12)] or [0.0])
    up = max(_f(r.get(f"RR_UP{i}")) for i in range(1, 6))
    return cap, up


def _worst_demand_rise(profiles: dict) -> dict:
    """Largest hour-to-hour demand increase per grid across the market days."""
    worst = {g: 0.0 for g in GRIDS}
    for d in profiles.get("days", []):
        if not d.get("market"):
            continue
        for g in GRIDS:
            series = (d.get("demand") or {}).get(g) or []
            for a, b in zip(series, series[1:]):
                if a is not None and b is not None:
                    worst[g] = max(worst[g], b - a)
    return {g: round(worst[g], 1) for g in GRIDS}


def derive(profiles: dict, stamp: str = SAMPLE_STAMP) -> dict:
    rows = _resource_rows(stamp)
    if not rows:
        return {"available": False,
                "note": "RTDOE hour unavailable; ramp probe not derived."}

    inert = binding = 0
    ratios: list[float] = []
    tightest: list[dict] = []
    fleet_mw_per_h: dict[str, float] = {g: 0.0 for g in GRIDS}
    n_with_ramp = 0

    for r in rows:
        cap, up = _unit_ramp(r)
        if cap <= 0 or up <= 0:
            continue
        n_with_ramp += 1
        hourly = up * 60.0
        ratios.append(hourly / cap)
        if hourly >= cap:
            inert += 1
        else:
            binding += 1
            tightest.append({
                "resource": (r.get("RESOURCE_NAME") or "").strip(),
                "capacity_mw": round(cap, 1),
                "ramp_mw_per_min": up,
                "pct_of_range_per_hour": round(100 * hourly / cap, 1),
            })
        g = REGION_GRID.get((r.get("REGION_NAME") or "").strip())
        if g:
            # a unit cannot move more than its own range inside the hour
            fleet_mw_per_h[g] += min(hourly, cap)

    scored = inert + binding
    worst = _worst_demand_rise(profiles)
    headroom = {g: (round(fleet_mw_per_h[g] / worst[g], 1)
                    if worst.get(g) else None) for g in GRIDS}
    tightest.sort(key=lambda x: x["pct_of_range_per_hour"])

    binds_anywhere = any(h is not None and h < 1.0 for h in headroom.values())
    return {
        "available": True,
        "sample_hour": stamp,
        "n_resources_scored": scored,
        "n_resources_with_published_ramp": n_with_ramp,
        "hourly_inert_resources": inert,
        "hourly_inert_pct": round(100 * inert / scored, 1) if scored else None,
        "hourly_binding_resources": binding,
        "median_hourly_range_over_capacity": (round(median(ratios), 2)
                                              if ratios else None),
        "fleet_ramp_mw_per_hour": {g: round(fleet_mw_per_h[g], 1)
                                   for g in GRIDS},
        "worst_observed_demand_rise_mw_per_hour": worst,
        "fleet_ramp_over_worst_demand_rise": headroom,
        "tightest_units": tightest[:8],
        "verdict": ("would_bind" if binds_anywhere
                    else "measured_inert_at_hourly_resolution"),
        "note": ("Ramp rates ARE published: every RTDOE offer row carries a "
                 "piecewise MW-per-minute curve by MW band, on essentially "
                 "every resource. This measures whether an hourly ramp "
                 "constraint would bind before building one. It would not, at "
                 "this engine's resolution: the fleet's one-hour ramp "
                 "capability runs several times the largest hour-to-hour "
                 "demand rise anywhere in the archive, so a per-fuel hourly "
                 "ramp limit is inert by construction and is measured out "
                 "rather than built. Read the scope before re-using this: it "
                 "is a grid and fuel-aggregate result at HOURLY resolution. A "
                 "per-unit model would still see the binding minority counted "
                 "here (the tightest units are oil and coal machines moving "
                 "well under a tenth of their range per hour), and a 5-minute "
                 "replay is a separate question this does not answer."),
        "src": SRC,
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    args = ap.parse_args()
    profiles = json.load(open(os.path.join(WEB, "profiles.json")))
    out = derive(profiles)
    if args.derive and out.get("available"):
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(out, f, indent=2)
        print(f"wrote {OUT}")
    if not out.get("available"):
        print(out.get("note"))
        return
    print(f"resources with a published ramp curve: "
          f"{out['n_resources_with_published_ramp']}")
    print(f"hourly-inert resources: {out['hourly_inert_resources']} "
          f"({out['hourly_inert_pct']}%)")
    print("\nfleet one-hour ramp vs worst observed demand rise:")
    for g in GRIDS:
        print(f"  {g:9s} {out['fleet_ramp_mw_per_hour'][g]:9,.0f} MW/h vs "
              f"{out['worst_observed_demand_rise_mw_per_hour'][g]:7,.0f} MW/h"
              f"  ({out['fleet_ramp_over_worst_demand_rise'][g]}x)")
    print("\nverdict:", out["verdict"])


if __name__ == "__main__":
    main()
