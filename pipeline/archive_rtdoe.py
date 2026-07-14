#!/usr/bin/env python3
"""Archive the FULL 5-minute RTDOE offer books for selected sample days.

offers.py keeps one representative book per hour (the HH:05 interval) because
an hourly LP only needs one book per hour. But the raw 5-minute detail is only
recoverable inside IEMOP's rolling ~90-day publication window: once a day ages
out, its intra-hour offer curves are gone for good. This module captures that
detail for a curated set of sample days and commits it, so the 5-minute
as-bid replay (roadmap item 10) has a permanent, public source no one else
keeps.

For each sample day it fetches the 24 hourly RTDOE files (and the matching
self-scheduled-nomination files), groups rows by TIME_INTERVAL, and writes one
compact per-grid stack per 5-minute interval to
data/derived/rtdoe_5min/RTDOE5_<YYYYMMDD>.json. Same {price, mw} block schema
and same compaction as offers.py, so the books are drop-in engine inputs at
5-minute resolution.

Resilient by design: a day whose files have aged out of the window is logged
and skipped, not fatal, so one lost day cannot abort the whole capture.

    python3 pipeline/archive_rtdoe.py --sample          # the curated set
    python3 pipeline/archive_rtdoe.py --days 2026-05-29,2026-06-17
    python3 pipeline/archive_rtdoe.py --sample --force   # re-derive existing
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta

from offers import (
    MAX_BLOCKS,
    OFFER_FLOOR,
    REGION,
    SLEEP,
    SLUG,
    SSN_SLUG,
    _compact,
    _fetch_hour_csv,
    _segments,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "data", "derived", "rtdoe_5min")
SCHEMA_VERSION = 1

# Curated sample days: a volatility/scarcity spread across the post-suspension
# window (WESM resumed 2026-05-01), oldest days first because early-May is
# nearest the ~90-day window edge and at most risk of aging out. Selected from
# the observed Luzon LWAP series (web/data/prices.json): scarcity peaks, a
# ramp/coincident-peak cluster, and calm baselines for contrast.
SAMPLE_DAYS = [
    "2026-05-05",  # LWAP 13.5, scarcity spike
    "2026-05-12",  # LWAP 11.6
    "2026-05-17",  # LWAP 2.95, calm contrast
    "2026-05-22",  # LWAP 12.6
    "2026-05-28",  # LWAP 14.2
    "2026-05-29",  # LWAP 15.2, window peak
    "2026-06-06",  # LWAP 3.25, calm contrast
    "2026-06-10",  # LWAP 11.7
    "2026-06-17",  # LWAP 13.7
    "2026-06-20",  # LWAP 11.7
    "2026-06-22",  # LWAP 12.0
    "2026-06-23",  # LWAP 12.2
    "2026-07-03",  # recent coverage
    "2026-07-06",  # recent coverage
]


def _interval_key(raw: str) -> str | None:
    """Normalize a published TIME_INTERVAL to 'YYYY-MM-DD HH:MM' (sortable,
    unambiguous across the day). Returns None on an unparseable stamp."""
    from offers import _ts

    ts = _ts(raw)
    return ts.strftime("%Y-%m-%d %H:%M") if ts else None


def _grid_rows_by_interval(rows: list[dict]) -> dict[str, dict[str, list]]:
    """{interval_key: {grid: [(price, mw), ...]}} from RTDOE rows."""
    out: dict[str, dict[str, list]] = {}
    for r in rows:
        key = _interval_key((r.get("TIME_INTERVAL") or "").strip())
        g = REGION.get((r.get("REGION_NAME") or "").strip())
        res = (r.get("RESOURCE_NAME") or "").strip()
        if not key or not g or not res:
            continue
        out.setdefault(key, {}).setdefault(g, []).extend(_segments(r))
    return out


def _ssn_by_interval(rows: list[dict]) -> dict[str, dict[str, float]]:
    """{interval_key: {grid: self_sched_mw}} from RTDNE rows."""
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        key = _interval_key((r.get("TIME_INTERVAL") or "").strip())
        g = REGION.get((r.get("REGION_NAME") or "").strip())
        if not key or not g:
            continue
        try:
            mw = float(r.get("SELF_SCHED_MW") or 0)
        except ValueError:
            continue
        if mw > 1e-9:
            slot = out.setdefault(key, {})
            slot[g] = slot.get(g, 0.0) + mw
    return out


def derive_day(date: str) -> dict:
    """Fetch the day's 24 hourly books and build a compact per-grid stack for
    every 5-minute interval. Raises RuntimeError if any hour fails to fetch."""
    d = datetime.strptime(date, "%Y-%m-%d")
    per_interval: dict[str, dict[str, list]] = {}
    ssn_all: dict[str, dict[str, float]] = {}
    for h in range(24):
        end = d + timedelta(hours=h + 1)
        stamp = end.strftime("%Y%m%d%H%M")
        rows = _fetch_hour_csv(SLUG, "RTDOE", stamp)
        time.sleep(SLEEP)
        if rows is None:
            raise RuntimeError(f"rtdoe: fetch failed for {date} h{h} "
                               f"(RTDOE_{stamp})")
        ssn = _fetch_hour_csv(SSN_SLUG, "RTDNE", stamp)
        time.sleep(SLEEP)
        if ssn is None:
            raise RuntimeError(f"rtdoe: fetch failed for {date} h{h} "
                               f"(RTDNE_{stamp})")
        for key, grids in _grid_rows_by_interval(rows).items():
            slot = per_interval.setdefault(key, {})
            for g, segs in grids.items():
                slot.setdefault(g, []).extend(segs)
        for key, grids in _ssn_by_interval(ssn).items():
            slot = ssn_all.setdefault(key, {})
            for g, mw in grids.items():
                slot[g] = slot.get(g, 0.0) + mw

    if not per_interval:
        raise RuntimeError(f"rtdoe: no intervals parsed for {date}")

    intervals: dict[str, dict[str, list]] = {}
    for key in sorted(per_interval):
        merged: dict[str, list] = {}
        for g in REGION.values():
            blocks = list(per_interval[key].get(g, []))
            ssn_mw = ssn_all.get(key, {}).get(g, 0.0)
            if ssn_mw > 1e-9:
                blocks.append((OFFER_FLOOR, ssn_mw))
            if blocks:
                merged[g] = [[p, m] for p, m in _compact(blocks)]
        if merged:
            intervals[key] = merged

    return {
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "grids": list(REGION.values()),
        "max_blocks": MAX_BLOCKS,
        "n_intervals": len(intervals),
        "intervals": intervals,
        "source": ("IEMOP rtd-generation-offers (RTDOE) + "
                   "rtd-self-scheduled-nominations (RTDNE), per 5-minute "
                   "interval"),
        "note": ("Full 5-minute offer books for a sample day. Each interval "
                 "is that interval's per-grid supply stack, all resource "
                 "segments pooled and compacted to at most "
                 f"{MAX_BLOCKS} price blocks (MW-weighted merges), self-"
                 "scheduled nominations added as a price-taking block at the "
                 f"offer floor ({OFFER_FLOOR} PhP/kWh). offers.py keeps only "
                 "the HH:05 book per hour; this preserves the intra-hour "
                 "detail that IEMOP's rolling window would otherwise erase."),
    }


def _existing_days() -> set[str]:
    if not os.path.isdir(OUT_DIR):
        return set()
    out = set()
    for fn in os.listdir(OUT_DIR):
        if fn.startswith("RTDOE5_") and fn.endswith(".json"):
            s = fn[len("RTDOE5_"):-len(".json")]
            out.add(f"{s[:4]}-{s[4:6]}-{s[6:]}")
    return out


def _latest_offer_days(n: int) -> list[str]:
    """The n newest days that have a derived HH:05 offer book (so RTDOE is
    published and available) but no 5-minute book yet. This is the cron's
    compounding capture: each run preserves the freshest day's intra-hour
    detail before IEMOP's rolling window erases it."""
    offer_dir = os.path.join(HERE, "..", "data", "derived", "offer_daily")
    have = _existing_days()
    days = []
    for fn in os.listdir(offer_dir) if os.path.isdir(offer_dir) else []:
        if fn.startswith("OFFERD_") and fn.endswith(".json"):
            s = fn[len("OFFERD_"):-len(".json")]
            date = f"{s[:4]}-{s[4:6]}-{s[6:]}"
            if date not in have:
                days.append(date)
    return sorted(days, reverse=True)[:n]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="capture the curated SAMPLE_DAYS set")
    ap.add_argument("--latest", type=int, default=0, metavar="N",
                    help="capture the N newest offer-available days not yet on "
                         "disk (the compounding daily-cron mode)")
    ap.add_argument("--days", default="",
                    help="comma-separated YYYY-MM-DD list")
    ap.add_argument("--force", action="store_true",
                    help="re-derive days already on disk")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    days: list[str] = []
    if args.sample:
        days += SAMPLE_DAYS
    if args.latest:
        days += _latest_offer_days(args.latest)
    if args.days:
        days += [d.strip() for d in args.days.split(",") if d.strip()]
    if not days:
        print("nothing to do: pass --sample, --latest N, or --days")
        return 1

    ok, skipped, failed = [], [], []
    for date in days:
        out = os.path.join(OUT_DIR, f"RTDOE5_{date.replace('-', '')}.json")
        if os.path.isfile(out) and not args.force:
            skipped.append(date)
            print(f"[skip] {date} already on disk", flush=True)
            continue
        try:
            data = derive_day(date)
        except Exception as e:  # one bad day must never abort the capture run
            failed.append(date)
            print(f"[FAIL] {date}: {type(e).__name__}: {e}", flush=True)
            continue
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        ok.append(date)
        print(f"[ok]   {date}: {data['n_intervals']} intervals -> "
              f"{os.path.getsize(out) // 1024} KB", flush=True)

    print(f"\ndone: {len(ok)} written, {len(skipped)} skipped, "
          f"{len(failed)} failed")
    if failed:
        print(f"failed (likely aged out of window): {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
