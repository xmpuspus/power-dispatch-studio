#!/usr/bin/env python3
"""Derive per-resource cleared RESERVE results from IEMOP's DIPC reserve
results final (DIPCRF).

The round-7 reserve replay clears the RTDOR-derived reserve books at the
operator's scheduled MW and scores them against the regional RSVPR price.
Both sides of that comparison drop resource identity: the compacted books
pool segments per grid x commodity, and RSVPR is one price per region. The
round-8/9 convergence audits named the per-resource reserve results (DIPCRF)
as the tighter reserve validation and as the input the queued joint
energy+reserve LP needs.

DIPCRF is the final reserve calculation, one hourly zip of 12 five-minute
intervals, ~10 KB zipped per hour but per-resource, so this module mirrors
fuelmix.py / reserve_offers.py: fetch a day's 24 hourly zips transiently,
take each hour's first interval (HH:05, the same interval the reserve books
are taken at), keep every resource's cleared reserve schedule and price per
commodity (Fr contingency, Dr dispatchable, Ru/Rd regulation), and commit
only the compact daily JSON under data/derived/reserve_results_daily/.

Gate, mirroring DIPCEF: each grid-commodity cleared schedule at the book's
interval must reconcile to the RTDSUM scheduled reserve at that same
interval, or the day is refused. DIPCRF is IEMOP's own final schedule, so
this is a near-exact cross-source check (the same 668 MW appears in both).

DIPCRF names its regions in full (LUZON) while RTDSUM uses the CLUZ/CVIS/CMIN
codes; the REGION map below carries both spellings so the reconciliation
does not silently drop to null (the round-8 CLUZ-vs-LUZON gotcha).

    python3 pipeline/reserve_results.py --derive
    python3 pipeline/reserve_results.py --derive --limit 3
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import zipfile
from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime, timedelta

from archive_iemop import fetch, list_files, page_config
from offers import _ts
from reserve_offers import COMMODITIES, _rtdsum_reserve

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "data", "derived", "reserve_results_daily")
SLUG = "dipc-reserve-results-final"
# 2: the HH:00 file holds the PRIOR hour's opening interval (like the offer
#    books), so DIPCRF_D0000 carries D-1 23:05; v1 grouped it into day D's
#    hour 23, shifting every day's hour-23 slot back one calendar day. v2
#    assigns the 00:00 file to the previous day so day D's hour 23 comes from
#    the D+1 00:00 file, matching reserve_offers.py's stamp = day + h + 1.
SCHEMA_VERSION = 2
# DIPCRF names commodities in upper case; carry them to the title case the
# rest of the archive uses (RTDSUM / RSVPR / the reserve books).
COMM_CANON = {"DR": "Dr", "FR": "Fr", "RU": "Ru", "RD": "Rd"}
# both region spellings -> lower-case grid (DIPCRF full names, RTDSUM codes)
REGION = {"LUZON": "luzon", "CLUZ": "luzon",
          "VISAYAS": "visayas", "CVIS": "visayas",
          "MINDANAO": "mindanao", "CMIN": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")


def derive_day(date: str, hour_files: list[tuple[str, str]]) -> dict:
    """Fetch one day's 24 hourly DIPCRF zips, keep each hour's first-interval
    per-resource cleared reserve, and reconcile to the RTDSUM schedule."""
    # per grid x commodity: 24 hourly lists of [resource, mw, price]
    hours: dict = {g: {c: [None] * 24 for c in COMMODITIES} for g in GRIDS}
    cleared: dict = {g: {c: [None] * 24 for c in COMMODITIES} for g in GRIDS}
    sched: dict = {g: {c: [None] * 24 for c in COMMODITIES} for g in GRIDS}
    first_dt: list = [None] * 24
    n_res = 0
    with __import__("tempfile").TemporaryDirectory() as tmp:
        for b64, name in hour_files:
            m = re.search(r"DIPCRF_\d{8}(\d{2})\d{2}", name)
            if not m:
                continue
            # end-labelled like the other hourly series: file stamped (h+1)00
            # holds hour h, so hour = stamp_hour - 1 (23 -> hour 22, 00 -> 23)
            stamp_h = int(m.group(1))
            h = (stamp_h - 1) % 24
            dest = os.path.join(tmp, name)
            ok = fetch(SLUG, b64, dest)
            time.sleep(0.4)
            if not ok:
                time.sleep(45)
                ok = fetch(SLUG, b64, dest)
                time.sleep(0.4)
            if not ok:
                raise RuntimeError(f"fetch failed: {name}")
            rows = []
            with zipfile.ZipFile(dest) as z:
                for member in z.namelist():
                    with z.open(member) as fh:
                        rows.extend(csv.DictReader(
                            io.TextIOWrapper(fh, "utf-8", errors="replace")))
            ivals = sorted({(r.get("TIME_INTERVAL") or "").strip()
                            for r in rows if (r.get("TIME_INTERVAL") or "").strip()},
                           key=lambda s: _ts(s) or datetime.max)
            if not ivals:
                raise RuntimeError(f"empty DIPCRF file: {name}")
            first = ivals[0]
            first_dt[h] = _ts(first)
            pool: dict = {g: {c: [] for c in COMMODITIES} for g in GRIDS}
            seen = set()
            for r in rows:
                if (r.get("TIME_INTERVAL") or "").strip() != first:
                    continue
                g = REGION.get((r.get("REGION_NAME") or "").strip().upper())
                c = COMM_CANON.get((r.get("COMMODITY_TYPE") or "").strip().upper())
                res = (r.get("RESOURCE_NAME") or "").strip()
                if not g or not c or not res:
                    continue
                try:
                    mw = float(r.get("SCHEDULE") or 0)
                    pr = float(r.get("PRICE") or 0) / 1000.0
                except ValueError:
                    continue
                if mw <= 0:
                    continue
                seen.add(res)
                pool[g][c].append((res, round(mw, 2), round(pr, 4)))
            n_res = max(n_res, len(seen))
            for g in GRIDS:
                for c in COMMODITIES:
                    entries = pool[g][c]
                    if not entries:
                        continue
                    tot = sum(mw for _, mw, _ in entries)
                    hours[g][c][h] = [[res, mw, pr] for res, mw, pr in entries]
                    sched[g][c][h] = round(tot, 1)
                    # schedule-weighted clearing price for the pool
                    cleared[g][c][h] = round(
                        sum(mw * pr for _, mw, pr in entries) / tot, 4)
    # DIPCRF is the FINAL calculation (published ~2 weeks behind); RTDSUM is
    # the real-time run. They are different market solves, so the per-resource
    # cleared schedule does NOT reconcile to the RTDSUM reserve exactly (on
    # 2026-06-20 Visayas Fr the final re-scheduled batteries to 80 MW against
    # the RTD 60.5 MW, both under a 123 MW requirement). The final-vs-RTD
    # schedule gap is therefore REPORTED, not gated on. The gate is structural:
    # DIPCRF is authoritative on its own, so a day is refused only if it did
    # not parse into a populated reserve book.
    rtd = _rtdsum_reserve(date)
    rtd_gap: dict = {g: {} for g in GRIDS}
    for g in GRIDS:
        for c in COMMODITIES:
            diffs = []
            if rtd is not None:
                for h in range(24):
                    got = sched[g][c][h]
                    dt = first_dt[h]
                    tgt = (rtd[g][c]["at"].get(dt) if dt is not None else None)
                    if got is not None and tgt is not None:
                        diffs.append(round(got - tgt, 1))
            rtd_gap[g][c] = {"max_abs": round(max((abs(d) for d in diffs)), 1)
                             if diffs else None,
                             "mean": round(sum(diffs) / len(diffs), 1)
                             if diffs else None}
    populated = sum(1 for h in range(24)
                    if sched["luzon"]["Dr"][h] is not None
                    and sched["luzon"]["Fr"][h] is not None)
    if populated < 20:
        raise RuntimeError(
            f"{date}: only {populated}/24 hours have a Luzon reserve book; "
            "refused as an incomplete or corrupt day")
    return {
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "book_at": [dt.isoformat(sep=" ") if dt else None for dt in first_dt],
        "hours": hours,
        "cleared_price": cleared,
        "sched_mw": sched,
        "max_resources_seen": n_res,
        "rtd_schedule_gap_mw": rtd_gap,
        "note": ("Per-resource cleared reserve from IEMOP's DIPC reserve "
                 "results final (DIPCRF), per commodity (Fr contingency, Dr "
                 "dispatchable, Ru/Rd regulation). Each hour is the first "
                 "5-minute interval (HH:05), the same interval the reserve "
                 "offer books are taken at, so the cleared price is directly "
                 "comparable to the reserve replay. hours[grid][commodity][h] "
                 "lists [resource, scheduled_mw, price_php_kwh]; cleared_price "
                 "is the schedule-weighted pool clearing price (uniform per "
                 "pool); sched_mw the pool total. DIPCRF is the FINAL solve; "
                 "rtd_schedule_gap_mw records how far each pool's final "
                 "schedule sits from the real-time RTDSUM schedule (the "
                 "final-run reserve revision), which is not gated. A day is "
                 "refused only if the Luzon reserve book did not populate."),
        "src": "https://www.iemop.ph/market-data/dipc-reserve-results-final/",
        "src_sched": "https://www.iemop.ph/market-data/rtd-regional-summaries/",
    }


def derive(limit: int | None = None, frm: str = "2026-05-01",
           to: str | None = None) -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    post_id, _ = page_config(SLUG)
    listing = list_files(SLUG, post_id)
    by_day: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for b64, name in listing:
        m = re.search(r"DIPCRF_(\d{8})(\d{2})\d{2}", name)
        if m:
            fdate, fhh = m.group(1), int(m.group(2))
            # the 00:00 file holds the previous day's 23:05 opening interval,
            # so assign it there; day D's hour 23 then comes from D+1 00:00
            if fhh == 0:
                fdate = (datetime.strptime(fdate, "%Y%m%d")
                         - timedelta(days=1)).strftime("%Y%m%d")
            by_day[fdate].append((b64, name))
    days = sorted(by_day)
    print(f"listing: {len(listing)} files across {len(days)} days "
          f"({days[0]}..{days[-1]})" if days else "empty listing", flush=True)
    frm_s = frm.replace("-", "")
    to_s = (to or date_cls.today().isoformat()).replace("-", "")
    done = 0
    fail_streak = 0
    for date in days:
        if date < frm_s or date > to_s:
            continue
        hours = sorted(by_day[date], key=lambda t: t[1])
        if len(hours) < 24:
            continue  # newest day still publishing hourly
        out = os.path.join(OUT_DIR, f"RRESD_{date}.json")
        if os.path.isfile(out):
            try:
                with open(out) as fh:
                    if json.load(fh).get("schema_version", 0) >= SCHEMA_VERSION:
                        continue
            except (json.JSONDecodeError, OSError):
                pass
        try:
            day = derive_day(f"{date[:4]}-{date[4:6]}-{date[6:]}", hours[:24])
        except RuntimeError as e:
            print(f"SKIP {date}: {e}", flush=True)
            if "fetch failed" in str(e):
                fail_streak += 1
                if fail_streak >= 3:
                    print("aborting: 3 consecutive fetch-failure days",
                          flush=True)
                    break
                time.sleep(90)
            continue
        fail_streak = 0
        with open(out, "w") as fh:
            json.dump(day, fh, indent=1)
        done += 1
        print(f"derived {date}", flush=True)
        if limit and done >= limit:
            break
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    ap.add_argument("--from", dest="frm", default="2026-05-01")
    ap.add_argument("--to", dest="to", default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.derive:
        n = derive(a.limit, a.frm, a.to)
        print(f"derived {n} day(s)")
    else:
        print(__doc__)
