#!/usr/bin/env python3
"""Per-node daily price surfaces from DIPCEF, derived and committed compactly.

DIPCEF (nodal LMP results, final) prices every WESM resource node per
5-minute interval and decomposes each LMP into LMP_SMP + LMP_LOSS +
LMP_CONGESTION. The raw files are hourly zips, too heavy to commit (the
public window would be ~200 MB), and the window rolls at ~90 days, so
like fuelmix.py this module fetches a day's 24 hourly zips transiently,
compacts them to one JSON per day under data/derived/nodal_daily/, and
discards the zips. The derived dailies ARE the durable nodal-price
record; fuelmix.py keeps the energy side (SCHED_MW), this keeps the
price side.

What the sampled window shows: the published LMP_CONGESTION component is
zero through the WESM suspension window and small and intermittent after
real-time pricing resumed on 2026-05-01 (nonzero on 28 of the 70 sampled
days, up to about 19 PhP/kWh, but only 1.18 percent of clean-day
node-hours). The SMP is region-constant per interval, so most within-region
locational separation rides LMP_LOSS, inter-regional congestion appears as
the regional SMPs splitting, and the small nodal congestion that is priced
is sparse rather than a persistent per-node charge. The artifact
therefore stores, per node, the hourly mean DEVIATION from the node's
regional SMP (loss + congestion, PhP/kWh), plus the regional SMP series
and the day's pricing-flag tally (OK / PSM / SEC), and keeps a sparse
congestion map that stays empty unless IEMOP starts populating the
column.

Semantics and gates:
  - hourly files are end-labeled (offers.py convention): day D hour h
    lives in the file stamped D_(h+1)00, and h=23 in (D+1)_0000, so a
    day derives only once the NEXT day's first file publishes.
  - rows bin to hours with the shared dispatch.hour_of convention
    (printed hour; the bare-date midnight row belongs to the PREVIOUS
    day's hour 23).
  - decomposition gate: max |LMP - (SMP + LOSS + CONGESTION)| across the
    day must stay under 0.01 PhP/MWh or the day is refused, not written.
    Each node's deviation uses its own row's decomposition, so it is exact
    under that gate.
  - the SMP column is NOT always region-constant: administered (PSM/SEC)
    intervals carry a bimodal SMP (a base value and the same value about
    1.0217x higher, observed 2026-05-08 and 2026-06-25). The regional
    reference series therefore takes the per-interval MODE, and the day
    records how many intervals were multimodal instead of refusing.
  - prices are divided by 1,000 to PhP/kWh, matching every other artifact.

    python3 pipeline/nodal_prices.py --derive             # top up missing days
    python3 pipeline/nodal_prices.py --derive --limit 3   # bounded run
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from archive_iemop import fetch, list_files, page_config
from dispatch import hour_of

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "..", "data", "derived", "nodal_daily")
SLUG = "dipc-energy-results-final"
REGION = {"LUZON": "luzon", "VISAYAS": "visayas", "MINDANAO": "mindanao"}
SCHEMA_VERSION = 1
IDENTITY_TOL_PHP_MWH = 0.01

_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _day_of_interval(ti: str) -> str | None:
    """YYYYMMDD the interval belongs to. The bare-date midnight row (no time
    part) is the interval ENDING at that printed midnight: previous day."""
    m = _DATE_RE.search(ti or "")
    if not m:
        return None
    d = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    if ":" not in ti:
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


def _hour_files_for(date: str, listing: dict[str, str]) -> list[tuple[str, str]] | None:
    """The 24 end-labeled zips covering day D: D_0100..D_2300 + (D+1)_0000."""
    nxt = (datetime.strptime(date, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
    names = [f"DIPCEF_{date}{h:02d}00.zip" for h in range(1, 24)]
    names.append(f"DIPCEF_{nxt}0000.zip")
    out = []
    for n in names:
        if n not in listing:
            return None
        out.append((listing[n], n))
    return out


def derive_day(date: str, hour_files: list[tuple[str, str]]) -> dict:
    """Fetch one day's hourly zips to temp, bin to hours, compact."""
    smp_ti: dict[tuple[str, str], Counter] = defaultdict(Counter)
    hour_ti: dict[tuple[str, str], int] = {}
    dev: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    mw: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    cong: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    grid_of: dict[str, str] = {}
    flags: dict[str, Counter] = defaultdict(Counter)
    worst_resid = 0.0
    n_rows = 0
    with tempfile.TemporaryDirectory() as tmp:
        for n_file, (b64, name) in enumerate(hour_files):
            dest = os.path.join(tmp, name)
            ok = fetch(SLUG, b64, dest)
            time.sleep(0.5)
            if not ok:
                # transient mid-window failures are common; one paused retry
                print(f"  retry {name}", flush=True)
                time.sleep(45)
                ok = fetch(SLUG, b64, dest)
                time.sleep(0.5)
            if not ok:
                raise RuntimeError(f"fetch failed: {name}")
            if n_file % 6 == 0:
                print(f"  {name} ok ({n_file + 1}/24)", flush=True)
            with zipfile.ZipFile(dest) as z:
                for member in z.namelist():
                    with z.open(member) as fh:
                        rd = csv.DictReader(
                            io.TextIOWrapper(fh, "utf-8", errors="replace")
                        )
                        for r in rd:
                            res = (r.get("RESOURCE_NAME") or "").strip()
                            ti = r.get("TIME_INTERVAL") or ""
                            if not res or _day_of_interval(ti) != date:
                                continue
                            g = REGION.get((r.get("REGION_NAME") or "").strip())
                            if not g:
                                continue
                            h = hour_of(ti)
                            if h is None:
                                continue
                            lmp = float(r.get("LMP") or 0)
                            s = float(r.get("LMP_SMP") or 0)
                            lo = float(r.get("LMP_LOSS") or 0)
                            c = float(r.get("LMP_CONGESTION") or 0)
                            worst_resid = max(worst_resid, abs(lmp - (s + lo + c)))
                            smp_ti[(g, ti)][round(s, 2)] += 1
                            hour_ti[(g, ti)] = h
                            dev[res][h].append(lmp - s)
                            mw[res][h].append(float(r.get("SCHED_MW") or 0))
                            if c:
                                cong[res][h].append(c)
                            grid_of[res] = g
                            flags[g][(r.get("PRICING_FLAG") or "?").strip()] += 1
                            n_rows += 1
    if worst_resid > IDENTITY_TOL_PHP_MWH:
        raise RuntimeError(
            f"{date}: decomposition residual {worst_resid:.4f} PhP/MWh exceeds the gate"
        )
    # regional reference SMP: per-interval mode (administered intervals are
    # bimodal), averaged into the shared hour bins
    smp: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    multimodal = 0
    for (g, ti), cnt in smp_ti.items():
        if len(cnt) > 1:
            multimodal += 1
        smp[g][hour_ti[(g, ti)]].append(cnt.most_common(1)[0][0])
    hours_covered = {h for g in smp.values() for h in g}
    if len(hours_covered) < 24:
        raise RuntimeError(f"{date}: only {len(hours_covered)} hours covered")

    def hourly(
        acc: dict[int, list[float]], dp: int, scale: float = 1000.0
    ) -> list[float | None]:
        return [
            round(sum(acc[h]) / len(acc[h]) / scale, dp) if acc.get(h) else None
            for h in range(24)
        ]

    return {
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "schema_version": SCHEMA_VERSION,
        "n_rows": n_rows,
        "smp_multimodal_intervals": multimodal,
        "regions": {g: {"smp_php_kwh": hourly(smp[g], 4)} for g in sorted(smp)},
        "pricing_flags": {g: dict(flags[g].most_common()) for g in sorted(flags)},
        "nodes": {
            res: {
                "grid": grid_of[res],
                "dev_php_kwh": hourly(dev[res], 3),
                "mw": hourly(mw[res], 2, scale=1.0),
            }
            for res in sorted(dev)
        },
        "congestion_php_kwh": {
            res: {
                str(h): round(sum(v) / len(v) / 1000, 3) for h, v in sorted(hs.items())
            }
            for res, hs in sorted(cong.items())
        },
        "note": (
            "Per-node hourly mean deviation from the regional SMP "
            "(LMP - SMP = loss + congestion, PhP/kWh), from DIPCEF "
            "final 5-minute results, derived at archive time because "
            "the raw hourly zips are too heavy to commit and the "
            "public window rolls. The published LMP_CONGESTION column is "
            "zero through the WESM suspension window and small and "
            "intermittent after real-time pricing resumed on 2026-05-01; "
            "congestion_php_kwh carries the nonzero node-hours."
        ),
    }


