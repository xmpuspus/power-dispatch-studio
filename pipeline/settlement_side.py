#!/usr/bin/env python3
"""Derive a compact SAMPLED record of the settlement-side price families the
post-convergence build queue (Pass B) measured before deciding what to build.

Three IEMOP datasets, all hourly per-resource zips, measured on a small
sample of market days rather than built into the replay, because the
measurement decided each one:

- indicative administered prices (AP): the operator's own cost-substitute
  price per resource per interval, published as indicative on market days and
  binding during the suspension. Measured: it sits in the cost-stack regime
  on Luzon (near the P6.00 administered cost floor) and carries the same
  island premium on the corridors. A cost-regime cross-check, sampled here.
- prices used in settlement (STLPRICE): the LMP each resource is settled at,
  with the congestion component broken out. Measured: at the one-price-per-
  island granularity WESM settles at, the intra-region congestion component
  is ZERO, so there is no new settlement-side congestion receipt beyond the
  inter-island price differences the flows table already carries.
- day-ahead prices and schedules (DAP): the day-ahead projection LMP.
  Measured: it diverges from the real-time settlement in both directions and
  by a wide margin; the day-ahead run PROJECTS rather than records, so it
  stays out of the real-time replay's scope (the methodology's standing
  stance on projection series) and is reported here as a diagnostic spread.

Sampled, not full-window: AP/STLPRICE/DAP are 24 hourly zips per day like
DIPCEF (DAP alone is ~340 KB per hour), so a small representative sample
sizes each finding without a heavy backfill. The compact result is committed
under data/derived/settlement_sample.json.

    python3 pipeline/settlement_side.py --derive
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import statistics as st
import time
import zipfile
from datetime import datetime, timedelta

from archive_iemop import fetch, list_files, page_config
from offers import _ts

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "derived", "settlement_sample.json")
GRIDS = ("luzon", "visayas", "mindanao")
REGION = {"LUZON": "luzon", "CLUZ": "luzon", "VISAYAS": "visayas",
          "CVIS": "visayas", "MINDANAO": "mindanao", "CMIN": "mindanao"}
# representative market days spread across the post-resumption window
SAMPLE_DAYS = ["2026-05-20", "2026-06-05", "2026-06-15", "2026-06-25"]
SLUGS = {
    "AP": "indicative-administered-prices",
    "STL": "prices-used-in-settlement",
    "DAP": "dap-prices-and-schedules",
}


def _listing(slug: str) -> dict[str, str]:
    import base64
    pid, _ = page_config(slug)
    out = {}
    for entry in list_files(slug, pid):
        b64 = entry[0]
        out[os.path.basename(base64.b64decode(b64).decode())] = b64
    return out


def _rows(slug: str, name: str, b64: str, tmp: str) -> list[dict]:
    dest = os.path.join(tmp, name)
    if not fetch(slug, b64, dest):
        time.sleep(30)
        if not fetch(slug, b64, dest):
            raise RuntimeError(f"fetch failed: {name}")
    time.sleep(0.3)
    with zipfile.ZipFile(dest) as z:
        return list(csv.DictReader(io.TextIOWrapper(
            z.open(z.namelist()[0]), "utf-8", errors="replace")))


def _first_interval(rows: list[dict]) -> str | None:
    ivals = sorted({(r.get("TIME_INTERVAL") or "").strip()
                    for r in rows if _ts((r.get("TIME_INTERVAL") or "").strip())},
                   key=lambda s: _ts(s) or datetime.max)
    return ivals[0] if ivals else None


def _region_hourly(slug_key: str, day: str, fl: dict, tmp: str,
                   col: str, gen_only: bool = False,
                   extra: str | None = None) -> dict:
    """Per-grid list of 24 hourly means of `col` (and optionally `extra`) at
    each hour's opening interval."""
    slug = SLUGS[slug_key]
    d0 = datetime.strptime(day, "%Y-%m-%d")
    prefix = {"AP": "AP", "STL": "STLPRICE", "DAP": "DAP"}[slug_key]
    per = {g: [None] * 24 for g in GRIDS}
    per_x = {g: [None] * 24 for g in GRIDS}
    for h in range(24):
        stamp = (d0 + timedelta(hours=h + 1)).strftime("%Y%m%d%H00")
        cand = [n for n in fl if f"{prefix}_{stamp}" in n]
        if not cand:
            continue
        rows = _rows(slug, cand[0], fl[cand[0]], tmp)
        first = _first_interval(rows)
        if not first:
            continue
        # fail loud if the price column is ever renamed: a silent r.get(col)
        # would read None -> 0 and pass off an empty series as a real zero
        # (the settlement congestion component in particular reads a true 0)
        for need in (col, *( (extra,) if extra else () )):
            if need not in rows[0]:
                raise RuntimeError(f"{prefix}: column {need!r} missing; "
                                   f"header={sorted(rows[0])}")
        acc = {g: [] for g in GRIDS}
        acc_x = {g: [] for g in GRIDS}
        for r in rows:
            if (r.get("TIME_INTERVAL") or "").strip() != first:
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip().upper())
            if not g:
                continue
            if gen_only and (r.get("RESOURCE_TYPE") not in (None, "G")):
                continue
            try:
                acc[g].append(float(r.get(col)) / 1000.0)
                if extra is not None:
                    acc_x[g].append(float(r.get(extra) or 0) / 1000.0)
            except (TypeError, ValueError):
                continue
        for g in GRIDS:
            if acc[g]:
                per[g][h] = round(st.mean(acc[g]), 3)
            if extra is not None and acc_x[g]:
                per_x[g][h] = round(st.mean(acc_x[g]), 3)
    return (per, per_x) if extra is not None else per


