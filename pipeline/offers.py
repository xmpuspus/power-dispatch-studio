#!/usr/bin/env python3
"""Derive observed per-grid hourly OFFER stacks from IEMOP's real-time
generation offers (RTDOE), the dataset that retires the cost-proxy guess.

IEMOP publishes every resource's actual offer curve per 5-minute interval
(PRICE1..11 / QUANTITY1..11, cumulative MW breakpoints, floor -10,000 to
cap 32,000 PhP/MWh) in hourly CSVs with a few days' publication lag. The
files are ~0.5 MB per hour, too heavy to commit raw, so this module works
like fuelmix.py: fetch a day's 24 hourly files transiently, aggregate each
hour's offers into one per-grid supply stack, compact it to at most
MAX_BLOCKS price blocks, and commit only the compact daily JSON under
data/derived/offer_daily/.

Semantics and gates:
  - the hour's stack is the offer book at the hour's FIRST interval
    (HH:05); resources re-offer within the hour, and one representative
    book per hour is what an hourly LP can use (stated here, not
    hidden).
  - hourly files are end-labeled like DIPCEF: day D hour h lives in the
    file stamped D_(h+1)00, and h=23 in (D+1)_0000.
  - reconciliation gate: each grid-hour's offered MW total must be at
    least that hour's dispatched generation (RTDSUM); a book smaller than
    what actually ran means a parse or coverage bug, and the day is
    refused, not written.
  - prices are divided by 1,000 to PhP/kWh, matching every other artifact.

The compact stacks are drop-in engine inputs: the same {cost, mw} blocks
the cost-proxy merit order feeds the day LP, so an offer-mode replay needs
no LP change on either engine.

    python3 pipeline/offers.py --derive --limit 3   # newest N underived
    python3 pipeline/offers.py --derive --from 2026-05-01 --to 2026-06-25
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import time
from datetime import date as date_cls
from datetime import datetime, timedelta

from archive_iemop import BASE, curl
from pasa import _alias_for, grid_of_prefix

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT_DIR = os.path.join(HERE, "..", "data", "derived", "offer_daily")
SLUG = "rtd-generation-offers"
SSN_SLUG = "rtd-self-scheduled-nominations"
SERVER = "/var/www/html/wp-content/uploads/downloads/data"
REGION = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
MAX_BLOCKS = 48
# artifact schema: 2 adds the fuel-classified coal series and the
# min-stable-floor variant book (hours_floor); derive() rewrites any
# committed daily below this version
SCHEMA_VERSION = 2
# the WESM offer floor (-10,000 PhP/MWh) in PhP/kWh; self-scheduled MW
# enters the stack here as price-taking capacity
OFFER_FLOOR = -10.0
SLEEP = 0.3


# verified abbreviation -> fuel: each entry checked by hand against the DOE
# fleet (grid + plausible MW). Fuel-level only: the codes' unit mapping can
# stay ambiguous as long as every candidate row burns the same fuel.
FUEL_ALIAS = {"GNPD": "coal", "SUAL": "coal", "QPPL": "coal",
              "MSINLO": "coal", "MINBAL": "coal", "PALM": "coal",
              "SMC": "coal"}

_fleet_cache: dict | None = None


def _fleet_index():
    global _fleet_cache
    if _fleet_cache is None:
        import re as _re
        path = os.path.join(HERE, "..", "web", "data", "fleet.json")
        fleet = json.load(open(path))
        _fleet_cache = {
            "by_name": {p["name"]: p for p in fleet["plants"]},
            "norm": [(_re.sub(r"[^A-Z0-9]", "", p["name"].upper()), p)
                     for p in fleet["plants"]],
        }
    return _fleet_cache


def classify_fuel(res: str) -> str | None:
    """Fuel of an offer-book resource code, or None. Three verified paths:
    the pasa alias table (authoritative), the hand-verified FUEL_ALIAS
    abbreviations, then a fuel-tolerant core match against the DOE fleet
    (accepted only when every candidate row in the code's grid agrees on
    one fuel). Anything else stays unclassified; coverage is stated in the
    artifact, never guessed."""
    import re as _re
    idx = _fleet_index()
    alias = _alias_for(res)
    if alias:
        row = idx["by_name"].get(alias[0])
        if row:
            return row["fuel"]
    grid = grid_of_prefix(res)
    core = _re.sub(r"^\d+", "", res.split("_")[0])
    if core in FUEL_ALIAS:
        return FUEL_ALIAS[core]
    core_n = _re.sub(r"[^A-Z0-9]", "", core.upper())
    if len(core_n) < 3:
        return None
    fuels = {p["fuel"] for n, p in idx["norm"]
             if (core_n in n or n.startswith(core_n))
             and (grid is None or p["grid"] == grid)}
    return fuels.pop() if len(fuels) == 1 else None


def _fetch_hour_csv(slug: str, prefix: str, stamp: str) -> list[dict] | None:
    """Fetch <prefix>_<stamp>.csv transiently; None on failure."""
    path = f"{SERVER}/{prefix}/{prefix}_{stamp}.csv"
    b64 = base64.b64encode(path.encode()).decode()
    for attempt in range(3):
        code, body = curl([f"{BASE}/{slug}/?md_file={b64}"], timeout=120)
        head = body[:200].lstrip().lower()
        if code == 0 and body and not head.startswith(b"<"):
            return list(csv.DictReader(io.StringIO(
                body.decode("utf-8", "replace"))))
        time.sleep(5 + 10 * attempt)
    return None


def _first_interval(rows: list[dict]) -> str | None:
    """The hour file's earliest TIME_INTERVAL (the HH:05 book)."""
    stamps = sorted({(r.get("TIME_INTERVAL") or "").strip()
                     for r in rows if (r.get("TIME_INTERVAL") or "").strip()},
                    key=lambda s: _ts(s) or datetime.max)
    return stamps[0] if stamps else None


