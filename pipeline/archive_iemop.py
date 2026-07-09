#!/usr/bin/env python3
"""Archive IEMOP public market-data files into data/raw/<KEY>/.

IEMOP's public window is a rolling ~90 days per dataset page; this archiver plus
the daily cron turns that window into a permanent public archive (git history is
the archive). Access mechanic verified 2026-07-05: each market-data page embeds
post_id + min_date in a `var php = {...}` blob; POST to wp-admin/admin-ajax.php
with action=display_filtered_market_data_files returns the full base64 file list;
GET <page>?md_file=<b64> serves the file. No auth.

Courtesy rules (IEMOP firewalls repeated errors): sequential fetches, 0.25 s
sleep between requests, abort a dataset after 5 consecutive failures.

Uses curl via subprocess (macOS python3 + requests has TLS issues; curl exists
on both macOS and ubuntu runners).

    python3 pipeline/archive_iemop.py --backfill                # full window
    python3 pipeline/archive_iemop.py --daily     # newer than newest on disk
    python3 pipeline/archive_iemop.py --check     # staleness gate (cron tail)
    python3 pipeline/archive_iemop.py --only RTDCV,LWAPF
    python3 pipeline/archive_iemop.py --backfill --dipcef-days 3
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
BASE = "https://www.iemop.ph/market-data"
AJAX = "https://www.iemop.ph/wp-admin/admin-ajax.php"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SLEEP = 0.25
MAX_CONSECUTIVE_ERRORS = 5
PHT = timezone(timedelta(hours=8))

# key -> iemop.ph/market-data/<slug>/. DIPCEF is hourly zips (nodal LMP with the
# LMP_CONGESTION component); fetched for the last --dipcef-days only to keep the
# repo light. Everything else is one small CSV per day.
DATASETS = {
    "RTDCV": "congestions-manifesting-in-rtd",
    "DAPCV": "congestions-manifesting-in-dap",
    "RTDSUM": "rtd-regional-summaries",
    "LWAPF": "load-weighted-average-prices-final",
    "HVDCRTD": "hvdc-limits-imposed-in-rtd",
    "OUTRTD": "outage-schedules-used-in-rtd",
    "DIPCEF": "dipc-energy-results-final",
    # the page renamed to the plural slug at some point; the old singular
    # 301s and the archiver's curl does not follow redirects (caught in
    # the round-8 diff review; latent because RTDRS is a SAMPLE_KEY the
    # daily cron never touches)
    "RTDRS": "rtd-reserve-schedules",
    # Added 2026-07-07 (the analyst-parity pass). One small CSV per day each:
    # MCP names the marginal RESOURCE per region per 5-min interval (the
    # observed price setter); RSVPR is the official regional reserve prices;
    # CAPEG is registered maximum capacity per resource (the resource->MW
    # key the outage and reserve mappings need); MPI is the NSO advisory
    # stream (HVDC blocks/de-blocks, alerts); WAPOS is the week-ahead
    # projection outage schedule (forward-looking); MRU is the processed
    # must-run-unit instruction list (weekly file, range-stamped).
    "MCP": "rtd-market-clearing-price",
    "RSVPR": "rtd-regional-reserve-prices",
    "CAPEG": "registered-capacity-generation",
    "MPI": "mpi-advisories",
    "WAPOS": "outage-schedules-used-in-wap",
    "MRU": "list-of-must-run-units-based-on-so-dispatch-instruction-report",
    # Added 2026-07-08 (the round-7 convergence critic enumerated the full
    # market-data sitemap: 57 pages then, 58 as of 2026-07-09, the archive
    # carried 14, and three of the unused pages falsified written boundary
    # claims). GWAPF is the
    # per-region generator weighted average price per 5-min interval, the
    # series the ERC secondary cap's 72-hour rolling trigger runs on
    # (methodology had called it unpublished); RTDHS is the per-interval
    # HVDC schedule (flow, congestion flag, overload MW), the operator's
    # own corridor record (methodology had called the advisory stream the
    # only observed record). RTDOR (per-participant reserve offers) is
    # hourly and too heavy to keep raw; pipeline/reserve_offers.py derives
    # daily books from it, mirroring offers.py.
    "GWAPF": "generator-weighted-average-price-final",
    "RTDHS": "rtd-hvdc-schedules",
    # Added 2026-07-09 (the round-8 convergence critic): PSMCOG is the
    # operator's roster of generators network/security constraints force
    # ON out of merit, named per 5-minute interval with the cleared or
    # substituted price (a final-calculation dataset, published about two
    # weeks behind); RTDSL is the per-resource security limit used in RTD
    # (MAX/MIN operating MW per window; in practice MAX equals MIN, the
    # security-pinned operating point), next-day current. Both sit
    # squarely on the congestion question and neither had an in-repo
    # substitute.
    "PSMCOG": "psm-constrained-on-generators",
    "RTDSL": "security-limits-used-in-rtd",
}

# Large datasets kept as a static SAMPLE of recent days, not the full public
# window: one day is multi-MB, so committing 90 of them would bloat the repo.
# The daily cron fetches 0 of these (sample_days defaults to 0 on --daily); a
# human tops up the sample with --sample-days N on a backfill. RTDRS (reserve
# schedules with co-optimised reserve clearing prices) joins DIPCEF here.
SAMPLE_KEYS = {"DIPCEF", "RTDRS"}


def curl(args: list[str], timeout: int = 60) -> tuple[int, bytes]:
    """Run curl, return (exit_code, stdout_bytes)."""
    try:
        p = subprocess.run(["curl", "-s", "-m", str(timeout), "-A", UA] + args,
                           capture_output=True, timeout=timeout + 15)
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, b""


def _curl_retry(args: list[str], timeout: int = 60,
                tries: int = 3) -> tuple[int, bytes]:
    """curl with retries for IEMOP's transient TLS resets (exit 35 on
    roughly one listing call in six under load); backs off between tries."""
    code, body = 1, b""
    for attempt in range(tries):
        code, body = curl(args, timeout)
        if code == 0 and body:
            return code, body
        time.sleep(3 + 7 * attempt)
    return code, body


def page_config(slug: str) -> tuple[str, str]:
    """Return (post_id, min_date) from the dataset page's php config blob."""
    code, body = _curl_retry(["-L", f"{BASE}/{slug}/"])
    if code != 0 or not body:
        raise RuntimeError(f"page fetch failed for {slug} (curl exit {code})")
    text = body.decode("utf-8", "replace").replace("\\", "")
    pid = re.search(r'"post_id":"(\d+)"', text)
    mind = re.search(r'"min_date":"([^"]+)"', text)
    if not pid:
        raise RuntimeError(f"no post_id found on {slug}")
    return pid.group(1), (mind.group(1) if mind else "")


