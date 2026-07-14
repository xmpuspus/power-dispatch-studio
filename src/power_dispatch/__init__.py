"""power_dispatch: the PH WESM dispatch engine behind Power Dispatch Studio,
as an importable, citable module.

The studio runs this same linear-program merit-order engine in the browser
(wasm HiGHS); this package is the Python reference implementation of one
observed-day replay: build the per-grid supply stacks from baked IEMOP data,
apply scenario overrides, and clear a coupled multi-grid LP with corridor
limits, storage, reserves, and a hydro water budget.

Public API:
    load_baked(data_dir=None) -> (dispatch, profiles)
    run_scenario(scenario, data_dir=None) -> result dict
    run_chronology_lp(dispatch, profiles, date, opts) -> result dict  (engine)

A scenario is {"date": "YYYY-MM-DD", "opts": {...}} where opts is the override
map documented in run_scenario. Data is a bundled snapshot of the public
archive; point data_dir at a fresh web/data/ to run against a newer bake.
"""
from __future__ import annotations

import json
import os

from .engine.lp_dispatch import run_chronology_lp

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "load_baked",
    "list_days",
    "run_scenario",
    "run_chronology_lp",
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, "data")

# the scenario override keys the engine honors (see engine/lp_dispatch._assemble)
OPT_KEYS = (
    "demand_delta",       # {grid: MW} load added/removed
    "fuel_cost",          # {fuel: PhP/kWh} marginal-cost override
    "fuel_avail_delta",   # {grid: {fuel: MW}} availability edit
    "solar_delta_mw",     # {grid: MW} installed solar edit
    "hydrology",          # float, water multiplier (1.0 = observed)
    "caps",               # {leyte|mvip: MW or [24 MW]} corridor limits
    "storage",            # [{grid, power_mw, energy_mwh}] added BESS
    "reserve_deduction",  # bool, withhold scheduled reserve from the book
    "offer_mode",         # bool, replay the observed offer book (item: loads it)
)


def _data_dir(override: str | None = None) -> str:
    """Resolve the data directory: an explicit override, the
    POWER_DISPATCH_DATA env var, or the bundled snapshot."""
    return override or os.environ.get("POWER_DISPATCH_DATA") or _BUNDLED


def load_baked(data_dir: str | None = None) -> tuple[dict, dict]:
    """Load the baked dispatch.json and profiles.json."""
    root = _data_dir(data_dir)
    with open(os.path.join(root, "dispatch.json"), encoding="utf-8") as fh:
        dispatch = json.load(fh)
    with open(os.path.join(root, "profiles.json"), encoding="utf-8") as fh:
        profiles = json.load(fh)
    return dispatch, profiles


def list_days(data_dir: str | None = None) -> list[str]:
    """The observed days available for replay (profiles.json day list)."""
    _, profiles = load_baked(data_dir)
    return [d["date"] for d in profiles["days"]]


def _load_offer_book(date: str, root: str) -> dict:
    path = os.path.join(root, "offers",
                        f"OFFERD_{date.replace('-', '')}.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"offer_mode requested but no observed offer book for {date} "
            f"(looked in {os.path.join(root, 'offers')})")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_scenario(scenario: dict, data_dir: str | None = None) -> dict:
    """Run one observed-day replay with scenario overrides.

    scenario = {"date": "YYYY-MM-DD", "opts": {...}}. When opts["offer_mode"]
    is true the observed offer book for the day is loaded and the replay runs
    against the market's own bids instead of the cost proxy. Returns the
    engine result dict (hours, summary, objective, lp_sha256)."""
    root = _data_dir(data_dir)
    dispatch, profiles = load_baked(root)
    date = scenario["date"]
    days = {d["date"] for d in profiles["days"]}
    if date not in days:
        raise ValueError(
            f"{date} is not an observed day in this data snapshot; "
            f"list_days() shows the available range")
    opts = dict(scenario.get("opts") or {})
    if opts.pop("offer_mode", False):
        opts["offer_day"] = _load_offer_book(date, root)
    return run_chronology_lp(dispatch, profiles, date, opts)
