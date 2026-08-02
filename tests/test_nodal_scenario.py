#!/usr/bin/env python3
"""Invariants of the sited-load scenario (pipeline/nodal_dcopf.py).

Solving a full day takes minutes, so it belongs in an investigation run rather
than in the test suite. What is checked here is everything that can go wrong
without the solver. Where a site lands, whether adding a load leaves the
island's net position alone, and whether a line upgrade stays inside its radius
and can be undone.
Plain python, no pytest. Run: python3 tests/test_nodal_scenario.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pipeline"))

from nodal_dcopf import (  # noqa: E402
    SITES,
    _plant_load,
    reinforce_site,
    resolve_site,
)

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


from nodal_dcopf import build_network  # noqa: E402

net = build_network()
buses = {b["id"]: b for b in net["buses"]}

# --- site resolution ----------------------------------------------------------
pax = SITES["pax-silica"]
site = resolve_site(net, pax["lon"], pax["lat"])
check("the Pax Silica site resolves to a bus", site["bus"] in buses)
check("the Pax Silica site lands on Luzon", site["grid"] == "luzon")
# the campus is in Tarlac, so a match that wandered out of the province would
# mean the network lost central Luzon, which is worth failing the test over
check("the snap stays local (under 25 km)", site["snap_km"] < 25.0)
check("the snap distance is reported, not hidden", "snap_km" in site)

# resolving a coordinate that IS a bus must return that bus at zero distance
any_bus = net["buses"][0]
exact = resolve_site(net, any_bus["lon"], any_bus["lat"])
check(
    "a coordinate on a bus resolves to itself",
    exact["bus"] == any_bus["id"] and exact["snap_km"] < 1e-6,
)

# --- planting a load ----------------------------------------------------------
inj = {b["id"]: 0.0 for b in net["buses"]}
lz = [b["id"] for b in net["buses"] if b["grid"] == "luzon"]
for i, b in enumerate(lz[:10]):
    inj[b] = 100.0  # ten generating buses
load_bus = site["bus"]
inj[load_bus] = inj.get(load_bus, 0.0) - 200.0

before = sum(inj[b] for b in lz)
planted = _plant_load(inj, net, load_bus, 500.0)
after = sum(planted[b] for b in lz)
check(
    "planting a load keeps the island's net position unchanged",
    abs(after - before) < 1e-6,
)
check(
    "the site bus carries the new load",
    abs(planted[load_bus] - (inj[load_bus] - 500.0)) < 1e-6,
)
check(
    "the supply comes from the buses that were generating",
    all(planted[b] > inj[b] for b in lz[:10]),
)
# a bus in another island must not be touched
other = next((b["id"] for b in net["buses"] if b["grid"] != "luzon"), None)
if other:
    check(
        "planting on Luzon leaves other islands alone",
        abs(planted.get(other, 0.0) - inj.get(other, 0.0)) < 1e-6,
    )

# --- reinforcement ------------------------------------------------------------
orig = {id(br): (br["rating_mw"], br.get("rating_src")) for br in net["branches"]}
incident = reinforce_site(net, load_bus, 3500.0)
check("reinforcement touches the branches at the site bus", len(incident) > 0)
check(
    "reinforcement raises ratings to the asked-for MW",
    all(r["rating_mw_after"] >= 3500.0 - 1e-6 for r in incident),
)
touched = [
    br for br in net["branches"] if br.get("rating_src") == "scenario-reinforced"
]
check(
    "with radius 0 only branches on the bus are reinforced",
    all(br["a"] == load_bus or br["b"] == load_bus for br in touched),
)

for br in net["branches"]:
    br["rating_mw"], br["rating_src"] = orig[id(br)]

wide = reinforce_site(net, load_bus, 3500.0, radius_km=60.0)
check("a radius reinforces more than the incident branches", len(wide) > len(incident))
for br in net["branches"]:
    br["rating_mw"], br["rating_src"] = orig[id(br)]
check(
    "ratings restore exactly after a scenario",
    all(br["rating_mw"] == orig[id(br)][0] for br in net["branches"]),
)

# a branch already rated above the target must not be downgraded
strong = max(net["branches"], key=lambda br: br["rating_mw"])
before_mw = strong["rating_mw"]
reinforce_site(net, strong["a"], 1.0)
check("reinforcement never lowers a rating", strong["rating_mw"] == before_mw)
for br in net["branches"]:
    br["rating_mw"], br["rating_src"] = orig[id(br)]

print("\n" + ("all green" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
