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
import random
import re

from build_data import REGION_MAP, dataset_files, day_of, f, rows_of
from constants_ph import DEMAND_ANCHORS, GENERATORS, MARKET_ANCHORS
from coupled_dispatch import CORRIDORS, clear_coupled
from fleet_ph import (
    COAL_COMMIT_PHP_KWH,
    COAL_MIN_LOAD_FRAC,
    FORCED_OUTAGE_RATE,
    FUEL_AVAIL,
    FUEL_CO2_T_PER_MWH,
    FUEL_COST_PHP_KWH,
    GRID_FUEL_MW,
    GRIDS,
    NATIONAL_FUEL_MW,
    STORAGE_MW,
    STORAGE_ROUND_TRIP_EFF,
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


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def build_coupling(intervals: dict, prices: dict) -> dict:
    """Couple the three grids over the market window and decompose the regional
    price spread the coupled model reproduces vs the residual it cannot.

    The honest finding, stated up front: with the STATIC fleet all three grids sit
    on the ~P6 coal margin most of the market window, so 250 MW of Luzon import
    slides Visayas back under its own coal ceiling and the Leyte-Luzon corridor
    almost never binds. The coupled model therefore reproduces almost none of the
    observed Visayas-Luzon spread on baseline demand: that spread is the scarcity /
    offer premium of the 52-day yellow-alert streak, which a cost model cannot see.
    What the coupling DOES show, under the documented ~935 MW Visayas outage, is the
    mechanism itself: the 250 MW corridor saturates and prices the islands apart by
    the congestion rent. That scenario is reported separately and never folded into
    the calibration.
    """
    resumed = MARKET_ANCHORS.get("wesm_resumed", "2026-05-01")
    grids = ["luzon", "visayas", "mindanao"]
    up = {g: g.upper() for g in grids}

    # base coupled clear over every market interval that has all three grids
    obs = {g: [] for g in grids}
    cpl = {g: [] for g in grids}
    unc = {g: [] for g in grids}  # uncapped counterfactual (corridors -> infinite)
    sat_count = {c["id"]: 0 for c in CORRIDORS}
    rent_sum = {c["id"]: 0.0 for c in CORRIDORS}
    flow_abs = {c["id"]: [] for c in CORRIDORS}
    n_coupled = 0
    big = {"leyte_luzon_hvdc": 1e6, "mvip_hvdc": 1e6}

    for (day, ti), iv in intervals.items():
        if not iv["market"] or len(iv["dem"]) < 3:
            continue
        pday = prices.get(day, {})
        op = {g: pday.get((up[g], ti)) for g in grids}
        if any(op[g] is None for g in grids):
            continue
        demand = {up[g]: iv["dem"][up[g]] for g in grids}
        res = clear_coupled(demand, iv["hour"])
        unc_res = clear_coupled(demand, iv["hour"], caps=big)
        n_coupled += 1
        for g in grids:
            obs[g].append(op[g])
            cpl[g].append(res["grids"][g]["price"])
            unc[g].append(unc_res["grids"][g]["price"])
        for c, cid in zip(res["corridors"], (x["id"] for x in CORRIDORS)):
            flow_abs[cid].append(abs(c["flow_mw"]))
            if c["saturated"]:
                sat_count[cid] += 1
                rent_sum[cid] += c["congestion_rent_php_kwh"]

    def spread(series: dict, a: str, b: str) -> float | None:
        ma, mb = _mean(series[a]), _mean(series[b])
        return round(ma - mb, 3) if ma is not None and mb is not None else None

    def explained(model_series: dict, hi: str, lo: str) -> dict:
        s_obs = spread(obs, hi, lo)
        s_mod = spread(model_series, hi, lo)
        frac = (round(s_mod / s_obs, 3)
                if s_obs not in (None, 0) and s_mod is not None else None)
        return {"observed_php_kwh": s_obs, "coupled_model_php_kwh": s_mod,
                "explained_fraction": frac}

    per_grid = {}
    for g in grids:
        o, m = obs[g], cpl[g]
        per_grid[g] = {
            "observed_mean_php_kwh": round(_mean(o), 3) if o else None,
            "coupled_modeled_mean_php_kwh": round(_mean(m), 3) if m else None,
            "mae_php_kwh": (round(sum(abs(a - b) for a, b in zip(m, o)) / len(o), 3)
                            if o else None),
            "correlation": _corr(m, o),
        }

    corridor_stats = []
    for c in CORRIDORS:
        cid = c["id"]
        fa = flow_abs[cid]
        corridor_stats.append({
            "id": cid, "name": c["name"], "limit_mw": c["limit_mw"],
            "limit_kind": c["limit_kind"], "nameplate_mw": c["nameplate_mw"],
            "src": c["src"],
            "saturated_pct": round(100 * sat_count[cid] / n_coupled, 1)
            if n_coupled else None,
            "mean_congestion_rent_php_kwh": round(rent_sum[cid] / sat_count[cid], 3)
            if sat_count[cid] else 0.0,
            "mean_abs_flow_mw": round(_mean(fa), 1) if fa else None,
            "peak_abs_flow_mw": round(max(fa), 1) if fa else None,
        })

    coupling = {
        "model": "inter-island coupled economic dispatch (radial 3-grid path over "
                 "the two HVDC corridors); still not PLEXOS",
        "wheeling_cost_php_kwh": 0.02,
        "calibration_window": {"regime": "market-only", "from": resumed},
        "n_coupled_intervals": n_coupled,
        "corridors": corridor_stats,
        "per_grid": per_grid,
        "spread_decomposition": {
            "note": "How much of the observed regional price spread the coupled "
                    "merit-order model reproduces from corridor limits alone. The "
                    "rest is scarcity and offer behaviour a cost model cannot price.",
            "visayas_vs_luzon": explained(cpl, "visayas", "luzon"),
            "mindanao_vs_luzon": explained(cpl, "mindanao", "luzon"),
            "uncapped_counterfactual": {
                "note": "Coupled spread if the corridors were infinite: what remains "
                        "is pure stack difference, not transmission.",
                "visayas_vs_luzon_php_kwh": spread(unc, "visayas", "luzon"),
                "mindanao_vs_luzon_php_kwh": spread(unc, "mindanao", "luzon"),
            },
        },
    }
    coupling["outage_scenario"] = _coupling_outage(intervals, prices)
    coupling["dc_binding_threshold"] = _coupling_binding_threshold(intervals)
    return coupling


def _coupling_outage(intervals: dict, prices: dict) -> dict:
    """Labelled scenario: re-clear the streak window with the documented Visayas
    outage applied. This is where the corridor binds and prices the islands apart
    endogenously. Kept OUT of the calibration; a scenario, not a fit."""
    frm = MARKET_ANCHORS.get("visayas_yellow_streak_from", "2026-05-11")
    to = MARKET_ANCHORS.get("visayas_yellow_streak_to", "2026-07-01")
    out_mw = MARKET_ANCHORS.get("visayas_unavailable_mw_jul1", 935.3)
    removed = {"VISAYAS": {"coal": out_mw}}
    grids = ["luzon", "visayas", "mindanao"]
    up = {g: g.upper() for g in grids}
    base_obs = {g: [] for g in grids}
    out_cpl = {g: [] for g in grids}
    sat = rent_sum = n = 0
    for (day, ti), iv in intervals.items():
        if not (frm <= day <= to) or len(iv["dem"]) < 3:
            continue
        pday = prices.get(day, {})
        op = {g: pday.get((up[g], ti)) for g in grids}
        if any(op[g] is None for g in grids):
            continue
        demand = {up[g]: iv["dem"][up[g]] for g in grids}
        res = clear_coupled(demand, iv["hour"], removed=removed)
        n += 1
        for g in grids:
            base_obs[g].append(op[g])
            out_cpl[g].append(res["grids"][g]["price"])
        leyte = res["corridors"][0]
        if leyte["saturated"]:
            sat += 1
            rent_sum += leyte["congestion_rent_php_kwh"]
    s_obs = (round(_mean(base_obs["visayas"]) - _mean(base_obs["luzon"]), 3)
             if n else None)
    s_mod = (round(_mean(out_cpl["visayas"]) - _mean(out_cpl["luzon"]), 3)
             if n else None)
    return {
        "label": "documented Visayas outage applied (NGCP: ~935 MW unavailable, "
                 "Jul 1 2026, during the 52-day yellow-alert streak)",
        "outage_mw": out_mw,
        "src": MARKET_ANCHORS.get("src_visayas_jul1"),
        "window": {"from": frm, "to": to},
        "n_intervals": n,
        "leyte_luzon_saturated_pct": round(100 * sat / n, 1) if n else None,
        "leyte_luzon_mean_rent_php_kwh": round(rent_sum / sat, 3) if sat else 0.0,
        "visayas_vs_luzon_observed_php_kwh": s_obs,
        "visayas_vs_luzon_coupled_php_kwh": s_mod,
        "explained_fraction": (round(s_mod / s_obs, 3)
                               if s_obs not in (None, 0) and s_mod is not None
                               else None),
    }


def _coupling_binding_threshold(intervals: dict) -> dict:
    """Forward lever, the DC-wave question the project exists to ask: at a typical
    evening, how much added flat load on Visayas makes the 250 MW Leyte-Luzon
    corridor bind (Visayas can no longer be relieved from Luzon)?"""
    eve = [iv["dem"] for iv in intervals.values()
           if iv["hour"] == PEAK_HOUR and len(iv["dem"]) >= 3]
    if not eve:
        return {"available": False}
    base = {g: round(sum(d[g] for d in eve) / len(eve)) for g in
            ("LUZON", "VISAYAS", "MINDANAO")}
    thr = None
    for add in range(0, 3001, 25):
        demand = dict(base)
        demand["VISAYAS"] = base["VISAYAS"] + add
        res = clear_coupled(demand, PEAK_HOUR)
        if res["corridors"][0]["saturated"]:
            thr = add
            break
    return {
        "available": True,
        "reference_hour": PEAK_HOUR,
        "typical_evening_demand_mw": {g.lower(): base[g] for g in base},
        "added_visayas_load_to_bind_leyte_mw": thr,
        "note": "Extra flat Visayas load at a typical evening before the 250 MW "
                "Leyte-Luzon corridor saturates and Visayas prices above Luzon. "
                "The corridor binds well below the DICT 1.5 GW national forecast.",
    }


def _pctl(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    i = min(len(sorted_vals) - 1, int(p * len(sorted_vals)))
    return sorted_vals[i]


def _named_outage_model():
    """Per named unit: running capacity when up (so E[contribution] = the unit's
    deterministic derated MW) and the deterministic derated MW; plus each grid's
    named list and deterministic named total."""
    named = {g: [u for u in GENERATORS if u["grid"] == g] for g in GRIDS}
    run_cap, det_cap = {}, {}
    for g in GRIDS:
        for u in named[g]:
            fa = FUEL_AVAIL.get(u["fuel"], 1.0)
            fr = FORCED_OUTAGE_RATE.get(u["fuel"], 0.0)
            det_cap[u["name"]] = u["capacity_mw"] * fa
            run_cap[u["name"]] = u["capacity_mw"] * fa / (1 - fr) if fr < 1 else 0.0
    det_named = {g: sum(det_cap[u["name"]] for u in named[g]) for g in GRIDS}
    return named, run_cap, det_named


def _mc_distribution(rng, loads, base_eve, det_named_g, units, run_cap, draws):
    """One snapshot Monte Carlo: each draw trips the units (Bernoulli at their
    forced-outage rate) and samples a tight-hour load; returns the shortfall
    distribution and loss-of-load probability."""
    shorts = []
    n_short = 0
    for _ in range(draws):
        contrib = sum(run_cap[u["name"]] for u in units
                      if rng.random() >= FORCED_OUTAGE_RATE.get(u["fuel"], 0.0))
        avail = base_eve + (contrib - det_named_g)
        sf = rng.choice(loads) - avail
        if sf > 0:
            shorts.append(sf)
            n_short += 1
        else:
            shorts.append(0.0)
    shorts.sort()
    exp_sf = sum(shorts) / draws
    return {
        "lolp_pct": round(100 * n_short / draws, 2),
        "expected_shortfall_mw": round(exp_sf, 1),
        "shortfall_mw_p50": round(_pctl(shorts, 0.50), 1),
        "shortfall_mw_p90": round(_pctl(shorts, 0.90), 1),
        "shortfall_mw_p99": round(_pctl(shorts, 0.99), 1),
        "shortfall_mw_max": round(shorts[-1], 1),
        "eue_mwh_evening_window": round(exp_sf * len(loads) * 5 / 60, 1),
    }


def _eve_capacity_and_load(hourly_dem: dict):
    """Evening-peak available capacity (hour 19, solar ~ 0) and the tight-hour
    (18-21) load pool per grid."""
    eve_avail = {g: round(sum(b["mw"] for b in stack(g, PEAK_HOUR)), 1) for g in GRIDS}
    eve_load = {g: [d for h in range(18, 22) for d in hourly_dem[g][h]] for g in GRIDS}
    return eve_avail, eve_load


def build_reliability_mc(hourly_dem: dict, draws: int = 20000, seed: int = 42) -> dict:
    """Monte Carlo forced-outage reliability: the deterministic LOLE/EUE is a point,
    this is a distribution. Each draw is one independent tight-hour realisation: it
    samples the 11 named large units as up or forced-out (Bernoulli at the sourced
    per-fuel rate), then samples one evening-peak load (hours 18-21, when solar is
    gone and the risk sits), and takes the shortfall. Over the draws that gives a
    loss-of-load probability (share of tight intervals that go short) and the
    distribution of shortfall size. Still not PLEXOS: only the named contingency
    drivers are sampled, and the mean available capacity is pinned to the
    deterministic model so the outages add variance, not a lower mean. Snapshot
    draws, so no single outage is frozen across the window.
    """
    rng = random.Random(seed)
    named, run_cap, det_named = _named_outage_model()
    eve_avail, eve_load = _eve_capacity_and_load(hourly_dem)

    def run(loads, base_eve, g):
        return _mc_distribution(rng, loads, base_eve, det_named[g], named[g],
                                run_cap, draws)

    per_grid = {g.lower(): run(eve_load[g], eve_avail[g], g) for g in GRIDS}
    dict_dist = run([d + 1500 for d in eve_load["LUZON"]], eve_avail["LUZON"], "LUZON")

    return {
        "method": "Monte Carlo forced outages on the 11 named large units (Bernoulli "
                  "at the sourced per-fuel rate) vs a sampled evening-peak load; "
                  "snapshot draws give a loss-of-load probability and a shortfall "
                  "distribution, not a point. Still not PLEXOS.",
        "draws": draws,
        "seed": seed,
        "load_hours": "18-21 (evening peak, solar ~ 0)",
        "forced_outage_rates": FORCED_OUTAGE_RATE,
        "src_for": "https://www.nerc.com/programs/reliability-assessment--performance-analysis/generating-availability-data-system/gads-conventional/general-availability-review-weighted-efor-dashboard",
        "note": "Coal (~10%) and gas (~5%) forced-outage rates are from NERC GADS; "
                "hydro, geothermal, oil, and biomass are labeled industry-typical "
                "values. Only the named units are sampled; the rest of the fleet is "
                "held at its deterministic availability, so the mean is unchanged and "
                "the draws add the outage variance.",
        "per_grid": per_grid,
        "dict_2028_luzon": {
            "added_mw": 1500, "owner": "DICT", "date": "2025-10",
            "src": "https://www.bworldonline.com/corporate/2025/10/23/707346/",
            "distribution": dict_dist,
        },
    }


def build_storage(hourly_dem: dict, draws: int = 20000, seed: int = 42) -> dict:
    """Storage as a peak-firming time-shifter (item 4). Batteries and Kalayaan
    pumped hydro charge off-peak and discharge at the evening peak. Two honest
    questions: how much does the existing 634 MW of batteries plus 685 MW of pumped
    hydro shave the DICT-wave peak price, and how much of the DC-wave loss-of-load
    probability does it buy back. Existing storage is already in the observed prices,
    so this is a forward scenario against the modeled DC wave, not a calibration
    change. Energy is limited (BESS ~1-4h, pumped hydro longer): it firms the peak
    interval, not a multi-day event.
    """
    lz = STORAGE_MW["LUZON"]
    storage_mw = lz["bess"] + lz["pumped_hydro"]
    disc = round(COAL_COMMIT_PHP_KWH / STORAGE_ROUND_TRIP_EFF, 2)

    # peak price under the DICT wave, with and without the storage discharge block,
    # at a TIGHT (95th-percentile) evening where the grid is on the oil margin and
    # storage can actually shave it. At a typical evening Luzon is still on coal and
    # storage does not move the price, which we would be over-claiming to show.
    eve_luzon = sorted(hourly_dem["LUZON"][PEAK_HOUR])
    p95_eve = eve_luzon[min(len(eve_luzon) - 1, int(0.95 * len(eve_luzon)))] \
        if eve_luzon else 0
    dc_demand = round(p95_eve + 1500)
    base = stack("LUZON", PEAK_HOUR)
    with_stor = base + [{"fuel": "storage", "cost": disc, "mw": storage_mw}]
    price_without = clear(base, dc_demand)
    price_with = clear(with_stor, dc_demand)

    # reliability buy-back: rerun the MC with storage added to evening capacity
    rng = random.Random(seed)
    named, run_cap, det_named = _named_outage_model()
    eve_avail, eve_load = _eve_capacity_and_load(hourly_dem)

    def dist(loads, base_eve, g):
        return _mc_distribution(rng, loads, base_eve, det_named[g], named[g],
                                run_cap, draws)

    lz_base_load = eve_load["LUZON"]
    lz_dict_load = [d + 1500 for d in lz_base_load]
    av = eve_avail["LUZON"]
    return {
        "assets": {
            "luzon": {"bess_mw": lz["bess"], "pumped_hydro_mw": lz["pumped_hydro"],
                      "total_mw": storage_mw},
        },
        "round_trip_eff": STORAGE_ROUND_TRIP_EFF,
        "discharge_offer_php_kwh": disc,
        "src_bess": "https://legacy.doe.gov.ph/electric-power/list-existing-power-plants-march-2025",
        "src_pumped_hydro": "http://www.cbkpower.com/project/kalayaan-pumped-storage-power-plant-kpspp/",
        "note": "Batteries (634 MW, DOE) plus Kalayaan pumped hydro (685 MW, CBK "
                "Power), both on Luzon (the national BESS placed on Luzon is a "
                "labeled simplification). They charge off-peak near the P4.14 "
                "commitment offer and discharge at about P" + f"{disc:.2f}" + "/kWh "
                "after round-trip loss. Energy-limited, so this firms the evening "
                "peak interval, not a sustained multi-day shortfall.",
        "dict_wave_peak_price": {
            "reference": "95th-percentile evening demand plus the DICT 1.5 GW wave",
            "demand_mw": dc_demand,
            "without_storage_php_kwh": price_without["price"],
            "with_storage_php_kwh": price_with["price"],
            "without_storage_marginal_fuel": price_without["marginal_fuel"],
            "with_storage_marginal_fuel": price_with["marginal_fuel"],
            "shortfall_without_mw": price_without["shortfall_mw"],
            "shortfall_with_mw": price_with["shortfall_mw"],
        },
        "reliability_buyback": {
            "luzon_baseline": {
                "lolp_without_pct": dist(lz_base_load, av, "LUZON")["lolp_pct"],
                "lolp_with_pct": dist(lz_base_load, av + storage_mw, "LUZON")["lolp_pct"],
            },
            "luzon_dict_2028": {
                "without": dist(lz_dict_load, av, "LUZON"),
                "with_storage": dist(lz_dict_load, av + storage_mw, "LUZON"),
            },
        },
    }


def build_dispatch() -> dict:
    prices = _read_prices()
    rtd = dataset_files("RTDSUM")
    if not rtd or not prices:
        return {"available": False,
                "note": "RTDSUM or LWAPF absent; dispatch model omitted"}

    # cache one stack per (grid, hour) so we clear cheaply over many intervals. The
    # `nc` cache is the static (no unit-commitment) stack, for the before/after.
    stack_cache: dict[tuple, list[dict]] = {}
    stack_cache_nc: dict[tuple, list[dict]] = {}

    def stk(grid: str, hour: int) -> list[dict]:
        key = (grid, hour)
        if key not in stack_cache:
            stack_cache[key] = stack(grid, hour)
        return stack_cache[key]

    def stk_nc(grid: str, hour: int) -> list[dict]:
        key = (grid, hour)
        if key not in stack_cache_nc:
            stack_cache_nc[key] = stack(grid, hour, commitment=False)
        return stack_cache_nc[key]

    obs: dict[str, list[float]] = {g: [] for g in GRIDS}
    mod: dict[str, list[float]] = {g: [] for g in GRIDS}
    mod_nc: dict[str, list[float]] = {g: [] for g in GRIDS}
    peak_demand: dict[str, float] = {g: 0.0 for g in GRIDS}
    demands: dict[str, list[float]] = {g: [] for g in GRIDS}
    fuel_mwh: dict[str, dict[str, float]] = {g: {} for g in GRIDS}
    lole_intervals: dict[str, int] = {g: 0 for g in GRIDS}
    eue_mwh: dict[str, float] = {g: 0.0 for g in GRIDS}
    # hourly accumulation for the representative curves (mean over the window)
    hourly: dict[str, dict[int, list]] = {g: {h: [] for h in range(24)}
                                          for g in GRIDS}
    # per-hour demand over ALL intervals (physical, whole window) for the Monte
    # Carlo reliability model, which is about capacity adequacy not market price
    hourly_dem: dict[str, dict[int, list]] = {g: {h: [] for h in range(24)}
                                              for g in GRIDS}
    days_seen: set[str] = set()
    # per-interval simultaneous demand across all three grids, for the coupled model
    intervals: dict[tuple, dict] = {}

    # WESM was suspended (administered prices) through wesm_resumed; the price
    # calibration must be MARKET-window only, or an administered ~P6 evening sits
    # on the modeled coal line and flatters the fit. Demand-based metrics (peak,
    # adequacy, N-1, emissions) are physical and use the whole window.
    resumed = MARKET_ANCHORS.get("wesm_resumed", "2026-05-01")
    market_days: set[str] = set()

    for path in rtd:
        day = day_of(path)
        pday = prices.get(day, {})
        if not pday:
            continue
        days_seen.add(day)
        is_market = day >= resumed
        if is_market:
            market_days.add(day)
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
            iv = intervals.setdefault((day, ti),
                                      {"hour": hour, "market": is_market, "dem": {}})
            iv["dem"][grid] = gen
            blocks = stk(grid, hour)
            res = clear(blocks, gen)
            peak_demand[grid] = max(peak_demand[grid], gen)
            demands[grid].append(gen)
            hourly_dem[grid][hour].append(gen)
            if res["shortfall_mw"] > 0:
                lole_intervals[grid] += 1
                eue_mwh[grid] += res["shortfall_mw"] * 5 / 60
            for fuel, mw in _fuel_dispatch(blocks, res["served_mw"]).items():
                fuel_mwh[grid][fuel] = fuel_mwh[grid].get(fuel, 0.0) + mw * 5 / 60
            price = pday.get((grid, ti))
            if price is not None and is_market:
                obs[grid].append(price)
                mod[grid].append(res["price"])
                mod_nc[grid].append(clear(stk_nc(grid, hour), gen)["price"])
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

    # before/after the unit-commitment layer, reported honestly (not tuned). The
    # committed must-run coal tranche lowers the modeled overnight price; whether it
    # cuts MAE and lifts correlation is measured, per grid, against the static stack.
    unit_commitment = {
        "layer": "must-run committed coal (min stable load "
                 f"{int(COAL_MIN_LOAD_FRAC * 100)}% of available coal offered at "
                 f"P{COAL_COMMIT_PHP_KWH:.2f}/kWh, below the P6.00 administered "
                 "price); cycling coal stays at P6.00",
        "min_load_frac": COAL_MIN_LOAD_FRAC,
        "commit_offer_php_kwh": COAL_COMMIT_PHP_KWH,
        "src_min_load": "https://powerline.net.in/2023/04/04/flexibilisation-roadmap-aiming-for-tpps-to-operate-at-40-per-cent-minimum-technical-load/",
        "src_offer": "https://www.philstar.com/business/2026/01/05/2498730/wesm-prices-hit-fresh-lows-2025",
        "note": "The commitment offer is anchored on the observed H1 2025 WESM "
                "average (P4.14/kWh), not fitted to the overnight trough. Where the "
                "grid's overnight demand still exceeds the committed tranche the "
                "modeled price does not move, and that gap stays in the residual.",
        "per_grid": {},
    }
    for g in GRIDS:
        o, m, mnc = obs[g], mod[g], mod_nc[g]
        if not o:
            continue
        mae = lambda s: round(sum(abs(a - b) for a, b in zip(s, o)) / len(o), 3)  # noqa: E731, B023
        unit_commitment["per_grid"][g.lower()] = {
            "mae_before_php_kwh": mae(mnc),
            "mae_after_php_kwh": mae(m),
            "correlation_before": _corr(mnc, o),
            "correlation_after": _corr(m, o),
            "modeled_mean_before_php_kwh": round(sum(mnc) / len(mnc), 3),
            "modeled_mean_after_php_kwh": round(sum(m) / len(m), 3),
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

    # merit-order stack for the Simulate panel (reference = evening peak hour). The
    # panel's baseline demand is the TYPICAL evening peak (mean demand at hour 19),
    # not the annual maximum: at the annual max Luzon already clears on oil, so the
    # levers only move shortfall; at a typical evening the grid is on the coal margin
    # and a lever visibly flips the price from coal to oil.
    merit_order = {}
    for g in GRIDS:
        blocks = stack(g, PEAK_HOUR)
        eve = hourly[g][PEAK_HOUR]
        typical = round(sum(p[0] for p in eve) / len(eve)) if eve else 0
        merit_order[g.lower()] = {
            "reference_hour": PEAK_HOUR,
            "installed_mw": sum(GRID_FUEL_MW[g].values()),
            "avail_mw": round(sum(b["mw"] for b in blocks), 1),
            "typical_evening_demand_mw": typical,
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

    coupling = build_coupling(intervals, prices)
    reliability_mc = build_reliability_mc(hourly_dem)
    storage = build_storage(hourly_dem)

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
        "calibration_window": {
            "regime": "market-only",
            "from": resumed,
            "days": len(market_days),
            "note": "Calibration, representative day, and the panel baseline use only "
                    "the market-priced window (WESM resumed " + resumed + "); the "
                    "suspension's administered prices are excluded. Demand-based "
                    "metrics (peak, adequacy, N-1, emissions) use the whole window.",
        },
        "merit_order": merit_order,
        "coupling": coupling,
        "unit_commitment": unit_commitment,
        "calibration": calibration,
        "representative_day": representative,
        "n1": n1,
        "adequacy": adequacy,
        "reliability": reliability,
        "reliability_mc": reliability_mc,
        "storage": storage,
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
