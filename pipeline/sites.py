#!/usr/bin/env python3
"""Bake the connection limits for every announced load site (web/data/sites.json).

The studio can then answer siting what-ifs live, without solving a network in the
browser. Solving is the expensive half and it only depends on the grid and the
day, never on what a user types, so it belongs in the bake. What a user types is
how big the campus is and how much of its own power it makes, and that is
arithmetic against these numbers.

Per site this records:
  - the modelled bus it sits nearest, and how far away that is
  - the circuits on that bus, with their ratings and where each rating came from
  - how many more megawatts the site could draw in each hour of the day before
    a circuit on it reaches its rating
  - what happens to that when each of those circuits is out in turn

The hourly limit is solved rather than swept. Flow rises in step with load added,
so two replay solves an hour give the exact crossing point, and a third solve at
that point is checked to sit on the rating.

    python3 pipeline/sites.py --day 2026-06-25
"""
from __future__ import annotations

import argparse
import json
import os

from constants_ph import DC_SITES
from nodal_dcopf import (
    SITES,
    _load_day,
    _plant_load,
    build_network,
    hour_injections,
    map_resources,
    resolve_site,
    solve_hour,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "web", "data")
PROBE_MW = 1000.0


def _catalogue() -> list[dict]:
    """Every site the studio can plant, from both registries.

    The announced data centres carry city precision at best, and the Pax Silica
    entry is a campus centroid. Both are labelled so the view can say so.
    """
    out = []
    for key, s in sorted(SITES.items()):
        out.append({
            "id": key,
            "name": s["label"],
            "lon": s["lon"],
            "lat": s["lat"],
            "mw": s["mw_range"][0],
            "mw_range": s["mw_range"],
            "precision": s["precision"],
            "src": s.get("mw_src"),
            "kind": "announced zone",
        })
    for s in DC_SITES:
        if not s.get("mw"):
            continue
        out.append({
            "id": s["name"].lower().replace(" ", "-").replace(".", ""),
            "name": s["name"],
            "city": s.get("city"),
            "lon": s["coords"][0],
            "lat": s["coords"][1],
            "mw": s["mw"],
            "precision": s.get("precision", "city"),
            "src": s.get("src"),
            "status": s.get("status"),
            "kind": "data centre",
        })
    return out


def _limit(net, inj, bus, local) -> tuple[float | None, float]:
    """Added MW at which the worst circuit on the bus reaches its rating, and
    how loaded the worst of them already is before anything is added.

    A circuit can already sit over its estimated rating with no new load at all,
    which happens across this network because the ratings are standard figures
    rather than the operator's own. When that is true there is no headroom to
    report and the honest answer is nothing, not a crossing point extrapolated
    past a limit that is already breached. Missing that returned limits of
    thousands of megawatts for sites whose circuits were already over."""
    s0 = solve_hour(net, _plant_load(inj, net, bus, 0.0), "replay")
    s1 = solve_hour(net, _plant_load(inj, net, bus, PROBE_MW), "replay")
    if s0 is None or s1 is None:
        return None, 0.0
    base = max(abs(s0["flows_mw"][bi]) / net["branches"][bi]["rating_mw"]
               for bi in local)
    if base >= 1.0:
        return 0.0, base
    best = None
    for bi in local:
        f0, f1 = s0["flows_mw"][bi], s1["flows_mw"][bi]
        slope = (f1 - f0) / PROBE_MW
        if abs(slope) < 1e-9:
            continue
        rating = net["branches"][bi]["rating_mw"]
        for target in (rating, -rating):
            d = (target - f0) / slope
            if d > 0 and (best is None or d < best):
                best = d
    return best, base


def _reaches(branches, bus, island) -> int:
    """How many buses of its own island the site can still reach."""
    adj: dict[str, set[str]] = {}
    for b in branches:
        adj.setdefault(b["a"], set()).add(b["b"])
        adj.setdefault(b["b"], set()).add(b["a"])
    seen, stack = {bus}, [bus]
    while stack:
        for nxt in adj.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return len(seen & island)


