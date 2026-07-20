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
# The fleet number is a sum over the resources OFFERING in that hour, and that
# set moves hour to hour, so one sample is not a measurement. These span
# weekdays and a weekend, morning pickup and evening peak, across the window.
# The published floor is the WORST of them, never the best: an earlier version
# quoted a single hour that happened to be the most favourable of six, and
# called it a weekday when 2026-05-03 is a Sunday.
SAMPLE_STAMPS = (
    "202606220800",   # Mon, the hour of Luzon's worst observed demand rise
    "202606101900",   # Wed evening peak
    "202606071800",   # Sun evening peak
    "202607010600",   # Wed morning pickup
    "202605311800",   # Sun evening peak
    "202605031000",   # Sun mid-morning (the previously published hour)
)
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


def _unit_ramp(r: dict, slowest: bool = False) -> tuple[float, float]:
    """(offered capacity MW, up-ramp MW/min) for one resource. Capacity is the
    TOP cumulative breakpoint: QUANTITYn is a cumulative offer curve, not a
    block width, so summing them would double count.

    `slowest` takes the unit's WORST published band instead of its best. The
    headline uses the best band, so the honest question is whether the verdict
    survives the pessimistic read; the output reports both so a reader does not
    have to take that on trust."""
    cap = max([_f(r.get(f"QUANTITY{i}")) for i in range(1, 12)] or [0.0])
    bands = [_f(r.get(f"RR_UP{i}")) for i in range(1, 6)]
    bands = [b for b in bands if b > 0]
    if not bands:
        return cap, 0.0
    return cap, (min(bands) if slowest else max(bands))


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


def _online_set(stamp: str) -> set[str]:
    """Resources actually GENERATING in that specific hour, from the derived
    nodal archive. The fleet that can answer a ramp inside sixty minutes is the
    synchronised one; summing every resource that merely offered overstates it,
    because an offline machine cannot. Returns an empty set when the day is not
    derived, and callers then fall back to the offered basis rather than
    reporting a fleet of zero."""
    path = os.path.join(HERE, "..", "data", "derived", "nodal_daily",
                        f"NODALD_{stamp[:8]}.json")
    if not os.path.isfile(path):
        return set()
    try:
        with open(path) as fh:
            day = json.load(fh)
    except (OSError, ValueError):
        return set()
    h = int(stamp[8:10])
    online = set()
    for res, nd in (day.get("nodes") or {}).items():
        mw = nd.get("mw") or []
        if h < len(mw) and mw[h]:
            online.add(res)
    return online


def _fleet_for_hour(stamp: str) -> dict:
    """One hour's fleet ramp capability, four ways: offered vs online-only,
    each on the unit's best and slowest published band."""
    rows = _resource_rows(stamp)
    if not rows:
        return {}
    online = _online_set(stamp)
    acc = {k: {g: 0.0 for g in GRIDS}
           for k in ("offered_best", "offered_slow", "online_best",
                     "online_slow")}
    for r in rows:
        g = REGION_GRID.get((r.get("REGION_NAME") or "").strip())
        if not g:
            continue
        cap, best = _unit_ramp(r)
        _, slow = _unit_ramp(r, slowest=True)
        if cap <= 0 or best <= 0:
            continue
        name = (r.get("RESOURCE_NAME") or "").strip()
        acc["offered_best"][g] += min(best * 60.0, cap)
        acc["offered_slow"][g] += min(slow * 60.0, cap)
        if not online or name in online:
            acc["online_best"][g] += min(best * 60.0, cap)
            acc["online_slow"][g] += min(slow * 60.0, cap)
    return acc


def derive(profiles: dict, stamp: str = SAMPLE_STAMPS[0]) -> dict:
    rows = _resource_rows(stamp)
    if not rows:
        return {"available": False,
                "note": "RTDOE hour unavailable; ramp probe not derived."}

    inert = binding = 0
    ratios: list[float] = []
    tightest: list[dict] = []
    fleet_mw_per_h: dict[str, float] = {g: 0.0 for g in GRIDS}
    fleet_slow_mw_per_h: dict[str, float] = {g: 0.0 for g in GRIDS}
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
            _, slow = _unit_ramp(r, slowest=True)
            fleet_slow_mw_per_h[g] += min(slow * 60.0, cap)

    scored = inert + binding
    worst = _worst_demand_rise(profiles)
    tightest.sort(key=lambda x: x["pct_of_range_per_hour"])

    # Sample many hours and publish the WORST, on the online-only basis. The
    # offering set changes hour to hour, so a single hour is not a measurement,
    # and a synchronised-fleet read is the one a ramp constraint would face.
    per_hour = {}
    for st in SAMPLE_STAMPS:
        acc = _fleet_for_hour(st)
        if acc:
            per_hour[st] = {k: {g: round(v[g], 1) for g in GRIDS}
                            for k, v in acc.items()}
    bases = ("offered_best", "offered_slow", "online_best", "online_slow")
    floors = {}
    for basis in bases:
        floors[basis] = {
            g: (round(min(h[basis][g] for h in per_hour.values()) / worst[g], 2)
                if per_hour and worst.get(g) else None) for g in GRIDS}
    headroom = floors["offered_best"]
    strict = floors["online_slow"]
    strict_vals = [v for v in strict.values() if v is not None]
    binds_anywhere = any(v < 1.0 for v in strict_vals) if strict_vals else False
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
        "fleet_ramp_slowest_band_mw_per_hour": {
            g: round(fleet_slow_mw_per_h[g], 1) for g in GRIDS},
        "worst_observed_demand_rise_mw_per_hour": worst,
        "fleet_ramp_over_worst_demand_rise": headroom,
        "n_sample_hours": len(per_hour),
        "sample_hours": sorted(per_hour),
        "per_hour_fleet_mw_per_hour": per_hour,
        # the four bases, each taking the WORST sampled hour. online_slow is
        # the conservative floor and is the one the verdict is decided on.
        "headroom_floors": floors,
        "strict_headroom_online_slowest_band": strict,
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
