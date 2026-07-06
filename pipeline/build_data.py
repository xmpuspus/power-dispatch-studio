#!/usr/bin/env python3
"""Bake gridbill-ph web/data/ from the IEMOP archive + verified constants.

Compute before narrate: every number the site shows is either computed here from
archived IEMOP files (data/raw/) or a labeled constant with a primary source in
pipeline/constants_ph.py. The frontend reads only the baked artifacts, so copy
can never drift from the data.

Schemas (verified against fetched files, 2026-07-05):
  RTDCV/DAPCV: RUN_TIME, MKT_TYPE, TIME_INTERVAL, CONGEST_TYPE, RUN_TYPE,
               EQUIPMENT_NAME, STATION_NAME, VOLTAGE_LEVEL, BINDING_LIMIT,
               MW_FLOW, OVERLOAD_MW, PCT_MW
  RTDSUM:      RUN_TIME, MKT_TYPE, TIME_INTERVAL, REGION_NAME(CLUZ/CVIS/CMIN),
               COMMODITY_TYPE(En/Dr/Fr/Ru/Rd), MKT_REQT, LOAD_BID,
               LOAD_CURTAILED, LOSSES, GENERATION, MKT_IMPORT, MKT_EXPORT
  LWAPF:       RUN_TIME, MKT_TYPE, TIME_INTERVAL, REGION_NAME, LWAP (PhP/MWh)
  DIPCEF:      zips of TIME_INTERVAL, REGION_NAME(LUZON/...), RESOURCE_NAME,
               PRICING_FLAG, LMP, SCHED_MW, LMP_SMP, LMP_LOSS, LMP_CONGESTION
Parsers fail LOUDLY (header printed) on drift; a missing dataset degrades that
layer with an explicit note in meta.json instead of inventing values.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from constants_ph import (
    CHOKEPOINTS,
    DC_SITES,
    DEMAND_ANCHORS,
    MARKET_ANCHORS,
    SUAL,
)

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "web", "data")

REGION_MAP = {"CLUZ": "LUZON", "CVIS": "VISAYAS", "CMIN": "MINDANAO",
              "LUZON": "LUZON", "VISAYAS": "VISAYAS", "MINDANAO": "MINDANAO"}
GRIDS = ["LUZON", "VISAYAS", "MINDANAO"]
RESERVE_COMMODITIES = {"Dr", "Fr", "Ru", "Rd"}

NOTES: list[str] = []


def rows_of(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip()
                                                    for v in r.values())]


def dataset_files(key: str) -> list[str]:
    d = os.path.join(RAW, key)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, n) for n in os.listdir(d)
                  if not n.startswith("."))


def assert_cols(path: str, rows: list[dict], needed: set[str]) -> None:
    if not rows:
        return
    missing = needed - set(rows[0])
    if missing:
        raise SystemExit(f"SCHEMA DRIFT in {os.path.basename(path)}: "
                         f"missing {sorted(missing)}; header={sorted(rows[0])}")


def day_of(name: str) -> str:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# --- congestion league (RTDCV + DAPCV) -----------------------------------------
# RTDCV rows are 5-minute real-time dispatch intervals: time at the limit.
# DAPCV rows are HOURLY day-ahead intervals, and the DAP re-runs through the day
# (the same equipment-hour can appear up to ~23 times), so raw DAP row counts
# measure re-run persistence, not time at the limit. The league therefore keeps
# the two markets apart (rtd_intervals vs dap_rows/dap_days) and RANKS BY DAYS,
# which a re-run cannot inflate (a day counts once).

def build_congestion() -> dict:
    league: dict[tuple, dict] = {}
    days_seen: set[str] = set()
    base_days: set[str] = set()
    corridors = {c["id"]: {
        "days": set(), "rtd_intervals": 0, "rtd_days": set(),
        "dap_rows": 0, "dap_days": set(), "max_overload_mw": 0.0,
        "matched": defaultdict(int),
    } for c in CHOKEPOINTS if c.get("equipment_match")}

    def corridor_ids(name: str) -> list[str]:
        out = []
        for c in CHOKEPOINTS:
            for pat in c.get("equipment_match", []):
                if name == pat or name.startswith(pat):
                    out.append(c["id"])
                    break
        return out

    for key in ("RTDCV", "DAPCV"):
        for path in dataset_files(key):
            day = day_of(path)
            rows = rows_of(path)
            assert_cols(path, rows, {"EQUIPMENT_NAME", "STATION_NAME",
                                     "CONGEST_TYPE", "PCT_MW"})
            days_seen.add(day)
            for r in rows:
                name = (r.get("EQUIPMENT_NAME") or "").strip()
                if not name:
                    continue
                eq = (name, (r.get("STATION_NAME") or "").strip(),
                      (r.get("VOLTAGE_LEVEL") or "").strip())
                e = league.setdefault(eq, {
                    "equipment": eq[0], "station": eq[1], "voltage": eq[2],
                    "days": set(), "rtd_intervals": 0, "rtd_days": set(),
                    "dap_rows": 0, "dap_days": set(),
                    "base_case_rows": 0, "max_overload_mw": 0.0,
                })
                e["days"].add(day)
                if key == "RTDCV":
                    e["rtd_intervals"] += 1
                    e["rtd_days"].add(day)
                else:
                    e["dap_rows"] += 1
                    e["dap_days"].add(day)
                if (r.get("CONGEST_TYPE") or "").strip().upper() == "BASE CASE":
                    e["base_case_rows"] += 1
                    base_days.add(day)
                ov = f(r.get("OVERLOAD_MW"))
                e["max_overload_mw"] = max(e["max_overload_mw"], ov)
                for cid in corridor_ids(name):
                    c = corridors[cid]
                    c["days"].add(day)
                    c["matched"][name] += 1
                    if key == "RTDCV":
                        c["rtd_intervals"] += 1
                        c["rtd_days"].add(day)
                    else:
                        c["dap_rows"] += 1
                        c["dap_days"].add(day)
                    c["max_overload_mw"] = max(c["max_overload_mw"], ov)
    out = []
    for e in league.values():
        e["days"] = len(e["days"])
        e["rtd_days"] = len(e["rtd_days"])
        e["dap_days"] = len(e["dap_days"])
        e["max_overload_mw"] = round(e["max_overload_mw"], 2)
        out.append(e)
    out.sort(key=lambda e: (-e["days"], -e["rtd_intervals"], -e["dap_rows"],
                            e["equipment"]))
    days = sorted(d for d in days_seen if d)
    if not days:
        NOTES.append("RTDCV/DAPCV absent; congestion league unavailable")
    receipts = {}
    for cid, c in corridors.items():
        receipts[cid] = {
            "days": len(c["days"]), "rtd_intervals": c["rtd_intervals"],
            "rtd_days": len(c["rtd_days"]), "dap_rows": c["dap_rows"],
            "dap_days": len(c["dap_days"]),
            "max_overload_mw": round(c["max_overload_mw"], 2),
            "matched_equipment": [
                {"name": k, "rows": v} for k, v in
                sorted(c["matched"].items(), key=lambda kv: -kv[1])],
        }
    return {
        "window": {"from": days[0], "to": days[-1]} if days else None,
        "days_covered": len(days),
        "days_with_base_case_binding": len(base_days),
        "distinct_equipment": len(out),
        "total_rtd_intervals": sum(e["rtd_intervals"] for e in out),
        "total_dap_rows": sum(e["dap_rows"] for e in out),
        "league": out[:30],
        "corridor_receipts": receipts,
    }


# --- reliability from RTDSUM: demand, curtailment, reserve slack ----------------

def build_reliability() -> dict:
    files = dataset_files("RTDSUM")
    if not files:
        NOTES.append("RTDSUM absent; reliability panel uses report anchors only")
        return {}
    peak: dict[tuple, float] = defaultdict(float)
    curtailed: dict[tuple, float] = defaultdict(float)     # MW*interval
    slack_min: dict[tuple, float] = {}
    shortfall_intervals: dict[tuple, int] = defaultdict(int)
    days_set: set[str] = set()
    for path in files:
        day = day_of(path)
        rows = rows_of(path)
        assert_cols(path, rows, {"REGION_NAME", "COMMODITY_TYPE", "LOAD_BID",
                                 "LOAD_CURTAILED", "GENERATION", "MKT_REQT"})
        days_set.add(day)
        for r in rows:
            grid = REGION_MAP.get(((r.get("REGION_NAME") or "").strip()))
            if not grid:
                continue
            com = (r.get("COMMODITY_TYPE") or "").strip()
            if com == "En":
                peak[(day, grid)] = max(peak[(day, grid)], f(r["LOAD_BID"]))
                curtailed[(day, grid)] += f(r["LOAD_CURTAILED"])
            elif com in RESERVE_COMMODITIES:
                slack = f(r["GENERATION"]) - f(r["MKT_REQT"])
                k = (day, grid)
                slack_min[k] = min(slack_min.get(k, slack), slack)
                if slack < 0:
                    shortfall_intervals[k] += 1
    days = sorted(days_set)
    series = {}
    for grid in GRIDS:
        # LOAD_BID in the RTD regional summary is bid-in load (hundreds of MW),
        # NOT grid peak demand; it is kept for reference but never displayed as
        # "peak demand". LOAD_CURTAILED is curtailment in the dispatch schedule.
        series[grid.lower()] = [{
            "date": day,
            "load_bid_peak_mw": round(peak.get((day, grid), 0), 1),
            "curtailed_mwh": round(curtailed.get((day, grid), 0) * 5 / 60, 2),
            "reserve_slack_min_mw": round(slack_min.get((day, grid), 0), 1),
            "reserve_shortfall_intervals": shortfall_intervals.get((day, grid), 0),
        } for day in days]
    totals = {}
    for grid in GRIDS:
        rows_ = series[grid.lower()]
        curt_days = [r for r in rows_ if r["curtailed_mwh"] > 0]
        short_days = [r for r in rows_ if r["reserve_shortfall_intervals"] > 0]
        totals[grid.lower()] = {
            "days": len(rows_),
            "curtailment_days": len(curt_days),
            "curtailed_mwh_total": round(sum(r["curtailed_mwh"] for r in rows_), 1),
            "worst_curtailment": max(curt_days, key=lambda r: r["curtailed_mwh"],
                                     default=None),
            "reserve_shortfall_days": len(short_days),
            "median_daily_min_reserve_slack_mw": round(median(
                [r["reserve_slack_min_mw"] for r in rows_]), 1) if rows_ else None,
        }
    return {"dates": days, "series": series, "totals": totals}


# --- price vs load (RTDSUM GENERATION joined to LWAPF price) ---------------------
# The honest load axis is dispatched generation (thousands of MW, grid scale), NOT
# LOAD_BID (bid-in incremental load, near zero). Joined per 5-minute interval to the
# load-weighted price. Produces the price-as-a-shape relationship and one
# representative day's demand-and-price curve, both from the archive.

def build_price_load() -> dict:
    lwf = dataset_files("LWAPF")
    rtf = dataset_files("RTDSUM")
    if not lwf or not rtf:
        NOTES.append("LWAPF or RTDSUM absent; price-vs-load layer omitted")
        return {}
    price_by_day: dict[str, dict[tuple, float]] = {}
    for path in lwf:
        day = day_of(path)
        d = price_by_day.setdefault(day, {})
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            ti = (r.get("TIME_INTERVAL") or "").strip()
            if grid and ti:
                d[(grid, ti)] = f(r.get("LWAP")) / 1000  # PhP/kWh

    # scatter of (generation MW, price PhP/kWh) per grid, plus a per-day series
    scatter: dict[str, list] = {g.lower(): [] for g in GRIDS}
    day_series: dict[str, dict[str, list]] = {}
    for path in rtf:
        day = day_of(path)
        prices = price_by_day.get(day, {})
        if not prices:
            continue
        rows = rows_of(path)
        for r in rows:
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            ti = (r.get("TIME_INTERVAL") or "").strip()
            if not grid:
                continue
            price = prices.get((grid, ti))
            if price is None:
                continue
            gen = f(r.get("GENERATION"))
            if gen <= 0:
                continue
            scatter[grid.lower()].append([round(gen), round(price, 3)])
            ds = day_series.setdefault(day, {g.lower(): [] for g in GRIDS})
            ds[grid.lower()].append([ti, round(gen), round(price, 3)])

    # binned mean-price curve per grid (the shape): equal-width bins over generation
    def binned(points, nbins=18):
        if len(points) < nbins:
            return []
        gs = sorted(p[0] for p in points)
        lo, hi = gs[0], gs[-1]
        if hi <= lo:
            return []
        width = (hi - lo) / nbins
        buckets: dict[int, list] = defaultdict(list)
        for gen, price in points:
            b = min(nbins - 1, int((gen - lo) / width))
            buckets[b].append(price)
        out = []
        for b in range(nbins):
            vals = buckets.get(b)
            if vals:
                out.append({"gen_mw": round(lo + (b + 0.5) * width),
                            "n": len(vals),
                            "mean_price": round(sum(vals) / len(vals), 3),
                            "median_price": round(median(vals), 3)})
        return out

    curves = {g: binned(scatter[g]) for g in scatter}

    # one representative day for the demand-and-price animation: the day whose
    # Luzon price swings widest (the clearest evening-peak story), full 288 intervals
    best_day, best_swing = None, -1.0
    for day, ds in day_series.items():
        lz = ds.get("luzon", [])
        if len(lz) >= 200:
            ps = [p for _, _, p in lz]
            swing = max(ps) - min(ps)
            if swing > best_swing:
                best_day, best_swing = day, swing
    rep = None
    if best_day:
        ds = day_series[best_day]
        rep = {"date": best_day,
               "series": {g: [{"t": t, "gen_mw": gen, "price": pr}
                              for t, gen, pr in ds[g]] for g in ds if ds[g]}}

    # downsample the scatter so the baked file stays small (charts read the curve;
    # the scatter is only the faint context cloud)
    def thin(points, keep=1400):
        if len(points) <= keep:
            return points
        step = len(points) / keep
        return [points[int(i * step)] for i in range(keep)]

    return {"unit": "generation MW vs load-weighted price PhP/kWh, per 5-min interval",
            "days": len([d for d in price_by_day if d in day_series]),
            "curve": curves,
            "scatter": {g: thin(scatter[g]) for g in scatter},
            "representative_day": rep}


# --- regional prices (LWAPF, PhP/MWh -> PhP/kWh) --------------------------------

def build_prices() -> dict:
    files = dataset_files("LWAPF")
    if not files:
        NOTES.append("LWAPF absent; price series uses report anchors only")
        return {}
    daily: dict[tuple, list] = defaultdict(list)
    for path in files:
        day = day_of(path)
        rows = rows_of(path)
        assert_cols(path, rows, {"REGION_NAME", "LWAP"})
        for r in rows:
            grid = REGION_MAP.get(((r.get("REGION_NAME") or "").strip()))
            if grid:
                daily[(day, grid)].append(f(r.get("LWAP")))
    days = sorted({k[0] for k in daily})
    series = {}
    for grid in GRIDS:
        series[grid.lower()] = [
            round(sum(v) / len(v) / 1000, 3)
            if (v := daily.get((day, grid))) else None
            for day in days]
    spread = []
    for i in range(len(days)):
        vals = [series[g.lower()][i] for g in GRIDS
                if series[g.lower()][i] is not None]
        spread.append(round(max(vals) - min(vals), 3) if len(vals) > 1 else None)
    valid = [(d, s) for d, s in zip(days, spread) if s is not None]
    max_day = max(valid, key=lambda t: t[1]) if valid else (None, None)
    # Regime split: WESM was suspended (administered pricing) until the
    # resumption date; days before it are not market outcomes and every mean
    # the site displays says which regime it covers.
    resumed = MARKET_ANCHORS["wesm_resumed"]

    def regime_stats(pred):
        keep = [i for i, d in enumerate(days) if pred(d)]
        means = {}
        for g in GRIDS:
            vals = [series[g.lower()][i] for i in keep
                    if series[g.lower()][i] is not None]
            means[g.lower()] = round(sum(vals) / len(vals), 2) if vals else None
        sp = [spread[i] for i in keep if spread[i] is not None]
        return {
            "days": len(keep),
            "means": means,
            "mean_spread": round(sum(sp) / len(sp), 2) if sp else None,
            "max_spread": round(max(sp), 3) if sp else None,
            "days_spread_gt5": sum(1 for s in sp if s > 5),
        }
    regimes = {
        "administered": regime_stats(lambda d: d < resumed),
        "market": regime_stats(lambda d: d >= resumed),
    }
    return {"dates": days, "series": series, "spread": spread,
            "unit": "PhP/kWh (unweighted daily mean of 5-min LWAP, from PhP/MWh)",
            "as_of": days[-1] if days else None,
            "resumed": resumed,
            "regimes": regimes,
            "max_spread": {"date": max_day[0], "php": max_day[1]}}


# --- HVDC limits (schema-discovered) ---------------------------------------------

def build_hvdc() -> dict:
    files = dataset_files("HVDCRTD")
    if not files:
        NOTES.append("HVDCRTD absent; HVDC panel uses report anchors only")
        return {}
    limit_rows = 0
    limit_days: set[str] = set()
    header: list[str] = []
    for path in files:
        rows = rows_of(path)
        if rows and not header:
            header = sorted(rows[0])
        for r in rows:
            if (r.get("HVDC_NAME") or "").strip():
                limit_rows += 1
                limit_days.add(day_of(path))
    return {"header": header, "files": len(files),
            "limit_rows": limit_rows,
            "limit_days": sorted(d for d in limit_days if d),
            "note": ("no HVDC limit events recorded in RTD in this window; "
                     "the binding evidence for the links is in IEMOP's monthly "
                     "reports" if limit_rows == 0 else
                     "per-interval limit series is a v1.1 layer")}


# --- outages (OUTRTD): Sual receipts ----------------------------------------------

def build_outages() -> dict:
    files = dataset_files("OUTRTD")
    if not files:
        NOTES.append("OUTRTD absent; Sual outage receipts unavailable")
        return {}
    sample = rows_of(files[-1])
    if not sample:
        return {}
    header = set(sample[0])
    name_col = next((c for c in header if any(
        k in c.upper() for k in ("RESOURCE", "PLANT", "NAME", "FACILITY"))), None)
    if not name_col:
        raise SystemExit(f"OUTRTD: no resource column; header={sorted(header)}")
    sual_days: set[str] = set()
    for path in files:
        day = day_of(path)
        for r in rows_of(path):
            if "SUAL" in (r.get(name_col) or "").upper():
                sual_days.add(day)
    return {"header": sorted(header), "name_col": name_col,
            "days_covered": len(files),
            "sual_outage_days": sorted(sual_days),
            "sual_outage_day_count": len(sual_days)}


# --- DIPCEF congestion premium (sample days) --------------------------------------

def build_congestion_premium() -> dict:
    files = dataset_files("DIPCEF")
    if not files:
        NOTES.append("DIPCEF sample absent; congestion-premium stat omitted")
        return {}
    agg: dict[tuple, list] = defaultdict(list)
    for path in files:
        day = day_of(path)
        try:
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    with z.open(name) as fh:
                        rd = csv.DictReader(io.TextIOWrapper(fh, "utf-8",
                                                             errors="replace"))
                        for r in rd:
                            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
                            if grid:
                                agg[(day, grid)].append(f(r.get("LMP_CONGESTION")))
        except zipfile.BadZipFile:
            continue
    days = sorted({k[0] for k in agg})
    regions = {}
    for grid in GRIDS:
        rows_ = []
        for day in days:
            vals = agg.get((day, grid), [])
            nonzero = [abs(v) for v in vals if v]
            rows_.append({
                "date": day, "n": len(vals),
                "share_nonzero_pct": round(100 * len(nonzero) / len(vals), 1)
                if vals else None,
                "max_abs_php_kwh": round(max(nonzero) / 1000, 3) if nonzero else 0.0,
            })
        regions[grid.lower()] = rows_
    return {"days": days, "regions": regions,
            "unit": "LMP congestion component, PhP/kWh (from PhP/MWh)"}


# --- findings (the drawer: computed cards that fly the map to their evidence) ------

def build_findings(cong, rel, prices, outs, named_dc_mw, n_dc) -> dict:
    A = MARKET_ANCHORS
    margin = A["wesm_may2026_margin_mw"]
    dict_fc = next(a for a in DEMAND_ANCHORS if a["owner"] == "DICT")
    mer = next(a for a in DEMAND_ANCHORS if a["owner"] == "Meralco")
    findings = []

    def add(fid, tag, title, stat, blurb, source, center, zoom, mode):
        findings.append({"id": fid, "tag": tag, "title": title, "stat": stat,
                         "blurb": blurb, "source": source,
                         "focus": {"center": center, "zoom": zoom, "mode": mode}})

    cr = (cong.get("corridor_receipts") or {}).get("leyte_cebu_230kv")
    ltc = next((e for e in cong.get("league", [])
                if e["equipment"] == "LEYTE_TO_CEBU"), None)
    top = (cong.get("league") or [None])[0]
    if cr and ltc and top:
        add("corridor-named", "The receipts",
            "The grid names its own choke point",
            f"A row literally named LEYTE_TO_CEBU appears in the day-ahead "
            f"runs on {ltc['dap_days']} of {cong['days_covered']} days",
            f"IEMOP's congestions-manifesting files put named equipment at "
            f"100% of its binding limit. The Tabango (Leyte) to Daanbantayan "
            f"(Cebu) 230 kV lines that carry this corridor top the league: at "
            f"a limit on {top['days']} of {cong['days_covered']} archive days "
            f"across the day-ahead and real-time runs, including "
            f"{cr['rtd_intervals']} five-minute real-time intervals on "
            f"{cr['rtd_days']} days. The same corridor IEMOP's December 2025 "
            f"report names in prose.",
            "IEMOP congestions-manifesting files (RTD + DAP), archive window",
            [124.27, 10.7], 7.2, "choke")
    add("wave-vs-margin", "The arithmetic",
        "The announced wave is the size of the margin",
        f"{dict_fc['mw']:,} MW forecast (DICT, by 2028) against a "
        f"{margin:,} MW May 2026 system supply margin",
        f"The DICT forecast alone equals {round(100 * dict_fc['mw'] / margin)}% "
        f"of the whole system's May margin; Meralco has committed "
        f"{mer['mw']:,} MW for 10 data centers. The {n_dc} pinned sites with a "
        f"public figure name {named_dc_mw:,} MW between them, and a data "
        f"center is near-flat 24/7 load: it consumes margin in every interval, "
        f"not just at the evening peak.",
        "IEMOP May 2026 report; DICT via BusinessWorld; PCIJ",
        [121.05, 14.45], 8.2, "supply")
    if rel:
        t = rel["totals"]
        curt_days = sum(t[g]["curtailment_days"] for g in t)
        curt_mwh = round(sum(t[g]["curtailed_mwh_total"] for g in t), 1)
        add("thin-normal", "Thin is the normal state",
            "Reserves ran below requirement on most days",
            f"Luzon scheduled reserves fell below the stated requirement on "
            f"{t['luzon']['reserve_shortfall_days']} of "
            f"{t['luzon']['days']} archive days",
            f"In the operator's own dispatch schedules, load was curtailed on "
            f"{curt_days} grid-days in this window ({curt_mwh:,} MWh), and the "
            f"Visayas ran short of scheduled reserves on "
            f"{t['visayas']['reserve_shortfall_days']} days. Thin margins are "
            f"the observed normal state, not a forecast.",
            "IEMOP RTD regional summaries, archive window",
            [121.5, 15.0], 6.4, "supply")
    P = prices or {}
    reg = (P.get("regimes") or {})
    mk, ad = reg.get("market"), reg.get("administered")
    if mk and ad and P.get("max_spread"):
        add("market-prices-geography", "One market, three prices",
            "The market prices the geography the day it comes back",
            f"Administered window: the three grids priced within "
            f"P{ad['max_spread']}/kWh of each other. Market window: a mean "
            f"daily spread of P{mk['mean_spread']}/kWh",
            f"While WESM was suspended (through {P['resumed']}), daily "
            f"regional prices were near-identical. After trading resumed, the "
            f"islands split: Luzon P{mk['means']['luzon']}, Visayas "
            f"P{mk['means']['visayas']}, Mindanao P{mk['means']['mindanao']} "
            f"per kWh on average, with {mk['days_spread_gt5']} days spreading "
            f"beyond P5/kWh and a widest daily spread of "
            f"P{P['max_spread']['php']}/kWh on {P['max_spread']['date']}. The "
            f"links between the islands are the reason the numbers differ.",
            "IEMOP load-weighted average prices (final), archive window",
            [123.3, 11.2], 6.6, "price")
    if outs is not None:
        sual_days = (outs or {}).get("sual_outage_day_count", 0)
        sual_pct = round(100 * 647 / margin)
        add("sual-arithmetic", "The single contingency",
            f"One plant trip takes {sual_pct}% of the margin with it",
            f"One 647 MW Sual unit equals {sual_pct}% of the "
            f"May 2026 system margin",
            f"Sual's two 647 MW units are the largest single contingencies on "
            f"the Luzon grid. The archive's outage schedules list a Sual unit "
            f"out on {sual_days} day(s) in this window; the map's toggle "
            f"subtracts one unit from the published margin as arithmetic, not "
            f"a dispatch simulation.",
            "IEMOP outage schedules used in RTD; IEMOP May 2026 report",
            [120.1, 16.12], 7.8, "choke")
    if A.get("visayas_yellow_streak_days"):
        v = rel["totals"]["visayas"] if rel else None
        worst = (v or {}).get("worst_curtailment") or {}
        add("streak-ended", "Alert season",
            f"A {A['visayas_yellow_streak_days']}-day Visayas alert streak "
            f"just ended",
            f"Daily yellow alerts ran {A['visayas_yellow_streak_from']} to "
            f"{A['visayas_yellow_streak_to']}",
            f"The streak ended when one 150 MW unit returned; "
            f"{A['visayas_unavailable_mw_jul1']:,} MW was still unavailable "
            f"that day. In the same window the dispatch schedules show the "
            f"Visayas short of scheduled reserves on "
            f"{(v or {}).get('reserve_shortfall_days', 0)} days, with "
            f"{worst.get('curtailed_mwh', 0):,} MWh of load curtailed in the "
            f"schedules on {worst.get('date', 'n/a')} alone.",
            "NGCP advisories via SunStar and GMA (Jul 1-2, 2026); IEMOP RTD "
            "regional summaries",
            [123.7, 10.6], 7.0, "choke")
    return {"findings": findings}


# --- answers (the story rail copy, interpolated from computed values) --------------

def build_answers(cong, rel, prices, outs) -> dict:
    A = MARKET_ANCHORS
    margin = A["wesm_may2026_margin_mw"]
    dict_fc = next(a for a in DEMAND_ANCHORS if a["owner"] == "DICT")
    mer = next(a for a in DEMAND_ANCHORS if a["owner"] == "Meralco")
    curt_days = curt_mwh = short_days = None
    if rel:
        t = rel["totals"]
        curt_days = sum(t[g]["curtailment_days"] for g in t)
        curt_mwh = round(sum(t[g]["curtailed_mwh_total"] for g in t), 1)
        short_days = t["luzon"]["reserve_shortfall_days"]
    spread = (prices.get("max_spread") or {}) if prices else {}
    win = cong.get("window") or {}
    q1_stat = (f"{dict_fc['mw']:,} MW forecast by 2028 vs a "
               f"{margin:,} MW May 2026 system margin")
    q1_blurb = (f"DICT's 2028 forecast alone equals "
                f"{round(100 * dict_fc['mw'] / margin)}% of the whole system's "
                f"May margin, and Meralco has committed {mer['mw']:,} MW for 10 "
                f"data centers. A data center is near-flat 24/7 load.")
    if curt_days is not None:
        q1_blurb += (f" The operator's own dispatch schedules recorded load "
                     f"curtailed on {curt_days} grid-day(s) in this archive "
                     f"window ({curt_mwh:,} MWh). Headroom for a wave this size "
                     f"means new firm supply, not spare change.")
    q2_stat = (f"{cong.get('distinct_equipment', 0)} pieces of equipment hit "
               f"limits across the real-time and day-ahead runs on "
               f"{cong.get('days_covered', 0)} archive days; the "
               f"Leyte-Luzon HVDC ran at max or offline "
               f"{A['hvdc_binding_share_dec2025_pct']}% of Dec 2025")
    q2_blurb = ("The inter-island links and named 230 kV corridors already bind "
                "routinely; the table lists the receipts by equipment name. "
                "Nearly every announced data-center megawatt sits in the Luzon "
                "load pocket, on the importing side of those links. One Sual "
                f"unit (647 MW) equals {round(100 * 647 / margin)}% of the May "
                "system margin, which is why a single trip moves the whole grid.")
    if short_days is not None and short_days > 0:
        q2_blurb += (f" Luzon scheduled reserves fell below the stated "
                     f"requirement in at least one 5-minute interval on "
                     f"{short_days} of the window's days.")
    if outs and outs.get("sual_outage_day_count"):
        q2_blurb += (f" The outage files list a Sual unit out on "
                     f"{outs['sual_outage_day_count']} day(s).")
    q3_stat = (f"May 2026: P{A['wesm_may2026_system_avg_php_kwh']}/kWh system "
               f"(+{A['wesm_may2026_vs_april_pct']}% vs April); Luzon "
               f"P{A['wesm_may2026_luzon']}, Visayas P{A['wesm_may2026_visayas']}, "
               f"Mindanao P{A['wesm_may2026_mindanao']}")
    q3_blurb = ("One market on paper, three prices in practice: when a link "
                "binds, the islands price apart.")
    reg = (prices.get("regimes") or {}) if prices else {}
    mk, ad = reg.get("market"), reg.get("administered")
    if mk and ad and ad.get("max_spread") is not None:
        q3_blurb += (f" While WESM ran administered prices (through "
                     f"{prices['resumed']}), the three grids stayed within "
                     f"P{ad['max_spread']}/kWh of each other; once trading "
                     f"resumed the mean daily spread was "
                     f"P{mk['mean_spread']}/kWh.")
    if spread.get("php") is not None:
        q3_blurb += (f" Widest daily regional spread in the archive: "
                     f"P{spread['php']}/kWh on {spread['date']}.")
    q3_blurb += (" WESM passes into the Meralco generation charge monthly: June "
                 f"carried WESM at P{A['meralco_june2026_wesm_cost_php_kwh']}/kWh "
                 f"inside a P{A['meralco_june2026_generation_charge']}/kWh "
                 "generation charge. New flat 24/7 load raises the demand the "
                 "market clears against in every interval.")
    return {
        "window": win,
        "q1": {"title": "Can the grid handle more data centers? Is there supply?",
               "verdict": "Only with new firm supply: the announced wave is the "
                          "size of the margin.",
               "stat": q1_stat, "blurb": q1_blurb,
               "src": "IEMOP May 2026 report; PCIJ (Meralco commitment); DICT "
                      "forecast via BusinessWorld; IEMOP RTD regional summaries"},
        "q2": {"title": "Is the infrastructure ready? Where would they have to sit?",
               "verdict": "The choke points are named, public, and already "
                          "binding; siting that ignores them inherits them.",
               "stat": q2_stat, "blurb": q2_blurb,
               "src": "IEMOP congestions-manifesting files; IEMOP Dec 2025 "
                      "report; IEMOP outage schedules"},
        "q3": {"title": "What would it do to market and retail prices?",
               "verdict": "The market already prices the geography daily; the "
                          "bill follows monthly.",
               "stat": q3_stat, "blurb": q3_blurb,
               "src": "IEMOP monthly reports; archived LWAP files; Meralco June "
                      "2026 advisory"},
    }


# --- assemble ----------------------------------------------------------------------

def geojson(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    # dispatch imports build_data helpers; import it here to avoid a load-time cycle
    from dispatch import build_dispatch, generators_features
    congestion = build_congestion()
    reliability = build_reliability()
    prices = build_prices()
    price_load = build_price_load()
    hvdc = build_hvdc()
    outages = build_outages()
    premium = build_congestion_premium()
    answers = build_answers(congestion, reliability, prices, outages)
    named_mw = round(sum(s["mw"] for s in DC_SITES if s.get("mw")), 1)
    n_named = sum(1 for s in DC_SITES if s.get("mw"))
    findings = build_findings(congestion, reliability, prices, outages,
                              named_mw, n_named)

    receipts = congestion.get("corridor_receipts") or {}
    ck = []
    for c in CHOKEPOINTS:
        props = {k: v for k, v in c.items()
                 if k not in ("coords", "equipment_match")}
        if c["id"] in receipts:
            props["receipts"] = receipts[c["id"]]
        elif c["kind"] == "hvdc" and hvdc.get("limit_rows") == 0:
            props["window_note"] = ("No RTD HVDC limit events recorded in "
                                    "this archive window; binding evidence is "
                                    "from IEMOP's monthly reports.")
        ck.append({"type": "Feature",
                   "geometry": {"type": "LineString",
                                "coordinates": c["coords"]},
                   "properties": props})
    with open(os.path.join(OUT, "chokepoints.geojson"), "w") as fh:
        json.dump(geojson(ck), fh, indent=1)
    dc = []
    for s in DC_SITES:
        props = {k: v for k, v in s.items() if k != "coords"}
        props["precision"] = "city"
        dc.append({"type": "Feature",
                   "geometry": {"type": "Point", "coordinates": s["coords"]},
                   "properties": props})
    with open(os.path.join(OUT, "dc_sites.geojson"), "w") as fh:
        json.dump(geojson(dc), fh, indent=1)

    with open(os.path.join(OUT, "sual.geojson"), "w") as fh:
        json.dump(geojson([{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": SUAL["coords"]},
            "properties": {k: v for k, v in SUAL.items() if k != "coords"},
        }]), fh, indent=1)

    # named generators (map layer + N-1 picker) and the dispatch model
    with open(os.path.join(OUT, "generators.geojson"), "w") as fh:
        json.dump(geojson(generators_features()), fh, indent=1)
    dispatch = build_dispatch()
    with open(os.path.join(OUT, "dispatch.json"), "w") as fh:
        json.dump(dispatch, fh, indent=1)

    for name, obj in [("congestion.json", congestion),
                      ("reliability.json", reliability),
                      ("prices.json", prices),
                      ("price_load.json", price_load), ("hvdc.json", hvdc),
                      ("outages.json", outages),
                      ("congestion_premium.json", premium),
                      ("demand_anchors.json", DEMAND_ANCHORS),
                      ("market_anchors.json", MARKET_ANCHORS),
                      ("answers.json", answers),
                      ("findings.json", findings)]:
        with open(os.path.join(OUT, name), "w") as fh:
            json.dump(obj, fh, indent=1)

    meta = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "named_dc_mw_total": named_mw,
        "dc_sites": len(DC_SITES),
        "notes": NOTES,
        "datasets": {k: len(dataset_files(k)) for k in
                     ("RTDCV", "DAPCV", "RTDSUM", "LWAPF", "HVDCRTD",
                      "OUTRTD", "DIPCEF")},
    }
    with open(os.path.join(OUT, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    print(json.dumps(meta, indent=1))
    print("baked:", sorted(os.listdir(OUT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
