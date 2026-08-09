"""power_dispatch: the PH WESM dispatch engine behind Power Dispatch Studio,
as an importable, citable module.

The studio runs this same linear-program merit-order engine in the browser
(wasm HiGHS); this package is the Python reference implementation of one
observed-day replay: build the per-grid supply stacks from generated IEMOP data,
apply scenario overrides, and clear a coupled multi-grid LP with corridor
limits, storage, reserves, and a hydro water budget.

Public API:
    load_data(data_dir=None) -> (dispatch, profiles)
    run_scenario(scenario, data_dir=None) -> result dict
    run_chronology_lp(dispatch, profiles, date, opts) -> result dict  (engine)

A scenario is {"date": "YYYY-MM-DD", "opts": {...}} where opts is the override
map documented in run_scenario. Data is a bundled snapshot of the public
archive; point data_dir at a fresh web/data/ to run against newer generated data.
"""

from __future__ import annotations

import json
import os

from .engine.lp_dispatch import run_chronology_lp
from .schema import SCHEMA as SCENARIO_SCHEMA
from .schema import load as load_scenario
from .schema import validate as validate_scenario
from .contracts import compare as compare_position
from .contracts import settle
from .contracts import validate_book

__version__ = "0.2.1"

__all__ = [
    "__version__",
    "load_baked",
    "load_data",
    "list_days",
    "run_scenario",
    "run_chronology_lp",
    "validate_scenario",
    "offer_days",
    "load_scenario",
    "SCENARIO_SCHEMA",
    "settle",
    "compare_position",
    "validate_book",
]

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, "data")

# the scenario override keys the engine honors (see engine/lp_dispatch._assemble)
OPT_KEYS = (
    "demand_delta",  # {grid: MW} flat load added/removed, or
    # {grid: [24 MW]} for a load with an hourly shape
    "fuel_cost",  # {fuel: PhP/kWh} marginal-cost override
    "fuel_avail_delta",  # {grid: {fuel: MW}} availability edit
    "solar_delta_mw",  # {grid: MW} installed solar edit
    "hydrology",  # float, water multiplier (1.0 = observed)
    "caps",  # {leyte|mvip: MW or [24 MW]} corridor limits
    "storage",  # [{grid, power_mw, energy_mwh}] added BESS
    "reserve_deduction",  # bool, withhold scheduled reserve from the book
    "offer_mode",  # bool, replay the observed offer book (item: loads it)
    # a daily gas-energy limit, {grid: MWh}, for a lower-supply case. The engine
    # has read it since the Malampaya lever landed and this list did not name it,
    # which tests/test_scenario_file.py now fails on.
    "gas_budget",
)


def _data_dir(override: str | None = None) -> str:
    """Resolve the data directory: an explicit override, the
    POWER_DISPATCH_DATA env var, or the bundled snapshot."""
    return override or os.environ.get("POWER_DISPATCH_DATA") or _BUNDLED


def load_data(data_dir: str | None = None) -> tuple[dict, dict]:
    """Load dispatch.json and profiles.json."""
    root = _data_dir(data_dir)
    with open(os.path.join(root, "dispatch.json"), encoding="utf-8") as fh:
        dispatch = json.load(fh)
    with open(os.path.join(root, "profiles.json"), encoding="utf-8") as fh:
        profiles = json.load(fh)
    return dispatch, profiles


# Keep the 0.1 public name working for existing package users.
load_baked = load_data


def list_days(data_dir: str | None = None) -> list[str]:
    """The observed days available for replay (profiles.json day list)."""
    _, profiles = load_data(data_dir)
    return [d["date"] for d in profiles["days"]]


def offer_days(data_dir: str | None = None) -> list[str]:
    """The days that carry a published offer book.

    The operator publishes an offer book several days after the price and
    summary files, so the newest replayable day and the newest OFFER day are
    not the same day. A caller who wants offer mode has to be able to ask.
    """
    root = os.path.join(_data_dir(data_dir), "offers")
    if not os.path.isdir(root):
        return []
    out = []
    for n in sorted(os.listdir(root)):
        if n.startswith("OFFERD_") and n.endswith(".json"):
            d = n[7:-5]
            out.append(f"{d[:4]}-{d[4:6]}-{d[6:]}")
    return out


def _load_offer_book(date: str, root: str) -> dict:
    path = os.path.join(root, "offers", f"OFFERD_{date.replace('-', '')}.json")
    if not os.path.isfile(path):
        have = offer_days(root)
        latest = f" The newest one is {have[-1]}." if have else ""
        raise FileNotFoundError(
            f"no published offer book for {date}, because the operator "
            f"publishes a book several days after the day itself."
            f"{latest} Run without --offer-mode to use the cost model."
        )
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def run_scenario(scenario: dict, data_dir: str | None = None) -> dict:
    """Run one observed-day replay with scenario overrides.

    scenario = {"date": "YYYY-MM-DD", "opts": {...}}. When opts["offer_mode"]
    is true the observed offer book for the day is loaded and the replay runs
    against the market's own bids instead of the cost proxy. Returns the
    engine result dict (hours, summary, objective, lp_sha256)."""
    root = _data_dir(data_dir)
    dispatch, profiles = load_data(root)
    date = scenario["date"]
    days = {d["date"] for d in profiles["days"]}
    if date not in days:
        raise ValueError(
            f"{date} is not an observed day in this data snapshot; "
            f"list_days() shows the available range"
        )
    opts = dict(scenario.get("opts") or {})
    if opts.pop("offer_mode", False):
        opts["offer_day"] = _load_offer_book(date, root)
    return run_chronology_lp(dispatch, profiles, date, opts)
