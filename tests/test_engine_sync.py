#!/usr/bin/env python3
"""The pip package (src/power_dispatch) must be the same engine as pipeline/.

Two guarantees, both plain python, no pytest:
  1. no drift: the vendored engine files match what tools/sync_engine.py would
     regenerate from the pipeline source right now (so a pipeline edit that
     was not re-synced fails here, not silently in a stale wheel).
  2. same numbers: the package's run_scenario and the pipeline's
     run_chronology_lp produce a byte-identical LP (equal lp_sha256) and equal
     summaries on the same day, so "it is the same engine" is a test, not a
     claim.

Run: python3 tests/test_engine_sync.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# 1. drift check
import sync_engine  # noqa: E402

check("vendored engine is in sync with pipeline source",
      sync_engine.sync(check=True) == 0)

# 2. same-engine parity: pick a baked day and run both sides
import power_dispatch as pkg  # noqa: E402
from lp_dispatch import run_chronology_lp  # noqa: E402

WEB = os.path.join(ROOT, "web", "data")
dispatch = json.load(open(os.path.join(WEB, "dispatch.json")))
profiles = json.load(open(os.path.join(WEB, "profiles.json")))
day = profiles["days"][len(profiles["days"]) // 2]["date"]

pipe = run_chronology_lp(dispatch, profiles, day, {})
pack = pkg.run_scenario({"date": day, "opts": {}})

check(f"package and pipeline produce identical LP on {day} (lp_sha256)",
      pipe["lp_sha256"] == pack["lp_sha256"])
check("package and pipeline agree on the day summary",
      pipe["summary"] == pack["summary"])

# 3. a lever run solves and moves price the expected way (demand up -> price up)
base = pkg.run_scenario({"date": day, "opts": {}})
up = pkg.run_scenario({"date": day, "opts": {"demand_delta": {"luzon": 1500}}})
check("adding 1.5 GW Luzon load does not lower the Luzon mean price",
      up["summary"]["mean_price"]["luzon"]
      >= base["summary"]["mean_price"]["luzon"] - 1e-9)

# 4. list_days is the baked day list
check("list_days matches the baked profiles day count",
      len(pkg.list_days()) == len(profiles["days"]))

print("\n" + ("all green" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
