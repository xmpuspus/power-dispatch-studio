#!/usr/bin/env python3
"""Pins on the baked siting limits (web/data/sites.json).

The studio does its what-if as arithmetic against these numbers, so anything
wrong here is wrong on screen with nothing to catch it. Plain python, no pytest.
Run: python3 tests/test_sites.py
"""
import json
import os
import sys

WEB = os.path.join(os.path.dirname(__file__), "..", "web", "data")
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


path = os.path.join(WEB, "sites.json")
if not os.path.exists(path):
    print("SKIP sites.json absent; run python3 pipeline/sites.py")
    sys.exit(0)

d = json.load(open(path))
check("sites.json is available", d.get("available") is True)
check("every site carries the day it was solved on", bool(d.get("day")))
check("at least one site is baked", d.get("n_sites", 0) > 0)
check("the count matches the list", d["n_sites"] == len(d["sites"]))
check("the note says the ratings are estimates",
      "rated to carry" in d.get("note", ""))
check("an analytics disclaimer ships with it", bool(d.get("disclaimer")))

for s in d["sites"]:
    tag = s["name"][:34]
    check(f"{tag}: has a bus and a grid", bool(s.get("bus")) and bool(s.get("grid")))
    check(f"{tag}: reports how far it sits from the model",
          isinstance(s.get("snap_km"), (int, float)))
    check(f"{tag}: 24 hourly limits", len(s.get("limit_mw_by_hour", [])) == 24)
    good = [x for x in s["limit_mw_by_hour"] if x is not None]
    # zero is a real answer: it means a circuit there is already over its
    # estimated rating with nothing added
    check(f"{tag}: no limit is negative", all(x >= 0 for x in good))
    check(f"{tag}: min and max bracket the hours",
          not good or (s["limit_min_mw"] <= min(good) + 1e-6
                       and s["limit_max_mw"] >= max(good) - 1e-6))
    # the limit is solved by where a circuit hits its rating, so re-solving at
    # that point must land on the rating. A drift here means the linear
    # assumption broke and every number in the view moved with it.
    err = s.get("linearity_max_error")
    check(f"{tag}: solving at the limit sits on the rating",
          err is None or err < 0.01)
    check(f"{tag}: has at least one circuit", len(s.get("circuits", [])) > 0)
    check(f"{tag}: one outage row per circuit",
          len(s.get("outages", [])) == len(s["circuits"]))
    check(f"{tag}: radial flag agrees with the outage rows",
          s["radially_fed"] == any(o["cuts_site_off"] for o in s["outages"]))
    for o in s["outages"]:
        check(f"{tag}: an outage never leaves a negative limit",
              o["limit_mw"] is None or o["limit_mw"] >= 0)
        # losing a circuit can RAISE the limit, because taking a line out
        # reroutes the through-flow that was loading the ones left. That is
        # physical, so it is not pinned.
        check(f"{tag}: a cut-off site reaches less than half its island",
              not o["cuts_site_off"]
              or o["buses_still_reached"] < o["buses_on_island"] / 2)

    # a site whose circuits are already over their estimated rating has no
    # headroom to report, and the two must never disagree
    if s.get("already_over_rating"):
        check(f"{tag}: no headroom where a circuit is already over",
              min(s["limit_mw_by_hour"], key=lambda x: 1e9 if x is None else x) == 0)

# Pax Silica is the site the whole siting story was built on, so its shape is
# pinned rather than left to drift silently
pax = next((s for s in d["sites"] if s["id"] == "pax-silica"), None)
check("the Pax Silica site is baked", pax is not None)
if pax:
    check("Pax Silica sits on Luzon", pax["grid"] == "luzon")
    check("Pax Silica has two circuits on its bus", len(pax["circuits"]) == 2)
    check("Pax Silica is fed radially", pax["radially_fed"] is True)
    check("exactly one of its circuits cuts it off",
          sum(1 for o in pax["outages"] if o["cuts_site_off"]) == 1)

print("\n" + ("all green" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
