#!/usr/bin/env python3
"""One scenario file, and both sides read the same bytes.

tests/fixtures/scenario_example.json is the fixture. The browser suite reads it
in studio/src/studio/scenarioFile.test.ts and this file reads it here, so the
two mappings cannot drift apart without one of them failing.

What this pins:
  1. the fixture validates, and it actually solves through the engine,
  2. every option key the document names is a key the engine honors,
  3. a broken file produces messages a person can act on, not a traceback,
  4. the CLI's validate subcommand agrees with the library.

Plain python + highspy, no pytest dependency. Run: python3 tests/test_scenario_file.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import power_dispatch as pdx  # noqa: E402
from power_dispatch.schema import OPT_SPEC, SCHEMA, dumps, load, validate  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


FIXTURE = os.path.join(HERE, "fixtures", "scenario_example.json")
fixture = json.load(open(FIXTURE))

# 1. the fixture is valid and it runs
check("the shared fixture validates", validate(fixture) == [])
check("load() returns it", load(FIXTURE)["date"] == fixture["date"])
check("the schema stamp matches this build", fixture["schema"] == SCHEMA)

days = pdx.list_days()
runnable = dict(fixture)
runnable["date"] = days[-1]  # the fixture's date can age out of the rolling window
res = pdx.run_scenario(runnable)
check("the fixture solves 24 hours", len(res["hours"]) == 24)
check("its edits move the price off the flat base",
      len({h["price"]["luzon"] for h in res["hours"]}) > 1)

base = pdx.run_scenario({"date": days[-1], "opts": {}})
moved = res["summary"]["mean_price"]["luzon"] != base["summary"]["mean_price"]["luzon"]
check("the fixture's edits reach the solved price", moved)

# 2. the document names every key, and the engine honors every key it names
doc = open(os.path.join(ROOT, "docs", "scenario-schema.md")).read()
for k in OPT_SPEC:
    check(f"docs/scenario-schema.md names {k}", f"`{k}`" in doc)
for k in OPT_SPEC:
    check(f"the engine honors {k}", k in pdx.OPT_KEYS)
for k in pdx.OPT_KEYS:
    check(f"the schema covers the engine's {k}", k in OPT_SPEC)

# 3. a broken file says what is wrong
bad = {
    "schema": "pds-scenario/1",
    "date": "17 June 2026",
    "opts": {
        "demand_delto": {"luzon": 1500},
        "fuel_avail_delta": {"lozon": {"coal": -647}},
        "caps": {"leyte": "wide open"},
        "storage": [{"grid": "luzon", "power_mw": "300"}],
        "offer_mode": "yes",
    },
}
msgs = validate(bad)
joined = " | ".join(msgs)
check("a bad date is named", any("YYYY-MM-DD" in m for m in msgs))
check("a misspelled option suggests the real one", "demand_delta" in joined)
check("a misspelled grid is named", "'lozon'" in joined)
check("a text link limit is caught", any("caps.leyte" in m for m in msgs))
check("a text power rating is caught", any("power_mw" in m for m in msgs))
check("a missing energy rating is caught", any("energy_mwh" in m for m in msgs))
check("a text flag is caught", any("offer_mode" in m for m in msgs))
check("nothing raises on a broken file", isinstance(msgs, list))

check("an empty scenario still needs a schema and a date",
      len(validate({})) >= 2)
check("a scenario that is not an object says so",
      validate([1, 2, 3]) == ["the scenario must be a JSON object"])

# 4. dumps stamps the schema, and the CLI agrees with the library
text = dumps({"date": "2026-06-17", "opts": {}})
check("dumps stamps the schema first", json.loads(text)["schema"] == SCHEMA)

env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"))
ok = subprocess.run(
    [sys.executable, "-m", "power_dispatch.cli", "validate", FIXTURE],
    capture_output=True, text=True, env=env,
)
check("the CLI accepts the fixture", ok.returncode == 0)
check("the CLI counts the options", "8 option(s)" in ok.stdout)

with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
    json.dump(bad, fh)
    bad_path = fh.name
no = subprocess.run(
    [sys.executable, "-m", "power_dispatch.cli", "validate", bad_path],
    capture_output=True, text=True, env=env,
)
check("the CLI rejects a broken file", no.returncode == 1)
check("the CLI prints every problem", no.stderr.count("\n") >= len(msgs))
os.unlink(bad_path)

# a file without the schema stamp is the older shape and still runs
old = {"date": days[-1], "opts": {"demand_delta": {"luzon": 500}}}
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
    json.dump(old, fh)
    old_path = fh.name
ran = subprocess.run(
    [sys.executable, "-m", "power_dispatch.cli", "run", "--scenario", old_path],
    capture_output=True, text=True, env=env,
)
check("an unstamped scenario from before this schema still runs", ran.returncode == 0)
os.unlink(old_path)

print()
print(f"scenario file: {len(fails)} failures" if fails else "scenario file: all green")
sys.exit(1 if fails else 0)