def list_files(slug: str, post_id: str) -> list[tuple[str, str]]:
    """Return [(b64_server_path, filename), ...] newest first."""
    code, body = _curl_retry(["-X", "POST", AJAX, "--data",
                              "action=display_filtered_market_data_files&sort="
                              f"&datefilter=&page=1&post_id={post_id}"])
    if code != 0 or not body:
        raise RuntimeError(f"ajax list failed for {slug} (curl exit {code})")
    data = json.loads(body)
    out = []
    for b64 in data.get("source", []):
        try:
            path = base64.b64decode(b64).decode()
        except Exception:
            continue
        name = os.path.basename(path)
        if name:
            out.append((b64, name))
    return out


def looks_valid(dest: str) -> bool:
    """A real file, not the WP 404 page. Header-only CSVs (a day with no
    congestion) are valid and small, so the floor is low."""
    if not os.path.isfile(dest) or os.path.getsize(dest) < 20:
        return False
    with open(dest, "rb") as f:
        head = f.read(200).lstrip().lower()
    return not (head.startswith(b"<!doctype") or head.startswith(b"<html"))


def fetch(slug: str, b64: str, dest: str) -> bool:
    code, body = curl([f"{BASE}/{slug}/?md_file={b64}", "-o", dest])
    if code != 0:
        # curl -o writes partial output on failure; a truncated file left on
        # disk would pass looks_valid() next run and poison the archive.
        if os.path.exists(dest):
            os.remove(dest)
        return False
    if not looks_valid(dest):
        if os.path.exists(dest):
            os.remove(dest)
        return False
    return True