def _dap_next_day(day: str, fl: dict, tmp: str) -> dict:
    """Day-ahead projected per-grid mean LMP for `day`, from the projection
    run posted the prior evening (one DAP file projects the whole next day)."""
    d0 = datetime.strptime(day, "%Y-%m-%d")
    prev = (d0 - timedelta(days=1)).strftime("%Y%m%d")
    cand = sorted(n for n in fl if f"DAP_{prev}23" in n)
    if not cand:
        return {g: None for g in GRIDS}
    rows = _rows("DAP", cand[0], fl[cand[0]], tmp)
    acc = {g: [] for g in GRIDS}
    for r in rows:
        g = REGION.get((r.get("REGION_NAME") or "").strip().upper())
        if not g or (r.get("RESOURCE_TYPE") not in (None, "G")):
            continue
        try:
            acc[g].append(float(r.get("LMP")) / 1000.0)
        except (TypeError, ValueError):
            continue
    return {g: (round(st.mean(v), 3) if v else None) for g, v in acc.items()}


def derive() -> dict:
    import tempfile
    fl = {k: _listing(v) for k, v in SLUGS.items()}
    days = []
    with tempfile.TemporaryDirectory() as tmp:
        for day in SAMPLE_DAYS:
            ap = _region_hourly("AP", day, fl["AP"], tmp, "ADMIN_LMP",
                                gen_only=True)
            stl, stlc = _region_hourly("STL", day, fl["STL"], tmp, "LMP",
                                       extra="LMP_CONGESTION")
            dap = _dap_next_day(day, fl["DAP"], tmp)
            days.append({
                "date": day,
                "admin_lmp": {g: _mean(ap[g]) for g in GRIDS},
                "settlement_lmp": {g: _mean(stl[g]) for g in GRIDS},
                "settlement_congestion": {g: _mean(stlc[g]) for g in GRIDS},
                "dap_lmp": dap,
                "dap_vs_rt_spread": {
                    g: (round(dap[g] - _mean(stl[g]), 3)
                        if dap[g] is not None and _mean(stl[g]) is not None
                        else None) for g in GRIDS},
            })
            print(f"derived sample {day}", flush=True)
    return {
        "sample_days": SAMPLE_DAYS,
        "days": days,
        "note": ("Sampled settlement-side price families (Pass B measure "
                 "record). admin_lmp is the mean generator-node indicative "
                 "administered price (AP), the operator's cost-substitute "
                 "price; settlement_lmp the mean settled LMP (STLPRICE); "
                 "settlement_congestion its congestion component (zero at the "
                 "one-price-per-island granularity WESM settles at); dap_lmp "
                 "the day-ahead projection mean and dap_vs_rt_spread its "
                 "signed gap to the settled price. Daily means over a small "
                 "market-day sample: these families were measured, not built "
                 "into the replay (administered prices are cost-substitute "
                 "counterfactuals, the settlement congestion component is "
                 "empty at regional granularity, and the day-ahead run is a "
                 "projection, out of the real-time replay's scope)."),
        "src_admin": ("https://www.iemop.ph/market-data/"
                      "indicative-administered-prices/"),
        "src_settlement": ("https://www.iemop.ph/market-data/"
                           "prices-used-in-settlement/"),
        "src_dayahead": ("https://www.iemop.ph/market-data/"
                         "dap-prices-and-schedules/"),
    }


def _mean(vals: list) -> float | None:
    v = [x for x in vals if x is not None]
    return round(st.mean(v), 3) if v else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}")
    else:
        print(__doc__)
