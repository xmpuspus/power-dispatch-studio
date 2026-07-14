#!/usr/bin/env python3
"""Measure whether replaying each day's OWN observed solar energy improves the
backcast, and record the answer (roadmap item 8).

The shipped model credits solar as a flat clear-sky 24-hour shape times an
installed capacity. The archive carries each day's actual WESM-dispatched solar
energy per grid (DIPCEF dailies), so the replay could instead scale the shape to
reproduce the observed daily energy. This probe runs the backcast both ways and
compares the price error, the independent judge.

Measured 2026-07-14: it does not help. The observed energy scaled onto the flat
shape COLLAPSES the Luzon price correlation (about 0.36 to 0.07 vs both LWAP and
MCP) while barely moving MAE, because Luzon's observed solar runs about 1.75x
the clear-sky credit and the flat shape dumps that extra energy into midday,
crushing modeled daytime prices below what actually cleared. The gap is the
missing observed hourly SHAPE, which DIPCEF's daily energy cannot supply. So the
shipped backcast keeps the clear-sky credit; the per-day solar stays a reported
observation (market_ops.json solar_wind_observed), not a replay input.

    python3 pipeline/vre_probe.py --derive   # remeasure, write finding
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web", "data")
OUT = os.path.join(HERE, "..", "data", "derived", "vre_probe.json")


def _price(bc: dict) -> dict:
    out = {}
    for blk in ("per_grid", "per_grid_mcp"):
        out[blk] = {
            g: {"mae": v.get("mae_php_kwh"), "corr": v.get("correlation")}
            for g, v in (bc.get(blk) or {}).items()
            if isinstance(v, dict) and "mae_php_kwh" in v
        }
    return out


def derive() -> dict:
    from chrono import build_backcast

    dispatch = json.load(open(os.path.join(WEB, "dispatch.json")))
    profiles = json.load(open(os.path.join(WEB, "profiles.json")))

    baseline = _price(build_backcast(dispatch, profiles))
    withsolar = _price(build_backcast(dispatch, profiles, observed_solar=True))

    corr_worse = [
        g for blk in ("per_grid", "per_grid_mcp")
        for g in baseline[blk]
        if (withsolar[blk][g]["corr"] or 0) < (baseline[blk][g]["corr"] or 0) - 0.02
    ]
    lz = baseline["per_grid_mcp"].get("luzon", {})
    lz2 = withsolar["per_grid_mcp"].get("luzon", {})
    return {
        "available": True,
        "baseline": baseline,
        "with_observed_solar": withsolar,
        "shipped": "baseline",
        "verdict": (
            "Replaying each day's observed DIPCEF solar energy on the flat "
            f"clear-sky shape collapses the Luzon price correlation "
            f"({lz.get('corr')} to {lz2.get('corr')} vs MCP) while barely "
            "moving MAE; the shipped backcast keeps the clear-sky credit."
        ),
        "corr_worse_grids": sorted(set(corr_worse)),
        "note": ("The observed DAILY energy without the observed hourly shape "
                 "cannot be a replay input: dumping it onto the flat midday "
                 "shape crushes daytime prices below what cleared. The missing "
                 "piece is a per-resource hourly solar series."),
        "src": "https://www.iemop.ph/market-data/dipc-energy-results-final/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"vre_probe: shipped={out['shipped']}; "
              f"corr worse on {out['corr_worse_grids']}")
        print(out["verdict"])
    else:
        print("pass --derive to remeasure and write the finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
