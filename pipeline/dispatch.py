#!/usr/bin/env python3
"""A simplified merit-order economic-dispatch model for the Philippine grid.

NOT PLEXOS. This stacks the sourced fleet (pipeline/fleet_ph.py) by marginal cost
against the archive's observed dispatched generation, per grid, per interval, and
reads off the marginal clearing price. Its honesty gate is the calibration residual
against observed load-weighted average price (LWAP): a competitive cost stack fits
normal hours and UNDER-predicts tight hours, and that residual is the scarcity /
offer premium a pure cost model cannot see. We ship the residual, we do not tune it
away (inflating fuel costs to fake peaks would corrupt the off-peak fit).

Each grid is cleared against its OWN demand and its OWN fleet, because the whole
point of this project is that Luzon / Visayas / Mindanao are separated by binding
HVDC limits and price apart. HVDC enters as an optional import block in the
scenario levers, capped at the corridor's operating limit.

Outputs baked to web/data/dispatch.json (+ generators.geojson):
  - merit_order: the per-grid supply stack the Simulate panel re-clears client-side
  - calibration: MAE / bias / correlation of modeled vs observed LWAP, per grid
  - representative_day: hourly demand, modeled price, observed price, per grid
  - n1: every named unit's price impact and shortfall when tripped at peak
  - adequacy: reserve margin now, and against the DICT 1.5 GW by 2028 forecast
  - reliability: model shortfall intervals (LOLE-style) and EUE (MWh)
  - emissions: modeled generation and tCO2 by fuel, per grid
"""
from __future__ import annotations

import math
import re

from build_data import REGION_MAP, dataset_files, day_of, f, rows_of
from constants_ph import DEMAND_ANCHORS, GENERATORS
from fleet_ph import (
    FUEL_CO2_T_PER_MWH,
    FUEL_COST_PHP_KWH,
    GRID_FUEL_MW,
    GRIDS,
    NATIONAL_FUEL_MW,
    avail_mw,
    clear,
    stack,
)

PEAK_HOUR = 19  # evening peak: solar ~0, the tight hour the N-1/adequacy use
# IEMOP TIME_INTERVAL is a 12-hour clock, e.g. "4/7/2026 1:05:00 PM".
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2}):\d{2}\s*(AM|PM)\b", re.I)
_TIME_RE_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def hour_of(ti: str) -> int:
    """Hour 0-23 from an IEMOP TIME_INTERVAL string (interval-ending time)."""
    m = _TIME_RE.search(ti or "")
    if m:
        h = int(m.group(1)) % 12
        if m.group(3).upper() == "PM":
            h += 12
        return h
    m = _TIME_RE_24.search(ti or "")
    return int(m.group(1)) % 24 if m else PEAK_HOUR