def _ts(s: str) -> datetime | None:
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _segments(r: dict) -> list[tuple[float, float]]:
    """(price PhP/kWh, mw width) segments from one resource's cumulative
    breakpoints."""
    out = []
    prev_q = 0.0
    for i in range(1, 12):
        p = (r.get(f"PRICE{i}") or "").strip()
        q = (r.get(f"QUANTITY{i}") or "").strip()
        if not p or not q:
            break
        try:
            price, qty = float(p) / 1000, float(q)
        except ValueError:
            break
        width = qty - prev_q
        if width > 1e-9:
            out.append((price, width))
        prev_q = max(prev_q, qty)
    return out


def _compact(blocks: list[tuple[float, float]],
             max_blocks: int = MAX_BLOCKS) -> list[tuple[float, float]]:
    """Sort by price, merge equal prices, then merge the closest adjacent
    price levels until at most max_blocks remain (MW-weighted price)."""
    merged: dict[float, float] = {}
    for price, mw in blocks:
        key = round(price, 3)
        merged[key] = merged.get(key, 0.0) + mw
    levels = sorted(merged.items())
    while len(levels) > max_blocks:
        gaps = [(levels[i + 1][0] - levels[i][0], i)
                for i in range(len(levels) - 1)]
        _, i = min(gaps)
        (p1, m1), (p2, m2) = levels[i], levels[i + 1]
        pw = round((p1 * m1 + p2 * m2) / (m1 + m2), 3)
        levels[i:i + 2] = [(pw, m1 + m2)]
    return [(p, round(m, 1)) for p, m in levels if m > 0.05]


def _rtdsum_gen(date: str) -> dict[str, dict[int, float]] | None:
    """{grid: {hour: mean dispatched generation MW}} for the gate."""
    p = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    if not os.path.isfile(p):
        return None
    from dispatch import hour_of
    acc: dict[str, dict[int, list[float]]] = {g: {} for g in REGION.values()}
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            if not g:
                continue
            try:
                gen = float(r.get("GENERATION") or 0)
            except ValueError:
                continue
            h = hour_of((r.get("TIME_INTERVAL") or "").strip())
            acc[g].setdefault(h, []).append(gen)
    return {g: {h: sum(v) / len(v) for h, v in by_h.items()}
            for g, by_h in acc.items()}


