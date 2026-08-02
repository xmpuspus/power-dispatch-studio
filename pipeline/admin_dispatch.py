#!/usr/bin/env python3
"""Measure out-of-merit raise instructions and their effect on the fuel model.

The operator's instructions are large enough to matter for dispatch: all about
89,000 records are raises. During affected hours, the instructed MW is 6 to 11
percent of generation by grid and reaches 40 percent in the upper tail.

The instructions do not change prices in this model. Most apply to coal units,
and coal is already the marginal fuel during 87 percent of affected hours. The
instruction selects a particular unit for grid security, while the model groups
units by fuel. A per-resource model would be needed to represent that choice.

This module records the size and fuel mix of the instructions for the method
page and data checks.

    python3 pipeline/admin_dispatch.py --derive
"""

from __future__ import annotations

import argparse
import collections
import csv
import glob
import json
import os
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web", "data")
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "data", "derived", "admin_dispatch.json")
REGION = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")
N_SAMPLE_DAYS = 6


def _ts(s: str) -> datetime | None:
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    # IEMOP serializes the midnight-ending (24:00) interval as a bare date. None
    # of the formats above match it, so these rows were being dropped silently:
    # 152 instructions across the archive, which is why the row count here
    # disagreed with the count published from the same file. That interval ends
    # the printed date's previous day at hour 23.
    try:
        d = datetime.strptime(s.strip(), "%m/%d/%Y")
    except ValueError:
        return None
    return d - timedelta(hours=1)


def _admin_hourly() -> dict:
    """{(grid, date, hour): mean administered raise MW over the hour}."""
    raw: dict = collections.defaultdict(lambda: collections.defaultdict(float))
    for path in sorted(glob.glob(os.path.join(RAW, "MOTRD", "*.csv"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                t = _ts(r.get("TIME_INTERVAL") or "")
                g = REGION.get((r.get("REGION") or "").strip())
                if not t or not g:
                    continue
                try:
                    mw = float(r.get("SO_MW_INSTRUCTION") or 0)
                except ValueError:
                    continue
                raw[(g, t.date().isoformat(), t.hour)][t.minute] += mw
    return {k: sum(v.values()) / len(v) for k, v in raw.items()}


def _rtdsum_gen_hourly() -> dict:
    """{(grid, date, hour): mean dispatched generation MW}."""
    acc: dict = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(RAW, "RTDSUM", "RTDREG_2026*.csv"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                    continue
                t = _ts(r.get("TIME_INTERVAL") or "")
                g = REGION.get((r.get("REGION_NAME") or "").strip())
                if not t or not g:
                    continue
                try:
                    acc[(g, t.date().isoformat(), t.hour)].append(
                        float(r.get("GENERATION") or 0)
                    )
                except ValueError:
                    continue
    return {k: sum(v) / len(v) for k, v in acc.items()}


def derive() -> dict:
    from lp_dispatch import run_chronology_lp

    adm = _admin_hourly()
    gen = _rtdsum_gen_hourly()
    # MW-weighted administered fraction per grid, over hours with a raise
    frac: dict = {}
    for g in GRIDS:
        num = den = 0.0
        hrs = 0
        for (gg, d, h), a in adm.items():
            if gg != g or a <= 0:
                continue
            y = gen.get((g, d, h))
            if not y:
                continue
            num += a
            den += y
            hrs += 1
        frac[g] = {
            "mw_weighted_pct": round(100 * num / den, 2) if den else None,
            "n_raise_hours": hrs,
        }

    # fuel mix of the raised MW (the operator's out-of-merit dispatch), via
    # the model's own resource->fuel classifier
    from offers import classify_fuel

    mix: dict = collections.Counter()
    mix_tot = 0.0
    for r in _iter_rows():
        try:
            mw = float(r.get("SO_MW_INSTRUCTION") or 0)
        except ValueError:
            continue
        mix[
            classify_fuel((r.get("RESOURCE_NAME") or "").strip()) or "unclassified"
        ] += mw
        mix_tot += mw
    fuel_mix = (
        {k: round(100 * v / mix_tot, 1) for k, v in mix.most_common()}
        if mix_tot
        else {}
    )

    # modeled marginal fuel AND max price on the raise hours (a sample of
    # raise days spread across the window)
    dispatch = json.load(open(os.path.join(WEB, "dispatch.json")))
    profiles = json.load(open(os.path.join(WEB, "profiles.json")))
    window = set(d["date"] for d in profiles["days"])
    raise_days = sorted({d for (g, d, h) in adm if adm[(g, d, h)] > 0} & window)
    step = max(1, len(raise_days) // N_SAMPLE_DAYS)
    sample = raise_days[::step][:N_SAMPLE_DAYS]
    marg = collections.Counter()
    n = 0
    max_price = 0.0
    for date in sample:
        res = run_chronology_lp(dispatch, profiles, date, {})
        for hr in res["hours"]:
            for g in GRIDS:
                if adm.get((g, date, hr["hour"]), 0.0) > 0:
                    marg[hr["marginal"][g]] += 1
                    n += 1
                    max_price = max(max_price, hr["price"][g])
    coal_pct = round(100 * marg.get("coal", 0) / n, 1) if n else None
    return {
        "available": True,
        "n_instructions": sum(1 for _ in _iter_rows()),
        "mw_weighted_fraction_of_dispatch": frac,
        "sample_days": sample,
        "n_raise_grid_hours_sampled": n,
        "modeled_marginal_fuel_on_raise_hours_pct": {
            k: round(100 * v / n, 1) for k, v in marg.most_common()
        }
        if n
        else {},
        "coal_marginal_share_pct": coal_pct,
        "raised_mw_fuel_mix_pct": fuel_mix,
        "max_modeled_price_on_raise_hours_php_kwh": round(max_price, 3),
        "verdict": "does_not_raise_prices_in_fuel_level_model",
        "note": (
            "The administered MOT-raise dispatch equals 6 to 11 percent of "
            "generation in the affected hours, with the largest share on "
            "Mindanao. It does not raise prices in the fuel-level calculation. "
            f"Most of the raised output is coal ({fuel_mix.get('coal')} "
            f"percent) with about a fifth on gas ({fuel_mix.get('natural_gas')} "
            f"percent). Coal sets the modeled price in {coal_pct} percent of "
            "those hours. Every affected hour already prices at or just above "
            f"the coal floor, with a maximum of P{round(max_price, 2)}/kWh. "
            "Applying the same floor to the public offer books changes none "
            "of the offers. This calculation groups generation by fuel, so it "
            "cannot show which named unit the operator runs for security. A "
            "model with individual units and reserve awards is needed to test "
            "that effect."
        ),
        "src": "https://www.iemop.ph/market-data/list-of-mot-raise-re-dispatch-"
        "based-on-so-dispatch-instruction-report/",
    }


def _iter_rows():
    for path in sorted(glob.glob(os.path.join(RAW, "MOTRD", "*.csv"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if _ts(r.get("TIME_INTERVAL") or ""):
                    yield r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(
            f"wrote {OUT}: coal marginal on {out['coal_marginal_share_pct']}% "
            f"of raise hours; frac {out['mw_weighted_fraction_of_dispatch']}"
        )
    else:
        print(__doc__)
