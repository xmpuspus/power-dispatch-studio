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

def build_congestion() -> dict:
    league: dict[tuple, dict] = {}
    days_seen: set[str] = set()
    base_days: set[str] = set()
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
                    "intervals": 0, "days": set(), "base_case_intervals": 0,
                    "max_overload_mw": 0.0, "markets": set(),
                })
                e["intervals"] += 1
                e["days"].add(day)
                e["markets"].add(key)
                if (r.get("CONGEST_TYPE") or "").strip().upper() == "BASE CASE":
                    e["base_case_intervals"] += 1
                    base_days.add(day)
                e["max_overload_mw"] = max(e["max_overload_mw"],
                                           f(r.get("OVERLOAD_MW")))
    out = []
    for e in league.values():
        e["days"] = len(e["days"])
        e["markets"] = sorted(e["markets"])
        e["max_overload_mw"] = round(e["max_overload_mw"], 2)
        out.append(e)
    out.sort(key=lambda e: (-e["intervals"], e["equipment"]))
    days = sorted(d for d in days_seen if d)
    return {
        "window": {"from": days[0], "to": days[-1]} if days else None,
        "days_covered": len(days),
        "days_with_base_case_binding": len(base_days),
        "distinct_equipment": len(out),
        "total_binding_rows": sum(e["intervals"] for e in out),
        "league": out[:30],
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
    return {"dates": days, "series": series, "spread": spread,
            "unit": "PhP/kWh (unweighted daily mean of 5-min LWAP, from PhP/MWh)",
            "max_spread": {"date": max_day[0], "php": max_day[1]}}


# --- HVDC limits (schema-discovered) ---------------------------------------------

def build_hvdc() -> dict:
    files = dataset_files("HVDCRTD")
    if not files:
        NOTES.append("HVDCRTD absent; HVDC panel uses report anchors only")
        return {}
    sample = rows_of(files[-1])
    if not sample:
        return {}
    header = sorted(sample[0])
    return {"header": header, "files": len(files),
            "note": "schema captured; per-interval limit series is a v1.1 layer"}


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
               f"limits on {cong.get('days_covered', 0)} archive days; the "
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
    congestion = build_congestion()
    reliability = build_reliability()
    prices = build_prices()
    hvdc = build_hvdc()
    outages = build_outages()
    premium = build_congestion_premium()
    answers = build_answers(congestion, reliability, prices, outages)

    ck = [{"type": "Feature",
           "geometry": {"type": "LineString", "coordinates": c["coords"]},
           "properties": {k: v for k, v in c.items() if k != "coords"}}
          for c in CHOKEPOINTS]
    with open(os.path.join(OUT, "chokepoints.geojson"), "w") as fh:
        json.dump(geojson(ck), fh, indent=1)

    named_mw = round(sum(s["mw"] for s in DC_SITES if s.get("mw")), 1)
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

    for name, obj in [("congestion.json", congestion),
                      ("reliability.json", reliability),
                      ("prices.json", prices), ("hvdc.json", hvdc),
                      ("outages.json", outages),
                      ("congestion_premium.json", premium),
                      ("demand_anchors.json", DEMAND_ANCHORS),
                      ("market_anchors.json", MARKET_ANCHORS),
                      ("answers.json", answers)]:
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
