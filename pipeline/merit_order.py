#!/usr/bin/env python3
"""Derive the operator's own dispatch cut from IEMOP's Regional Merit Order
Table (MOT) files, the one market-data page the archive never named.

Each daily zip is ~3 MB and holds 1,152 members: 4 regions (cluz, cvis,
cmin, sys) x 288 five-minute intervals. A member lists every offer tranche
of that region's stack, split by two markers into an "Offers Not
Dispatched" and an "Offers Dispatched" section, with a Running Total column
that is zero-based AT the cut and grows away from it in both directions:
the not-dispatched total counts up as you read toward the top of the file
(its first row carries the region's whole undispatched MW), the dispatched
total counts up as you read down (its last row carries the region's whole
dispatched MW). Verified across all 288 intervals of a sample day: zero
non-monotone pairs, and the two rows touching the cut carry a running total
equal to their own MW.

What this earns its place on: not-dispatched MW is the operator's OWN
published economic headroom per region per 5-minute interval, which the
supply question currently answers from RTDSUM and registered capacity
instead. MOT is NOT finer-grained than the offer books already archived:
its Block column is the same tranche index as RTDOE's PRICE/QUANTITY
breakpoints, so the subhourly accounting boundary in the methodology
stands untouched.

Measured, not assumed:
  - the dispatched section is strictly ordered most expensive first. Joined
    against RTDOE offer prices on two sample intervals, 0 ascending steps
    of 89 and 0 of 87. The join needs an offset: MOT Block b is the
    resource's b-th priced tranche, while RTDOE's PRICE1 sits at
    QUANTITY1 = 0 (an anchor, not a tranche), so tranche b carries
    PRICE(b+1). Reading the sections as one descending list without that
    offset makes the ordering look broken.
  - the marginal resource is the PARTIALLY CLEARED one, named in both
    sections at once, not the head of the dispatched section. The head is
    only the most expensive thing running, which agreed with the
    operator's own named price setter on 25 percent of intervals; the
    partially-cleared set carries it on 97 to 99 percent against a
    same-size random draw of 20 to 23 percent. Both numbers are published
    together because the first means nothing without the second.
  - MOT's MW is CLEARED, not as-bid: summed per region it tracks RTDSUM
    generation at a ratio of 0.998 to 1.015 (Mindanao MAE 3 to 4 MW on
    ~2,470 MW). Resources show it directly, a coal unit offering a flat
    600 MW all day while its dispatched MW moves between 349 and 600.
  - the sys region is the exact sum of the three grids on every interval
    sampled, so it is parsed past, not stored.

MCP and MOT come out of the same RTD solve, so the agreement rate is not
independent confirmation of the operator's price setter. It is the check
that this module's cut parse reproduces it.

Zips are far too heavy to commit (84 x 3 MB), so this module follows
offers.py and reserve_offers.py: fetch a day transiently, keep the headroom
totals at full 5-minute resolution and the resource names hourly, and
commit only the compact daily JSON under data/derived/merit_order_daily/.

    python3 pipeline/merit_order.py --derive              # newest 3 undone
    python3 pipeline/merit_order.py --derive --limit 10
    python3 pipeline/merit_order.py --derive --from 2026-04-21
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import random
import time
import zipfile
from datetime import date as date_cls
from datetime import datetime, timedelta

import json

from archive_iemop import SLEEP, fetch, list_files, page_config
from offers import RAW, _ts

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "data", "derived", "merit_order_daily")
SLUG = "regional-merit-order-table-mot-files"
SCHEMA_VERSION = 1
# member prefix -> grid. sys is the three grids summed (verified exact on
# every interval sampled), so it carries nothing the parts do not.
REGION = {"cluz": "luzon", "cvis": "visayas", "cmin": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")
INTERVALS = 288
# resource names are the heavy part of the artifact; they are kept at the
# hour's opening interval only, the same HH:05 book the offer stacks use
NAME_MINUTE = 5
# the dispatched total is a cleared-MW sum and RTDSUM is the operator's
# regional generation; they are the same quantity read two ways, so a day
# whose regional means disagree by more than this is a parse bug, not a
# rounding difference (observed 0.2 to 1.5 percent)
GATE_REL = 0.05
# how many random draws back the agreement null; fixed seed so a re-derive
# of the same day reproduces the same number
NULL_SEED = 20260720


def parse_member(text: str) -> tuple[str, list, list]:
    """(interval stamp, not-dispatched rows, dispatched rows) from one MOT
    member. Rows are (resource, mw, block, running_total)."""
    lines = [ln for ln in text.splitlines()
             if ln.strip() and ln.strip() != "EOF"]
    if not lines:
        raise RuntimeError("empty MOT member")
    stamp = lines[0].strip()
    nd: list = []
    dp: list = []
    cur = None
    for ln in lines[1:]:
        if "Offers Not Dispatched" in ln:
            cur = nd
            continue
        if "Offers Dispatched" in ln:
            cur = dp
            continue
        if ln.startswith("Resource ID") or cur is None:
            continue
        parts = ln.split(",")
        if len(parts) < 4:
            continue
        try:
            cur.append((parts[0].strip(), float(parts[1]), int(parts[2]),
                        float(parts[3])))
        except ValueError:
            continue
    return stamp, nd, dp


def cut_of(nd: list, dp: list) -> dict:
    """The dispatch cut of one region-interval. marginal is the set of
    resources named on BOTH sides, the partially cleared ones the clearing
    price runs through; next_up is the not-dispatched tranche sitting
    nearest the cut."""
    dispatched = dp[-1][3] if dp else 0.0
    not_dispatched = nd[0][3] if nd else 0.0
    dn = [r[0] for r in dp]
    marginal = sorted(set(dn) & {r[0] for r in nd})
    # dispatched MW sitting above the marginal tranche: capacity running
    # while the clearing price is lower, the positional out-of-merit read.
    # Usually zero, which is itself the finding.
    above = None
    for i, name in enumerate(dn):
        if name in set(marginal):
            above = round(dp[i][3] - dp[i][1], 1)
            break
    return {
        "dispatched_mw": round(dispatched, 1),
        "not_dispatched_mw": round(not_dispatched, 1),
        "marginal": marginal,
        "next_up": nd[-1][0] if nd else None,
        "above_marginal_mw": above,
    }


def _mcp_setters(date: str) -> dict:
    """{(grid, interval): {resource}} the operator names marginal, from the
    archived MCP dailies. Empty when the day is not archived."""
    path = os.path.join(RAW, "MCP", f"MP_{date.replace('-', '')}.csv")
    if not os.path.isfile(path):
        return {}
    code = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
    out: dict = collections.defaultdict(set)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = code.get((r.get("REGION_NAME") or "").strip())
            ts = _ts((r.get("TIME_INTERVAL") or "").strip())
            res = (r.get("RESOURCE_NAME") or "").strip()
            if g and ts is not None and res:
                out[(g, ts)].add(res)
    return out


def _rtdsum_gen(date: str) -> dict:
    """{(grid, interval): generation MW} for the reconciliation gate."""
    path = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    if not os.path.isfile(path):
        return {}
    code = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
    out: dict = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = code.get((r.get("REGION_NAME") or "").strip())
            ts = _ts((r.get("TIME_INTERVAL") or "").strip())
            if not g or ts is None:
                continue
            try:
                out[(g, ts)] = float(r.get("GENERATION") or 0)
            except ValueError:
                continue
    return out


def _read_zip(path: str, date: str) -> dict:
    """{(grid, interval): (nd rows, dp rows)} from one daily MOT zip."""
    d0 = datetime.strptime(date, "%Y-%m-%d")
    out: dict = {}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        for prefix, grid in REGION.items():
            for i in range(INTERVALS):
                t = (d0 + timedelta(minutes=5 * i)).strftime("%Y%m%d%H%M%S")
                member = f"rtd_smerit_{prefix}_{t}.csv"
                if member not in names:
                    continue
                stamp, nd, dp = parse_member(
                    z.read(member).decode("utf-8", "replace"))
                ts = _ts(stamp) or datetime.strptime(stamp,
                                                     "%Y-%m-%d %H:%M:%S")
                out[(grid, ts)] = (nd, dp)
    return out


def _check_running_totals(nd: list, dp: list, where: str) -> None:
    """The cut invariant: both running totals grow away from the cut and the
    rows touching it carry their own MW. A file that fails this is not the
    format this module parses."""
    for k in range(len(nd) - 1):
        if nd[k][3] < nd[k + 1][3] - 1e-3:
            raise RuntimeError(f"{where}: not-dispatched running total rises")
    for k in range(len(dp) - 1):
        if dp[k][3] > dp[k + 1][3] + 1e-3:
            raise RuntimeError(f"{where}: dispatched running total falls")
    if nd and abs(nd[-1][3] - nd[-1][1]) > 1e-2:
        raise RuntimeError(f"{where}: not-dispatched tail is not zero-based")
    if dp and abs(dp[0][3] - dp[0][1]) > 1e-2:
        raise RuntimeError(f"{where}: dispatched head is not zero-based")


def derive_day(date: str, b64: str, name: str) -> dict:
    """Fetch one daily MOT zip transiently and reduce it to the committed
    record. Raises RuntimeError on fetch failure or a refused gate."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = os.path.join(tmp, name)
        if not fetch(SLUG, b64, dest):
            time.sleep(30)
            if not fetch(SLUG, b64, dest):
                raise RuntimeError(f"merit order: fetch failed for {name}")
        time.sleep(SLEEP)
        day = _read_zip(dest, date)
    if not day:
        raise RuntimeError(f"merit order: no members parsed for {date}")

    d0 = datetime.strptime(date, "%Y-%m-%d")
    stamps = [(d0 + timedelta(minutes=5 * i)) for i in range(INTERVALS)]
    setters = _mcp_setters(date)
    gen = _rtdsum_gen(date)
    rng = random.Random(NULL_SEED)

    dispatched: dict = {g: [None] * INTERVALS for g in GRIDS}
    headroom: dict = {g: [None] * INTERVALS for g in GRIDS}
    marginal: dict = {g: {} for g in GRIDS}
    next_up: dict = {g: {} for g in GRIDS}
    above: dict = {g: [] for g in GRIDS}
    agree: dict = {g: [0, 0] for g in GRIDS}
    null: dict = {g: [0, 0] for g in GRIDS}
    ratio: dict = {g: [] for g in GRIDS}

    for g in GRIDS:
        for i, ts in enumerate(stamps):
            rows = day.get((g, ts))
            if rows is None:
                continue
            nd, dp = rows
            _check_running_totals(nd, dp, f"{date} {g} {ts:%H:%M}")
            cut = cut_of(nd, dp)
            dispatched[g][i] = cut["dispatched_mw"]
            headroom[g][i] = cut["not_dispatched_mw"]
            if cut["above_marginal_mw"] is not None:
                above[g].append(cut["above_marginal_mw"])
            if ts.minute == NAME_MINUTE:
                marginal[g][f"{ts:%H}"] = cut["marginal"]
                next_up[g][f"{ts:%H}"] = cut["next_up"]
            obs = gen.get((g, ts))
            if obs and obs > 1.0:
                ratio[g].append(cut["dispatched_mw"] / obs)
            named = setters.get((g, ts))
            if named and dp:
                mset = set(cut["marginal"])
                agree[g][1] += 1
                if named & mset:
                    agree[g][0] += 1
                # null: the same number of names drawn at random from the
                # region's dispatched resources, so the agreement rate is
                # read against what an uninformed guess would score
                pool = sorted({r[0] for r in dp})
                draw = set(rng.sample(pool, min(len(named), len(pool))))
                null[g][1] += 1
                if draw & mset:
                    null[g][0] += 1

    for g in GRIDS:
        if not ratio[g]:
            raise RuntimeError(f"merit order: no RTDSUM overlap for {date} "
                               f"{g}; gate impossible")
        mean_ratio = sum(ratio[g]) / len(ratio[g])
        if abs(mean_ratio - 1.0) > GATE_REL:
            raise RuntimeError(
                f"merit order: {date} {g} dispatched total is "
                f"{mean_ratio:.3f}x RTDSUM generation; refused")

    def _pct(pair):
        return round(100 * pair[0] / pair[1], 1) if pair[1] else None

    return {
        "date": date,
        "schema_version": SCHEMA_VERSION,
        "intervals": INTERVALS,
        "dispatched_mw": dispatched,
        "not_dispatched_mw": headroom,
        "marginal": marginal,
        "next_up": next_up,
        "above_marginal_mw_mean": {
            g: (round(sum(above[g]) / len(above[g]), 1) if above[g] else None)
            for g in GRIDS},
        "above_marginal_mw_max": {
            g: (round(max(above[g]), 1) if above[g] else None) for g in GRIDS},
        "mcp_agreement": {
            g: {"n_intervals": agree[g][1],
                "agree_pct": _pct(agree[g]),
                "null_pct": _pct(null[g])} for g in GRIDS},
        "rtdsum_ratio": {g: round(sum(ratio[g]) / len(ratio[g]), 4)
                         for g in GRIDS},
        "note": ("The operator's own dispatch cut per region per 5-minute "
                 "RTD interval, from IEMOP's Regional Merit Order Table "
                 "(MOT). Each interval's offer stack is split into an "
                 "offers-not-dispatched and an offers-dispatched section "
                 "whose running totals are zero-based at the cut and grow "
                 "away from it. not_dispatched_mw is the operator's own "
                 "published economic headroom, the MW offered and not "
                 "taken; dispatched_mw is cleared MW, which tracks RTDSUM "
                 "generation (rtdsum_ratio) rather than as-bid quantity. "
                 "Headroom and dispatch are kept every 5 minutes; the "
                 "marginal and next-up resource names are kept at the "
                 "hour's opening interval to keep the daily small. "
                 "marginal is the set of resources named on both sides of "
                 "the cut, the partially cleared ones the clearing price "
                 "runs through; next_up is the not-dispatched tranche "
                 "nearest the cut. MOT carries no price column and its "
                 "Block index is the same tranche index as the RTDOE offer "
                 "books, so it is not a finer view of supply than those "
                 "books already give."),
        "validation_note": ("mcp_agreement scores this module's cut parse "
                            "against the marginal resource IEMOP names in "
                            "the MCP dataset: how often the MCP setter "
                            "falls inside the partially-cleared set, beside "
                            "null_pct, the same score for the same number "
                            "of names drawn at random from that interval's "
                            "dispatched resources. MCP and MOT come out of "
                            "the same RTD solve, so this is a parse check, "
                            "not independent confirmation of the setter. "
                            "The head of the dispatched section is only the "
                            "most expensive resource running and is a much "
                            "worse match for the setter than the "
                            "partially-cleared set."),
        "src": ("https://www.iemop.ph/market-data/"
                "regional-merit-order-table-mot-files/"),
        "src_setters": ("https://www.iemop.ph/market-data/"
                        "rtd-market-clearing-price/"),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def derive(dates: list[str]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    post_id, _ = page_config(SLUG)
    listing = {name: b64 for b64, name in list_files(SLUG, post_id)}
    consec = 0
    for date in dates:
        stamp = date.replace("-", "")
        out = os.path.join(OUT_DIR, f"MOTD_{stamp}.json")
        if os.path.isfile(out):
            try:
                with open(out) as fh:
                    if json.load(fh).get("schema_version", 0) >= SCHEMA_VERSION:
                        continue
            except (json.JSONDecodeError, OSError):
                pass
        name = f"mot_files_{stamp}.zip"
        if name not in listing:
            print(f"SKIP {date}: not in the public window", flush=True)
            continue
        try:
            day = derive_day(date, listing[name], name)
        except (RuntimeError, zipfile.BadZipFile) as e:
            print(f"SKIP {date}: {e}", flush=True)
            consec += 1
            if consec >= 3:
                print("ABORT: 3 consecutive day failures", flush=True)
                return
            continue
        consec = 0
        with open(out, "w") as fh:
            json.dump(day, fh, indent=1)
        agr = day["mcp_agreement"]["luzon"]
        print(f"derived {date} (luzon setter agreement "
              f"{agr['agree_pct']}% vs null {agr['null_pct']}%)", flush=True)


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
    ap.add_argument("--from", dest="frm", default="2026-04-21")
    ap.add_argument("--to", dest="to",
                    default=(date_cls.today() - timedelta(days=6)).isoformat())
    ap.add_argument("--limit", type=int, default=3,
                    help="derive only the newest N underived days")
    a = ap.parse_args()
    if a.derive:
        dates = _market_dates(a.frm, a.to)
        if a.limit:
            underived = [dt for dt in dates if not os.path.isfile(
                os.path.join(OUT_DIR, f"MOTD_{dt.replace('-', '')}.json"))]
            dates = underived[-a.limit:]
        derive(dates)
