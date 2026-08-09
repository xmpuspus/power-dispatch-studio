"""One scenario file the command line, the notebook, and the browser all read.

A scenario used to exist in two shapes that could not meet. The command line
took `{"date": ..., "opts": {...}}`. The studio kept its edits in a URL hash. So
a scenario built by dragging a slider could not re-run in Python, and a scenario
written in Python could not open in a browser.

This module defines the one file, version `pds-scenario/1`, and validates it
with errors a person can act on:

    {
      "schema": "pds-scenario/1",
      "name": "DICT 1.5 GW on Luzon",
      "date": "2026-06-17",
      "opts": { "demand_delta": {"luzon": 1500} },
      "meta": { "note": "free text, never read by the engine" }
    }

`validate` returns a list of messages and never raises. `load` raises
ValueError with every message joined, for a caller who wants the exception.

The schema carries exactly the keys the engine honors today, and no more. A key
the engine cannot act on has no place in a file that claims to reproduce a run.
Named units, contracts, and start costs are absent because the engine holds fuel
blocks per grid; when that changes the version goes to 2.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA = "pds-scenario/1"
GRIDS = ("luzon", "visayas", "mindanao")
CAP_KEYS = ("leyte", "mvip")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# key -> (checker name, one-line meaning). The CLI, the document, and the test
# all read this, so a new engine option is described in exactly one place.
OPT_SPEC: dict[str, str] = {
    "demand_delta": "{grid: MW} or {grid: [24 MW]}, load added or removed",
    "fuel_cost": "{fuel: PhP/kWh}, marginal-cost override",
    "fuel_avail_delta": "{grid: {fuel: MW}}, availability edit",
    "solar_delta_mw": "{grid: MW}, installed solar edit",
    "hydrology": "float, water multiplier where 1.0 is the recorded day",
    "caps": "{leyte|mvip: MW or [24 MW]}, link limits",
    "storage": "[{grid, power_mw, energy_mwh}], added batteries",
    "reserve_deduction": "bool, withhold scheduled reserve from the stack",
    "offer_mode": "bool, replay the recorded offer book instead of the cost model",
    "gas_budget": "{grid: MWh}, a daily gas-energy limit",
}


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _mw_or_shape(v: Any) -> bool:
    if _num(v):
        return True
    return isinstance(v, list) and len(v) == 24 and all(_num(x) for x in v)


def validate(scenario: Any) -> list[str]:
    """Every problem with a scenario, as messages a person can act on."""
    e: list[str] = []
    if not isinstance(scenario, dict):
        return ["the scenario must be a JSON object"]

    got = scenario.get("schema")
    if got is None:
        e.append(f"missing 'schema'. Add \"schema\": \"{SCHEMA}\"")
    elif got != SCHEMA:
        e.append(f"'schema' is {got!r}, and this build reads {SCHEMA!r}")

    date = scenario.get("date")
    if not isinstance(date, str) or not _DATE.match(date):
        e.append("'date' must be a string shaped YYYY-MM-DD")

    for key in ("name",):
        if key in scenario and not isinstance(scenario[key], str):
            e.append(f"'{key}' must be a string")
    if "meta" in scenario and not isinstance(scenario["meta"], dict):
        e.append("'meta' must be an object. Nothing in it reaches the engine")

    opts = scenario.get("opts", {})
    if not isinstance(opts, dict):
        return e + ["'opts' must be an object"]

    for k in opts:
        if k not in OPT_SPEC:
            near = [n for n in OPT_SPEC if n.startswith(k[:4])]
            hint = f". Did you mean {near[0]!r}?" if near else ""
            e.append(f"unknown option {k!r}{hint}")

    def grids(key: str, val: Any, check, what: str):
        if not isinstance(val, dict):
            e.append(f"'{key}' must be an object keyed by grid")
            return
        for g, v in val.items():
            if g not in GRIDS:
                e.append(f"'{key}' names {g!r}, and the grids are {', '.join(GRIDS)}")
            elif not check(v):
                e.append(f"'{key}.{g}' must be {what}")

    if "demand_delta" in opts:
        grids("demand_delta", opts["demand_delta"], _mw_or_shape, "MW or 24 hourly MW")
    if "solar_delta_mw" in opts:
        grids("solar_delta_mw", opts["solar_delta_mw"], _num, "a number of MW")
    if "gas_budget" in opts:
        grids("gas_budget", opts["gas_budget"], _num, "a number of MWh")

    if "fuel_cost" in opts:
        fc = opts["fuel_cost"]
        if not isinstance(fc, dict):
            e.append("'fuel_cost' must be an object keyed by fuel")
        else:
            for f, v in fc.items():
                if not _num(v):
                    e.append(f"'fuel_cost.{f}' must be a price in PhP/kWh")

    if "fuel_avail_delta" in opts:
        fad = opts["fuel_avail_delta"]
        if not isinstance(fad, dict):
            e.append("'fuel_avail_delta' must be an object keyed by grid")
        else:
            for g, per in fad.items():
                if g not in GRIDS:
                    e.append(f"'fuel_avail_delta' names {g!r}, not a grid")
                elif not isinstance(per, dict):
                    e.append(f"'fuel_avail_delta.{g}' must be an object keyed by fuel")
                else:
                    for f, v in per.items():
                        if not _num(v):
                            e.append(f"'fuel_avail_delta.{g}.{f}' must be MW")

    if "hydrology" in opts and not _num(opts["hydrology"]):
        e.append("'hydrology' must be a number, where 1.0 is the recorded day")

    if "caps" in opts:
        caps = opts["caps"]
        if not isinstance(caps, dict):
            e.append("'caps' must be an object keyed by link")
        else:
            for k, v in caps.items():
                if k not in CAP_KEYS:
                    e.append(f"'caps' names {k!r}, and the links are leyte, mvip")
                elif not _mw_or_shape(v):
                    e.append(f"'caps.{k}' must be MW or 24 hourly MW")

    if "storage" in opts:
        st = opts["storage"]
        if not isinstance(st, list):
            e.append("'storage' must be a list of batteries")
        else:
            for i, s in enumerate(st):
                if not isinstance(s, dict):
                    e.append(f"'storage[{i}]' must be an object")
                    continue
                if s.get("grid") not in GRIDS:
                    e.append(f"'storage[{i}].grid' must be one of {', '.join(GRIDS)}")
                for f in ("power_mw", "energy_mwh"):
                    if not _num(s.get(f)):
                        e.append(f"'storage[{i}].{f}' must be a number")
                # 'id' names which battery a studio row means. Two batteries can
                # sit on one grid, so a file without it cannot say which. The
                # engine ignores it and the studio matches on it.
                if "id" in s and not isinstance(s["id"], str):
                    e.append(f"'storage[{i}].id' must be a string when present")

    for flag in ("reserve_deduction", "offer_mode"):
        if flag in opts and not isinstance(opts[flag], bool):
            e.append(f"'{flag}' must be true or false")

    return e


def load(path_or_text: str) -> dict:
    """Read a scenario file (a path or the JSON itself) and validate it."""
    text = path_or_text
    if not path_or_text.lstrip().startswith("{"):
        with open(path_or_text, encoding="utf-8") as fh:
            text = fh.read()
    try:
        scenario = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    problems = validate(scenario)
    if problems:
        raise ValueError("scenario file has problems:\n  " + "\n  ".join(problems))
    return scenario


def dumps(scenario: dict, indent: int = 2) -> str:
    """Write a scenario with the schema stamped, ready for a file."""
    out = {"schema": SCHEMA, **{k: v for k, v in scenario.items() if k != "schema"}}
    return json.dumps(out, indent=indent, sort_keys=False)
