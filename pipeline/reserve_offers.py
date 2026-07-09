#!/usr/bin/env python3
"""Derive observed per-grid hourly RESERVE offer books from IEMOP's
real-time reserve offers (RTDOR), the dataset the methodology wrongly
called unpublished until the round-7 convergence critic enumerated the
market-data sitemap (57 pages; the archive carried 14).

WESM co-optimises energy and reserves. RTDOR publishes every resource's
actual reserve offer curve per 5-minute interval, per commodity (Fr
contingency, Dr dispatchable, Ru/Rd regulation up/down), in the same
PRICE1..11/QUANTITY1..11 cumulative-breakpoint schema as the generation
offers (RTDOE). Files are hourly and end-labeled like RTDOE (day D hour h
lives in RTDOR_D_(h+1)00), ~350 KB per hour, too heavy to commit raw, so
this module mirrors offers.py: fetch a day's 24 hourly files transiently,
take each hour's book at the hour's first interval (HH:05), pool segments
per grid x commodity, compact, and commit only the daily JSON under
data/derived/reserve_daily/.

The artifact also carries the hour's scheduled reserve and requirement
per grid x commodity (RTDSUM GENERATION / MKT_REQT means), so a joint
energy+reserve clear has its constraint targets in one file.

Gate, mirroring the energy books: each grid-hour-commodity book must
cover that hour's scheduled reserve MW or the day is refused, not
written.

    python3 pipeline/reserve_offers.py --derive --limit 3
    python3 pipeline/reserve_offers.py --derive --from 2026-04-10
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import date as date_cls
from datetime import datetime, timedelta

from offers import (MAX_BLOCKS, RAW, REGION, SLEEP, _compact,
                    _fetch_hour_csv, _first_interval, _segments, _ts)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "data", "derived", "reserve_daily")
SLUG = "rtd-reserve-offers"
COMMODITIES = ("Fr", "Dr", "Ru", "Rd")
# 2: added sched_open_mw (the gate's like-for-like first-interval target).
# 3: sched_open_mw is now the RTDSUM row EXACTLY matching the book's first
#    interval; v2 took the hour bucket's earliest row, which under hour_of's
#    clock-hour binning is the HH:00 boundary row whose GENERATION sits at
#    the full requirement (2026-04-28 h23: boundary row 668 = MKT_REQT vs
#    the book's 23:05 schedule of 578.5, refusing four days falsely)
SCHEMA_VERSION = 3
# reserve books are far smaller than energy books (168 resources across
# 12 grid x commodity pools in the sampled hour); 24 blocks loses nothing
RESERVE_MAX_BLOCKS = min(24, MAX_BLOCKS)


def _rtdsum_reserve(date: str) -> dict | None:
    """{grid: {commodity: {"sched": [24], "req": [24], "at": {dt: MW}}}}
    from the day's RTDSUM: hourly means plus every 5-minute scheduled MW
    keyed by its exact interval timestamp (for the like-for-like gate).
    None when the file is missing (gate impossible)."""
    p = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    if not os.path.isfile(p):
        return None
    from dispatch import hour_of
    acc: dict = {g: {c: {"sched": [[] for _ in range(24)],
                         "req": [[] for _ in range(24)],
                         "at": {}}
                     for c in COMMODITIES} for g in REGION.values()}
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            c = (r.get("COMMODITY_TYPE") or "").strip()
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            if c not in COMMODITIES or not g:
                continue
            ival = (r.get("TIME_INTERVAL") or "").strip()
            h = hour_of(ival)
            for field, key in (("GENERATION", "sched"), ("MKT_REQT", "req")):
                try:
                    acc[g][c][key][h].append(float(r.get(field) or 0))
                except ValueError:
                    continue
            dt = _ts(ival)
            if dt is not None:
                try:
                    acc[g][c]["at"][dt] = float(r.get("GENERATION") or 0)
                except ValueError:
                    pass
    return {g: {c: {"sched": [round(sum(v) / len(v), 1) if v else None
                              for v in acc[g][c]["sched"]],
                    "req": [round(sum(v) / len(v), 1) if v else None
                            for v in acc[g][c]["req"]],
                    "at": acc[g][c]["at"]}
                for c in COMMODITIES} for g in REGION.values()}


def derive_day(date: str) -> dict:
    """Fetch the day's 24 hourly RTDOR files, build compact per-grid,
    per-commodity reserve books. Raises RuntimeError on fetch failure or
    when the gate refuses."""
    d = datetime.strptime(date, "%Y-%m-%d")
    hours: dict = {g: {c: [None] * 24 for c in COMMODITIES}
                   for g in REGION.values()}
    # gate on the RAW pooled MW, not the compacted book: compaction rounds
    # each block to 0.1 MW and drops slivers, which can shave ~2 MW off a
    # 250 MW regulation book and trip the gate falsely (2026-05-15 did)
    raw_off: dict = {g: {c: [0.0] * 24 for c in COMMODITIES}
                     for g in REGION.values()}
    first_dt: list = [None] * 24
    n_res = 0
    for h in range(24):
        stamp = (d + timedelta(hours=h + 1)).strftime("%Y%m%d%H%M")
        rows = _fetch_hour_csv(SLUG, "RTDOR", stamp)
        time.sleep(SLEEP)
        if rows is None:
            raise RuntimeError(f"reserve offers: fetch failed for {date} "
                               f"h{h} (RTDOR_{stamp})")
        first = _first_interval(rows)
        if first is None:
            raise RuntimeError(f"reserve offers: empty book for {date} h{h}")
        first_dt[h] = _ts(first)
        pools: dict = {g: {c: [] for c in COMMODITIES}
                       for g in REGION.values()}
        seen = set()
        for r in rows:
            if (r.get("TIME_INTERVAL") or "").strip() != first:
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            c = (r.get("COMMODITY_TYPE") or "").strip()
            res = (r.get("RESOURCE_NAME") or "").strip()
            if not g or c not in COMMODITIES or not res:
                continue
            seen.add(res)
            pools[g][c].extend(_segments(r))
        n_res = max(n_res, len(seen))
        for g in REGION.values():
            for c in COMMODITIES:
                if pools[g][c]:
                    raw_off[g][c][h] = sum(m for _, m in pools[g][c])
                    hours[g][c][h] = [
                        [p, m]
                        for p, m in _compact(pools[g][c], RESERVE_MAX_BLOCKS)]
    sched = _rtdsum_reserve(date)
    if sched is None:
        raise RuntimeError(f"reserve offers: no RTDSUM for {date}; "
                           "gate impossible")
    # like-for-like: the book is the hour's FIRST interval (HH:05), so it
    # is gated against the RTDSUM schedule at EXACTLY that interval.
    # Resources re-offer within the hour (a mid-hour rise is invisible to
    # the opening book: 2026-05-15 luzon Rd h13, book 256 vs 13:05
    # schedule 255.5 but hour mean 258), and the hour bucket's earliest
    # ROW is the HH:00 boundary row whose GENERATION sits at the full
    # requirement, so neither the mean nor a min-dt pick is the opening
    # book's obligation.
    open_mw: dict = {g: {c: [None] * 24 for c in COMMODITIES}
                     for g in REGION.values()}
    for g in REGION.values():
        for c in COMMODITIES:
            for h in range(24):
                offered = raw_off[g][c][h]
                target = (sched[g][c]["at"].get(first_dt[h])
                          if first_dt[h] is not None else None)
                if target is not None:
                    open_mw[g][c][h] = round(target, 1)
                if target is not None and offered < target - 1.0:
                    raise RuntimeError(
                        f"reserve offers: {date} {g} {c} h{h} book "
                        f"{offered:.0f} MW < opening scheduled "
                        f"{target:.0f} MW; refused")
    return {
        "date": date,
        "schema_version": SCHEMA_VERSION,
        # the exact interval each hour's book was taken at, so consumers
        # pairing against other per-interval series can verify the HH:05
        # opening-interval assumption instead of inheriting it (days
        # derived before this field carry no record of it)
        "book_at": [dt.isoformat(sep=" ") if dt else None
                    for dt in first_dt],
        "hours": hours,
        "sched_mw": {g: {c: sched[g][c]["sched"] for c in COMMODITIES}
                     for g in REGION.values()},
        "sched_open_mw": open_mw,
        "req_mw": {g: {c: sched[g][c]["req"] for c in COMMODITIES}
                   for g in REGION.values()},
        "max_resources_seen": n_res,
        "max_blocks": RESERVE_MAX_BLOCKS,
        "note": ("Observed per-grid hourly reserve offer books from "
                 "IEMOP's real-time reserve offers (RTDOR), per commodity "
                 "(Fr contingency, Dr dispatchable, Ru/Rd regulation): "
                 "each hour is the book at the hour's first 5-minute "
                 "interval, segments pooled per grid x commodity and "
                 f"compacted to at most {RESERVE_MAX_BLOCKS} price blocks "
                 "(MW-weighted merges). Prices PhP/kWh as offered. "
                 "sched_mw/req_mw are the hour's mean scheduled reserve "
                 "and market requirement from RTDSUM; sched_open_mw is "
                 "the schedule at exactly the book's interval. Gate, "
                 "like-for-like: each grid-hour-commodity book (the "
                 "hour's first interval) must cover the schedule at that "
                 "same interval or the day is refused; resources "
                 "re-offer within the hour, so the hour mean is not the "
                 "opening book's obligation."),
        "src": "https://www.iemop.ph/market-data/rtd-reserve-offers/",
        "src_sched": "https://www.iemop.ph/market-data/rtd-regional-summaries/",
    }


def derive(dates: list[str]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    consec = 0
    for date in dates:
        out = os.path.join(OUT_DIR, f"RESD_{date.replace('-', '')}.json")
        if os.path.isfile(out):
            try:
                with open(out) as fh:
                    if json.load(fh).get("schema_version", 0) >= SCHEMA_VERSION:
                        continue
            except (json.JSONDecodeError, OSError):
                pass
        try:
            day = derive_day(date)
        except RuntimeError as e:
            print(f"SKIP {date}: {e}", flush=True)
            consec += 1
            if consec >= 3:
                print("ABORT: 3 consecutive day failures", flush=True)
                return
            continue
        consec = 0
        with open(out, "w") as fh:
            json.dump(day, fh, indent=1)
        print(f"derived {date}", flush=True)


def _market_dates(frm: str, to: str) -> list[str]:
    d0 = datetime.strptime(frm, "%Y-%m-%d").date()
    d1 = datetime.strptime(to, "%Y-%m-%d").date()
    out = []
    d = d0
    while d <= d1:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--from", dest="frm", default="2026-04-10")
    ap.add_argument("--to", dest="to",
                    default=(date_cls.today() - timedelta(days=6)).isoformat())
    ap.add_argument("--limit", type=int, default=None,
                    help="derive only the newest N underived days")
    a = ap.parse_args()
    if a.derive:
        dates = _market_dates(a.frm, a.to)
        if a.limit:
            underived = [dt for dt in dates if not os.path.isfile(
                os.path.join(OUT_DIR, f"RESD_{dt.replace('-', '')}.json"))]
            dates = underived[-a.limit:]
        derive(dates)
