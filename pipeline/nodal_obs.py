#!/usr/bin/env python3
"""Observed per-node price deviations, compacted for the map and the studio.

Reads the derived nodal dailies (data/derived/nodal_daily/, DIPCEF final
results compacted per day) and reduces them to one question an analyst can
read off a map: which WESM nodes persistently price above or below their
regional SMP, and by how much.

Semantics, stated on every surface that shows this:
  - the statistic is the mean over CLEAN days (at least 90 percent of the
    day's rows OK-flagged; administered PSM/SEC days are excluded and
    counted) of the node's daily mean deviation from its regional SMP.
  - WESM publishes no nodal congestion component (zero on every sampled
    day), so the deviation is formally loss-dominated and intra-regional
    congestion is handled administratively. The honest name is "persistent
    locational price deviation", never "congestion premium".
  - a node makes the table when it has data on at least 80 percent of the
    clean days.
  - map placement reuses the station-token matcher (nodal_dcopf.map_resources):
    only nodes whose station resolves onto the OSM-mapped grid get
    coordinates, and the artifact reports that count against the total.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
NODAL_DIR = os.path.join(HERE, "..", "data", "derived", "nodal_daily")

CLEAN_OK_SHARE = 0.9
PRESENCE_SHARE = 0.8


def build_nodal_obs() -> dict:
    days = sorted(os.listdir(NODAL_DIR)) if os.path.isdir(NODAL_DIR) else []
    days = [d for d in days if d.startswith("NODALD_")]
    if not days:
        return {
            "available": False,
            "note": "no nodal dailies derived yet (pipeline/nodal_prices.py --derive)",
        }
    node_dev: dict[str, list[float]] = defaultdict(list)
    node_mw: dict[str, list[float]] = defaultdict(list)
    node_grid: dict[str, str] = {}
    clean_days = []
    for name in days:
        with open(os.path.join(NODAL_DIR, name)) as f:
            d = json.load(f)
        flags = d.get("pricing_flags", {})
        tot = sum(sum(v.values()) for v in flags.values())
        ok = sum(v.get("OK", 0) for v in flags.values())
        if not tot or ok / tot < CLEAN_OK_SHARE:
            continue
        clean_days.append(d["date"])
        for res, nd in d["nodes"].items():
            devs = [v for v in nd["dev_php_kwh"] if v is not None]
            if not devs:
                continue
            node_dev[res].append(sum(devs) / len(devs))
            mws = [abs(v) for v in nd["mw"] if v]
            node_mw[res].append(sum(mws) / len(mws) if mws else 0.0)
            node_grid[res] = nd["grid"]

    need = max(1, int(PRESENCE_SHARE * len(clean_days)))
    nodes = []
    for res, vs in node_dev.items():
        if len(vs) < need:
            continue
        nodes.append(
            {
                "res": res,
                "grid": node_grid[res],
                "dev": round(mean(vs), 3),
                "days": len(vs),
                "mw": round(mean(node_mw[res]), 1),
            }
        )
    nodes.sort(key=lambda n: n["dev"])

    per_grid = {}
    for g in ("luzon", "visayas", "mindanao"):
        sub = [n for n in nodes if n["grid"] == g]
        if not sub:
            continue
        vs = [n["dev"] for n in sub]
        per_grid[g] = {
            "n_nodes": len(sub),
            "p5": round(vs[int(0.05 * len(vs))], 2),
            "p50": round(vs[len(vs) // 2], 2),
            "p95": round(vs[int(0.95 * len(vs))], 2),
            "top": sorted(sub, key=lambda n: -n["dev"])[:8],
            "bottom": sub[:8],
        }

    # place what the station matcher can place on the OSM grid
    from nodal_dcopf import build_network, map_resources

    net = build_network()
    day_like = {
        "nodes": {n["res"]: {"grid": n["grid"], "mw": [n["mw"]]} for n in nodes}
    }
    res_bus, _stats = map_resources(day_like, net)
    sub_at: dict[str, str] = {}
    for i, s in enumerate(net["subs"]):
        node = net["graph"].node_of_sub.get(i)
        if node and s.get("name") and node not in sub_at:
            sub_at[node] = s["name"]
    placed = []
    for n in nodes:
        bus = res_bus.get(n["res"])
        if not bus:
            continue
        lon, lat = (round(float(x), 5) for x in bus.split(","))
        placed.append({**n, "lon": lon, "lat": lat, "station": sub_at.get(bus)})

    return {
        "available": True,
        "window": {
            "first": days[0][7:11] + "-" + days[0][11:13] + "-" + days[0][13:15],
            "last": days[-1][7:11] + "-" + days[-1][11:13] + "-" + days[-1][13:15],
            "days_derived": len(days),
            "clean_days": len(clean_days),
            "clean_criterion": "at least 90% of the day's rows OK-flagged "
            "(administered PSM/SEC days excluded)",
        },
        "n_nodes": len(nodes),
        "n_placed": len(placed),
        "per_grid": per_grid,
        "nodes": nodes,
        "placed": placed,
        "notes": [
            "Mean over clean days of each node's daily mean deviation from "
            "its regional SMP (DIPCEF final, PhP/kWh). Nodes need data on "
            "80% of clean days to appear.",
            "WESM's published nodal congestion component is zero on every "
            "sampled day; deviations are formally loss-dominated and "
            "intra-regional congestion is administered. Read this as "
            "persistent locational price deviation, not a congestion "
            "premium.",
            "Map placement covers only nodes whose station token resolves "
            "onto the OSM-mapped grid; the full table lists every node.",
        ],
    }


if __name__ == "__main__":
    out = build_nodal_obs()
    slim = {k: v for k, v in out.items() if k not in ("nodes", "placed")}
    print(json.dumps(slim, indent=1)[:2000])
    print("nodes:", out.get("n_nodes"), "placed:", out.get("n_placed"))