def recent_pht_stamps(days: int) -> set[str]:
    now = datetime.now(PHT)
    return {(now - timedelta(days=d)).strftime("%Y%m%d") for d in range(days)}


def wanted(key: str, name: str, mode: str, sample_days: int,
           newest_stamp: str = "", newest_on_disk: str = "") -> bool:
    m = re.search(r"(\d{8})", name)
    stamp = m.group(1) if m else ""
    if key in SAMPLE_KEYS:
        # Sample datasets keep only the most recent N days, filtered relative to
        # the newest stamp IN THE LISTING (final files lag publication by days),
        # not to today. sample_days <= 0 fetches none (the daily-cron default).
        if sample_days <= 0 or not stamp or not newest_stamp:
            return False
        anchor = datetime.strptime(newest_stamp, "%Y%m%d")
        keep = {(anchor - timedelta(days=d)).strftime("%Y%m%d")
                for d in range(sample_days)}
        return stamp in keep
    if mode == "daily":
        # Fetch everything newer than what is already on disk, not a fixed
        # 2-day lookback: final datasets publish with a lag (LWAPF ran ~10
        # days behind when measured on 2026-07-05), and a cron outage must
        # self-heal within the public window instead of leaving holes.
        if newest_on_disk:
            return stamp > newest_on_disk
        return stamp in recent_pht_stamps(2)
    return True


