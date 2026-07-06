#!/usr/bin/env python3
"""Bake the WESM Reserve Market layer from IEMOP RTD reserve schedules (RTDRS).

The studio's merit order clears ENERGY only. The real WESM market co-optimises
energy and reserves in real-time dispatch: a generator scheduled to hold reserve
is not available to sell energy, and in a tight hour the reserve clearing price
spikes alongside the energy price. The energy-only stack cannot see that cost
layer. This bakes the observed reserve clearing prices, per grid and per reserve
category, from IEMOP's public RTD Reserve Schedule files so the studio can show
what the energy-only view leaves out.

NOT PLEXOS, and not a model: these are the operator's own published reserve
clearing prices (PhP/MWh -> PhP/kWh) over a sample of recent days.

The WESM Reserve Market ran full commercial operations from 26 January 2024, with
three reserve products (Frequency Control Ancillary Services): Regulation, Contingency,
and Dispatchable (definitions sourced, see below). The RTD reserve schedule tags each
row with a commodity CODE (Ru, Rd, Dr, Fr). IEMOP does not publish a code->product key
on the dataset page, so the mapping here is INFERRED from the sourced product
definitions and corroborated by the scheduled quantities, not asserted as sourced:
  - Ru / Rd = Regulation (up / down): small (~285 MW each) and dear, the profile of
    the frequency-regulation product that corrects moment-to-moment deviations.
  - Dr = Dispatchable: cheapest and large, the reserve that replenishes contingency.
  - Fr = Contingency: ~890 MW, close to the largest single contingency on the grid
    (a 647 MW Sual unit plus margin), the reserve held to cover the loss of the
    biggest unit. This last code is the least certain and is labelled as inferred in
    the baked output.
Sources (three-product structure and definitions; commercial-ops date):
  https://www.iemop.ph/news/iemop-commences-the-full-commercial-operations-of-reserve-market/
  https://www.iemop.ph/market-data/rtd-reserve-schedule/  (the RTDRS dataset)
"""
from __future__ import annotations

import csv
import glob
import os
import re
from collections import defaultdict
from statistics import mean

HERE = os.path.dirname(os.path.abspath(__file__))
RTDRS_DIR = os.path.join(HERE, "..", "data", "raw", "RTDRS")

# IEMOP region code -> our grid key.
REGION_GRID = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}

# RTD reserve schedule commodity code -> (category key, human label, mapping basis).
# The three published products are Regulation (up/down), Contingency, and
# Dispatchable. The code->product mapping is inferred (see module docstring): the
# regulation and dispatchable reads are well corroborated; the contingency code is
# the least certain and is flagged as such in the output.
COMMODITY = {
    "Ru": ("regulation_up", "Regulation (up)", "inferred_corroborated"),
    "Rd": ("regulation_down", "Regulation (down)", "inferred_corroborated"),
    "Fr": ("contingency", "Contingency", "inferred"),
    "Dr": ("dispatchable", "Dispatchable", "inferred_corroborated"),
}

# The reserve offer cap is PhP25,000/MWh (PhP25/kWh) in this window; a clearing
# price at the cap is a scarcity print, the reserve analogue of an energy price cap.
RESERVE_CAP_PHP_KWH = 25.0


def _sample_days(files: list[str]) -> list[str]:
    days = []
    for p in files:
        m = re.search(r"(\d{8})", os.path.basename(p))
        if m:
            d = m.group(1)
            days.append(f"{d[:4]}-{d[4:6]}-{d[6:]}")
    return sorted(set(days))


