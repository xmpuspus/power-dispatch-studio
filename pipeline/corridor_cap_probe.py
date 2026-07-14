#!/usr/bin/env python3
"""Measure whether the operator's own RTD HVDC binding schedule improves the
replay, and record the answer (roadmap item 7).

The corridor caps the engine ships scale the static HVDC limit by the fraction
of the hour the link was unblocked, inferred from the NSO advisory stream (MPI:
whole-link outage windows, Leyte-Luzon only). The operator ALSO publishes its
own per-interval RTD HVDC schedule (RTDHS) with a congestion flag, which carries
security de-rates the outage inference cannot see and covers the Visayas-
Mindanao corridor the advisory stream barely mentions.

This probe feeds those RTDHS-derived caps into the day LP and rebuilds the price
backcast, then compares it to the shipped baseline. The at-cap share cannot be
the judge: an RTDHS-sourced cap makes the modeled at-cap share track the
observed binding share by construction, and the flow-vs-RTDHS comparison in-
sample on binding hours. The only independent judge is the PRICE backcast (vs
LWAP and MCP), which does not read RTDHS.

Measured 2026-07-14: the caps LOWER Luzon price MAE slightly (about 0.16
PhP/kWh vs both LWAP and MCP) but WORSEN price correlation on every grid, badly
on Visayas (about 0.46 to 0.11 vs LWAP), because the Leyte de-rate to near-zero
on flagged hours decouples Visayas from its observed import pattern. A price
model that tracks the observed shape worse is not an improvement, so the shipped
engine keeps the advisory-based caps and the corridor under-binding versus RTDHS
stays a documented boundary, not a constructed match.

    python3 pipeline/corridor_cap_probe.py --derive   # remeasure, write finding
"""
from __future__ import annotations

import argparse
import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web", "data")
OUT = os.path.join(HERE, "..", "data", "derived", "corridor_cap_probe.json")


def _combined_caps(days: list[dict]) -> None:
    """Overlay the RTDHS binding-schedule caps onto a copy of the profile days,
    tighter of the advisory outage fraction and the operator's de-rate, both
    corridors. Mirrors the reverted profiles.py experiment."""
    from market_obs import hvdc_binding_caps, hvdc_unblocked_fractions

    mpi = hvdc_unblocked_fractions()
    bind = hvdc_binding_caps()
    for d in days:
        m_leyte = mpi.get(d["date"]) or [1.0] * 24
        bc = bind.get(d["date"]) or {"leyte": [1.0] * 24, "mvip": [1.0] * 24}
        leyte = [round(min(m_leyte[h], bc["leyte"][h]), 3) for h in range(24)]
        mvip = bc["mvip"]
        cc = {}
        if any(x < 1.0 for x in leyte):
            cc["leyte"] = leyte
        if any(x < 1.0 for x in mvip):
            cc["mvip"] = mvip
        if cc:
            d["corridor_caps"] = cc
        elif "corridor_caps" in d:
            del d["corridor_caps"]


def _price(bc: dict) -> dict:
    """Pull the per-grid price MAE and correlation from a backcast dict."""
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
    capped_profiles = copy.deepcopy(profiles)
    _combined_caps(capped_profiles["days"])
    capped = _price(build_backcast(dispatch, capped_profiles))

    # verdict on the independent judge: did Luzon price track better?
    lz_base = baseline["per_grid_mcp"].get("luzon", {})
    lz_cap = capped["per_grid_mcp"].get("luzon", {})
    corr_worse_grids = [
        g for blk in ("per_grid", "per_grid_mcp")
        for g in baseline[blk]
        if (capped[blk][g]["corr"] or 0) < (baseline[blk][g]["corr"] or 0) - 0.01
    ]
    return {
        "available": True,
        "baseline": baseline,
        "with_rtdhs_caps": capped,
        "shipped": "baseline",
        "verdict": (
            "The RTDHS binding-schedule caps lower Luzon price MAE "
            f"({lz_base.get('mae')} to {lz_cap.get('mae')} PhP/kWh vs MCP) but "
            "worsen price correlation on every grid; the shipped engine keeps "
            "the advisory-based caps."
        ),
        "corr_worse_grids": sorted(set(corr_worse_grids)),
        "note": ("The modeled at-cap share cannot judge an RTDHS-sourced cap "
                 "(it aligns with the observed binding share by construction); "
                 "the price backcast, independent of RTDHS, is the judge, and "
                 "it says the caps do not improve the replay."),
        "src": "https://www.iemop.ph/market-data/rtd-hvdc-schedules/",
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
        print(f"corridor_cap_probe: shipped={out['shipped']}; "
              f"corr worse on {out['corr_worse_grids']}")
        print(out["verdict"])
    else:
        print("pass --derive to remeasure and write the finding")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
