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


def _interval_hour(ts: str) -> int:
    """Hour bucket for an interval-ENDING timestamp. IEMOP serializes the
    midnight-ending interval as a bare date (no time part): that interval
    belongs to hour 23, not to hour_of's peak-hour fallback."""
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
                acc[g].setdefault(_interval_hour(ts), []).append(
                    sum(prices) / len(prices))
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