def build_sites(date: str) -> dict:
    net = build_network()
    day = _load_day(date)
    res_bus, _ = map_resources(day, net)
    all_branches = list(net["branches"])
    hours = list(range(24))
    inj_by_hour = {h: hour_injections(day, res_bus, net, h) for h in hours}

    rows = []
    for site in _catalogue():
        placed = resolve_site(net, site["lon"], site["lat"])
        bus = placed["bus"]
        island = {b["id"] for b in net["buses"] if b["grid"] == placed["grid"]}
        local = [bi for bi, b in enumerate(all_branches)
                 if b["a"] == bus or b["b"] == bus]
        if not local:
            continue

        limits, checks, bases = [], [], []
        for h in hours:
            lim, base = _limit(net, inj_by_hour[h], bus, local)
            bases.append(base)
            limits.append(round(lim, 1) if lim is not None else None)
            if lim:
                sol = solve_hour(
                    net, _plant_load(inj_by_hour[h], net, bus, float(lim)), "replay")
                if sol is not None:
                    checks.append(max(
                        abs(sol["flows_mw"][bi]) / all_branches[bi]["rating_mw"]
                        for bi in local))

        # each circuit on the bus, out in turn
        outages = []
        for drop in local:
            kept = [b for i, b in enumerate(all_branches) if i != drop]
            net["branches"] = kept
            local2 = [i for i, b in enumerate(kept)
                      if b["a"] == bus or b["b"] == bus]
            reach = _reaches(kept, bus, island)
            cut = reach < len(island) / 2
            lim = (_limit(net, inj_by_hour[19], bus, local2)[0]
                   if local2 and not cut else None)
            net["branches"] = all_branches
            outages.append({
                "circuit": all_branches[drop]["names"]
                or [all_branches[drop]["kind"]],
                "km": all_branches[drop]["km"],
                "limit_mw": round(lim, 1) if lim is not None else None,
                "cuts_site_off": bool(cut),
                "buses_still_reached": reach,
                "buses_on_island": len(island),
            })

        good = [x for x in limits if x is not None]
        rows.append({
            **site,
            "bus": bus,
            "grid": placed["grid"],
            "snap_km": placed["snap_km"],
            "circuits": [
                {"names": all_branches[bi]["names"] or [all_branches[bi]["kind"]],
                 "kind": all_branches[bi]["kind"],
                 "km": all_branches[bi]["km"],
                 "rating_mw": all_branches[bi]["rating_mw"],
                 "rating_src": all_branches[bi].get("rating_src")}
                for bi in local
            ],
            "limit_mw_by_hour": limits,
            "limit_min_mw": round(min(good), 1) if good else None,
            "limit_max_mw": round(max(good), 1) if good else None,
            "outages": outages,
            "radially_fed": any(o["cuts_site_off"] for o in outages),
            "already_over_rating": bool(bases and max(bases) >= 1.0),
            "worst_base_loading": round(max(bases), 3) if bases else None,
            "linearity_max_error": (round(max(abs(c - 1.0) for c in checks), 4)
                                    if checks else None),
        })
        print(f"  {site['name'][:44]:46} {placed['grid']:9} "
              f"{placed['snap_km']:6.1f} km  "
              f"limit {min(good) if good else 0:,.0f}-{max(good) if good else 0:,.0f} MW"
              f"{'  RADIAL' if rows[-1]['radially_fed'] else ''}")

    return {
        "available": True,
        "day": date,
        "n_sites": len(rows),
        "sites": rows,
        "note": (
            "How much more each site could draw before a circuit on its own bus "
            "reaches its rating, solved for every hour of one recorded day on "
            "the reduced network built from the public map. NGCP does not "
            "publish what its lines are rated to carry, so those ratings are "
            "standard figures for the voltage except where the market record "
            "named an operating limit, and every number moves with them. Site "
            "coordinates are city or campus precision and are moved to the "
            "nearest modelled bus, which is not the connection anyone will "
            "build. Read snap_km before trusting a site."
        ),
        "disclaimer": (
            "Statistical indicators derived from public data. Patterns may have "
            "legitimate explanations."
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="YYYY-MM-DD; defaults to the latest derived day")
    a = ap.parse_args()
    if not a.day:
        # the bake runs unattended, so pick the newest day the nodal archive has
        derived = os.path.join(HERE, "..", "data", "derived", "nodal_daily")
        days = sorted(f[7:15] for f in os.listdir(derived)
                      if f.startswith("NODALD_") and f.endswith(".json"))
        if not days:
            raise SystemExit("no derived nodal days; run the nodal pipeline first")
        a.day = f"{days[-1][:4]}-{days[-1][4:6]}-{days[-1][6:]}"
    print(f"siting limits on {a.day}")
    res = build_sites(a.day)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "sites.json"), "w") as fh:
        json.dump(res, fh, indent=1)
    n_radial = sum(1 for s in res["sites"] if s["radially_fed"])
    print(f"\nwrote web/data/sites.json: {res['n_sites']} sites, "
          f"{n_radial} fed radially")
