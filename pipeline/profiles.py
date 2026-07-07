#!/usr/bin/env python3
"""Bake observed hourly day profiles from the IEMOP archive (web/data/profiles.json).

The chronological engine (pipeline/chrono.py and the studio's chrono.ts) replays
OBSERVED days, not synthetic ones: per-grid hourly demand comes from the RTD
regional summaries and the observed hourly price from the final LWAP files. Demand
here means dispatched generation (the same load axis dispatch.py calibrates
against); the label travels with the artifact.

Also carried here, because the chronological run needs them in one place:
  - the 24-hour solar availability shape (fleet_ph.SOLAR_PROFILE, a labeled
    assumption)
  - the storage fleet the chronological run can cycle (power sourced, energy
    duration a labeled assumption; the snapshot views keep storage out of the
    energy stack exactly as before)
  - the per-grid mean scheduled reserve requirement (RTDSUM reserve rows), for
    the reserve-deduction option
"""
from __future__ import annotations

from build_data import GRIDS, REGION_MAP, dataset_files, day_of, f, rows_of
from constants_ph import MARKET_ANCHORS
from dispatch import hour_of
from fleet_ph import SOLAR_PROFILE, STORAGE_ROUND_TRIP_EFF

RESERVE_COMMODITIES = {"Dr", "Fr", "Ru", "Rd"}


def _hourly_mean(acc: dict[int, list[float]], dp: int) -> list[float | None]:
    out: list[float | None] = []
    for h in range(24):
        vals = acc.get(h) or []
        out.append(round(sum(vals) / len(vals), dp) if vals else None)
    return out


def build_profiles() -> dict:
    lw_files = {day_of(p): p for p in dataset_files("LWAPF")}
    resumed = MARKET_ANCHORS.get("wesm_resumed", "2026-05-01")

    days = []
    reserve_req: dict[str, dict[str, list[float]]] = {
        g.lower(): {} for g in GRIDS}
    for path in dataset_files("RTDSUM"):
        day = day_of(path)
        dem: dict[str, dict[int, list[float]]] = {
            g.lower(): {} for g in GRIDS}
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            if not grid:
                continue
            com = (r.get("COMMODITY_TYPE") or "").strip()
            h = hour_of((r.get("TIME_INTERVAL") or "").strip())
            if com == "En":
                gen = f(r.get("GENERATION"))
                if gen > 0:
                    dem[grid.lower()].setdefault(h, []).append(gen)
            elif com in RESERVE_COMMODITIES:
                req = f(r.get("MKT_REQT"))
                if req > 0:
                    reserve_req[grid.lower()].setdefault(com, []).append(req)
        # a replayable day needs the full 24 demand hours on every grid
        if not all(len(dem[g.lower()]) == 24 for g in GRIDS):
            continue
        lwap: dict[str, list[float | None]] = {}
        lw_path = lw_files.get(day)
        if lw_path:
            acc: dict[str, dict[int, list[float]]] = {}
            for r in rows_of(lw_path):
                grid = (r.get("REGION_NAME") or "").strip()
                key = ("system" if grid == "SYSTEM"
                       else (REGION_MAP.get(grid) or "").lower())
                if not key:
                    continue
                h = hour_of((r.get("TIME_INTERVAL") or "").strip())
                acc.setdefault(key, {}).setdefault(h, []).append(
                    f(r.get("LWAP")) / 1000)
            for key, by_h in acc.items():
                lwap[key] = _hourly_mean(by_h, 3)
        days.append({
            "date": day,
            "market": day >= resumed,
            "demand": {g.lower(): [round(v) for v in
                                   _hourly_mean(dem[g.lower()], 1)]
                       for g in GRIDS},
            "lwap": lwap,
        })
    days.sort(key=lambda d: d["date"])

    def full_lwap(d: dict) -> bool:
        lz = d["lwap"].get("luzon") or []
        return len(lz) == 24 and all(v is not None for v in lz)

    market = [d for d in days if d["market"] and full_lwap(d)]
    default_day = None
    if market:
        default_day = max(
            market,
            key=lambda d: max(d["lwap"]["luzon"]) - min(d["lwap"]["luzon"]),
        )["date"]
    stress_day = None
    if market:
        stress_day = max(
            market, key=lambda d: max(d["demand"]["luzon"]))["date"]

    return {
        "unit": "hourly mean per grid: demand MW (dispatched generation, "
                "RTDSUM En rows) and observed LWAP PhP/kWh (LWAPF)",
        "note": "Observed days replayed as-is, no synthetic profiles. Demand is "
                "dispatched generation, the same load axis the dispatch model "
                "calibrates against. Days without full 24-hour demand coverage "
                "on all three grids are dropped, not filled.",
        "resumed": resumed,
        "days": days,
        "default_day": default_day,
        "stress_day": stress_day,
        "solar_profile": [SOLAR_PROFILE[h] for h in range(24)],
        "solar_profile_note": "Normalised clear-sky-ish PH solar output by hour, "
                              "a labeled model assumption (fleet_ph.SOLAR_PROFILE), "
                              "not measured irradiance.",
        "storage_defaults": [
            {
                "id": "bess_luzon", "label": "Luzon BESS fleet", "grid": "luzon",
                "power_mw": 634, "energy_mwh": 634,
                "src_power": "https://legacy.doe.gov.ph/electric-power/list-existing-power-plants-march-2025",
                "energy_note": "ASSUMPTION: about one hour of storage at rated "
                               "power; the DOE lists MW, not MWh.",
            },
            {
                "id": "kalayaan", "label": "Kalayaan pumped storage", "grid": "luzon",
                "power_mw": 685, "energy_mwh": 4110,
                "src_power": "http://www.cbkpower.com/project/kalayaan-pumped-storage-power-plant-kpspp/",
                "energy_note": "ASSUMPTION: about six hours at rated power from "
                               "the upper reservoir; CBK publishes MW, not MWh.",
            },
        ],
        "storage_round_trip_eff": STORAGE_ROUND_TRIP_EFF,
        "storage_note": "The chronological run cycles this fleet with a labeled "
                        "charge-cheap / discharge-dear heuristic (quartile "
                        "thresholds from a first pass without storage). The "
                        "snapshot views keep storage out of the energy stack, "
                        "as before.",
        "reserve_req_mean_mw": {
            g: {com: round(sum(v) / len(v), 1)
                for com, v in reserve_req[g].items() if v}
            for g in (k.lower() for k in GRIDS)
        },
        "reserve_req_note": "Mean scheduled reserve requirement per grid and "
                            "commodity over the archive window (RTDSUM MKT_REQT; "
                            "Ru/Rd regulation, Dr dispatchable, Fr contingency "
                            "mapping INFERRED as in reserve.json).",
    }