def _corr(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return round(sxy / math.sqrt(sxx * syy), 3)


def _read_prices() -> dict[str, dict[tuple, float]]:
    """LWAP by day -> (grid, time_interval) -> PhP/kWh."""
    by_day: dict[str, dict[tuple, float]] = {}
    for path in dataset_files("LWAPF"):
        d = by_day.setdefault(day_of(path), {})
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            ti = (r.get("TIME_INTERVAL") or "").strip()
            if grid and ti:
                d[(grid, ti)] = f(r.get("LWAP")) / 1000  # PhP/MWh -> PhP/kWh
    return by_day


def _fuel_dispatch(blocks: list[dict], demand: float) -> dict[str, float]:
    """Split served MW across fuels by merit order (for the emissions estimate)."""
    out: dict[str, float] = {}
    remaining = demand
    for b in sorted(blocks, key=lambda x: x["cost"]):
        if remaining <= 0:
            break
        take = min(b["mw"], remaining)
        out[b["fuel"]] = out.get(b["fuel"], 0.0) + take
        remaining -= take
    return out


def build_dispatch() -> dict:
    prices = _read_prices()
    rtd = dataset_files("RTDSUM")
    if not rtd or not prices:
        return {"available": False,
                "note": "RTDSUM or LWAPF absent; dispatch model omitted"}

    # cache one stack per (grid, hour) so we clear cheaply over many intervals
    stack_cache: dict[tuple, list[dict]] = {}

    def stk(grid: str, hour: int) -> list[dict]:
        key = (grid, hour)
        if key not in stack_cache:
            stack_cache[key] = stack(grid, hour)
        return stack_cache[key]

    obs: dict[str, list[float]] = {g: [] for g in GRIDS}
    mod: dict[str, list[float]] = {g: [] for g in GRIDS}
    peak_demand: dict[str, float] = {g: 0.0 for g in GRIDS}
    demands: dict[str, list[float]] = {g: [] for g in GRIDS}
    fuel_mwh: dict[str, dict[str, float]] = {g: {} for g in GRIDS}
    lole_intervals: dict[str, int] = {g: 0 for g in GRIDS}
    eue_mwh: dict[str, float] = {g: 0.0 for g in GRIDS}
    # hourly accumulation for the representative curves (mean over the window)
    hourly: dict[str, dict[int, list]] = {g: {h: [] for h in range(24)}
                                          for g in GRIDS}
    days_seen: set[str] = set()

    for path in rtd:
        day = day_of(path)
        pday = prices.get(day, {})
        if not pday:
            continue
        days_seen.add(day)
        for r in rows_of(path):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            if not grid:
                continue
            gen = f(r.get("GENERATION"))
            if gen <= 0:
                continue
            ti = (r.get("TIME_INTERVAL") or "").strip()
            hour = hour_of(ti)
            blocks = stk(grid, hour)
            res = clear(blocks, gen)
            peak_demand[grid] = max(peak_demand[grid], gen)
            demands[grid].append(gen)
            if res["shortfall_mw"] > 0:
                lole_intervals[grid] += 1
                eue_mwh[grid] += res["shortfall_mw"] * 5 / 60
            for fuel, mw in _fuel_dispatch(blocks, res["served_mw"]).items():
                fuel_mwh[grid][fuel] = fuel_mwh[grid].get(fuel, 0.0) + mw * 5 / 60
            price = pday.get((grid, ti))
            if price is not None:
                obs[grid].append(price)
                mod[grid].append(res["price"])
                hourly[grid][hour].append((gen, res["price"], price))

    calibration = {}
    for g in GRIDS:
        o, m = obs[g], mod[g]
        if not o:
            continue
        mae = round(sum(abs(a - b) for a, b in zip(m, o)) / len(o), 3)
        omean, mmean = sum(o) / len(o), sum(m) / len(m)
        # The window residual (observed - modeled) flips sign across the day: the
        # static stack OVER-prices the overnight trough (real units bid below cost
        # to stay committed) and UNDER-prices the evening peak (scarcity + offers).
        # So the honest headline is MAE, not the netted mean. The one-directional
        # scarcity signal is the evening-peak residual (hours 17-21), where observed
        # exceeds modeled every hour.
        peak_pts = [(mp, op) for h in range(17, 22)
                    for _g, mp, op in hourly[g][h]]
        peak_resid = (round(sum(op - mp for mp, op in peak_pts) / len(peak_pts), 3)
                      if peak_pts else None)
        corr = _corr(m, o)
        calibration[g.lower()] = {
            "n_intervals": len(o),
            "observed_mean_php_kwh": round(omean, 3),
            "modeled_mean_php_kwh": round(mmean, 3),
            "mae_php_kwh": mae,
            "bias_php_kwh": round(mmean - omean, 3),
            "evening_peak_residual_php_kwh": peak_resid,
            "correlation": corr,
            "note": ("modeled price is flat (demand never leaves the coal block); "
                     "zero variance, correlation undefined"
                     if corr is None else None),
        }

    representative = {}
    for g in GRIDS:
        hrs = []
        for h in range(24):
            pts = hourly[g][h]
            if not pts:
                continue
            hrs.append({
                "hour": h,
                "demand_mw": round(sum(p[0] for p in pts) / len(pts)),
                "modeled_price": round(sum(p[1] for p in pts) / len(pts), 3),
                "observed_price": round(sum(p[2] for p in pts) / len(pts), 3),
            })
        if hrs:
            representative[g.lower()] = hrs

    # merit-order stack for the Simulate panel (reference = evening peak hour)
    merit_order = {}
    for g in GRIDS:
        blocks = stack(g, PEAK_HOUR)
        merit_order[g.lower()] = {
            "reference_hour": PEAK_HOUR,
            "installed_mw": sum(GRID_FUEL_MW[g].values()),
            "avail_mw": round(sum(b["mw"] for b in blocks), 1),
            "peak_demand_mw": round(peak_demand[g]),
            "blocks": blocks,
        }

    # N-1: trip each named unit at a representative tight-evening demand (the grid's
    # 95th-percentile observed demand). At the absolute peak Luzon already clears on
    # oil, so a p95 reference is where a trip that flips coal->oil shows its price
    # move; the shortfall column is the reliability signal at that condition.
    def pctl(vals: list[float], p: float) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return s[min(len(s) - 1, int(p * len(s)))]

    n1_ref = {g: round(pctl(demands[g], 0.95)) for g in GRIDS}
    n1 = []
    for u in GENERATORS:
        g = u["grid"]
        ref = n1_ref[g] or sum(b["mw"] for b in stack(g, PEAK_HOUR)) * 0.9
        pk = peak_demand[g] or ref
        trip_mw = min(u["capacity_mw"], avail_mw(g, u["fuel"], PEAK_HOUR))
        removed = {u["fuel"]: trip_mw}
        # price move at a tight evening (p95); shortfall at the annual peak
        base = clear(stack(g, PEAK_HOUR), ref)
        tripped = clear(stack(g, PEAK_HOUR, removed=removed), ref)
        at_peak = clear(stack(g, PEAK_HOUR, removed=removed), pk)
        n1.append({
            "unit": u["name"], "grid": g.lower(), "fuel": u["fuel"],
            "capacity_mw": u["capacity_mw"],
            "tight_evening_demand_mw": round(ref),
            "base_price_php_kwh": base["price"],
            "tripped_price_php_kwh": tripped["price"],
            "delta_price_php_kwh": round(tripped["price"] - base["price"], 3),
            "peak_demand_mw": round(pk),
            "shortfall_at_peak_mw": at_peak["shortfall_mw"],
        })
    n1.sort(key=lambda x: (-x["shortfall_at_peak_mw"],
                           -x["delta_price_php_kwh"], -x["capacity_mw"]))

    # adequacy now, and against the DICT 1.5 GW by 2028 forecast (added to Luzon)
    adequacy = {}
    for g in GRIDS:
        blocks = stack(g, PEAK_HOUR)
        av = sum(b["mw"] for b in blocks)
        pk = peak_demand[g]
        adequacy[g.lower()] = {
            "installed_mw": sum(GRID_FUEL_MW[g].values()),
            "avail_at_peak_mw": round(av, 1),
            "peak_demand_mw": round(pk),
            "reserve_margin_pct": round((av - pk) / pk * 100, 1) if pk else None,
        }
    dict_anchor = next((a for a in DEMAND_ANCHORS
                        if a.get("owner") == "DICT" and a.get("mw") == 1500), None)
    added = 1500
    lz_blocks = stack("LUZON", PEAK_HOUR)
    lz_av = sum(b["mw"] for b in lz_blocks)
    lz_pk = peak_demand["LUZON"]
    short_intervals = short_eue = 0
    for h in range(24):
        for gen, _mp, _op in hourly["LUZON"][h]:
            deficit = (gen + added) - lz_av
            if deficit > 0:
                short_intervals += 1
                short_eue += deficit * 5 / 60
    adequacy["dict_2028"] = {
        "added_mw": added, "owner": "DICT", "label": "forecast: PH data-center "
        "capacity by 2028", "date": "2025-10",
        "src": dict_anchor["src"] if dict_anchor else None,
        "luzon_avail_at_peak_mw": round(lz_av, 1),
        "luzon_peak_now_mw": round(lz_pk),
        "luzon_peak_plus_dc_mw": round(lz_pk + added),
        "reserve_margin_now_pct": round((lz_av - lz_pk) / lz_pk * 100, 1)
        if lz_pk else None,
        "reserve_margin_with_dc_pct": round((lz_av - lz_pk - added)
                                            / (lz_pk + added) * 100, 1)
        if lz_pk else None,
        "shortfall_intervals_with_dc": short_intervals,
        "eue_mwh_with_dc": round(short_eue, 1),
    }

    reliability = {}
    for g in GRIDS:
        reliability[g.lower()] = {
            "shortfall_intervals": lole_intervals[g],
            "eue_mwh": round(eue_mwh[g], 1),
        }

    emissions = {}
    for g in GRIDS:
        per_fuel = {}
        for fuel, mwh in sorted(fuel_mwh[g].items()):
            per_fuel[fuel] = {
                "generation_gwh": round(mwh / 1000, 1),
                "tco2": round(mwh * FUEL_CO2_T_PER_MWH.get(fuel, 0.0)),
            }
        emissions[g.lower()] = {
            "by_fuel": per_fuel,
            "total_tco2": round(sum(v["tco2"] for v in per_fuel.values())),
            "total_generation_gwh": round(
                sum(v["generation_gwh"] for v in per_fuel.values()), 1),
        }

    return {
        "available": True,
        "unit": "PhP/kWh clearing price from a merit-order stack vs observed "
                "dispatched generation, per grid, per 5-min interval",
        "model": "simplified merit-order economic dispatch, calibrated against "
                 "observed LWAP; not PLEXOS",
        "assumptions": {
            "fuel_marginal_cost_php_kwh": FUEL_COST_PHP_KWH,
            "national_fuel_mw": NATIONAL_FUEL_MW,
            "note": "Coal (P6.00) and Malampaya gas (P4.80) costs are sourced (ERC "
                    "administered price; Malampaya FOI). Availability derates, the "
                    "solar profile, the oil peaker cost, and the per-grid fuel "
                    "split are labeled model assumptions. A competitive cost stack "
                    "gives a near-flat ~P6 line: it over-prices the overnight "
                    "trough (units bid below cost to stay committed) and "
                    "under-prices the evening peak (scarcity and offers). The daily "
                    "shape and the island spread are commitment, scarcity, and "
                    "offer behaviour, not data-center load.",
        },
        "days": len(days_seen),
        "merit_order": merit_order,
        "calibration": calibration,
        "representative_day": representative,
        "n1": n1,
        "adequacy": adequacy,
        "reliability": reliability,
        "emissions": emissions,
    }


def generators_features() -> list[dict]:
    """GeoJSON features for the named-generator map layer + N-1 picker."""
    feats = []
    for u in GENERATORS:
        props = {k: v for k, v in u.items() if k != "coords"}
        props["marginal_cost_php_kwh"] = FUEL_COST_PHP_KWH.get(u["fuel"])
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": u["coords"]},
                      "properties": props})
    return feats


if __name__ == "__main__":
    import json
    d = build_dispatch()
    print(json.dumps({k: v for k, v in d.items()
                      if k in ("calibration", "adequacy", "reliability")},
                     indent=1))