def archive(keys: list[str], mode: str, sample_days: int) -> list[str]:
    """Fetch into data/raw/, update manifest.json, return failure strings."""
    manifest_path = os.path.join(RAW, "manifest.json")
    manifest = {}
    failures: list[str] = []
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    for key in keys:
        slug = DATASETS[key]
        ddir = os.path.join(RAW, key)
        os.makedirs(ddir, exist_ok=True)
        try:
            post_id, min_date = page_config(slug)
            time.sleep(SLEEP)
            files = list_files(slug, post_id)
        except (RuntimeError, json.JSONDecodeError) as e:
            print(f"{key}: LIST FAILED: {e}")
            failures.append(f"{key}: list failed: {e}")
            continue
        fetched = skipped = errors = 0
        consecutive = 0
        stamps_all = [m.group(1) for _, n in files
                      if (m := re.search(r"(\d{8})", n))]
        newest_stamp = max(stamps_all) if stamps_all else ""
        on_disk = [m.group(1) for n in os.listdir(ddir)
                   if (m := re.search(r"(\d{8})", n))]
        newest_on_disk = max(on_disk) if on_disk else ""
        for b64, name in files:
            if not wanted(key, name, mode, sample_days, newest_stamp,
                          newest_on_disk):
                continue
            dest = os.path.join(ddir, name)
            if looks_valid(dest):
                skipped += 1
                continue
            ok = fetch(slug, b64, dest)
            time.sleep(SLEEP)
            if ok:
                fetched += 1
                consecutive = 0
            else:
                errors += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_ERRORS:
                    print(f"{key}: aborting after {consecutive} consecutive errors")
                    failures.append(f"{key}: aborted after {consecutive} "
                                    "consecutive fetch errors")
                    break
        have = sorted(os.listdir(ddir))
        stamps = [re.search(r"(\d{8})", n).group(1)
                  for n in have if re.search(r"(\d{8})", n)]
        manifest[key] = {
            "slug": slug, "post_id": post_id, "page_min_date": min_date,
            "files": len(have),
            "bytes": sum(os.path.getsize(os.path.join(ddir, n)) for n in have),
            "oldest": min(stamps) if stamps else None,
            "newest": max(stamps) if stamps else None,
        }
        print(f"{key}: listed {len(files)}, fetched {fetched}, "
              f"skipped {skipped}, errors {errors}, on disk {len(have)}")
    manifest["fetched_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    os.makedirs(RAW, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    return failures


# Publication-lag budget per dataset, in days behind today (PHT). LWAPF is a
# settlement-final series and ran ~10 days behind when measured 2026-07-05;
# DIPCEF is a static sample by design and is exempt. A dataset older than its
# budget means the cron has been failing silently: --check exits nonzero so
# the workflow goes red instead.
# MRU is a WEEKLY processed report (12 files across the 90-day window),
# so its budget is a week of cadence plus a week of publication lag; the
# 4-day default tripped the gate on 2026-07-08 with the source itself
# simply between weekly prints.
# PSMCOG is a final-calculation dataset: the newest file trails the
# market day by about two weeks, so its budget is that lag plus slack.
LAG_BUDGET_DAYS = {"LWAPF": 16, "GWAPF": 16, "MRU": 14, "PSMCOG": 24,
                   "DIPCEF": None, "RTDRS": None}
LAG_DEFAULT_DAYS = 4


def check_staleness() -> int:
    manifest_path = os.path.join(RAW, "manifest.json")
    if not os.path.exists(manifest_path):
        print("STALE: no manifest.json (archiver has never run?)")
        return 1
    with open(manifest_path) as f:
        manifest = json.load(f)
    today = datetime.now(PHT)
    stale = []
    for key in DATASETS:
        budget = LAG_BUDGET_DAYS.get(key, LAG_DEFAULT_DAYS)
        if budget is None:
            continue
        newest = (manifest.get(key) or {}).get("newest")
        if not newest:
            stale.append(f"{key}: no files recorded")
            continue
        age = (today - datetime.strptime(newest, "%Y%m%d")
               .replace(tzinfo=PHT)).days
        status = "STALE" if age > budget else "ok"
        print(f"{key}: newest {newest}, {age}d old (budget {budget}d) {status}")
        if age > budget:
            stale.append(f"{key}: newest {newest} is {age}d old "
                         f"(budget {budget}d)")
    for s in stale:
        print("STALE:", s)
    return 1 if stale else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--backfill", action="store_true", help="full public window")
    g.add_argument("--daily", action="store_true",
                   help="everything newer than the archive's newest file")
    g.add_argument("--check", action="store_true",
                   help="staleness check against manifest.json (exit 1 if stale)")
    ap.add_argument("--only", help="comma-separated dataset keys")
    ap.add_argument("--sample-days", "--dipcef-days", dest="sample_days",
                    type=int, default=None,
                    help="fetch the last N days of the SAMPLE datasets "
                         "(DIPCEF, RTDRS; default: 3 on backfill, 0 on daily). "
                         "These files are multi-MB per day, so the sample stays "
                         "static and the repo stays light.")
    a = ap.parse_args()
    if a.check:
        return check_staleness()
    keys = list(DATASETS)
    if a.only:
        keys = [k.strip().upper() for k in a.only.split(",")]
        bad = [k for k in keys if k not in DATASETS]
        if bad:
            print(f"unknown dataset keys: {bad}")
            return 2
    mode = "daily" if a.daily else "backfill"
    sample_days = a.sample_days
    if sample_days is None:
        sample_days = 0 if mode == "daily" else 3
    failures = archive(keys, mode, sample_days)
    if failures:
        print(f"{len(failures)} dataset failure(s); exiting nonzero so the "
              "cron goes red instead of silently losing window days")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
