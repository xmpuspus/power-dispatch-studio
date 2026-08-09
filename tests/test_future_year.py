#!/usr/bin/env python3
"""A future year has to satisfy the same contract the engine already reads.

pipeline/future_year.py joins four published inputs into a data directory. The
risks are all arithmetic: a demand ratio taken from the wrong row, a project
counted whose target year has not arrived, a calendar that drops February 29,
or a build that quietly claims a retirement schedule it does not have.

This builds 2028 into a temporary directory, checks each of those, and solves
one day through the package to prove the directory actually runs.

Plain python + highspy, no pytest dependency. Run: python3 tests/test_future_year.py
"""

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import future_year as fy  # noqa: E402
import power_dispatch as pdx  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


GRIDS = ("luzon", "visayas", "mindanao")
YEAR = 2028
BASE = 2026

built = fy.build(YEAR, BASE, indicative=False)
d, p, m = built["dispatch"], built["profiles"], built["meta"]

# --- calendar ---------------------------------------------------------------
days = p["days"]
expected = (dt.date(YEAR + 1, 1, 1) - dt.date(YEAR, 1, 1)).days
check(f"{YEAR} carries all {expected} dates", len(days) == expected)
check(
    "2028 is a leap year and February 29 is present",
    any(x["date"] == "2028-02-29" for x in days),
)
check(
    "dates are unique and sorted",
    [x["date"] for x in days] == sorted({x["date"] for x in days}),
)
check(
    "every day names the recorded day it borrowed",
    all(x.get("source_day") for x in days),
)

# each date borrows a day of its own kind, weekday or weekend
kind_ok = True
for x in days:
    want = dt.date.fromisoformat(x["date"]).weekday() >= 5
    got = dt.date.fromisoformat(x["source_day"]).weekday() >= 5
    if want != got:
        kind_ok = False
        break
check("a weekday borrows a weekday and a weekend borrows a weekend", kind_ok)

# --- demand -----------------------------------------------------------------
path = json.load(open(os.path.join(ROOT, "web", "data", "demand_path.json")))
years = path["years"]
for g in GRIDS:
    want = (
        path["per_grid_mw"][g][years.index(YEAR)]
        / path["per_grid_mw"][g][years.index(BASE)]
    )
    got = m["demand"]["ratio_per_grid"][g]
    check(f"{g} growth ratio matches the DOE path ({got})", abs(got - want) < 5e-4)

src = json.load(open(os.path.join(ROOT, "web", "data", "profiles.json")))
by_date = {x["date"]: x for x in src["days"]}
sample = days[180]
# the exact ratio, not the 4-decimal one meta reports for a reader
ratio = (
    path["per_grid_mw"]["luzon"][years.index(YEAR)]
    / path["per_grid_mw"]["luzon"][years.index(BASE)]
)
base_hours = by_date[sample["source_day"]]["demand"]["luzon"]
check(
    "an hour equals its recorded hour times the ratio",
    all(
        abs(a - round(b * ratio, 1)) < 0.05
        for a, b in zip(sample["demand"]["luzon"], base_hours)
    ),
)
check(
    "every day still carries 24 hours per grid",
    all(len(x["demand"][g]) == 24 for x in days for g in GRIDS),
)

# --- supply -----------------------------------------------------------------
projects = json.load(open(os.path.join(ROOT, "web", "data", "projects.json")))
late = [
    r
    for r in projects["rows"]
    if r["status"] == "committed" and (r.get("target_year") or 9999) > YEAR
]
check(
    f"{len(late)} committed projects land after {YEAR} and none of them count",
    all(
        (r.get("target_year") or 9999) <= YEAR
        for r in projects["rows"]
        if r["status"] == "committed" and r.get("counted")
    ),
)

base_dispatch = json.load(open(os.path.join(ROOT, "web", "data", "dispatch.json")))
for g in GRIDS:
    for fuel, add in m["supply"]["added_stack_mw"][g].items():
        was = base_dispatch["merit_order"][g]["fuel_avail_mw"].get(fuel, 0.0)
        now = d["merit_order"][g]["fuel_avail_mw"][fuel]
        check(
            f"{g} {fuel} rises by exactly the added MW", abs(now - (was + add)) < 0.15
        )

check(
    "solar stays out of the dispatchable stack",
    all("solar" not in d["merit_order"][g]["fuel_avail_mw"] for g in GRIDS),
)
check(
    "storage projects are reported and never added to the stack",
    all("storage" not in d["merit_order"][g]["fuel_avail_mw"] for g in GRIDS),
)
check("the build states that it retires nothing", "none" in m["supply"]["retirements"])
check("the build labels itself a scenario", "not a forecast" in m["label"])

# --- links ------------------------------------------------------------------
base_caps = {c["id"]: c["limit_mw"] for c in base_dispatch["coupling"]["corridors"]}
for c in d["coupling"]["corridors"]:
    add = m["links"]["added_mw"].get(c["id"], 0.0)
    check(
        f"{c['id']} limit rises by exactly its upgrade",
        abs(c["limit_mw"] - (base_caps[c["id"]] + add)) < 0.15,
    )

# --- it actually solves -----------------------------------------------------
import tempfile  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    for name in ("dispatch", "profiles", "meta"):
        with open(os.path.join(tmp, f"{name}.json"), "w") as fh:
            json.dump(built[name], fh)
    listed = pdx.list_days(tmp)
    check("the package lists the whole year", len(listed) == expected)
    r = pdx.run_scenario({"date": f"{YEAR}-06-17", "opts": {}}, data_dir=tmp)
    check("a future day solves 24 hours", len(r["hours"]) == 24)
    check("every hour prices", all(h["price"]["luzon"] > 0 for h in r["hours"]))
    # the exact command the README, the analyst page, and the contract publish
    import subprocess  # noqa: E402

    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "power_dispatch.cli",
            "run",
            "--data-dir",
            tmp,
            "--date",
            f"{YEAR}-06-17",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    check("the published CLI command runs a future year", cli.returncode == 0)
    check(
        "it writes a header plus 24 hourly rows",
        len(cli.stdout.strip().split("\n")) == 25,
    )

    peak = max(h["demand"]["luzon"] for h in r["hours"])
    check(
        f"the day's Luzon peak ({peak:,.0f} MW) exceeds the recorded base",
        peak > max(by_date[days[168]["source_day"]]["demand"]["luzon"]),
    )

print()
print(f"future year: {len(fails)} failures" if fails else "future year: all green")
sys.exit(1 if fails else 0)
