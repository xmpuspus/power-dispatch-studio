#!/usr/bin/env python3
"""Observed market operations, from the 2026-07-07 dataset expansion.

Five IEMOP datasets joined the daily archive because the analyst-parity
review showed each one replaces a modeled guess with the operator's own
record:

  MCP    rtd-market-clearing-price: names the marginal RESOURCE and its
         price per region per 5-minute interval. Two uses: the observed
         price-setter table (who actually set the price, vs the model's
         marginal block), and the hourly regional clearing-price series the
         backcast scores against (per_grid_mcp), the target commensurate
         with a dispatch dual.
  RSVPR  rtd-regional-reserve-prices: the official co-optimised regional
         reserve prices, superseding the two-day per-resource sample as the
         reserve view's price series.
  MPI    mpi-advisories: the NSO advisory stream (HVDC blocks and
         de-blocks, alert states, trips), the operator's own event log.
  WAPOS  outage-schedules-used-in-wap: the week-ahead projection outage
         schedule, the archive's only forward-looking file.
  MRU    must-run-unit instructions (processed SO dispatch report).

Resource codes map to DOE-fleet plants through the pasa alias table;
anything without a confident alias stays unmatched and carries no MW
(coverage stated, never guessed).
"""
from __future__ import annotations

import functools
import os
import re

from build_data import REGION_MAP, dataset_files, day_of, f, rows_of
from dispatch import hour_of
from pasa import _alias_for, grid_of_prefix

GRIDS_L = ("luzon", "visayas", "mindanao")


def _resolve(resource: str, rows_by_name: dict) -> tuple[str | None, float | None]:
    """(fuel, unit_mw) for a resource code via the pasa alias table; None
    when unmatched. Batteries are storage with no fleet MW."""
    if resource.endswith("_BAT"):
        return "storage", None
    alias = _alias_for(resource)
    if not alias:
        return None, None
    row = rows_by_name.get(alias[0])
    if row is None:
        return None, None
    units = max(1, int(row.get("units") or 1))
    mw = row["dependable_mw"] / units if alias[1] == "per_unit" else row["dependable_mw"]
    return row["fuel"], round(mw, 1)


def _hourly_mean(acc: dict[int, list[float]], dp: int) -> list[float | None]:
    out: list[float | None] = []
    for h in range(24):
        vals = acc.get(h) or []
        out.append(round(sum(vals) / len(vals), dp) if vals else None)
    return out


def _interval_hour(ts: str) -> int | None:
    """Hour bucket for an interval-ENDING timestamp, or None if unparseable.
    IEMOP serializes the midnight-ending interval as a bare date (no time
    part): that interval belongs to hour 23."""
    if ":" not in ts:
        return 23
    return hour_of(ts)


def _interval_means(path: str) -> dict[str, dict[str, list[float]]]:
    """{grid: {interval_ts: [row prices PhP/kWh]}} for one MCP file. A tied
    interval carries several marginal rows; callers average per interval
    FIRST so hours and shares are interval-weighted, not row-weighted."""
    acc: dict[str, dict[str, list[float]]] = {g: {} for g in GRIDS_L}
    for r in rows_of(path):
        grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
        if not grid or (r.get("COMMODITY_TYPE") or "").strip() != "En":
            continue
        ts = (r.get("TIME_INTERVAL") or "").strip()
        acc[grid.lower()].setdefault(ts, []).append(
            f(r.get("MARGINAL_PRICE")) / 1000)
    return acc


def mcp_hourly() -> dict[str, dict[str, list[float | None]]]:
    """{date: {grid: [24 hourly mean clearing prices, PhP/kWh]}} from the
    MCP files; the observed ex-ante price series per region. Hour means are
    means of per-interval means (a tied interval counts once)."""
    out: dict[str, dict[str, list[float | None]]] = {}
    for path in dataset_files("MCP"):
        day = day_of(path)
        by_int = _interval_means(path)
        acc: dict[str, dict[int, list[float]]] = {g: {} for g in GRIDS_L}
        for g in GRIDS_L:
            for ts, prices in by_int[g].items():
                h = _interval_hour(ts)
                if h is None:
                    continue
                acc[g].setdefault(h, []).append(sum(prices) / len(prices))
        out[day] = {g: _hourly_mean(acc[g], 3) for g in GRIDS_L}
    return out