def build_reserve() -> dict:
    files = sorted(glob.glob(os.path.join(RTDRS_DIR, "*.csv")))
    if not files:
        return {"available": False,
                "note": "RTDRS reserve schedules absent; run "
                        "pipeline/archive_iemop.py --backfill --only RTDRS "
                        "--sample-days 3"}

    # price rows (PhP/kWh) per (grid, category); scheduled MW per (interval, grid,
    # category) so a system MW can be averaged over intervals.
    price = defaultdict(list)
    price_cat = defaultdict(list)
    sched = defaultdict(float)
    intervals = set()
    for path in files:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                code = row.get("COMMODITY_TYPE")
                cat = COMMODITY.get(code)
                grid = REGION_GRID.get(row.get("REGION_NAME", ""))
                if not cat or not grid:
                    continue
                try:
                    p_kwh = float(row["PRICE"]) / 1000.0
                    mw = float(row["SCHED_MW"])
                except (ValueError, KeyError):
                    continue
                iv = row.get("TIME_INTERVAL", "")
                intervals.add(iv)
                catkey = cat[0]
                price[(grid, catkey)].append(p_kwh)
                price_cat[catkey].append(p_kwh)
                sched[(iv, grid, catkey)] += mw

    # mean scheduled system MW per interval, per category (sum across grids first)
    per_iv_cat = defaultdict(lambda: defaultdict(float))
    per_iv_grid_cat = defaultdict(lambda: defaultdict(float))
    for (iv, grid, catkey), mw in sched.items():
        per_iv_cat[iv][catkey] += mw
        per_iv_grid_cat[(iv, grid)][catkey] += mw
    sys_mw = defaultdict(list)
    for iv, cd in per_iv_cat.items():
        for catkey, mw in cd.items():
            sys_mw[catkey].append(mw)
    grid_mw = defaultdict(list)
    for (iv, grid), cd in per_iv_grid_cat.items():
        for catkey, mw in cd.items():
            grid_mw[(grid, catkey)].append(mw)

    def stats(vals: list[float]) -> dict:
        return {
            "mean_php_kwh": round(mean(vals), 3),
            "min_php_kwh": round(min(vals), 3),
            "max_php_kwh": round(max(vals), 3),
            "cap_hit_pct": round(
                100 * sum(1 for v in vals if v >= RESERVE_CAP_PHP_KWH - 0.1) / len(vals), 1),
        }

    categories = []
    for code, (catkey, label, basis) in COMMODITY.items():
        vals = price_cat.get(catkey)
        if not vals:
            continue
        s = stats(vals)
        categories.append({
            "code": code,
            "category": catkey,
            "label": label,
            "code_mapping": basis,
            **s,
            "mean_system_mw": round(mean(sys_mw[catkey])) if sys_mw[catkey] else 0,
        })
    # order by mean price, dearest first (the scarce products lead)
    categories.sort(key=lambda c: -c["mean_php_kwh"])

    by_grid = {}
    for grid in ("luzon", "visayas", "mindanao"):
        rows = []
        for code, (catkey, label, _basis) in COMMODITY.items():
            vals = price.get((grid, catkey))
            if not vals:
                continue
            rows.append({
                "code": code,
                "category": catkey,
                "label": label,
                "mean_php_kwh": round(mean(vals), 3),
                "mean_mw": round(mean(grid_mw[(grid, catkey)]))
                if grid_mw[(grid, catkey)] else 0,
            })
        rows.sort(key=lambda r: -r["mean_php_kwh"])
        by_grid[grid] = rows

    # scarcity headline: the dearest reserve product's mean vs its top-decile mean
    lead = categories[0]["category"] if categories else None
    scarcity = {}
    if lead:
        lead_vals = sorted(price_cat[lead], reverse=True)
        top = lead_vals[: max(1, len(lead_vals) // 10)]
        scarcity = {
            "category": lead,
            "label": next(c["label"] for c in categories if c["category"] == lead),
            "mean_php_kwh": round(mean(lead_vals), 3),
            "top_decile_mean_php_kwh": round(mean(top), 3),
        }

    return {
        "available": True,
        "commercial_since": "2024-01-26",
        "sample_days": _sample_days(files),
        "n_intervals": len(intervals),
        "reserve_cap_php_kwh": RESERVE_CAP_PHP_KWH,
        "categories": categories,
        "by_grid": by_grid,
        "scarcity": scarcity,
        "mapping_note": "The three reserve products (Regulation, Contingency, "
                        "Dispatchable) and their definitions are sourced to IEMOP. "
                        "IEMOP does not publish a code key on the dataset, so the RTD "
                        "schedule commodity codes (Ru/Rd regulation, Dr dispatchable, "
                        "Fr contingency) are mapped by inference from those "
                        "definitions and the scheduled quantities: contingency clears "
                        "about 890 MW, close to the largest single unit it must cover.",
        "note": "The WESM Reserve Market co-optimises energy and reserves in "
                "real-time dispatch: a unit holding reserve cannot also sell that "
                "MW as energy, and in a tight hour the reserve clearing price "
                "spikes with the energy price. The studio's merit order clears "
                "energy only, so it does not price this layer. These are the "
                "operator's own published RTD reserve clearing prices over a "
                "sample of recent days, not a model output.",
        "disclaimer": "Statistical indicators derived from public data. Patterns "
                      "may have legitimate explanations.",
        "src_market": "https://www.iemop.ph/news/iemop-commences-the-full-commercial-operations-of-reserve-market/",
        "src_data": "https://www.iemop.ph/market-data/rtd-reserve-schedule/",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_reserve(), indent=1))