def derive_day(date: str) -> dict:
    """Fetch the day's 24 hourly books, build compact per-grid stacks.
    Raises RuntimeError when a fetch fails or the gate refuses."""
    d = datetime.strptime(date, "%Y-%m-%d")
    hours: dict[str, list[list[list[float]] | None]] = {
        g: [None] * 24 for g in REGION.values()}
    coal_mw: dict[str, list[float]] = {g: [0.0] * 24 for g in REGION.values()}
    offered_mw_sum = {g: 0.0 for g in REGION.values()}
    classified_mw_sum = {g: 0.0 for g in REGION.values()}
    n_res = 0
    for h in range(24):
        end = d + timedelta(hours=h + 1)
        stamp = end.strftime("%Y%m%d%H%M")
        rows = _fetch_hour_csv(SLUG, "RTDOE", stamp)
        time.sleep(SLEEP)
        if rows is None:
            raise RuntimeError(f"offers: fetch failed for {date} h{h} "
                               f"(RTDOE_{stamp})")
        ssn = _fetch_hour_csv(SSN_SLUG, "RTDNE", stamp)
        time.sleep(SLEEP)
        if ssn is None:
            raise RuntimeError(f"offers: fetch failed for {date} h{h} "
                               f"(RTDNE_{stamp})")
        first = _first_interval(rows)
        if first is None:
            raise RuntimeError(f"offers: empty book for {date} h{h}")
        per_grid: dict[str, list[tuple[float, float]]] = {
            g: [] for g in REGION.values()}

        seen = set()
        for r in rows:
            if (r.get("TIME_INTERVAL") or "").strip() != first:
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            res = (r.get("RESOURCE_NAME") or "").strip()
            if not g or not res:
                continue
            seen.add(res)
            segs = _segments(r)
            per_grid[g].extend(segs)
            mw = sum(m for _, m in segs)
            offered_mw_sum[g] += mw
            fuel = classify_fuel(res)
            if fuel:
                classified_mw_sum[g] += mw
            if fuel == "coal":
                coal_mw[g][h] += mw
        # self-scheduled capacity offers no curve; it enters as one
        # price-taking block at the offer floor (nuclear option of the
        # merit order: it runs whenever the grid runs)
        ssn_first = _first_interval(ssn)
        for r in ssn:
            if (r.get("TIME_INTERVAL") or "").strip() != ssn_first:
                continue
            g = REGION.get((r.get("REGION_NAME") or "").strip())
            if not g:
                continue
            try:
                mw = float(r.get("SELF_SCHED_MW") or 0)
            except ValueError:
                continue
            if mw > 1e-9:
                per_grid[g].append((OFFER_FLOOR, mw))
        n_res = max(n_res, len(seen))
        for g in REGION.values():
            if per_grid[g]:
                hours[g][h] = [[p, m] for p, m in _compact(per_grid[g])]
            coal_mw[g][h] = round(coal_mw[g][h], 1)
    gen = _rtdsum_gen(date)
    if gen is None:
        raise RuntimeError(f"offers: no RTDSUM for {date}; gate impossible")
    for g in REGION.values():
        for h in range(24):
            offered = sum(m for _, m in (hours[g][h] or []))
            served = gen.get(g, {}).get(h)
            if served is not None and offered < served - 1.0:
                raise RuntimeError(
                    f"offers: {date} {g} h{h} book {offered:.0f} MW < "
                    f"dispatched {served:.0f} MW; refused")
    tot_off = sum(offered_mw_sum.values())
    tot_cls = sum(classified_mw_sum.values())
    return {
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "hours": hours,
        "coal_mw": coal_mw,
        "fuel_classified_share_pct": (
            round(100 * tot_cls / tot_off, 1) if tot_off else None),
        "classification_note": ("coal_mw is the hour's offered MW from "
                                "resources classified as coal (pasa alias "
                                "+ hand-verified abbreviations + a "
                                "fuel-tolerant fleet match; coverage "
                                "stated). A min-stable floor carved from "
                                "this series was MEASURED INERT before "
                                "shipping: the coal fleet already offers "
                                "its committed tranche at the price floor "
                                "(the 40 percent carve left the books "
                                "byte-identical), so commitment behavior "
                                "is in the bids, not missing from them."),
        "max_resources_seen": n_res,
        "max_blocks": MAX_BLOCKS,
        "note": ("Observed per-grid hourly offer stacks from IEMOP's "
                 "real-time generation offers (RTDOE) plus self-scheduled "
                 "nominations (RTDNE, price-taking at the offer floor: "
                 "capacity that runs whenever the grid runs and submits no "
                 "curve): each hour is the book at the hour's first "
                 "5-minute interval, all segments pooled and compacted to "
                 f"at most {MAX_BLOCKS} price blocks (MW-weighted merges). "
                 "Prices PhP/kWh, floor to cap as offered. Gate: each "
                 "grid-hour's book must cover that hour's dispatched "
                 "generation or the day is refused."),
        "src": "https://www.iemop.ph/market-data/rtd-generation-offers/",
        "src_ssn": ("https://www.iemop.ph/market-data/"
                    "rtd-self-scheduled-nominations/"),
    }


def derive(dates: list[str]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    consec = 0
    for date in dates:
        out = os.path.join(
            OUT_DIR, f"OFFERD_{date.replace('-', '')}.json")
        if os.path.isfile(out):
            try:
                with open(out) as fh:
                    if json.load(fh).get("schema_version", 1) >= SCHEMA_VERSION:
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
    ap.add_argument("--from", dest="frm", default="2026-05-01")
    ap.add_argument("--to", dest="to",
                    default=(date_cls.today() - timedelta(days=6)).isoformat())
    ap.add_argument("--limit", type=int, default=None,
                    help="derive only the newest N underived days")
    a = ap.parse_args()
    if a.derive:
        dates = _market_dates(a.frm, a.to)
        if a.limit:
            underived = [dt for dt in dates if not os.path.isfile(
                os.path.join(OUT_DIR, f"OFFERD_{dt.replace('-', '')}.json"))]
            dates = underived[-a.limit:]
        derive(dates)
