#!/usr/bin/env python3
"""How many megawatts the Concepcion bus can take, hour by hour.

The DC power flow is linear in injection, so each hour needs exactly two
replay solves: one at zero added draw for the base flows, one at a probe draw
for the sensitivity. The headroom is then where the worst circuit on the site
bus reaches its rating, solved rather than swept.

Linearity is not assumed, it is checked: a third solve at the computed
headroom must land the worst circuit on 1.0 of rating.

Writes hourly_headroom.json for the figure. Read-only otherwise.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from nodal_dcopf import (  # noqa: E402
    SITES,
    _load_day,
    _plant_load,
    build_network,
    hour_injections,
    map_resources,
    resolve_site,
    solve_hour,
)

DAY = "2026-06-25"
PROBE = 1000.0

net = build_network()
day = _load_day(DAY)
res_bus, _ = map_resources(day, net)
pax = SITES["pax-silica"]
site = resolve_site(net, pax["lon"], pax["lat"])
bus = site["bus"]
branches = net["branches"]
local = [bi for bi, br in enumerate(branches) if br["a"] == bus or br["b"] == bus]


def worst_ratio(sol):
    return max(abs(sol["flows_mw"][bi]) / branches[bi]["rating_mw"] for bi in local)


rows = []
for hr in range(24):
    inj = hour_injections(day, res_bus, net, hr)
    s0 = solve_hour(net, _plant_load(inj, net, bus, 0.0), "replay")
    s1 = solve_hour(net, _plant_load(inj, net, bus, PROBE), "replay")
    if s0 is None or s1 is None:
        rows.append(None)
        continue
    best = None
    for bi in local:
        f0, f1 = s0["flows_mw"][bi], s1["flows_mw"][bi]
        rating = branches[bi]["rating_mw"]
        slope = (f1 - f0) / PROBE
        if abs(slope) < 1e-9:
            continue
        for target in (rating, -rating):
            d = (target - f0) / slope
            if d > 0 and (best is None or d < best):
                best = d
    # linearity check: solving at the computed headroom must sit on the rating
    chk = solve_hour(net, _plant_load(inj, net, bus, float(best)), "replay")
    rows.append({
        "hour": hr,
        "headroom_mw": round(best, 1),
        "base_ratio": round(worst_ratio(s0), 3),
        "check_ratio_at_headroom": round(worst_ratio(chk), 3) if chk else None,
    })
    print(f"h{hr:02d} headroom {best:8.1f} MW   base {worst_ratio(s0):.3f} of rating"
          f"   check at headroom {worst_ratio(chk):.3f}")

good = [r for r in rows if r and r["check_ratio_at_headroom"] is not None]
err = max(abs(r["check_ratio_at_headroom"] - 1.0) for r in good)
print(f"\nlinearity check: worst deviation from 1.0 of rating = {err:.4f}")
hs = [r["headroom_mw"] for r in good]
print(f"headroom across the day: {min(hs):,.0f} to {max(hs):,.0f} MW")

json.dump(
    {
        "day": DAY,
        "bus": bus,
        "snap_km": site["snap_km"],
        "circuits": [
            {"names": branches[bi]["names"] or [branches[bi]["kind"]],
             "rating_mw": branches[bi]["rating_mw"],
             "rating_src": branches[bi].get("rating_src"),
             "km": branches[bi]["km"]}
            for bi in local
        ],
        "hours": rows,
        "linearity_max_error": round(err, 4),
    },
    open(os.path.join(ROOT, "tmp", "pax_silica_headroom.json"), "w"),
    indent=1,
)
print("wrote tmp/pax_silica_headroom.json")