def build_price_setters(fleet: dict) -> dict:
    """Who actually set the price: per grid, the resources IEMOP names as
    marginal, their share of intervals and mean price when setting."""
    files = dataset_files("MCP")
    if not files:
        return {"available": False,
                "note": "MCP dataset absent; observed price setters "
                        "unavailable."}
    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}
    # interval-weighted: a tied interval (k marginal resources named at once)
    # credits each setter 1/k, so shares sum to 100 and a tie cannot
    # double-credit anyone. Prices average over the resource's own rows.
    credit: dict[str, dict[str, float]] = {g: {} for g in GRIDS_L}
    price_sum: dict[str, dict[str, float]] = {g: {} for g in GRIDS_L}
    price_n: dict[str, dict[str, int]] = {g: {} for g in GRIDS_L}
    n_int: dict[str, int] = {g: 0 for g in GRIDS_L}
    for path in files:
        by_res: dict[str, dict[str, dict[str, list[float]]]] = {
            g: {} for g in GRIDS_L}
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            if not grid or (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = grid.lower()
            res = (r.get("RESOURCE_NAME") or "").strip()
            ts = (r.get("TIME_INTERVAL") or "").strip()
            if not res or not ts:
                continue
            by_res[g].setdefault(ts, {}).setdefault(res, []).append(
                f(r.get("MARGINAL_PRICE")) / 1000)
        for g in GRIDS_L:
            for ts, setters in by_res[g].items():
                n_int[g] += 1
                share = 1.0 / len(setters)
                for res, prices in setters.items():
                    credit[g][res] = credit[g].get(res, 0.0) + share
                    price_sum[g][res] = (price_sum[g].get(res, 0.0)
                                         + sum(prices))
                    price_n[g][res] = price_n[g].get(res, 0) + len(prices)
    per_grid = {}
    for g in GRIDS_L:
        rows = []
        matched = 0.0
        for res, n in sorted(credit[g].items(), key=lambda kv: -kv[1]):
            fuel, _ = _resolve(res, rows_by_name)
            if fuel:
                matched += n
            rows.append({
                "resource": res,
                "fuel": fuel,
                "share_pct": round(100 * n / n_int[g], 1),
                "mean_price_php_kwh": round(
                    price_sum[g][res] / price_n[g][res], 3),
            })
        per_grid[g] = {
            "n_intervals": n_int[g],
            "n_setters": len(rows),
            "fuel_matched_share_pct": (round(100 * matched / n_int[g], 1)
                                       if n_int[g] else None),
            "top": rows[:12],
        }
    return {
        "available": True,
        "days": len(files),
        "per_grid": per_grid,
        "note": ("The marginal resource IEMOP names per region per 5-minute "
                 "RTD interval (MCP files): the observed price setter. "
                 "Shares are interval-weighted; an interval naming several "
                 "tied resources splits its credit among them. The modeled "
                 "marginal-block table stays alongside as the model's own "
                 "view; this one is the market's."),
        "fuel_note": ("Fuel per setter comes from the pasa alias table into "
                      "the DOE fleet; codes without a confident alias show "
                      "no fuel rather than a guessed one."),
        "src": "https://www.iemop.ph/market-data/rtd-market-clearing-price/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_reserve_prices() -> dict:
    """Official regional reserve prices (RSVPR), daily mean per grid and
    reserve commodity, PhP/kWh."""
    files = dataset_files("RSVPR")
    if not files:
        return {"available": False,
                "note": "RSVPR dataset absent; official reserve prices "
                        "unavailable."}
    dates: list[str] = []
    series: dict[str, dict[str, list[float | None]]] = {g: {} for g in GRIDS_L}
    for path in files:
        dates.append(day_of(path))
        acc: dict[str, dict[str, list[float]]] = {g: {} for g in GRIDS_L}
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            if not grid:
                continue
            com = (r.get("COMMODITY_TYPE") or "").strip()
            if not com:
                continue
            acc[grid.lower()].setdefault(com, []).append(
                f(r.get("PRICE")) / 1000)
        for g in GRIDS_L:
            for com, vals in acc[g].items():
                series[g].setdefault(com, [None] * (len(dates) - 1)).append(
                    round(sum(vals) / len(vals), 4))
            for com, s in series[g].items():
                if len(s) < len(dates):
                    s.append(None)
    stats = {}
    for g in GRIDS_L:
        stats[g] = {}
        for com, s in series[g].items():
            vals = [v for v in s if v is not None]
            if vals:
                stats[g][com] = {"mean": round(sum(vals) / len(vals), 4),
                                 "max": round(max(vals), 4)}
    return {
        "available": True,
        "dates": dates,
        "series": series,
        "stats": stats,
        "unit": "PhP/kWh (daily mean of 5-minute regional reserve prices)",
        "commodity_note": ("Commodity codes as published (Dr, Fr, Ru, Rd...); "
                           "IEMOP publishes no key, so the product mapping "
                           "stays the reserve view's labeled inference."),
        "src": "https://www.iemop.ph/market-data/rtd-regional-reserve-prices/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


_HVDC_RE = re.compile(r"hvdc", re.I)
_ALERT_RE = re.compile(r"\b(yellow|red)\s+alert\b", re.I)
_BLOCK_RE = re.compile(r"(de-?blocked|blocked)", re.I)
_ORMOC_RE = re.compile(r"ormoc|naga", re.I)
_ADV_TS_RE = re.compile(r"(\d{2}/\d{2}/\d{4}) (\d{2}:\d{2})")
_AT_RE = re.compile(r"at (\d{3,4})H")


def hvdc_unblocked_fractions() -> dict[str, list[float]]:
    """{date: [24 unblocked fractions]} for the Leyte-Luzon (Ormoc-Naga)
    corridor, parsed from the raw NSO advisory stream (MPI). The operator
    announces every blocking and de-blocking with a timestamp; pairing them
    gives outage windows, and each hour's corridor cap scales by the time
    it was actually available. INFERRED from advisory text (labeled where
    consumed); the same event is announced on both grid streams, so
    same-kind events within 5 minutes dedupe to one. The MVIP corridor has
    single-digit mentions in the window and stays unscaled."""
    from datetime import datetime, timedelta

    events: list[tuple[datetime, str]] = []
    for path in dataset_files("MPI"):
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            import csv as _csv
            for r in _csv.DictReader(fh):
                msg = (r.get("ADV_TEXT_MESSAGE") or "").strip()
                mk = _BLOCK_RE.search(msg)
                if not mk or not _ORMOC_RE.search(msg):
                    continue
                kind = ("deblock" if "de" in mk.group(1).lower()
                        else "block")
                md = _ADV_TS_RE.search(msg)
                if not md:
                    continue
                day = datetime.strptime(md.group(1), "%m/%d/%Y")
                mt = _AT_RE.search(msg)
                if mt:
                    hhmm = mt.group(1).zfill(4)
                    ts = day.replace(hour=int(hhmm[:2]) % 24,
                                     minute=int(hhmm[2:]))
                else:
                    hh, mm = md.group(2).split(":")
                    ts = day.replace(hour=int(hh), minute=int(mm))
                events.append((ts, kind))
    events.sort()
    dedup: list[tuple[datetime, str]] = []
    for ts, kind in events:
        if (dedup and dedup[-1][1] == kind
                and (ts - dedup[-1][0]).total_seconds() <= 300):
            continue
        dedup.append((ts, kind))
    windows: list[tuple[datetime, datetime]] = []
    open_ts: datetime | None = None
    for ts, kind in dedup:
        if kind == "block":
            if open_ts is None:
                open_ts = ts
        elif open_ts is not None:
            windows.append((open_ts, ts))
            open_ts = None
    if open_ts is not None:
        # an unclosed block at the archive edge: hold it for one hour, the
        # median short-block scale, rather than severing the corridor to
        # the end of time
        windows.append((open_ts, open_ts + timedelta(hours=1)))
    blocked: dict[str, list[float]] = {}
    for s, e in windows:
        cur = s
        while cur < e:
            hour_end = cur.replace(minute=0) + timedelta(hours=1)
            seg = (min(e, hour_end) - cur).total_seconds() / 3600
            key = cur.date().isoformat()
            blocked.setdefault(key, [0.0] * 24)[cur.hour] += seg
            cur = hour_end
    return {d: [round(max(0.0, 1.0 - min(1.0, b)), 3) for b in hrs]
            for d, hrs in blocked.items()}


def build_advisories() -> dict:
    """The NSO advisory stream (MPI): HVDC block/de-block events and alert
    advisories, the operator's own event log per day."""
    files = dataset_files("MPI")
    if not files:
        return {"available": False,
                "note": "MPI dataset absent; advisory stream unavailable."}
    days = []
    hvdc_events = []
    alert_events = []
    for path in files:
        day = day_of(path)
        n = n_hvdc = n_alert = 0
        for r in rows_of(path):
            msg = (r.get("ADV_TEXT_MESSAGE") or "").strip()
            if not msg:
                continue
            n += 1
            ts = (r.get("ADV_SDATE") or r.get("RUN_TIME") or "").strip()
            if _HVDC_RE.search(msg):
                n_hvdc += 1
                if len(hvdc_events) < 400:
                    hvdc_events.append({"date": day, "ts": ts,
                                        "text": msg[:240]})
            m = _ALERT_RE.search(msg)
            if m:
                n_alert += 1
                if len(alert_events) < 400:
                    alert_events.append({"date": day, "ts": ts,
                                         "level": m.group(1).lower(),
                                         "text": msg[:240]})
        days.append({"date": day, "n": n, "n_hvdc": n_hvdc,
                     "n_alert": n_alert})
    return {
        "available": True,
        "days": days,
        "hvdc_events": hvdc_events,
        "alert_events": alert_events,
        "note": ("IEMOP market-participant-information advisories (NSO "
                 "stream): HVDC blockings and de-blockings, alert states, "
                 "trips, as the operator announced them. This is the event "
                 "log behind the alert-streak and corridor-separation "
                 "stories, replacing news citations with the operator's "
                 "own record inside the window."),
        "src": "https://www.iemop.ph/market-data/mpi-advisories/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_outlook(fleet: dict) -> dict:
    """Forward view: the newest week-ahead outage schedule (WAPOS) with
    fleet-matched MW, plus the newest must-run-unit instruction week."""
    wapos = dataset_files("WAPOS")
    mru = dataset_files("MRU")
    out: dict = {"available": bool(wapos)}
    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}
    if wapos:
        path = wapos[-1]
        as_of = day_of(path)
        seen: dict[str, dict] = {}
        for r in rows_of(path):
            res = (r.get("RESOURCE_NAME") or "").strip()
            if not res or (r.get("STATUS") or "").strip() != "OUT":
                continue
            fuel, mw = _resolve(res, rows_by_name)
            seen[res] = {
                "resource": res,
                "grid": grid_of_prefix(res),
                "fuel": fuel,
                "mw": mw,
                "from": (r.get("START_TIME") or "").strip(),
                "until": (r.get("END_TIME") or "").strip(),
            }
        rows = sorted(seen.values(), key=lambda x: -(x["mw"] or 0.0))
        out.update({
            "as_of": as_of,
            "scheduled_out": rows,
            "matched_mw": {
                g: round(sum(x["mw"] or 0.0 for x in rows
                             if x["grid"] == g), 1) for g in GRIDS_L},
            "n_unmatched": sum(1 for x in rows if x["mw"] is None),
            "note": ("The operator's week-ahead projection outage schedule "
                     "(WAPOS), the archive's only forward-looking file: "
                     "what is scheduled out for the coming days, matched to "
                     "DOE-fleet MW where the alias is confident. A schedule, "
                     "not a forecast of forced outages."),
            "src": "https://www.iemop.ph/market-data/outage-schedules-used-in-wap/",
        })
    if mru:
        path = mru[-1]
        per_res: dict[str, dict] = {}
        for r in rows_of(path):
            res = (r.get("RESOURCE_NAME") or "").strip()
            if not res:
                continue
            e = per_res.setdefault(res, {
                "resource": res,
                "region": (r.get("REGION") or "").strip(),
                "category": (r.get("CATEGORY") or "").strip(),
                "n_intervals": 0, "max_mw": 0.0})
            e["n_intervals"] += 1
            e["max_mw"] = max(e["max_mw"], f(r.get("SO_MW_INSTRUCTION")))
        out["must_run"] = {
            "week_file": os.path.basename(path),
            "units": sorted(per_res.values(),
                            key=lambda x: -x["n_intervals"]),
            "note": ("Processed must-run-unit instructions from the system "
                     "operator's dispatch report (weekly file): the units "
                     "run out of merit for grid security, with the stated "
                     "reason. These intervals are administered, not market "
                     "outcomes."),
            "src": ("https://www.iemop.ph/market-data/"
                    "list-of-must-run-units-based-on-so-dispatch-"
                    "instruction-report/"),
        }
    out["disclaimer"] = ("Statistical indicators derived from public data. "
                         "Patterns may have legitimate explanations.")
    return out


def build_not_offered() -> dict:
    """The registered-but-not-offered screen: per market day, registered
    generation capacity (CAPEG, grid via the inferred code prefix) against
    the offer book's fullest hour (RTDOE + self-scheduled, from the
    committed offer dailies) and the operator's matched scheduled-out MW
    (PASA). A data cut, not an accusation: the residual carries many
    legitimate explanations and says so."""
    from pasa import grid_of_prefix as _gof

    offer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "data", "derived", "offer_daily")
    if not os.path.isdir(offer_dir):
        return {"available": False,
                "note": "no derived offer days; run pipeline/offers.py"}
    import csv as _csv
    import json as _json

    # registered MW per grid per day (CAPEG)
    reg: dict[str, dict[str, float]] = {}
    for path in dataset_files("CAPEG"):
        day = day_of(path)
        acc = {g: 0.0 for g in GRIDS_L}
        with open(path, newline="", encoding="utf-8",
                  errors="replace") as fh:
            for r in _csv.DictReader(fh):
                g = _gof((r.get("RESOURCE_NAME") or "").strip())
                if not g:
                    continue
                try:
                    acc[g] += float(r.get("MAXIMUM_CAPACITY") or 0)
                except ValueError:
                    continue
        reg[day] = {g: round(v, 1) for g, v in acc.items()}

    # matched scheduled-out MW per grid per day (PASA bake input)
    pasa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "web", "data", "pasa.json")
    out_by_day: dict[str, dict[str, float]] = {}
    if os.path.isfile(pasa_path):
        pas = _json.load(open(pasa_path))
        for d in pas.get("days") or []:
            out_by_day[d["date"]] = d.get("matched_mw") or {}

    rows = []
    for name in sorted(os.listdir(offer_dir)):
        if not name.endswith(".json"):
            continue
        off = _json.load(open(os.path.join(offer_dir, name)))
        date = off["date"]
        if date not in reg:
            continue
        row: dict = {"date": date}
        for g in GRIDS_L:
            books = [sum(m for _, m in hb) for hb in off["hours"][g] if hb]
            if not books:
                continue
            book_max = max(books)
            out_mw = (out_by_day.get(date) or {}).get(g, 0.0)
            row[g] = {
                "registered_mw": reg[date][g],
                "book_max_mw": round(book_max, 1),
                "scheduled_out_mw": round(out_mw, 1),
                "not_offered_mw": round(
                    max(0.0, reg[date][g] - book_max - out_mw), 1),
            }
        rows.append(row)
    if not rows:
        return {"available": False,
                "note": "no overlapping CAPEG + offer days yet"}
    stats = {}
    for g in GRIDS_L:
        vals = [r[g]["not_offered_mw"] for r in rows if g in r]
        regs = [r[g]["registered_mw"] for r in rows if g in r]
        if vals:
            svals = sorted(vals)
            stats[g] = {
                "days": len(vals),
                "median_not_offered_mw": svals[len(svals) // 2],
                "max_not_offered_mw": max(vals),
                "median_share_of_registered_pct": round(
                    100 * svals[len(svals) // 2]
                    / (sum(regs) / len(regs)), 1),
            }
    return {
        "available": True,
        "days": rows,
        "stats": stats,
        "note": ("Registered generation capacity (CAPEG) minus the offer "
                 "book's fullest hour (offers plus self-scheduled) minus "
                 "the operator's matched scheduled-out MW, per market day: "
                 "capacity the register carries that neither offered nor "
                 "appears in the matched outage schedules. This is a data "
                 "cut, not an accusation: the residual has many "
                 "legitimate explanations the public files cannot "
                 "separate: outages beyond the matched subset, derates, "
                 "testing and commissioning, registration lag on retired "
                 "or embedded units, and non-market obligations. The grid "
                 "mapping uses the same inferred code prefix as the PASA "
                 "layer."),
        "src_registered": ("https://www.iemop.ph/market-data/"
                           "registered-capacity-generation/"),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_reserve_registration() -> dict:
    """The reserve-side registration denominator: per market day, registered
    ancillary-services capacity (CAPER, the reserve twin of CAPEG) per grid x
    commodity against the reserve offer book's fullest hour (RTDOR, the
    committed reserve dailies). The reserve counterpart of the generation
    not-offered screen; a data cut with the same legitimate explanations, not
    an accusation. It gives the reserve book a registration base."""
    import json as _json

    res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "data", "derived", "reserve_daily")
    if not os.path.isdir(res_dir):
        return {"available": False,
                "note": "no derived reserve days; run pipeline/reserve_offers.py"}
    commodities = ("Fr", "Dr", "Ru", "Rd")
    comm_canon = {"FR": "Fr", "DR": "Dr", "RU": "Ru", "RD": "Rd"}
    # registered AS capacity per grid x commodity per day (CAPER)
    reg: dict[str, dict[str, dict[str, float]]] = {}
    for path in dataset_files("CAPER"):
        day = day_of(path)
        acc = {g: {c: 0.0 for c in commodities} for g in GRIDS_L}
        for r in rows_of(path):
            g = grid_of_prefix((r.get("RESOURCE_NAME") or "").strip())
            c = comm_canon.get((r.get("PRODUCT_TYPE") or "").strip().upper())
            if not g or not c:
                continue
            try:
                acc[g][c] += float(r.get("MAX_CAPACITY") or 0)
            except ValueError:
                continue
        reg[day] = acc
    rows = []
    for name in sorted(os.listdir(res_dir)):
        if not name.startswith("RESD_") or not name.endswith(".json"):
            continue
        day = _json.load(open(os.path.join(res_dir, name)))
        date = day["date"]
        if date not in reg:
            continue
        row: dict = {"date": date}
        for g in GRIDS_L:
            for c in commodities:
                books = day["hours"][g][c]
                offered = [sum(m for _, m in hb) for hb in books if hb]
                if not offered:
                    continue
                registered = reg[date][g][c]
                book_max = max(offered)
                row.setdefault(g, {})[c] = {
                    "registered_mw": round(registered, 1),
                    "book_max_mw": round(book_max, 1),
                    "not_offered_mw": round(max(0.0, registered - book_max), 1),
                }
        if len(row) > 1:
            rows.append(row)
    if not rows:
        return {"available": False,
                "note": "no overlapping CAPER + reserve-book days yet"}
    stats: dict = {}
    for g in GRIDS_L:
        for c in commodities:
            regs = [r[g][c]["registered_mw"] for r in rows
                    if g in r and c in r[g]]
            noff = [r[g][c]["not_offered_mw"] for r in rows
                    if g in r and c in r[g]]
            if not regs:
                continue
            snoff = sorted(noff)
            med_reg = sum(regs) / len(regs)
            stats.setdefault(g, {})[c] = {
                "days": len(regs),
                "median_registered_mw": round(sorted(regs)[len(regs) // 2], 1),
                "median_not_offered_mw": round(snoff[len(snoff) // 2], 1),
                "median_share_of_registered_pct": (round(
                    100 * snoff[len(snoff) // 2] / med_reg, 1)
                    if med_reg > 0 else None),
            }
    return {
        "available": True,
        "days": rows,
        "stats": stats,
        "note": ("Registered ancillary-services capacity (CAPER) minus the "
                 "reserve offer book's fullest hour (RTDOR), per grid x "
                 "commodity per market day: registered reserve capacity that "
                 "did not appear in the operator's reserve offer book. The "
                 "same data cut as the generation not-offered screen and the "
                 "same caveats: a resource can be committed to energy, on "
                 "outage or derate, testing, or holding reserve under a "
                 "non-market obligation; registered capacity is a ceiling, "
                 "not an expectation. It sizes the reserve book against its "
                 "registration base. Grid via the inferred code prefix."),
        "src_registered": ("https://www.iemop.ph/market-data/"
                           "registered-capacity-ancillary-services/"),
        "src_offered": "https://www.iemop.ph/market-data/rtd-reserve-offers/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    if sx < 1e-9 or sy < 1e-9:
        return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                 / (sx * sy), 3)


def _rsvpr_open(path: str) -> dict[str, dict[str, dict[int, float]]]:
    """{grid: {commodity: {hour: PhP/kWh}}} at each hour's OPENING interval
    (HH:05) from one RSVPR file: the exact interval the derived reserve
    book was taken at, so the comparison is like-for-like."""
    from datetime import datetime

    out: dict[str, dict[str, dict[int, float]]] = {g: {} for g in GRIDS_L}
    for r in rows_of(path):
        ts = (r.get("TIME_INTERVAL") or "").strip()
        if ":05:00" not in ts:
            continue
        grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
        com = (r.get("COMMODITY_TYPE") or "").strip()
        if not grid or not com:
            continue
        try:
            dt = datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            continue
        out[grid.lower()].setdefault(com, {})[dt.hour] = (
            f(r.get("PRICE")) / 1000)
    return out


def _clear_book(book: list, mw: float) -> tuple[float, bool]:
    """(marginal offer price, book_short) clearing an ascending (price, MW)
    block list at mw. The deriver's gate allows the book to sit up to 1 MW
    under the schedule, so a short book clears at its last block."""
    cum = 0.0
    for p, m in book:
        cum += m
        if cum >= mw - 1e-9:
            return p, False
    return book[-1][0], True


def build_reserve_validation() -> dict:
    """The reserve replay: clear each derived reserve book (RTDOR, the
    hour's opening interval) at the operator's scheduled MW for that same
    interval, and score the marginal offer against the official RSVPR
    price at that interval, per grid x commodity pool."""
    import json as _json

    res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "data", "derived", "reserve_daily")
    if not os.path.isdir(res_dir):
        return {"available": False,
                "note": "no derived reserve days; run pipeline/reserve_offers.py"}
    rsvpr_by_day = {day_of(p): p for p in dataset_files("RSVPR")}
    commodities = ("Fr", "Dr", "Ru", "Rd")
    pairs: dict[tuple[str, str], list[tuple[float, float, bool]]] = {
        (g, c): [] for g in GRIDS_L for c in commodities}
    n_days = 0
    n_short = 0
    n_over = 0
    max_over = 0.0
    n_nonopen = 0
    for name in sorted(os.listdir(res_dir)):
        if not name.startswith("RESD_") or not name.endswith(".json"):
            continue
        day = _json.load(open(os.path.join(res_dir, name)))
        rsvpr = rsvpr_by_day.get(day["date"])
        if rsvpr is None:
            continue
        obs = _rsvpr_open(rsvpr)
        # artifacts derived from schema 4 on record the book's interval;
        # pairing assumes the HH:05 opening interval, so a recorded
        # off-minute hour is skipped and counted instead of mispaired
        book_at = day.get("book_at") or [None] * 24
        n_days += 1
        for g in GRIDS_L:
            for c in commodities:
                books = day["hours"][g][c]
                sched = day["sched_open_mw"][g][c]
                req = day["req_mw"][g][c]
                for h in range(24):
                    book, mw = books[h], sched[h]
                    if not book or mw is None or mw <= 0.0:
                        continue
                    if book_at[h] and not book_at[h].endswith(":05:00"):
                        n_nonopen += 1
                        continue
                    o = obs.get(g, {}).get(c, {}).get(h)
                    if o is None:
                        continue
                    m, short = _clear_book(book, mw)
                    if short:
                        n_short += 1
                    if m - o > 1e-12:
                        n_over += 1
                        max_over = max(max_over, m - o)
                    scarce = req[h] is not None and mw < req[h] - 0.1
                    pairs[(g, c)].append((m, o, scarce))
    pools: dict[str, dict[str, dict]] = {}
    for g in GRIDS_L:
        for c in commodities:
            pts = pairs[(g, c)]
            if not pts:
                continue
            n = len(pts)
            mod = [m for m, _, _ in pts]
            ob = [o for _, o, _ in pts]
            calm = [(m, o) for m, o, s in pts if not s]
            pools.setdefault(g, {})[c] = {
                "n_hours": n,
                "observed_mean_php_kwh": round(sum(ob) / n, 3),
                "modeled_mean_php_kwh": round(sum(mod) / n, 3),
                "mae_php_kwh": round(sum(abs(m - o) for m, o, _ in pts) / n, 3),
                "bias_php_kwh": round(sum(m - o for m, o, _ in pts) / n, 3),
                "correlation": _corr(mod, ob),
                "exact_hours_pct": round(100 * sum(
                    1 for m, o, _ in pts if abs(m - o) <= 0.005) / n, 1),
                "n_scarcity_hours": sum(1 for _, _, s in pts if s),
                "mae_nonscarcity_php_kwh": (round(sum(
                    abs(m - o) for m, o in calm) / len(calm), 3)
                    if calm else None),
            }
    if not pools:
        return {"available": False,
                "note": "no overlapping reserve-book + RSVPR days yet"}
    n_hours_total = sum(len(v) for v in pairs.values())
    return {
        "available": True,
        "days": n_days,
        "n_short_books": n_short,
        "n_nonopen_hours_skipped": n_nonopen,
        "hours_model_above_pct": round(100 * n_over / n_hours_total, 1),
        "max_model_above_php_kwh": round(max_over, 3),
        "pools": pools,
        "note": ("Each grid x commodity reserve book (RTDOR, the hour's "
                 "opening 5-minute interval) cleared at the MW the operator "
                 "actually scheduled at that same interval (RTDSUM); the "
                 "marginal offer is the modeled reserve price, scored "
                 "against the official regional reserve price (RSVPR) at "
                 "that exact interval. Exact hours match within half a "
                 "centavo."),
        "wedge_note": ("Every pool's mean residual is negative: the "
                       "book-only replay under-prices the official "
                       "co-optimised price, and the hours where the "
                       "marginal offer sits above it are noise-level "
                       "(hours_model_above_pct of scored hours, at most "
                       "max_model_above_php_kwh). WESM pays reserves the "
                       "forgone ENERGY margin, not just the reserve offer, "
                       "so the one-signed pool residual is the "
                       "co-optimisation opportunity-cost wedge, measured "
                       "per pool. Closing it needs a joint energy+reserve "
                       "clear with per-resource books on both sides, which "
                       "the compacted artifacts drop; that build stays "
                       "named in the methodology."),
        "scarcity_note": ("Hours where the scheduled MW sits under the "
                          "market requirement (RTDSUM MKT_REQT, hourly "
                          "mean) are counted per pool and excluded from "
                          "the non-scarcity MAE: when reserves are short, "
                          "administrative pricing can set RSVPR above any "
                          "offer in the book."),
        "src": "https://www.iemop.ph/market-data/rtd-reserve-offers/",
        "src_obs": "https://www.iemop.ph/market-data/rtd-regional-reserve-prices/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_reserve_results() -> dict:
    """The per-resource reserve validation. DIPC reserve results final
    (DIPCRF) is IEMOP's final per-resource cleared reserve, schedule and
    price per commodity. Two comparisons the pooled RTDOR replay could not
    make: the final cleared price against the real-time RSVPR (how far the
    final re-solve moves the reserve price), and the RTDOR book replay's
    marginal against the same final cleared price (does the book replay
    reproduce the authoritative final clearing, tighter than against the RTD
    price). The per-resource cleared schedules it archives are the input the
    queued joint energy+reserve LP needs."""
    import json as _json

    rr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "data", "derived", "reserve_results_daily")
    res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "data", "derived", "reserve_daily")
    if not os.path.isdir(rr_dir):
        return {"available": False,
                "note": "no DIPCRF days; run pipeline/reserve_results.py"}
    rsvpr_by_day = {day_of(p): p for p in dataset_files("RSVPR")}
    books_by_day = {}
    if os.path.isdir(res_dir):
        for n in os.listdir(res_dir):
            if n.startswith("RESD_") and n.endswith(".json"):
                d = _json.load(open(os.path.join(res_dir, n)))
                books_by_day[d["date"]] = d
    commodities = ("Fr", "Dr", "Ru", "Rd")
    # final-vs-RTD price pairs and replay-vs-final pairs, per pool
    fr_rtd: dict = {(g, c): [] for g in GRIDS_L for c in commodities}
    replay: dict = {(g, c): [] for g in GRIDS_L for c in commodities}
    sched_rev: dict = {(g, c): [] for g in GRIDS_L for c in commodities}
    n_days = 0
    resources = set()
    for name in sorted(os.listdir(rr_dir)):
        if not name.startswith("RRESD_") or not name.endswith(".json"):
            continue
        day = _json.load(open(os.path.join(rr_dir, name)))
        date = day["date"]
        n_days += 1
        obs = _rsvpr_open(rsvpr_by_day[date]) if date in rsvpr_by_day else {}
        book_day = books_by_day.get(date)
        for g in GRIDS_L:
            for c in commodities:
                final_p = day["cleared_price"][g][c]
                final_s = day["sched_mw"][g][c]
                gap = (day.get("rtd_schedule_gap_mw", {})
                       .get(g, {}).get(c, {}) or {})
                if gap.get("mean") is not None:
                    sched_rev[(g, c)].append(gap["mean"])
                for h in range(24):
                    fp = final_p[h]
                    if fp is None:
                        continue
                    for res, _mw, _pr in (day["hours"][g][c][h] or []):
                        resources.add(res)
                    o = obs.get(g, {}).get(c, {}).get(h)
                    if o is not None:
                        fr_rtd[(g, c)].append((fp, o))
                    if book_day is not None:
                        bk = book_day["hours"][g][c][h]
                        ba = (book_day.get("book_at") or [None] * 24)[h]
                        sm = final_s[h]
                        if bk and sm and (not ba or ba.endswith(":05:00")):
                            m, _short = _clear_book(bk, sm)
                            replay[(g, c)].append((m, fp))
    pools: dict = {}
    for g in GRIDS_L:
        for c in commodities:
            pool: dict = {}
            fp_rtd = fr_rtd[(g, c)]
            if fp_rtd:
                n = len(fp_rtd)
                pool["vs_rtd_price"] = {
                    "n_hours": n,
                    "final_mean_php_kwh": round(
                        sum(a for a, _ in fp_rtd) / n, 3),
                    "rtd_mean_php_kwh": round(
                        sum(b for _, b in fp_rtd) / n, 3),
                    "mae_php_kwh": round(
                        sum(abs(a - b) for a, b in fp_rtd) / n, 3),
                    "bias_php_kwh": round(
                        sum(a - b for a, b in fp_rtd) / n, 3),
                }
            rp = replay[(g, c)]
            if rp:
                n = len(rp)
                pool["replay_vs_final"] = {
                    "n_hours": n,
                    "mae_php_kwh": round(
                        sum(abs(a - b) for a, b in rp) / n, 3),
                    "bias_php_kwh": round(
                        sum(a - b for a, b in rp) / n, 3),
                    "correlation": _corr([a for a, _ in rp],
                                         [b for _, b in rp]),
                }
            rev = sched_rev[(g, c)]
            if rev:
                pool["final_vs_rtd_schedule_mw"] = {
                    "mean_daily_revision": round(sum(rev) / len(rev), 2),
                }
            if pool:
                pools.setdefault(g, {})[c] = pool
    if not pools:
        return {"available": False, "note": "no scored DIPCRF pools yet"}
    return {
        "available": True,
        "days": n_days,
        "resources_named": len(resources),
        "pools": pools,
        "note": ("IEMOP's final per-resource cleared reserve (DIPCRF), per "
                 "commodity. vs_rtd_price compares the final schedule-weighted "
                 "clearing price against the real-time RSVPR at the same "
                 "opening interval: the final re-solve's reserve-price "
                 "movement. replay_vs_final clears the RTDOR reserve book at "
                 "the final scheduled MW and scores its marginal offer against "
                 "the final cleared price, a tighter check than against the "
                 "RTD price. final_vs_rtd_schedule_mw is the mean daily "
                 "revision of the pool's scheduled reserve between the "
                 "real-time and final solves (near zero on Luzon, larger on "
                 "the tight island reserve pools). The per-resource cleared "
                 "schedules are archived under data/derived/"
                 "reserve_results_daily/ as the input for the queued joint "
                 "energy+reserve clear."),
        "src": ("https://www.iemop.ph/market-data/"
                "dipc-reserve-results-final/"),
        "src_rtd": ("https://www.iemop.ph/market-data/"
                    "rtd-regional-reserve-prices/"),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_settlement_side() -> dict:
    """The sampled settlement-side price record (Pass B measure): the
    indicative administered price (a cost-substitute, sitting in the cost
    regime on Luzon), the settlement congestion component (empty at the
    one-price-per-island granularity WESM settles at), and the day-ahead
    projection's signed spread to the real-time settlement (a projection,
    out of the replay's scope). Read from the committed sample; each family
    was measured, not built into the replay."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "settlement_sample.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no settlement sample; run pipeline/settlement_side.py"}
    s = _json.load(open(p))
    days = s.get("days") or []
    if not days:
        return {"available": False, "note": "settlement sample is empty"}

    def _vals(key, g):
        return [d[key][g] for d in days if (d.get(key) or {}).get(g) is not None]

    per_grid: dict = {}
    for g in GRIDS_L:
        admin = _vals("admin_lmp", g)
        settle = _vals("settlement_lmp", g)
        cong = _vals("settlement_congestion", g)
        spread = _vals("dap_vs_rt_spread", g)
        if not admin:
            continue
        per_grid[g] = {
            "admin_lmp_mean_php_kwh": round(sum(admin) / len(admin), 3),
            "settlement_lmp_mean_php_kwh": (round(sum(settle) / len(settle), 3)
                                            if settle else None),
            "settlement_congestion_max_abs_php_kwh": (round(
                max(abs(x) for x in cong), 4) if cong else None),
            "dap_vs_rt_spread_mean_php_kwh": (round(sum(spread) / len(spread), 3)
                                              if spread else None),
            "dap_vs_rt_spread_range_php_kwh": ([round(min(spread), 3),
                                                round(max(spread), 3)]
                                               if spread else None),
        }
    return {
        "available": True,
        "sample_days": s.get("sample_days"),
        "per_grid": per_grid,
        "note": s.get("note"),
        "src_admin": s.get("src_admin"),
        "src_settlement": s.get("src_settlement"),
        "src_dayahead": s.get("src_dayahead"),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def solar_observed_by_day() -> dict[str, dict[str, float]]:
    """{date: {grid: observed WESM-dispatched solar MWh}} from the committed
    DIPCEF dailies, same SOL/SPV resource classification as
    build_solar_wind_observed. The per-day observed solar energy a replay can
    reproduce instead of the flat clear-sky credit (roadmap item 8)."""
    import json as _json

    dd_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "data", "derived", "dipcef_daily")
    if not os.path.isdir(dd_dir):
        return {}
    out: dict[str, dict[str, float]] = {}
    for name in sorted(os.listdir(dd_dir)):
        if not name.endswith(".json"):
            continue
        day = _json.load(open(os.path.join(dd_dir, name)))
        per = {g: 0.0 for g in GRIDS_L}
        for res, v in (day.get("resources") or {}).items():
            g = v.get("grid")
            if not g or g not in per:
                continue
            up = res.upper()
            if "SOL" in up or "SPV" in up:
                per[g] += v.get("mwh") or 0.0
        out[day.get("date")] = per
    return out


def build_solar_wind_observed() -> dict:
    """Observed WESM-dispatched solar and wind daily energy per grid (from the
    committed DIPCEF dailies), beside the model's clear-sky solar credit.

    The measurement decided the framing: the observed dispatched energy is
    NOT a clean curtailment gap against the clear-sky potential, because the
    ratio flips by grid (Luzon runs well above the modeled credit, the islands
    below). That is the model's grid solar SPLIT (a labeled national-split
    assumption, GRID_FUEL_MW) being approximate, not a single curtailment
    story. Separating curtailment from the split needs the per-resource
    registered-capacity join (CAPEG, now archived) as a named refinement.
    Classification is by resource-code pattern (SOL/SPV, WIND/WPP) plus a
    named-alias set for renewable farms whose code carries no fuel token."""
    import json as _json

    dd_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "data", "derived", "dipcef_daily")
    if not os.path.isdir(dd_dir):
        return {"available": False,
                "note": "no DIPCEF dailies; run pipeline/fuelmix.py"}
    from fleet_ph import GRID_FUEL_MW
    prof_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "web", "data", "profiles.json")
    shape = 5.9
    if os.path.isfile(prof_path):
        sp = (_json.load(open(prof_path)).get("solar_profile") or [])
        if sp:
            shape = sum(sp)
    obs: dict = {(f, g): [] for f in ("solar", "wind") for g in GRIDS_L}
    for name in sorted(os.listdir(dd_dir)):
        if not name.endswith(".json"):
            continue
        day = _json.load(open(os.path.join(dd_dir, name)))
        per: dict = {}
        for res, v in (day.get("resources") or {}).items():
            g = v.get("grid")
            if not g:
                continue
            up = res.upper()
            # code-pattern classify, plus a small named-alias set for renewable
            # farms whose resource code carries no fuel token (BURGOS is the
            # ~150 MW EDC wind farm in Ilocos Norte; its daily energy is
            # wind-scale, impossible for its few MW of co-located solar)
            fuel = ("solar" if ("SOL" in up or "SPV" in up)
                    else "wind" if ("WIND" in up or "WPP" in up
                                    or "BURGOS" in up) else None)
            if fuel:
                per[(fuel, g)] = per.get((fuel, g), 0.0) + (v.get("mwh") or 0.0)
        for k in obs:
            if k in per:
                obs[k].append(per[k])
    per_grid: dict = {}
    for g in GRIDS_L:
        gf = GRID_FUEL_MW.get(g.upper(), {})
        sol = obs[("solar", g)]
        wnd = obs[("wind", g)]
        model_solar = round(gf.get("solar", 0) * shape, 0)
        obs_solar = round(sum(sol) / len(sol), 0) if sol else None
        per_grid[g] = {
            "observed_solar_mwh_day": obs_solar,
            "model_clearsky_solar_mwh_day": model_solar,
            "observed_over_model_solar": (round(obs_solar / model_solar, 2)
                                          if obs_solar and model_solar else None),
            "observed_wind_mwh_day": (round(sum(wnd) / len(wnd), 0)
                                      if wnd else None),
            "installed_solar_mw_assumed": gf.get("solar"),
            "installed_wind_mw_assumed": gf.get("wind"),
        }
    return {
        "available": True,
        "days": len(obs[("solar", "luzon")]),
        "per_grid": per_grid,
        "clearsky_flh_equiv": round(shape, 2),
        "note": ("Observed WESM-dispatched solar and wind daily energy per "
                 "grid (DIPCEF SCHED_MW, post-curtailment), beside the model's "
                 "clear-sky solar credit (the labeled GRID_FUEL_MW installed "
                 "solar times the clear-sky hourly shape). The observed/model "
                 "ratio is not a single curtailment gap: it runs above one on "
                 "Luzon and below one on the islands, which is the model's "
                 "national solar SPLIT being approximate, not curtailment. "
                 "Wind installed capacity is small and its shape is not "
                 "modeled, so only the observed wind series is shown. Solar "
                 "and wind are code-classified (SOL/SPV, WIND/WPP) plus a "
                 "named-alias set for renewable farms whose code carries no "
                 "fuel token (the Burgos wind farm), a labeled inference. A "
                 "clean split of "
                 "curtailment from the installed-split error needs the "
                 "per-resource registered-capacity join (CAPEG), a named "
                 "refinement; solar's dominance of the security-pinned "
                 "operating-point list (security_limits) is the curtailment "
                 "evidence meanwhile."),
        "src": ("https://www.iemop.ph/market-data/"
                "dipc-energy-results-final/"),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_admin_dispatch() -> dict:
    """The administered-dispatch overlay measurement (Pass E): the MOT-raise
    record is material in MW but price-inert in the per-fuel block engines
    (coal is the marginal fuel on ~90 percent of raise hours), so it is
    measured and documented, not built. Read from the committed derivation
    (pipeline/admin_dispatch.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "admin_dispatch.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no admin-dispatch measure; run pipeline/admin_dispatch.py"}
    d = _json.load(open(p))
    d.setdefault("disclaimer", "Statistical indicators derived from public "
                 "data. Patterns may have legitimate explanations.")
    return d


def build_joint_lp_probe() -> dict:
    """The per-resource joint energy+reserve LP probe (Pass F): prototyped on
    a sample of grid-hours, it does not reproduce the official co-optimised
    reserve price, so the reserve wedge stays measured, not closed. Read from
    the committed derivation (pipeline/joint_lp_probe.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "joint_lp_probe.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no joint-LP probe; run pipeline/joint_lp_probe.py"}
    d = _json.load(open(p))
    d.setdefault("disclaimer", "Statistical indicators derived from public "
                 "data. Patterns may have legitimate explanations.")
    return d


def build_subhourly_probe() -> dict:
    """The sub-hourly negative-price probe (Pass G): the 5-minute sign flips
    are a knife-edge, sub-hourly resolution is necessary but the crossing
    margin is finer than the offers pin down. Read from the committed
    derivation (pipeline/subhourly_probe.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "subhourly_probe.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no sub-hourly probe; run pipeline/subhourly_probe.py"}
    d = _json.load(open(p))
    d.setdefault("disclaimer", "Statistical indicators derived from public "
                 "data. Patterns may have legitimate explanations.")
    return d


_HS_KEYS = {"VISLUZ1": "lv", "MINVIS1": "vm"}


@functools.lru_cache(maxsize=1)
def rtdhs_hourly() -> dict[str, dict]:
    """{date: {"lv": [24], "vm": [24], "bind_y": {...}, "bind_n": {...}}}
    from the operator's per-interval HVDC schedule (RTDHS): hourly mean
    corridor flows plus per-corridor counts of intervals flagged binding
    (CONGESTION_FLAG). Sign convention, verified against the RTDSUM
    demand-identity flows: FLOW_FROM is positive toward the corridor's
    FROM side, so the map's lv (positive = Luzon to Visayas) is -VISLUZ1
    and vm (positive = Visayas to Mindanao) is -MINVIS1."""
    out: dict[str, dict] = {}
    for path in dataset_files("RTDHS"):
        day = day_of(path)
        acc: dict[str, dict[int, list[float]]] = {"lv": {}, "vm": {}}
        bind_y = {"lv": 0, "vm": 0}
        bind_n = {"lv": 0, "vm": 0}
        for r in rows_of(path):
            key = _HS_KEYS.get((r.get("HVDC_NAME") or "").strip())
            if not key:
                continue
            ts = (r.get("TIME_INTERVAL") or "").strip()
            if not ts:
                continue
            h = _interval_hour(ts)
            if h is None:
                continue
            acc[key].setdefault(h, []).append(-f(r.get("FLOW_FROM")))
            bind_n[key] += 1
            if (r.get("CONGESTION_FLAG") or "").strip() == "Y":
                bind_y[key] += 1
        out[day] = {
            "lv": _hourly_mean(acc["lv"], 1),
            "vm": _hourly_mean(acc["vm"], 1),
            "bind_y": bind_y,
            "bind_n": bind_n,
        }
    return out


# corridor nameplate limits (dispatch.json coupling.corridors limit_mw); the
# binding-cap fraction scales these, so on a congested hour the modeled cap
# equals the operator's own scheduled flow
_HVDC_NAMEPLATE = {"lv": 250.0, "vm": 450.0}
_HS_OUT = {"lv": "leyte", "vm": "mvip"}


def hvdc_binding_caps() -> dict[str, dict[str, list[float]]]:
    """{date: {"leyte":[24], "mvip":[24]}} per-hour corridor cap FRACTIONS from
    the operator's own RTD HVDC schedule (RTDHS). On an hour the operator flagged
    the corridor congested (CONGESTION_FLAG=Y in any interval), the effective
    limit is the operator's mean scheduled |flow| that hour, so the fraction is
    that flow over the corridor nameplate: a security de-rate the outage-advisory
    inference (leyte-only, whole-link blocks) cannot see, and the only source for
    the Visayas-Mindanao corridor at all. Hours with no flagged interval stay
    1.0 (uncapped). Same sign convention as rtdhs_hourly (-FLOW_FROM)."""
    out: dict[str, dict[str, list[float]]] = {}
    for path in dataset_files("RTDHS"):
        day = day_of(path)
        acc: dict[str, dict[int, list[tuple[float, bool]]]] = {
            "lv": {h: [] for h in range(24)},
            "vm": {h: [] for h in range(24)},
        }
        for r in rows_of(path):
            key = _HS_KEYS.get((r.get("HVDC_NAME") or "").strip())
            if not key:
                continue
            ts = (r.get("TIME_INTERVAL") or "").strip()
            if not ts:
                continue
            h = _interval_hour(ts)
            if h is None:
                continue
            flow = abs(f(r.get("FLOW_FROM")))
            flagged = (r.get("CONGESTION_FLAG") or "").strip() == "Y"
            acc[key][h].append((flow, flagged))
        caps = {"leyte": [1.0] * 24, "mvip": [1.0] * 24}
        for key in ("lv", "vm"):
            for h in range(24):
                # the enforced limit is the flow the operator held on the
                # intervals it actually flagged binding, not an average that
                # dilutes the de-rate with the hour's unconstrained intervals
                flagged_flow = [fw for fw, fl in acc[key][h] if fl]
                if not flagged_flow:
                    continue
                limit = sum(flagged_flow) / len(flagged_flow)
                frac = max(0.0, min(1.0, limit / _HVDC_NAMEPLATE[key]))
                caps[_HS_OUT[key]][h] = round(frac, 3)
        out[day] = caps
    return out


def build_reserve_aware(reserve_validation: dict, reserve_prices: dict,
                        prices: dict) -> dict:
    """The co-optimized reserve-aware price per grid (roadmap item 4): the
    energy price plus the reserve price, split into the part the offer stack
    prices (the pool-level joint clear that reproduces RSVPR on requirement-met
    hours) and the administered scarcity wedge (observed minus modeled, the
    empirical adder on short hours that is not in the public offers). The wedge
    stays reported, not hidden: this is the honest partial, energy plus the
    reserve stack clear, with the scarcity uplift labeled."""
    pv = reserve_validation.get("pools") or {}
    grids = {}
    for g in ("luzon", "visayas", "mindanao"):
        pools = pv.get(g) or {}
        if not pools:
            continue
        # requirement-weighted-ish mean across the reserve commodities
        obs = [p["observed_mean_php_kwh"] for p in pools.values()
               if p.get("observed_mean_php_kwh") is not None]
        mod = [p["modeled_mean_php_kwh"] for p in pools.values()
               if p.get("modeled_mean_php_kwh") is not None]
        if not obs or not mod:
            continue
        series = prices.get("series", {}).get(g) or []
        clean = [x for x in series if x is not None]
        energy = round(sum(clean) / len(clean), 3) if clean else None
        r_obs = round(sum(obs) / len(obs), 3)
        r_mod = round(sum(mod) / len(mod), 3)
        wedge = round(r_obs - r_mod, 3)
        grids[g] = {
            "energy_php_kwh": energy,
            "reserve_offer_clear_php_kwh": r_mod,
            "reserve_scarcity_wedge_php_kwh": wedge,
            "reserve_total_php_kwh": r_obs,
            "reserve_aware_php_kwh": (round(energy + r_obs, 3)
                                      if energy is not None else None),
        }
    return {
        "available": bool(grids),
        "by_grid": grids,
        "note": ("The reserve-aware price is the energy price plus the reserve "
                 "price. The reserve price splits into what the reserve offer "
                 "stack itself clears (the pool-level joint clear, which "
                 "reproduces the official RSVPR on requirement-met hours) and "
                 "the administered scarcity wedge on short hours (observed "
                 "minus modeled), an empirical adder that is not in the public "
                 "offers. The wedge is reported here, not tuned away: capacity "
                 "holding reserve cannot also sell energy, and scarce hours "
                 "price on an administered curve the offers do not carry."),
        "src": "https://www.iemop.ph/market-data/rtd-regional-reserve-prices/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_corridor_cap_probe() -> dict:
    """The RTDHS corridor-cap experiment (roadmap item 7): feeding the
    operator's own binding-schedule caps into the LP lowers Luzon price MAE a
    little but worsens price correlation on every grid, so the shipped engine
    keeps the advisory-based caps. Read from the committed derivation
    (pipeline/corridor_cap_probe.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "corridor_cap_probe.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": ("no corridor-cap probe; run "
                         "pipeline/corridor_cap_probe.py --derive")}
    return _json.load(open(p))


def build_vre_probe() -> dict:
    """The observed-solar backcast experiment (roadmap item 8): replaying each
    day's DIPCEF solar energy on the flat clear-sky shape worsens the price
    correlation, so the shipped backcast keeps the clear-sky credit. Read from
    the committed derivation (pipeline/vre_probe.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "vre_probe.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no VRE probe; run pipeline/vre_probe.py --derive"}
    return _json.load(open(p))


def build_uc_probe() -> dict:
    """The unit-commitment backcast experiment (roadmap item 9): adding binary
    commitment and a generic minimum-stable floor to the thermal blocks worsens
    the price correlation everywhere (block-level min-stable is too coarse; a
    per-PH-unit registry would be needed), so the LP stays the default engine.
    Read from the committed derivation (pipeline/uc_probe.py)."""
    import json as _json

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "data", "derived", "uc_probe.json")
    if not os.path.isfile(p):
        return {"available": False,
                "note": "no UC probe; run pipeline/uc_probe.py --derive"}
    return _json.load(open(p))


def build_flow_record(profiles: dict) -> dict:
    """Two observed sources, one table: the demand-identity corridor flows
    (RTDSUM net market imports/exports, what the replay demand is built
    from) against the operator's own per-interval HVDC schedule (RTDHS),
    plus the operator's binding-interval shares."""
    hs = rtdhs_hourly()
    if not hs:
        return {"available": False,
                "note": "RTDHS dataset absent; corridor record unavailable."}
    prof_by_date = {d["date"]: d for d in profiles.get("days", [])}
    corridors = {}
    for key, label in (("lv", "Luzon to Visayas"),
                       ("vm", "Visayas to Mindanao")):
        pts = []
        for date, rec in hs.items():
            nf = (prof_by_date.get(date) or {}).get("net_flow") or {}
            ident = nf.get(key) or []
            for h in range(24):
                r = rec[key][h]
                i = ident[h] if h < len(ident) else None
                if r is not None and i is not None:
                    pts.append((i, r))
        y = sum(rec["bind_y"][key] for rec in hs.values())
        nn = sum(rec["bind_n"][key] for rec in hs.values())
        if not pts:
            continue
        n = len(pts)
        corridors[key] = {
            "corridor": label,
            "n_hours": n,
            "identity_mean_mw": round(sum(i for i, _ in pts) / n, 1),
            "record_mean_mw": round(sum(r for _, r in pts) / n, 1),
            "mae_mw": round(sum(abs(i - r) for i, r in pts) / n, 1),
            "binding_share_pct": (round(100 * y / nn, 1) if nn else None),
            "n_intervals": nn,
        }
    return {
        "available": bool(corridors),
        "days": len(hs),
        "corridors": corridors,
        "note": ("The corridor flows the replay's demand construction "
                 "implies (net market imports and exports in the RTD "
                 "regional summaries) against the flows the operator "
                 "itself scheduled per 5-minute interval (RTDHS): two "
                 "independent published records of the same wire. The "
                 "binding share is the fraction of intervals the operator "
                 "flagged the corridor CONGESTION_FLAG=Y, per-interval "
                 "binding truth the advisory-window inference never had."),
        "src": "https://www.iemop.ph/market-data/rtd-hvdc-schedules/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_gwap_trigger(chrono_golden: dict | None = None,
                       profiles: dict | None = None) -> dict:
    """The ERC secondary-cap trigger, computed instead of cited: the
    72-hour rolling mean of the published 5-minute GWAP per region, its
    headroom to the P12.413/kWh trigger (breach imposes the P7.423/kWh
    cap, ERC Res. 26 s.2025), whether the studio's widest-swing as-bid
    scenario day would have tripped it, and the clamp scan that shows the
    operational cap never actually bound in the window."""
    from datetime import datetime, timedelta

    files = dataset_files("GWAPF")
    if not files:
        return {"available": False,
                "note": "GWAPF dataset absent; trigger series unavailable."}
    from constants_ph import MARKET_ANCHORS
    from fleet_ph import WESM_OFFER_CAP_PHP_KWH as OFFER_CAP

    trigger = MARKET_ANCHORS["wesm_secondary_cap_trigger_php_kwh"]
    cap = MARKET_ANCHORS["wesm_secondary_cap_php_kwh"]
    # GWAPF publishes FIVE region rows. CLUZ_CVIS is the combined Luzon-Visayas
    # pricing region, which is the operative regional entity while the
    # interconnection is in service; dropping it silently loses the row that
    # matters most for the regional test below.
    region_key = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao",
                  "System": "system", "CLUZ_CVIS": "luzon_visayas"}
    series: dict[str, dict] = {k: {} for k in region_key.values()}
    for path in files:
        for r in rows_of(path):
            k = region_key.get((r.get("REGION_NAME") or "").strip())
            if not k:
                continue
            ts = (r.get("TIME_INTERVAL") or "").strip()
            # the midnight-ending interval is serialized as a bare date;
            # midnight of that printed date IS the interval-ending moment
            try:
                dt = (datetime.strptime(ts, "%m/%d/%Y") if ":" not in ts
                      else datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p"))
            except ValueError:
                continue
            series[k][dt] = f(r.get("GWAP")) / 1000

    window = timedelta(hours=72)
    full = 864  # 72 h of 5-minute intervals

    def _roll(vals: dict, after=None) -> tuple[dict | None, int]:
        """(max full-coverage 72 h rolling mean, breach count), counting
        only windows that END after `after` when given (history still
        feeds the window sum)."""
        items = sorted(vals.items())
        best, breaches = None, 0
        lo, run = 0, 0.0
        for hi, (t, v) in enumerate(items):
            run += v
            while items[lo][0] <= t - window:
                run -= items[lo][1]
                lo += 1
            if hi - lo + 1 == full and (after is None or t > after):
                mean = run / full
                if best is None or mean > best[1]:
                    best = (t, mean)
                if mean > trigger:
                    breaches += 1
        if best is None:
            return None, 0
        return {"ends": best[0].isoformat(sep=" "),
                "rolling_php_kwh": round(best[1], 3)}, breaches

    # Intervals priced ABOVE the market's own P32/kWh offer cap are not market
    # clears: they are the dispatch engine's violation/scarcity coefficients
    # (this window tops out at P165.05/kWh, 5x the cap, with Visayas and
    # Mindanao pinned at the identical value while Luzon sits near P6). The
    # market's own price-substitution record (PSMCOG) caps at exactly the offer
    # cap with no exceptions, so the operational trigger cannot be reading
    # those intervals as prices either. Publish the rolling series BOTH ways:
    # the raw file as-is, and with the above-cap intervals held at the cap.
    per_region = {}
    for k, vals in series.items():
        if not vals:
            continue
        peak, breaches = _roll(vals)
        capped_vals = {t: min(v, OFFER_CAP) for t, v in vals.items()}
        capped_peak, capped_breaches = _roll(capped_vals)
        per_region[k] = {
            "n_intervals": len(vals),
            "max_interval_php_kwh": round(max(vals.values()), 3),
            "n_intervals_above_offer_cap": sum(1 for v in vals.values()
                                               if v > OFFER_CAP),
            "max_rolling_72h": peak,
            "headroom_php_kwh": (round(trigger - peak["rolling_php_kwh"], 3)
                                 if peak else None),
            "n_breach_windows": breaches,
            "offer_cap_held": {
                "max_rolling_72h": capped_peak,
                "headroom_php_kwh": (
                    round(trigger - capped_peak["rolling_php_kwh"], 3)
                    if capped_peak else None),
                "n_breach_windows": capped_breaches,
            },
        }

    # the clamp scan: if the cap had actually been imposed, hourly prices
    # would pin at the cap level; count days with 4+ hours within P0.05 of
    # the current (7.423) and prior (6.245) cap values
    clamp_scan = None
    if profiles:
        clamp_scan = {}
        for lvl in (cap, 6.245):
            pinned = 0
            for d in profiles.get("days", []):
                if not d.get("market"):
                    continue
                for g in GRIDS_L:
                    hrs = (d.get("lwap") or {}).get(g) or []
                    if sum(1 for v in hrs
                           if v is not None and abs(v - lvl) < 0.05) >= 4:
                        pinned += 1
            clamp_scan[str(lvl)] = pinned

    marquee = None
    cases = {c["label"]: c for c in (chrono_golden or {}).get("cases", [])}
    base = cases.get("observed offer book, no levers")
    wave = cases.get("DICT 1.5 GW on the observed offer book")
    if base and wave and series["luzon"]:
        gday = chrono_golden["date"]
        uplift = round(wave["expect"]["summary"]["mean_price"]["luzon"]
                       - base["expect"]["summary"]["mean_price"]["luzon"], 2)
        d0 = datetime.strptime(gday, "%Y-%m-%d")
        d1 = d0 + timedelta(days=1)
        lifted = {t: v + uplift if d0 < t <= d1 else v
                  for t, v in series["luzon"].items()}
        # score only windows that end on the scenario day or inside the
        # 72 hours after it, against the SAME windows unlifted: otherwise
        # the whole baseline rides along and a May breach would flag a
        # June scenario
        horizon = d1 + window
        peak, _ = _roll({t: v for t, v in lifted.items() if t <= horizon},
                        after=d0)
        base_peak, _ = _roll({t: v for t, v in series["luzon"].items()
                              if t <= horizon}, after=d0)
        marquee = {
            "scenario_day": gday,
            "uplift_php_kwh": uplift,
            "scenario_max_rolling_72h": peak,
            "baseline_max_rolling_72h": base_peak,
            "trips_trigger": bool(peak
                                  and peak["rolling_php_kwh"] > trigger),
            "baseline_trips": bool(base_peak
                                   and base_peak["rolling_php_kwh"]
                                   > trigger),
            "note": ("The studio's widest-swing as-bid scenario adds the "
                     "DICT wave's Luzon daily-mean uplift uniformly to the "
                     "scenario day's observed Luzon GWAP intervals and "
                     "recomputes the rolling trigger over the windows "
                     "ending on that day or in the 72 hours after it, "
                     "beside the same windows unlifted. An arithmetic flag "
                     "under the rule's stated numbers, not a prediction: "
                     "the window's own record (mechanism_note) shows the "
                     "operational trigger did not clamp even above the "
                     "threshold."),
        }

    return {
        "available": True,
        "days": len(files),
        "trigger_php_kwh": trigger,
        "cap_php_kwh": cap,
        "per_region": per_region,
        "clamp_scan_days_pinned": clamp_scan,
        "marquee": marquee,
        "note": ("The secondary price cap's own arithmetic, run on the "
                 "operator's published series: the 72-hour rolling mean of "
                 "the 5-minute generator-weighted average price (GWAPF), "
                 "per region, for the combined Luzon-Visayas region, and "
                 "for the System row as published. Only windows with all "
                 "864 intervals present are scored, so archive gaps cannot "
                 "fake a calm window."),
        "applies_note": ("Which row is the operative trigger is published, "
                         "not a guess. Under ERC Res. 26 s.2025 the "
                         "system-wide rolling average is the default "
                         "trigger; the regional or island cap applies ONLY "
                         "while a grid interconnection is on outage, using "
                         "the same cap value, threshold, and 72-hour "
                         "period. So the per-region breach counts below are "
                         "not exposure on their own: they are exposure only "
                         "for intervals when the interconnection was out. "
                         "Read the system row first."),
        "series_note": ("One named difference rather than an unknown: the "
                        "rule monitors the EX-ANTE rolling GWAP, and GWAPF "
                        "is the final (ex-post) series. The final series is "
                        "the closest published proxy and is what runs here, "
                        "but it is not byte-for-byte the series the "
                        "operational trigger reads."),
        "mechanism_note": ("Read the offer-cap-held numbers, not the raw "
                           "ones. The raw file carries intervals priced far "
                           "above the market's own P32/kWh offer cap (up to "
                           "P165.05/kWh here), which are violation and "
                           "scarcity coefficients rather than market "
                           "clears; the market's own price-substitution "
                           "record caps at exactly the offer cap with no "
                           "exceptions. Holding the series at the cap does "
                           "NOT make the breach story go away, and this "
                           "block should not be read as if it does. It "
                           "removes the story for LUZON only, where the "
                           "above-cap intervals generate the entire breach "
                           "count: held at the cap Luzon breaches zero "
                           "windows and peaks BELOW the threshold. The "
                           "operative System row still breaches held at the "
                           "cap, and so does the combined Luzon-Visayas "
                           "row; Visayas and Mindanao run hot either way, "
                           "and those two are the rows that bind only "
                           "during an interconnection outage "
                           "(applies_note). Both the raw and held counts "
                           "are in per_region so the reader can check "
                           "which is which. Against all of that, the "
                           "observed price record shows no day pinned at "
                           "either the current (P7.423) or prior (P6.245) "
                           "cap level (clamp_scan), so the gap between the "
                           "computed trigger and the operational one is "
                           "narrowed by the offer-cap correction but not "
                           "closed. The residual unknown is the weighting "
                           "and the imposition and lifting mechanics, "
                           "which the public file alone does not "
                           "reproduce."),
        "src": "https://www.iemop.ph/market-data/generator-weighted-average-price-final/",
        "src_rule": MARKET_ANCHORS["src_secondary_cap"],
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_constrained_on(fleet: dict) -> dict:
    """The operator's roster of generators that network and security
    constraints forced ON out of merit (PSM constrained-on generators),
    named per 5-minute interval with the cleared or substituted price:
    the congestion story with unit names, not just shadow prices."""
    files = dataset_files("PSMCOG")
    if not files:
        return {"available": False,
                "note": "PSMCOG dataset absent; constrained-on roster "
                        "unavailable."}
    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}
    grids_upper = {"LUZON": "luzon", "VISAYAS": "visayas",
                   "MINDANAO": "mindanao"}
    per_res: dict[str, dict] = {}
    per_grid = {g: 0 for g in GRIDS_L}
    days = []
    for path in files:
        day = day_of(path)
        n = 0
        res_seen = set()
        pmax = 0.0
        for r in rows_of(path):
            res = (r.get("RESOURCE_NAME") or "").strip()
            g = grids_upper.get((r.get("REGION_NAME") or "").strip())
            if not res or not g:
                continue
            price = f(r.get("CLEARED_PRICE")) / 1000
            n += 1
            res_seen.add(res)
            pmax = max(pmax, price)
            per_grid[g] += 1
            e = per_res.setdefault(res, {
                "resource": res, "grid": g, "n_intervals": 0,
                "price_sum": 0.0, "max_price_php_kwh": 0.0})
            e["n_intervals"] += 1
            e["price_sum"] += price
            e["max_price_php_kwh"] = max(e["max_price_php_kwh"], price)
        days.append({"date": day, "n_intervals": n,
                     "n_resources": len(res_seen),
                     "max_price_php_kwh": round(pmax, 3)})
    top = []
    for e in sorted(per_res.values(), key=lambda x: -x["n_intervals"])[:15]:
        fuel, _ = _resolve(e["resource"], rows_by_name)
        top.append({
            "resource": e["resource"],
            "grid": e["grid"],
            "fuel": fuel,
            "n_intervals": e["n_intervals"],
            "mean_price_php_kwh": round(e["price_sum"] / e["n_intervals"], 3),
            "max_price_php_kwh": round(e["max_price_php_kwh"], 3),
        })
    return {
        "available": True,
        "days": days,
        "n_days": len(days),
        "n_resources": len(per_res),
        "per_grid_intervals": per_grid,
        "top": top,
        "note": ("The generators the operator names as constrained ON per "
                 "5-minute interval (PSM constrained-on list): units that "
                 "network or security constraints forced to run out of "
                 "merit, with the cleared or substituted price. These are "
                 "administered outcomes the pricing methodology carries, "
                 "not market clearing, and they put unit names on the "
                 "congestion story the shadow-price league tells in "
                 "equipment terms. A final-calculation dataset, published "
                 "about two weeks behind the market day."),
        "fuel_note": ("Fuel per resource comes from the pasa alias table "
                      "into the DOE fleet; codes without a confident alias "
                      "show no fuel rather than a guessed one."),
        "src": "https://www.iemop.ph/market-data/psm-constrained-on-generators/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_security_limits(fleet: dict) -> dict:
    """Per-resource security limits used in RTD (RTDSL): the operating
    points security constraints pin resources to, per window. MAX equals
    MIN in 99.2 percent of archived windows (regulating hydro, the Agus
    units, is the exception), so nearly every row pair is a fixed
    security-constrained operating point rather than a range."""
    files = dataset_files("RTDSL")
    if not files:
        return {"available": False,
                "note": "RTDSL dataset absent; security limits unavailable."}
    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}
    # RTDSL region values are the CLUZ/CVIS/CMIN codes, not the full names
    # PSMCOG uses (the round-8 diff review caught the full-name map baking
    # a dead grid field)
    grid_names = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao",
                  "LUZON": "luzon", "VISAYAS": "visayas",
                  "MINDANAO": "mindanao"}
    per_res: dict[str, dict] = {}
    days = []
    n_windows_total = 0
    n_pinned_total = 0
    # a window that spans midnight is listed in both daily files; count it
    # once (322 of 82,084 in the first archived window)
    seen_windows: set[tuple] = set()
    for path in files:
        day = day_of(path)
        wins: dict[tuple, dict] = {}
        for r in rows_of(path):
            res = (r.get("RESOURCE_NAME") or "").strip()
            pt = (r.get("PARAMETER_TYPE") or "").strip()
            if not res or pt not in ("MAX_OPERATING_MW", "MIN_OPERATING_MW"):
                continue
            k = (res, (r.get("START_TIME") or "").strip(),
                 (r.get("END_TIME") or "").strip())
            w = wins.setdefault(k, {
                "grid": grid_names.get((r.get("REGION_NAME") or "").strip())})
            w[pt] = f(r.get("PARAMETER_VALUE"))
        n_win = n_pin = 0
        res_seen = set()
        for k, w in wins.items():
            if "MAX_OPERATING_MW" not in w or "MIN_OPERATING_MW" not in w:
                continue
            if k in seen_windows:
                continue
            seen_windows.add(k)
            res = k[0]
            n_win += 1
            res_seen.add(res)
            pinned = abs(w["MAX_OPERATING_MW"] - w["MIN_OPERATING_MW"]) < 0.05
            if pinned:
                n_pin += 1
            e = per_res.setdefault(res, {
                "resource": res, "grid": w.get("grid"), "n_windows": 0,
                "max_mw": 0.0})
            e["n_windows"] += 1
            e["max_mw"] = max(e["max_mw"], w["MAX_OPERATING_MW"])
        n_windows_total += n_win
        n_pinned_total += n_pin
        days.append({"date": day, "n_windows": n_win,
                     "n_resources": len(res_seen)})
    top = []
    for e in sorted(per_res.values(), key=lambda x: -x["n_windows"])[:15]:
        fuel, _ = _resolve(e["resource"], rows_by_name)
        top.append({
            "resource": e["resource"],
            "grid": e["grid"],
            "fuel": fuel,
            "n_windows": e["n_windows"],
            "max_mw": round(e["max_mw"], 1),
        })
    return {
        "available": True,
        "days": days,
        "n_days": len(days),
        "n_resources": len(per_res),
        "n_windows": n_windows_total,
        "pinned_share_pct": (round(100 * n_pinned_total / n_windows_total, 1)
                             if n_windows_total else None),
        "top": top,
        "note": ("The per-resource security limits the operator used in "
                 "real-time dispatch (RTDSL): each window names a resource "
                 "and the MAX and MIN operating MW security constraints "
                 "held it to. Where the two are equal (pinned_share_pct of "
                 "archived windows), the constraint is a fixed "
                 "security-constrained operating point, the physical "
                 "record of which units the grid's security limits held "
                 "and to what MW. Published next-day. A window revised "
                 "within a file resolves to the latest run's value; a "
                 "window spanning midnight appears in both daily files "
                 "and counts once."),
        "fuel_note": ("Fuel per resource comes from the pasa alias table "
                      "into the DOE fleet; codes without a confident alias "
                      "show no fuel rather than a guessed one."),
        "src": "https://www.iemop.ph/market-data/security-limits-used-in-rtd/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_so_instructions(fleet: dict) -> dict:
    """The System Operator's own out-of-merit dispatch record, three
    sibling publications the round-9 audit surfaced: the weekly processed
    MOT-raise re-dispatch list (MOTRD; same schema and cadence as the
    must-run list, but the full record), the per-grid dispatch
    instruction log (SODIR; dailies plus weekly compilations, dailies
    counted) whose remarks name the cause, and the operator's own
    valid-discrepancy list on that report (VDSODIR)."""
    import statistics as _stats

    motrd = dataset_files("MOTRD")
    sodir = dataset_files("SODIR")
    if not motrd or not sodir:
        return {"available": False,
                "note": "MOTRD/SODIR datasets absent; SO instruction "
                        "record unavailable."}
    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}
    # MOTRD REGION carries the CLUZ/CVIS/CMIN codes (same trap the RTDSL
    # review caught); cover both forms
    grid_names = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao",
                  "LUZON": "luzon", "VISAYAS": "visayas",
                  "MINDANAO": "mindanao"}

    # the weekly processed MOT-raise list: the full out-of-merit record
    weeks = []
    all_mw: list[float] = []
    per_res: dict[str, dict] = {}
    cats: dict[str, int] = {}
    for path in motrd:
        wk_rows = 0
        wk_mw: list[float] = []
        wk_res = set()
        for r in rows_of(path):
            res = (r.get("RESOURCE_NAME") or "").strip()
            if not res:
                continue
            mw = f(r.get("SO_MW_INSTRUCTION"))
            wk_rows += 1
            wk_mw.append(mw)
            wk_res.add(res)
            cat = (r.get("CATEGORY") or "").strip()
            if cat:
                cats[cat] = cats.get(cat, 0) + 1
            e = per_res.setdefault(res, {
                "resource": res,
                "grid": grid_names.get((r.get("REGION") or "").strip()),
                "n_rows": 0, "max_mw": 0.0})
            e["n_rows"] += 1
            e["max_mw"] = max(e["max_mw"], mw)
        all_mw.extend(wk_mw)
        weeks.append({"week": day_of(path), "n_rows": wk_rows,
                      "n_resources": len(wk_res),
                      "median_mw": (round(_stats.median(wk_mw), 1)
                                    if wk_mw else None),
                      "max_mw": round(max(wk_mw), 1) if wk_mw else None})
    top = []
    for e in sorted(per_res.values(), key=lambda x: -x["n_rows"])[:12]:
        fuel, _ = _resolve(e["resource"], rows_by_name)
        top.append({**e, "max_mw": round(e["max_mw"], 1), "fuel": fuel})

    # the must-run subset, measured beside it: the inertness claim is
    # scoped to THIS series and stays true; the full record is not inert
    mru_mw = [f(r.get("SO_MW_INSTRUCTION")) for p in dataset_files("MRU")
              for r in rows_of(p) if (r.get("RESOURCE_NAME") or "").strip()]

    # the daily per-grid instruction log: causes, named. The remarks are
    # free text, so the cause screen is a substring count (labeled), not
    # a grammar: "limitation" flags the remark, and the corridor tallies
    # count which named element the operator wrote
    n_instr = 0
    day_set = set()
    sodir_cats: dict[str, int] = {}
    causes = {"leyte-cebu": 0, "hvdc": 0, "other": 0}
    n_limit = 0
    n_weekly = 0
    n_daily = 0
    import csv as _csv
    import io as _io
    for path in sodir:
        # range-stamped names are the operator's WEEKLY compilations (and
        # occasional revisions) of the dailies; counting both would double
        # 84 of the window's 90 days (the round-9 diff review caught the
        # inflated counts)
        if re.search(r"\d{8}-\d{8}", os.path.basename(path)):
            n_weekly += 1
            continue
        n_daily += 1
        day_set.add(day_of(path))
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # three preamble lines (operations title, report name, date range)
        # sit above the header
        idx = text.find("UNIT,")
        if idx < 0:
            continue
        for r in _csv.DictReader(_io.StringIO(text[idx:])):
            if not (r.get("UNIT") or "").strip():
                continue
            n_instr += 1
            cat = (r.get("CATEGORY") or "").strip()
            if cat:
                sodir_cats[cat] = sodir_cats.get(cat, 0) + 1
            rem = (r.get("REMARKS") or "").lower()
            if "limitation" in rem:
                n_limit += 1
                # the operator writes the corridor as "Leyte-Cebu",
                # "Leyte - Cebu", and "Leyte Cebu"; squeeze separators so
                # all three count (the round-10 critic found 118 remarks
                # in the unhyphenated spellings misfiled as 'other')
                squeezed = re.sub(r"[\s-]+", "", rem)
                if "leytecebu" in squeezed:
                    causes["leyte-cebu"] += 1
                elif "hvdc" in squeezed:
                    causes["hvdc"] += 1
                else:
                    causes["other"] += 1

    # the operator's own discrepancy list: newest revision per week
    vd_by_week: dict[str, tuple[str, str]] = {}
    for path in dataset_files("VDSODIR"):
        name = os.path.basename(path)
        m = re.search(r"(\d{8})-\d{8}_as_of_(\d{8})", name)
        if not m:
            continue
        wk, asof = m.group(1), m.group(2)
        if wk not in vd_by_week or asof > vd_by_week[wk][0]:
            vd_by_week[wk] = (asof, path)
    vd_rows = sum(
        sum(1 for r in rows_of(p) if any((v or "").strip()
                                         for v in r.values()))
        for _, p in vd_by_week.values())

    return {
        "available": True,
        "motrd": {
            "weeks": weeks,
            "n_rows": len(all_mw),
            "n_resources": len(per_res),
            "median_mw": round(_stats.median(all_mw), 1),
            "max_mw": round(max(all_mw), 1),
            "n_at_least_100mw": sum(1 for m in all_mw if m >= 100),
            "categories": dict(sorted(cats.items(), key=lambda kv: -kv[1])),
            "top": top,
            "src": ("https://www.iemop.ph/market-data/list-of-mot-raise-"
                    "re-dispatch-based-on-so-dispatch-instruction-report/"),
        },
        "mru_contrast": {
            "mru_median_mw": (round(_stats.median(mru_mw), 1)
                              if mru_mw else None),
            "mru_max_mw": round(max(mru_mw), 1) if mru_mw else None,
            "note": ("The must-run list the methodology measured as inert "
                     "is the SUBSET; its median instruction sits at "
                     "roughly a tenth of the full MOT-raise record's, so "
                     "the inertness finding is scoped to must-run and "
                     "does not extend to this layer."),
        },
        "sodir": {
            "n_files": n_daily,
            "n_weekly_files_archived": n_weekly,
            "n_days": len(day_set),
            "n_instructions": n_instr,
            "categories": dict(sorted(sodir_cats.items(),
                                      key=lambda kv: -kv[1])[:10]),
            "n_limitation_remarks": n_limit,
            "limitation_causes": causes,
            "cause_note": ("The cause screen is a substring count over "
                           "the free-text REMARKS column, labeled as "
                           "such: a remark containing 'limitation' flags "
                           "the instruction, and the corridor tallies "
                           "count which named element the operator wrote "
                           "(the Leyte-Cebu corridor dominates). Counts "
                           "cover the DAILY files only; the operator's "
                           "weekly compilations are archived beside them "
                           "but not counted, or the window's days would "
                           "double."),
            "src": ("https://www.iemop.ph/market-data/"
                    "so-dispatch-instruction-report/"),
        },
        "discrepancies": {
            "n_weeks": len(vd_by_week),
            "n_rows_newest_revisions": vd_rows,
            "note": ("The operator's own valid-discrepancy list on the "
                     "dispatch instruction report, newest revision per "
                     "week: the data-quality flag that travels with "
                     "anything built from this family."),
            "src": ("https://www.iemop.ph/market-data/valid-discrepancies-"
                    "on-so-dispatch-instruction-report/"),
        },
        "note": ("The System Operator's out-of-merit dispatch record, "
                 "measured: every MOT-raise re-dispatch instruction per "
                 "5-minute interval with its MW (weekly processed files), "
                 "the per-grid daily instruction log with the operator's "
                 "stated cause, and the operator's own discrepancy list. "
                 "Consuming this record as an engine layer (an "
                 "administered-dispatch overlay on the replay) is a named "
                 "queued build; this block is the measured record that "
                 "sizes it."),
        "fuel_note": ("Fuel per resource comes from the pasa alias table "
                      "into the DOE fleet; codes without a confident alias "
                      "show no fuel rather than a guessed one."),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


def build_drivers(prices: dict, profiles: dict, pasa: dict,
                  advisories: dict, reserve_prices: dict) -> dict:
    """The per-day drivers timeline: what moved prices, joined from the
    layers the archive already carries. One row per archive day."""
    prof_by_date = {d["date"]: d for d in profiles.get("days", [])}
    pasa_by_date = {d["date"]: d for d in (pasa.get("days") or [])}
    adv_by_date = {d["date"]: d for d in (advisories.get("days") or [])}
    rsv_dates = reserve_prices.get("dates") or []
    rsv_idx = {d: i for i, d in enumerate(rsv_dates)}

    # per-day real-time binding constraints, straight from RTDCV
    bind_by_date: dict[str, dict] = {}
    for path in dataset_files("RTDCV"):
        day = day_of(path)
        eq: dict[str, int] = {}
        for r in rows_of(path):
            name = (r.get("EQUIPMENT_NAME") or "").strip()
            if name:
                eq[name] = eq.get(name, 0) + 1
        top = sorted(eq.items(), key=lambda kv: -kv[1])[:3]
        bind_by_date[day] = {
            "rtd_binding_rows": sum(eq.values()),
            "top_equipment": [{"name": k, "rows": v} for k, v in top],
        }

    rows = []
    for i, date in enumerate(prices.get("dates") or []):
        prof = prof_by_date.get(date) or {}
        pas = pasa_by_date.get(date) or {}
        adv = adv_by_date.get(date) or {}
        row = {
            "date": date,
            "market": date >= (prices.get("resumed") or "2026-05-01"),
            "lwap": {g: (prices["series"][g][i]
                         if i < len(prices["series"][g]) else None)
                     for g in GRIDS_L},
            "spread": (prices.get("spread") or [None] * (i + 1))[i]
            if i < len(prices.get("spread") or []) else None,
            "curtailed_mwh": prof.get("curtailed_mwh"),
            "out_matched_mw": pas.get("matched_mw"),
            "hydro_budget_mwh": prof.get("hydro_budget_mwh"),
            "n_advisories": adv.get("n"),
            "n_hvdc_advisories": adv.get("n_hvdc"),
            "n_alert_advisories": adv.get("n_alert"),
            "binding": bind_by_date.get(date),
        }
        j = rsv_idx.get(date)
        if j is not None:
            mx = None
            for g in GRIDS_L:
                for s in (reserve_prices.get("series") or {}).get(g, {}).values():
                    v = s[j] if j < len(s) else None
                    if v is not None and (mx is None or v > mx):
                        mx = v
            row["reserve_price_max"] = mx
        rows.append(row)
    return {
        "available": bool(rows),
        "days": rows,
        "note": ("One row per archive day: observed daily LWAP per grid, "
                 "the Visayas-Luzon spread, recorded curtailment, the "
                 "operator's matched scheduled-out MW, the day's observed "
                 "hydro water, advisory counts (HVDC events, alerts), the "
                 "day's real-time binding constraints, and the dearest "
                 "regional reserve price. Every column is observed data "
                 "from the archive; nothing here is modeled."),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }
