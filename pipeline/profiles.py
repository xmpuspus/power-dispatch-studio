#!/usr/bin/env python3
"""Bake observed hourly day profiles from the IEMOP archive (web/data/profiles.json).

The chronological engine (pipeline/chrono.py and the studio's chrono.ts) replays
OBSERVED days, not synthetic ones: per-grid hourly demand comes from the RTD
regional summaries and the observed hourly price from the final LWAP files.
Demand here means dispatched generation PLUS recorded curtailment (the load
that was there to serve, so a backcast can reproduce the scarcity it is scored
against); the label travels with the artifact.

Each day also carries the deviation of the operator's matched scheduled-out
MW from the window mean (per grid and fuel, from the PASA layer): the static
availability derates carry the AVERAGE outage state, so the engines subtract
only each day's deviation from that average, never both. Hydro is excluded
here because its daily variation is already the observed water budget.

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
from market_obs import mcp_hourly

RESERVE_COMMODITIES = {"Dr", "Fr", "Ru", "Rd"}


def _hourly_mean(acc: dict[int, list[float]], dp: int) -> list[float | None]:
    out: list[float | None] = []
    for h in range(24):
        vals = acc.get(h) or []
        out.append(round(sum(vals) / len(vals), dp) if vals else None)
    return out


def build_profiles(fleet: dict | None = None,
                   merit_hydro_mw: dict | None = None,
                   pasa: dict | None = None) -> dict:
    lw_files = {day_of(p): p for p in dataset_files("LWAPF")}
    resumed = MARKET_ANCHORS.get("wesm_resumed", "2026-05-01")

    days = []
    reserve_req: dict[str, dict[str, list[float]]] = {
        g.lower(): {} for g in GRIDS}
    for path in dataset_files("RTDSUM"):
        day = day_of(path)
        dem: dict[str, dict[int, list[float]]] = {
            g.lower(): {} for g in GRIDS}
        net_imp: dict[str, dict[int, list[float]]] = {
            g.lower(): {} for g in GRIDS}
        cur_mwh: dict[str, float] = {g.lower(): 0.0 for g in GRIDS}
        day_req: dict[str, dict[str, list[float]]] = {
            g.lower(): {} for g in GRIDS}
        for r in rows_of(path):
            grid = REGION_MAP.get((r.get("REGION_NAME") or "").strip())
            if not grid:
                continue
            com = (r.get("COMMODITY_TYPE") or "").strip()
            h = hour_of((r.get("TIME_INTERVAL") or "").strip())
            if com == "En":
                gen = f(r.get("GENERATION"))
                imp = f(r.get("MKT_IMPORT"))
                exp = f(r.get("MKT_EXPORT"))
                cur = max(0.0, f(r.get("LOAD_CURTAILED")))
                if gen > 0:
                    # demand = NATIVE LOAD: generation plus net market
                    # imports plus recorded curtailment. Generation alone
                    # self-balances every grid by construction and erases
                    # the observed inter-island flows (Visayas net-imports
                    # about a quarter of its own generation); the archived
                    # MKT_IMPORT/MKT_EXPORT columns carry the real geometry
                    dem[grid.lower()].setdefault(h, []).append(
                        gen + imp - exp + cur)
                    net_imp[grid.lower()].setdefault(h, []).append(imp - exp)
                    cur_mwh[grid.lower()] += cur * 5 / 60
            elif com in RESERVE_COMMODITIES:
                req = f(r.get("MKT_REQT"))
                if req > 0:
                    reserve_req[grid.lower()].setdefault(com, []).append(req)
                    day_req[grid.lower()].setdefault(com, []).append(req)
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
        # observed corridor flows on the radial path, from the same rows:
        # f1 (Luzon->Visayas, positive south) is Luzon's net export, f2
        # (Visayas->Mindanao, positive south) is Mindanao's net import
        lz = _hourly_mean(net_imp["luzon"], 1)
        mi = _hourly_mean(net_imp["mindanao"], 1)
        days.append({
            "date": day,
            "market": day >= resumed,
            "demand": {g.lower(): [round(v) for v in
                                   _hourly_mean(dem[g.lower()], 1)]
                       for g in GRIDS},
            "net_flow": {
                "lv": [None if v is None else round(-v, 1) for v in lz],
                "vm": [None if v is None else round(v, 1) for v in mi],
            },
            "curtailed_mwh": {g: round(v, 1) for g, v in cur_mwh.items()
                              if v > 0} or None,
            "reserve_req_mw": {
                g: {com: round(sum(vals) / len(vals), 1)
                    for com, vals in day_req[g].items() if vals}
                for g in ("luzon", "visayas", "mindanao")
                if day_req[g]} or None,
            "lwap": lwap,
        })
    days.sort(key=lambda d: d["date"])

    # the observed hourly regional clearing price (MCP), the backcast's
    # second target: commensurate with a dispatch dual, unlike LWAP which
    # also carries nodal spread and settlement substitution
    mcp = mcp_hourly()
    for d in days:
        d["mcp"] = mcp.get(d["date"])

    # the day's Leyte-Luzon corridor availability, inferred from the NSO
    # advisory stream: each hour's cap scales by the fraction of the hour
    # the link was unblocked (present only on days with a recorded block)
    from market_obs import hvdc_unblocked_fractions
    hvdc = hvdc_unblocked_fractions()
    for d in days:
        frac = hvdc.get(d["date"])
        if frac and any(f < 1.0 for f in frac):
            d["corridor_caps"] = {"leyte": frac}

    # each day's scheduled-outage DEVIATION from the MARKET-window mean, per
    # grid and fuel (PASA layer, matched MW only). The static derates carry
    # the average outage state; the engines subtract only this deviation,
    # and the baseline is the market days the backcast actually replays, so
    # the adjustment washes out over the scored window instead of importing
    # the suspension weeks' outage level. Hydro excluded: its daily
    # variation is the observed water budget. Storage excluded: it is not
    # in the energy stack.
    if pasa and pasa.get("available"):
        by_date = {d["date"]: d.get("matched_fuel_mw") or {}
                   for d in pasa["days"]}
        skip = {"hydro", "storage"}
        mean: dict[str, dict[str, float]] = {}
        covered = [d for d in days if d["date"] in by_date and d["market"]]
        for d in covered:
            for g, fm in by_date[d["date"]].items():
                for fuel, mw in fm.items():
                    if fuel in skip:
                        continue
                    mean.setdefault(g, {})[fuel] = (
                        mean.get(g, {}).get(fuel, 0.0) + mw / len(covered))
        for d in days:
            fm_day = by_date.get(d["date"])
            if fm_day is None:
                d["out_dev_mw"] = None
                continue
            dev: dict[str, dict[str, float]] = {}
            for g in mean:
                for fuel, mu in mean[g].items():
                    v = round((fm_day.get(g, {}).get(fuel, 0.0)) - mu, 1)
                    if abs(v) >= 0.1:
                        dev.setdefault(g, {})[fuel] = v
                for fuel, mw in (fm_day.get(g) or {}).items():
                    if fuel in skip or fuel in mean.get(g, {}):
                        continue
                    if mw >= 0.1:
                        dev.setdefault(g, {})[fuel] = round(mw, 1)
            d["out_dev_mw"] = dev or {}

    # observed daily hydro energy per grid (DIPCEF-derived), the water the
    # chronological LP may not exceed on that day
    hydro_note = None
    if fleet:
        from fuelmix import build_hydro_budgets
        hb = build_hydro_budgets(fleet, merit_hydro_mw)
        for d in days:
            d["hydro_budget_mwh"] = hb["days"].get(d["date"])
        hydro_note = {k: hb[k] for k in
                      ("n_days", "matched_cores", "suspects_mwh",
                       "budget_exceeds_modeled_capacity",
                       "excluded_note", "note")}

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
        "unit": "hourly mean per grid: demand MW (NATIVE LOAD: dispatched "
                "generation plus net market imports plus recorded "
                "curtailment, RTDSUM En rows), observed corridor flows MW "
                "(net_flow), observed LWAP PhP/kWh (LWAPF), and observed "
                "regional clearing price PhP/kWh (MCP) where archived",
        "note": "Observed days replayed as-is, no synthetic profiles. Demand "
                "is native load (generation + MKT_IMPORT - MKT_EXPORT + "
                "recorded curtailment): generation alone self-balances every "
                "grid and erases the observed inter-island flows, so the "
                "replay would never need the corridors the product is about. "
                "Days without full 24-hour demand coverage on all three "
                "grids are dropped, not filled. Each day also carries the "
                "observed corridor flows (net_flow), its scheduled-outage "
                "deviation from the market-window mean (out_dev_mw; hydro "
                "rides its water budget instead), its scheduled reserve "
                "requirement (reserve_req_mw), and, where archived, the "
                "hourly MCP.",
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
        "hydro_budget": hydro_note,
    }
