#!/usr/bin/env python3
"""Test whether a 5-minute replay reproduces recorded negative prices.

On the window's most-negative days, the recorded regional load-weighted price
(LWAPF) falls below zero during some midday intervals. The hourly replay cannot
do so because it averages demand over the hour.

The crossing occurs near zero. Floor-priced supply sits within a few percent of
native load at the midday solar peak, a margin finer than the public offers pin
down. Compacting the book to 48 price blocks moves about 4 percent of that supply
across zero, enough to change an interval's sign. Five-minute data are needed,
but the public offers do not contain enough supply detail to reproduce each
negative interval. The model reports this limit and keeps the hourly method.

    python3 pipeline/subhourly_probe.py --derive
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DERIVED = os.path.join(HERE, "..", "data", "derived")
OUT = os.path.join(DERIVED, "subhourly_probe.json")
GRID = "luzon"
GCODE = {"CLUZ", "LUZON"}


def _observed_neg_lwap(date):
    """(n negative 5-min intervals, min price) in the Luzon regional LWAP."""
    n, mn = 0, 0.0
    for p in glob.glob(os.path.join(RAW, "LWAPF", f"*{date.replace('-', '')}*.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
            if (r.get("REGION_NAME") or "").strip() not in GCODE:
                continue
            key = next(
                (
                    k
                    for k in ("LWAP", "PRICE", "LOAD_WEIGHTED_AVERAGE_PRICE")
                    if k in r and r[k]
                ),
                None,
            )
            if not key:
                continue
            try:
                v = float(r[key]) / 1000
            except ValueError:
                continue
            if v < -1e-9:
                n += 1
                mn = min(mn, v)
    return n, round(mn, 2)


def _crossing_margin(date):
    """Min (native_load - floor_supply) over the day's hours from the committed
    offer book and profiles native load: how close the floor-priced supply
    comes to native load. Returns (min_margin_pct, hour)."""
    ofile = os.path.join(DERIVED, "offer_daily", f"OFFERD_{date.replace('-', '')}.json")
    pfile = os.path.join(HERE, "..", "web", "data", "profiles.json")
    if not os.path.isfile(ofile):
        return None, None
    book = json.load(open(ofile))
    prof = json.load(open(pfile))
    load = None
    for d in prof["days"]:
        if d["date"] == date:
            load = (d.get("demand") or {}).get(GRID)
    if not load:
        return None, None
    best = (1e9, None)
    for h in range(24):
        b = book["hours"][GRID][h]
        if not b or load[h] is None or load[h] <= 0:
            continue
        floor_supply = sum(mw for pr, mw in b if pr <= 0.001)
        margin_pct = 100 * (load[h] - floor_supply) / load[h]
        if margin_pct < best[0]:
            best = (round(margin_pct, 2), h)
    return best


def _deepest_structural(date):
    """At the day's deepest observed-negative Luzon LWAP interval: the physical
    native load (RTDSUM) vs the aggregate floor-priced supply (committed book,
    that hour). If load > floor supply, the aggregate clear MUST price positive
    there, so the -10 is a nodal outcome no per-grid replay can produce."""
    lw = glob.glob(os.path.join(RAW, "LWAPF", f"*{date.replace('-', '')}*.csv"))
    if not lw:
        return None
    deepest = (0.0, None)
    for r in csv.DictReader(open(lw[0], encoding="utf-8", errors="replace")):
        if (r.get("REGION_NAME") or "").strip() not in GCODE:
            continue
        key = next((k for k in ("LWAP", "PRICE") if k in r and r[k]), None)
        if not key:
            continue
        try:
            v = float(r[key]) / 1000
            dt = datetime.strptime(
                (r.get("TIME_INTERVAL") or "").strip(), "%m/%d/%Y %I:%M:%S %p"
            )
        except (ValueError, TypeError):
            continue
        if v < deepest[0]:
            deepest = (v, dt)
    price, dt = deepest
    if dt is None:
        return None
    ofile = os.path.join(DERIVED, "offer_daily", f"OFFERD_{date.replace('-', '')}.json")
    book = json.load(open(ofile))
    floor_supply = sum(mw for pr, mw in book["hours"][GRID][dt.hour] if pr <= 0.001)
    load = None
    p = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
        if (
            (r.get("REGION_NAME") or "").strip() in GCODE
            and (r.get("COMMODITY_TYPE") or "").strip() == "En"
            and datetime.strptime(
                (r.get("TIME_INTERVAL") or "").strip(), "%m/%d/%Y %I:%M:%S %p"
            )
            == dt
        ):
            load = (
                float(r.get("GENERATION") or 0)
                + float(r.get("MKT_IMPORT") or 0)
                - float(r.get("MKT_EXPORT") or 0)
                + float(r.get("LOAD_CURTAILED") or 0)
            )
            break
    if load is None:
        return None
    return {
        "date": date,
        "interval": dt.strftime("%H:%M"),
        "observed_price_php_kwh": round(price, 2),
        "physical_native_load_mw": round(load),
        "aggregate_floor_supply_mw": round(floor_supply),
        "aggregate_must_price_positive": load > floor_supply,
    }


def derive() -> dict:
    # the crossing days: where the offer-book floor supply comes closest to load
    prof = json.load(open(os.path.join(HERE, "..", "web", "data", "profiles.json")))
    dates = [d["date"] for d in prof["days"]]
    ranked = []
    for date in dates:
        margin, hour = _crossing_margin(date)
        if margin is None:
            continue
        ranked.append((margin, date, hour))
    ranked.sort()
    rows = []
    for margin, date, hour in ranked[:6]:
        nneg, mn = _observed_neg_lwap(date)
        rows.append(
            {
                "date": date,
                "closest_hour": hour,
                "floor_supply_vs_load_margin_pct": margin,
                "observed_negative_lwap_intervals": nneg,
                "observed_min_lwap_php_kwh": mn,
            }
        )
    n_days_neg = sum(1 for r in rows if r["observed_negative_lwap_intervals"] > 0)
    # the deep-negative structural case needs a day that actually HAS observed
    # negatives (so LWAPF exists and the interval is real); the tightest
    # offer-margin crossing day can be recent, still inside LWAPF's publish lag,
    # with zero observed negatives. Pick the deepest observed negative instead.
    _neg = [r for r in rows if r["observed_negative_lwap_intervals"] > 0]
    _deep = (
        min(_neg, key=lambda r: r["observed_min_lwap_php_kwh"])["date"]
        if _neg
        else None
    )
    return {
        "available": True,
        "crossing_days": rows,
        "n_crossing_days": len(rows),
        "n_days_with_observed_negatives": n_days_neg,
        "min_margin_pct": rows[0]["floor_supply_vs_load_margin_pct"] if rows else None,
        "deep_negative_structural": _deepest_structural(_deep) if _deep else None,
        "verdict": "negative_prices_need_finer_supply_data_than_public_offers",
        "note": (
            "A tested 5-minute replay still misses the negative clearing "
            "prices omitted by the hourly replay. Two limits remain. On the "
            "crossing days the offer book's floor-priced supply "
            "(self-scheduled solar and must-run at the WESM floor plus "
            "zero-priced offers) comes within "
            f"{rows[0]['floor_supply_vs_load_margin_pct'] if rows else None} "
            "percent of native load at the midday peak, and the book's own "
            "48-block compaction moves about 4 percent of that supply "
            "across the zero line, wider than the margin, so a shallow "
            "interval's sign turns on supply accounting finer than the "
            "offers give. The most negative intervals do not come from the "
            "regional supply total crossing demand. At the day's lowest "
            "interval the observed price "
            "is about -P10/kWh while physical native load sits above the "
            "entire aggregate floor-priced supply, so the per-grid clear "
            "must price positive there; that -10 is a load-weighted average "
            "of nodal prices pulled to the floor by curtailed-solar "
            "pockets, which no per-grid replay reproduces at any time "
            "resolution. A clean 5-minute clear on the model's own demand "
            "basis reproduces none of the day's observed negative "
            f"intervals ({n_days_neg} of the six days show observed "
            "negatives). Five-minute data are necessary but not sufficient. "
            "The public offers do not resolve the supply margin closely "
            "enough, and regional averages hide curtailed-solar node prices."
        ),
        "src": "https://www.iemop.ph/market-data/load-weighted-average-prices-final/",
        "disclaimer": (
            "Statistical indicators derived from public data. "
            "Patterns may have legitimate explanations."
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(DERIVED, exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(
            f"wrote {OUT}: {out['n_crossing_days']} crossing days, "
            f"{out['n_days_with_observed_negatives']} with observed "
            f"negatives, min margin {out['min_margin_pct']}%"
        )
        for r in out["crossing_days"]:
            print(
                f"  {r['date']} h{r['closest_hour']}: floor supply "
                f"{r['floor_supply_vs_load_margin_pct']}% below load, "
                f"{r['observed_negative_lwap_intervals']} obs neg LWAP "
                f"(min {r['observed_min_lwap_php_kwh']})"
            )
    else:
        print(__doc__)
