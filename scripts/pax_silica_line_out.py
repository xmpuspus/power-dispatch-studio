#!/usr/bin/env python3
"""What the site can take when one of its two lines is out.

The chart so far only tests a generator failing. A transmission planner tests
the wires too, and the site is fed by exactly two circuits, so losing one is the
obvious case. This removes each of them in turn and re-solves the limit at the
evening peak, the same way the intact limit was found.

Read-only.
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
HOUR = 19
PROBE = 1000.0


def limit_at(net, inj, bus, local):
    """Where the worst remaining circuit on the bus reaches its rating."""
    s0 = solve_hour(net, _plant_load(inj, net, bus, 0.0), "replay")
    s1 = solve_hour(net, _plant_load(inj, net, bus, PROBE), "replay")
    if s0 is None or s1 is None:
        return None
    best = None
    for bi in local:
        f0, f1 = s0["flows_mw"][bi], s1["flows_mw"][bi]
        slope = (f1 - f0) / PROBE
        if abs(slope) < 1e-9:
            continue
        for target in (net["branches"][bi]["rating_mw"],
                       -net["branches"][bi]["rating_mw"]):
            d = (target - f0) / slope
            if d > 0 and (best is None or d < best):
                best = d
    return best


net = build_network()
day = _load_day(DAY)
res_bus, _ = map_resources(day, net)
pax = SITES["pax-silica"]
site = resolve_site(net, pax["lon"], pax["lat"])
bus = site["bus"]
inj = hour_injections(day, res_bus, net, HOUR)

all_branches = list(net["branches"])
local = [bi for bi, b in enumerate(all_branches) if b["a"] == bus or b["b"] == bus]
print(f"site bus {bus}, {len(local)} circuits on it, hour {HOUR} of {DAY}")
for bi in local:
    br = all_branches[bi]
    print(f"  {br['names'] or [br['kind']]}  {br['km']} km  "
          f"rating {br['rating_mw']} MW")

intact = limit_at(net, inj, bus, local)
print(f"\nboth circuits in service: {intact:,.0f} MW")

results = {"day": DAY, "hour": HOUR, "bus": bus, "intact_mw": round(intact, 1),
           "outages": []}
for drop in local:
    kept = [b for i, b in enumerate(all_branches) if i != drop]
    net["branches"] = kept
    local2 = [i for i, b in enumerate(kept) if b["a"] == bus or b["b"] == bus]
    if not local2:
        print(f"\ndropping {all_branches[drop]['km']} km circuit: bus is cut off")
        results["outages"].append({"dropped_km": all_branches[drop]["km"],
                                   "limit_mw": 0.0, "isolated": True})
        net["branches"] = all_branches
        continue
    # is the site bus still joined to the rest of its island at all?
    adj = {}
    for b in kept:
        adj.setdefault(b["a"], set()).add(b["b"])
        adj.setdefault(b["b"], set()).add(b["a"])
    seen, stack = {bus}, [bus]
    while stack:
        for nxt in adj.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    island = {b["id"] for b in net["buses"] if b["grid"] == site["grid"]}
    cut_off = len(seen & island) < len(island)

    out = limit_at(net, inj, bus, local2)
    name = all_branches[drop]["names"] or [all_branches[drop]["kind"]]
    print(f"\ndropping the {all_branches[drop]['km']} km circuit {name}:")
    if out is None:
        # two different reasons the solve can fail, and they mean opposite
        # things. If the bus can still reach most of its island the site is
        # fine and the failure is bookkeeping, a small pocket losing its
        # reference bus. If it reaches almost nothing, the site really is cut
        # off from the grid.
        reach = len(seen & island)
        stranded = reach < len(island) / 2
        print(f"  no solution. The bus still reaches {reach} of "
              f"{len(island)} buses on its island.")
        print("  " + ("The site is cut off from the grid by this outage."
                      if stranded else
                      "The site stays connected, so this is a limitation of "
                      "the model rather than a finding about the site."))
        results["outages"].append({"dropped_km": all_branches[drop]["km"],
                                   "limit_mw": 0.0 if stranded else None,
                                   "site_cut_off": stranded,
                                   "reachable_buses": reach,
                                   "model_limitation": not stranded})
    else:
        print(f"  limit falls {intact:,.0f} -> {out:,.0f} MW "
              f"({100 * out / intact:.0f}% of intact), cut off: {cut_off}")
        results["outages"].append({"dropped_km": all_branches[drop]["km"],
                                   "limit_mw": round(out, 1),
                                   "isolated": bool(cut_off)})
    net["branches"] = all_branches

cut = [o for o in results["outages"] if o.get("site_cut_off")]
results["radially_fed"] = bool(cut)
print(f"\ncircuits whose loss cuts the site off from the grid: "
      f"{len(cut)} of {len(results['outages'])}")
if cut:
    print("In the mapped network the site is fed radially. The two circuits are")
    print("two segments of one route, not two independent paths, so there is no")
    print("second way in. Whether the real network has one is not something the")
    print("public map can answer.")
    print("The self-build plan still draws 500 MW at this hour, and that 500 MW")
    print("has no route during such an outage.")
json.dump(results, open(os.path.join(ROOT, "tmp", "pax_silica_line_out.json"), "w"), indent=1)