def derive(limit: int | None = None) -> int:
    os.makedirs(DERIVED, exist_ok=True)
    post_id, _ = page_config(SLUG)
    listing_pairs = list_files(SLUG, post_id)
    listing = {name: b64 for b64, name in listing_pairs}
    days = sorted(
        {m.group(1) for n in listing if (m := re.search(r"DIPCEF_(\d{8})\d{4}", n))}
    )
    print(
        f"listing: {len(listing)} files across {len(days)} days ({days[0]}..{days[-1]})"
        if days
        else "empty listing",
        flush=True,
    )
    done = 0
    fetch_fail_streak = 0
    for date in days:
        out = os.path.join(DERIVED, f"NODALD_{date}.json")
        if os.path.isfile(out):
            continue
        hours = _hour_files_for(date, listing)
        if hours is None:
            continue  # end-labeled set incomplete (newest day, or window edge)
        try:
            day = derive_day(date, hours)
        except RuntimeError as e:
            print(f"SKIP {date}: {e}", flush=True)
            if "fetch failed" in str(e):
                # courtesy: IEMOP firewalls repeated HTTP errors; back off
                fetch_fail_streak += 1
                if fetch_fail_streak >= 3:
                    print("aborting: 3 consecutive fetch-failure days", flush=True)
                    break
                time.sleep(90)
            continue
        fetch_fail_streak = 0
        with open(out, "w") as f:
            json.dump(day, f, indent=None, separators=(",", ":"))
        done += 1
        pf = {g: max(v, key=v.get) for g, v in day["pricing_flags"].items()}
        print(f"derived {date}: {day['n_rows']} rows, dominant flags {pf}", flush=True)
        if limit and done >= limit:
            break
    return done


if __name__ == "__main__":
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--derive" in sys.argv:
        n = derive(limit)
        print(f"derived {n} day(s)")
    else:
        print(__doc__)
