#!/usr/bin/env python3
"""Chronological dispatch reference engine (the Python side of the parity pair).

The studio's chronological run (studio/src/studio/chrono.ts) replays an observed
day hour by hour: rebuild each grid's stack for the hour (solar follows the 24-hour
shape, everything else holds its derated availability), clear the three grids
coupled over the HVDC corridors, and cycle storage with a labeled charge-cheap /
discharge-dear heuristic. This module is the SAME loop in Python, consuming the
same baked inputs, and build_chrono_golden() emits input/output pairs the studio
test must reproduce (the parity harness, exactly like dispatch.scenario_golden).

Still NOT PLEXOS: block dispatch per hour, no inter-temporal optimisation. The
storage policy is a two-pass heuristic (quartile thresholds from a first pass
without storage), stated as such wherever it surfaces.

build_backcast() replays every market day with the BASE model (no storage cycling,
no levers) against the observed hourly LWAP and reports MAE / bias / correlation /
high-hour hit rate. No tuning: the residual is the finding.
"""
from __future__ import annotations

import json
import math
import os

from fleet_ph import WESM_OFFER_CAP_PHP_KWH

OIL_FALLBACK = 12.0
GRID_KEYS = ["luzon", "visayas", "mindanao"]
# outputs and epsilons mirror studio/src/studio/chrono.ts exactly; a change on
# either side must land on both, or the parity test fails (that is the point)
EPS_SOC = 1e-9


def _round(x: float, n: int) -> float:
    # JS Math.round semantics (half toward +infinity), not banker's rounding
    p = 10.0 ** n
    return math.floor(x * p + 0.5) / p


def round1(x: float) -> float:
    return _round(x, 1)


def round3(x: float) -> float:
    return _round(x, 3)


def floor1(x: float) -> float:
    # storage schedule values round DOWN so a cycle can never discharge more
    # than it stored or charge past the energy cap (round-half-up could do both)
    return math.floor(x * 10) / 10


# ---- stack + coupled clear over given stacks (mirrors engine.ts) --------------

def build_stack(fuel_avail: dict, removed: dict, added: list[dict],
                p: dict) -> list[dict]:
    blocks: list[dict] = []
    for fuel, avail in fuel_avail.items():
        mw = (avail or 0.0) - (removed.get(fuel) or 0.0)
        if mw <= 0:
            continue
        if fuel == "coal":
            must_run = round1(mw * p["coal_min_frac"])
            blocks.append({"fuel": "coal", "cost": p["coal_commit"],
                           "mw": must_run})
            blocks.append({"fuel": "coal", "cost": p["coal_price"],
                           "mw": round1(mw - must_run)})
        else:
            blocks.append({"fuel": fuel, "cost": p["costs"].get(fuel, 0.0),
                           "mw": round1(mw)})
    for b in added:
        if b["mw"] > 0:
            blocks.append(dict(b))
    blocks.sort(key=lambda b: b["cost"])
    return blocks


def marginal(blocks: list[dict], g: float) -> tuple[float, str | None]:
    """Marginal cost and fuel serving the g-th MW; beyond the stack the hour
    is short and prices at the sourced WESM offer cap, so the heuristic
    clear values serving exactly as the LP's shedding penalty does and the
    cost-dominance oracle keeps comparing the same problem."""
    if not blocks:
        return OIL_FALLBACK, None
    if g <= 0:
        return blocks[0]["cost"], blocks[0]["fuel"]
    cum = 0.0
    for b in blocks:
        cum += b["mw"]
        if cum >= g:
            return b["cost"], b["fuel"]
    return WESM_OFFER_CAP_PHP_KWH, "shortage"


def _root_decr(phi, lo: float, hi: float, target: float) -> float:
    i = 0
    while i < 40 and hi - lo > 0.25:
        mid = (lo + hi) / 2
        if phi(mid) > target:
            lo = mid
        else:
            hi = mid
        i += 1
    return (lo + hi) / 2


def _opt_flow(phi, lo: float, hi: float, wheel: float) -> float:
    if hi <= lo:
        return lo
    zero = min(max(0.0, lo), hi)
    p0 = phi(zero)
    if p0 > wheel:
        return hi if phi(hi) >= wheel else _root_decr(phi, zero, hi, wheel)
    if p0 < -wheel:
        return lo if phi(lo) <= -wheel else _root_decr(phi, lo, zero, -wheel)
    return zero


def clear_coupled_stacks(demand: dict, stacks: dict, caps: dict,
                         wheel: float) -> dict:
    dL, dV, dM = demand["luzon"], demand["visayas"], demand["mindanao"]
    bL, bV, bM = stacks["luzon"], stacks["visayas"], stacks["mindanao"]
    c1, c2 = caps["leyte"], caps["mvip"]

    def mcL(f1):
        return marginal(bL, dL + f1)[0]

    def mcV(f1, f2):
        return marginal(bV, dV + f2 - f1)[0]

    def mcM(f2):
        return marginal(bM, dM - f2)[0]

    f1 = f2 = 0.0
    for _ in range(60):
        lo = max(-c1, -dL)
        hi = min(c1, dV + f2)
        nf1 = _opt_flow(lambda x, f2=f2: mcV(x, f2) - mcL(x), lo, hi, wheel)
        lo2 = max(-c2, nf1 - dV)
        hi2 = min(c2, dM)
        nf2 = _opt_flow(lambda x, nf1=nf1: mcM(x) - mcV(nf1, x), lo2, hi2,
                        wheel)
        if abs(nf1 - f1) + abs(nf2 - f2) < 0.25:
            f1, f2 = nf1, nf2
            break
        f1, f2 = nf1, nf2

    gen = {"luzon": dL + f1, "visayas": dV + f2 - f1, "mindanao": dM - f2}
    avail = {g: sum(b["mw"] for b in stacks[g]) for g in GRID_KEYS}
    price = {g: round3(marginal(stacks[g], gen[g])[0]) for g in GRID_KEYS}
    marg = {g: marginal(stacks[g], gen[g])[1] for g in GRID_KEYS}
    shortfall = {g: max(0.0, round1(gen[g] - avail[g])) for g in GRID_KEYS}
    eps = 0.5
    sat1 = abs(f1) >= c1 - eps
    sat2 = abs(f2) >= c2 - eps
    rent1 = (round3(price["visayas"] - price["luzon"] if f1 > 0
                    else price["luzon"] - price["visayas"]) if sat1 else 0.0)
    rent2 = (round3(price["mindanao"] - price["visayas"] if f2 > 0
                    else price["visayas"] - price["mindanao"]) if sat2 else 0.0)
    return {"price": price, "marginal": marg, "shortfall": shortfall,
            "gen": gen, "flow_lv": round1(f1), "flow_vm": round1(f2),
            "leyte": {"sat": sat1, "rent": rent1},
            "mvip": {"sat": sat2, "rent": rent2}}


def _pctl_low(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    return sorted_vals[math.floor(q * (len(sorted_vals) - 1))]


def _fuel_dispatch(blocks: list[dict], served: float) -> dict:
    out: dict[str, float] = {}
    remaining = served
    for b in blocks:  # already cost-sorted
        if remaining <= 0:
            break
        take = min(b["mw"], remaining)
        out[b["fuel"]] = round1(out.get(b["fuel"], 0.0) + take)
        remaining -= take
    return out


# ---- the chronological run -----------------------------------------------------

def run_chronology(dispatch: dict, profiles: dict, date: str,
                   opts: dict | None = None) -> dict:
    """Replay one observed day, hour by hour, on the (optionally edited) model.

    opts (all optional, defaults = the base model):
      demand_delta:     {grid: MW} flat 24/7 load added per grid
      solar_delta_mw:   {grid: MW} installed solar added (follows the 24h shape)
      fuel_avail_delta: {grid: {fuel: MW}} availability change (a trip is negative)
      fuel_cost:        {fuel: PhP/kWh} cost overrides (LNG switch, coal price)
      hydrology:        multiplier on hydro availability
      caps:             {leyte, mvip} corridor limits (MW)
      storage:          [{grid, power_mw, energy_mwh}] cycled by the heuristic
      reserve_deduction: True prices each hour at demand + scheduled reserve
    """
    opts = opts or {}
    day = next(d for d in profiles["days"] if d["date"] == date)
    a = dispatch["assumptions"]
    wheel = a["wheeling_cost_php_kwh"]
    costs = dict(a["fuel_marginal_cost_php_kwh"])
    costs.update(opts.get("fuel_cost") or {})
    params = {"coal_commit": a["coal_commit_php_kwh"],
              "coal_min_frac": a["coal_min_load_frac"],
              "coal_price": costs["coal"], "costs": costs}
    hyd = opts.get("hydrology", 1.0)
    solar_profile = profiles["solar_profile"]
    caps = {"leyte": 250.0, "mvip": 450.0}
    for c in dispatch["coupling"]["corridors"]:
        key = "leyte" if c["id"] == "leyte_luzon_hvdc" else "mvip"
        caps[key] = c["limit_mw"]
    caps.update(opts.get("caps") or {})
    # observed HVDC blocks scale the hour's limit, exactly as in
    # lp_dispatch._assemble: the retired clear must keep solving the SAME
    # problem to stay a valid cross-oracle
    cc = day.get("corridor_caps") or {}
    for key in ("leyte", "mvip"):
        frac = cc.get(key)
        if frac:
            caps[key] = [round1(caps[key] * frac[h]) for h in range(24)]

    fuel_base: dict[str, dict[str, float]] = {}
    solar_inst: dict[str, float] = {}
    out_dev = day.get("out_dev_mw") or {}
    for g in GRID_KEYS:
        mo = dispatch["merit_order"][g]
        fa = dict(mo["fuel_avail_mw"])
        if hyd != 1.0 and fa.get("hydro") is not None:
            fa["hydro"] = round1(fa["hydro"] * hyd)
        # same day-outage deviation the LP engine applies (_assemble); the
        # retired clear must keep solving the SAME problem to stay a valid
        # cross-oracle for the cost-dominance test
        for fuel, dev in (out_dev.get(g) or {}).items():
            if fa.get(fuel) is not None:
                fa[fuel] = max(0.0, round1(fa[fuel] - dev))
        for fuel, delta in ((opts.get("fuel_avail_delta") or {})
                            .get(g) or {}).items():
            fa[fuel] = max(0.0, round1((fa.get(fuel) or 0.0) + delta))
        fuel_base[g] = fa
        solar_inst[g] = (mo["solar_installed_mw"]
                         + ((opts.get("solar_delta_mw") or {}).get(g) or 0.0))

    reserve_add = {g: 0.0 for g in GRID_KEYS}
    if opts.get("reserve_deduction"):
        day_req = day.get("reserve_req_mw") or {}
        mean_req = profiles.get("reserve_req_mean_mw") or {}
        for g in GRID_KEYS:
            reserve_add[g] = round1(sum(
                (day_req.get(g) or mean_req.get(g) or {}).values()))

    def fuel_avail_at(g: str, h: int) -> dict:
        fa = dict(fuel_base[g])
        solar = round1(max(0.0, solar_inst[g]) * solar_profile[h])
        fa["solar"] = solar
        return fa

    def demand_at(h: int) -> dict:
        return {g: (day["demand"][g][h]
                    + ((opts.get("demand_delta") or {}).get(g) or 0.0)
                    + reserve_add[g])
                for g in GRID_KEYS}

    hours = list(range(24))

    def clear_hour(h: int, extra_demand: dict | None = None,
                   added: dict | None = None) -> dict:
        dem = demand_at(h)
        if extra_demand:
            for g, v in extra_demand.items():
                dem[g] = dem[g] + v
        stacks = {g: build_stack(fuel_avail_at(g, h), {},
                                 (added or {}).get(g) or [], params)
                  for g in GRID_KEYS}
        caps_h = {k: (v[h] if isinstance(v, list) else v)
                  for k, v in caps.items()}
        res = clear_coupled_stacks(dem, stacks, caps_h, wheel)
        res["stacks"] = stacks
        res["demand"] = dem
        return res

    # pass 1: no storage, gives the price shape the heuristic reads
    pass1 = [clear_hour(h) for h in hours]

    # storage policy: rank the day's hours by (pass-1 price, demand, hour) on the
    # store's grid; charge in the cheapest hours, discharge in the dearest, walked
    # chronologically through the SoC state. Demand breaks the ties a flat cost
    # plateau leaves (charging lands overnight, discharge at the evening peak).
    # A labeled heuristic, not an optimisation.
    stores = []
    eff = profiles.get("storage_round_trip_eff", 0.8)
    offer = dispatch["storage"]["discharge_offer_php_kwh"]
    for s in opts.get("storage") or []:
        g = s["grid"]
        power, energy = s["power_mw"], s["energy_mwh"]
        if power <= 0 or energy <= 0:
            continue
        order = sorted(hours, key=lambda h, g=g: (
            pass1[h]["price"][g], pass1[h]["demand"][g], h))
        n_charge = min(24, math.ceil(energy / (power * eff)))
        n_dis = min(24 - n_charge, math.ceil(energy / power))
        charge_set = set(order[:n_charge])
        dis_set = set(order[len(order) - n_dis:]) - charge_set
        soc = 0.0
        charge = [0.0] * 24
        discharge = [0.0] * 24
        soc_series = [0.0] * 24
        for h in hours:
            if h in charge_set and soc < energy - EPS_SOC:
                charge[h] = floor1(min(power, (energy - soc) / eff))
                soc += charge[h] * eff
            elif h in dis_set and soc > EPS_SOC:
                discharge[h] = floor1(min(power, soc))
                soc -= discharge[h]
            soc_series[h] = round1(soc)
        stores.append({"grid": g, "charge": charge, "discharge": discharge,
                       "soc": soc_series})

    # pass 2: charge as extra demand, discharge as a storage block
    out_hours = []
    for h in hours:
        if stores:
            extra = {g: 0.0 for g in GRID_KEYS}
            added: dict[str, list[dict]] = {g: [] for g in GRID_KEYS}
            for s in stores:
                extra[s["grid"]] += s["charge"][h]
                if s["discharge"][h] > 0:
                    added[s["grid"]].append({"fuel": "storage", "cost": offer,
                                             "mw": s["discharge"][h]})
            res = clear_hour(h, extra, added)
        else:
            res = pass1[h]
        out_hours.append({
            "hour": h,
            "price": res["price"],
            "marginal": res["marginal"],
            "demand": {g: round1(res["demand"][g]) for g in GRID_KEYS},
            "shortfall": res["shortfall"],
            "flow_lv": res["flow_lv"],
            "flow_vm": res["flow_vm"],
            "leyte": res["leyte"],
            "mvip": res["mvip"],
            "fuel_gen": {g: _fuel_dispatch(
                res["stacks"][g],
                min(res["gen"][g], sum(b["mw"] for b in res["stacks"][g])))
                for g in GRID_KEYS},
            "soc_mwh": round1(sum(s["soc"][h] for s in stores)),
            "charge_mw": round1(sum(s["charge"][h] for s in stores)),
            "discharge_mw": round1(sum(s["discharge"][h] for s in stores)),
        })

    def rent_m_php(key: str, flow_key: str) -> float:
        total = 0.0
        for o in out_hours:
            if o[key]["sat"]:
                total += abs(o[flow_key]) * o[key]["rent"] / 1000.0
        return round3(total)

    summary = {
        "date": date,
        "mean_price": {g: round3(sum(o["price"][g] for o in out_hours) / 24)
                       for g in GRID_KEYS},
        "peak_price": {g: max(o["price"][g] for o in out_hours)
                       for g in GRID_KEYS},
        "unserved_mwh": {g: round1(sum(o["shortfall"][g] for o in out_hours))
                         for g in GRID_KEYS},
        "leyte_rent_m_php": rent_m_php("leyte", "flow_lv"),
        "mvip_rent_m_php": rent_m_php("mvip", "flow_vm"),
    }
    return {"hours": out_hours, "summary": summary}


# ---- golden fixtures (the parity harness) ---------------------------------------

def build_chrono_golden(dispatch: dict, profiles: dict) -> dict:
    date = profiles.get("default_day")
    if not date:
        return {"available": False,
                "note": "no full-coverage market day in the archive window"}
    stor = profiles["storage_defaults"]
    default_storage = [{"grid": s["grid"], "power_mw": s["power_mw"],
                        "energy_mwh": s["energy_mwh"]} for s in stor]
    lng = dispatch["assumptions"]["fuel_marginal_cost_php_kwh"].get("lng")
    dry = dispatch["assumptions"]["hydrology"]["dry_multiplier"]
    cases = [
        {"label": "base day, no storage", "opts": {}},
        {"label": "DICT 1.5 GW flat load on Luzon",
         "opts": {"demand_delta": {"luzon": 1500}}},
        {"label": "storage idles when the day is flat (2 GW solar + 1 GW / "
                  "2 GWh on Luzon)",
         "opts": {"solar_delta_mw": {"luzon": 2000},
                  "storage": [{"grid": "luzon", "power_mw": 1000,
                               "energy_mwh": 2000}]}},
        {"label": "LNG switch + El Nino dry hydro",
         "opts": {"fuel_cost": {"natural_gas": lng}, "hydrology": dry}},
        {"label": "both Sual units out all day",
         "opts": {"fuel_avail_delta": {"luzon": {"coal": -1294}}}},
        {"label": "default storage cycles against the DICT wave",
         "opts": {"demand_delta": {"luzon": 1500},
                  "storage": default_storage}},
        # pins the day-level reserve requirement path (and its per-grid
        # fallback semantics) across both engines
        {"label": "reserve withheld at the day's scheduled requirement",
         "opts": {"reserve_deduction": True}},
        # pins the day-level gas fuel-energy budget (Malampaya) across engines
        {"label": "Malampaya gas budget on Luzon",
         "opts": {"gas_budget": {"luzon": 40000}}},
    ]
    # pin the OFFER-MODE replay when the default day has a derived book:
    # the stored input carries only the marker; both engines load the same
    # per-day artifact (web/data/offers/) and must build identical text
    here = os.path.dirname(os.path.abspath(__file__))
    offer_path = os.path.join(here, "..", "data", "derived", "offer_daily",
                              f"OFFERD_{date.replace('-', '')}.json")
    offer_day = None
    if os.path.isfile(offer_path):
        with open(offer_path) as fh:
            offer_day = json.load(fh)
        cases.append({"label": "observed offer book, no levers",
                      "opts": {"offer_mode": True}})
        cases.append({"label": "DICT 1.5 GW on the observed offer book",
                      "opts": {"offer_mode": True,
                               "demand_delta": {"luzon": 1500}}})
        cases.append({"label": "reserve withheld from the observed book",
                      "opts": {"offer_mode": True,
                               "reserve_deduction": True}})
    from lp_dispatch import run_chronology_lp

    out = []
    for c in cases:
        run_opts = dict(c["opts"])
        if run_opts.pop("offer_mode", False):
            run_opts["offer_day"] = offer_day
        res = run_chronology_lp(dispatch, profiles, date, run_opts)
        out.append({
            "label": c["label"],
            "input": {"date": date, **c["opts"]},
            "lp_sha256": res["lp_sha256"],
            "expect": {
                "price": {g: [o["price"][g] for o in res["hours"]]
                          for g in GRID_KEYS},
                "flow_lv": [o["flow_lv"] for o in res["hours"]],
                "flow_vm": [o["flow_vm"] for o in res["hours"]],
                "soc_mwh": [o["soc_mwh"] for o in res["hours"]],
                "shortfall_luzon": [o["shortfall"]["luzon"]
                                    for o in res["hours"]],
                # exact label parity: a rounded-gen read can flip the marginal
                # block at a boundary, which prices never reveal
                "marginal_luzon": [o["marginal"]["luzon"]
                                   for o in res["hours"]],
                "summary": res["summary"],
            },
        })
    # native 168h WEEK golden: seven consecutive full-coverage days on ONE LP,
    # a battery and the DC-wave scenario so storage cycles and carries across
    # midnight (the day engine resets it). The explicit date list rides in the
    # input so the studio replays the exact same window, never recomputes it;
    # the studio must build the byte-identical 168h LP (pinned by lp_sha256)
    # and reproduce these arrays.
    from lp_dispatch import run_week_lp

    full = [dd["date"] for dd in profiles["days"] if dd["market"]
            and all(len((dd.get("lwap") or {}).get(g) or []) == 24
                    and all(v is not None for v in dd["lwap"][g])
                    for g in GRID_KEYS)]
    week_block = {"available": False,
                  "note": "fewer than seven full-coverage days in the window"}
    if len(full) >= 7:
        week_dates = full[-7:]
        week_opts = {"solar_delta_mw": {"luzon": 8000},
                     "demand_delta": {"luzon": 2500},
                     "storage": [{"grid": "luzon", "power_mw": 2000,
                                  "energy_mwh": 16000}]}
        wr = run_week_lp(dispatch, profiles, week_dates, week_opts)
        week_block = {
            "available": True,
            "label": "native 168h week, DC-wave with 2 GW / 16 GWh storage",
            "input": {"dates": week_dates, **week_opts},
            "lp_sha256": wr["lp_sha256"],
            "expect": {
                "price": {g: [o["price"][g] for o in wr["hours"]]
                          for g in GRID_KEYS},
                "soc_mwh": [o["soc_mwh"] for o in wr["hours"]],
                "flow_lv": [o["flow_lv"] for o in wr["hours"]],
                "days": wr["days"],
                "summary": wr["summary"],
            },
        }

    return {
        "available": True,
        "date": date,
        "engine": "highs_lp_v2",
        "tolerance_php_kwh": 0.02,
        "tolerance_mw": 1.0,
        "note": "Input/output pairs from the Python HiGHS LP engine on the "
                "default observed day. The studio must build the byte-identical "
                "LP (pinned by lp_sha256) and reproduce these outputs; the "
                "studio test asserts both.",
        "cases": out,
        "week": week_block,
    }


# ---- backcast: base model vs observed hourly LWAP, market window -----------------

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


def _score_pairs(pts: list[tuple[float, float]]) -> dict | None:
    """MAE/bias/correlation/high-hour metrics for (modeled, observed) pairs."""
    if not pts:
        return None
    mod = [m for m, _ in pts]
    obs = [o for _, o in pts]
    n = len(pts)
    mae = round(sum(abs(m - o) for m, o in pts) / n, 3)
    bias = round(sum(m - o for m, o in pts) / n, 3)
    obs_thr = _pctl_low(sorted(obs), 0.9)
    mod_sorted = sorted(mod)
    mod_thr = _pctl_low(mod_sorted, 0.9)
    mod_med = _pctl_low(mod_sorted, 0.5)
    # a flat model prices its median at its top decile; ranking is then
    # meaningless and the hit rate is reported as null, not a fake 100%
    rankable = mod_thr > mod_med
    high = [(m, o) for m, o in pts if o >= obs_thr]
    hit = sum(1 for m, _ in high if m >= mod_thr)
    hit_rate = (round(100 * hit / len(high), 1)
                if high and rankable else None)
    return {
        "n_hours": n,
        "observed_mean_php_kwh": round(sum(obs) / n, 3),
        "modeled_mean_php_kwh": round(sum(mod) / n, 3),
        "mae_php_kwh": mae,
        "bias_php_kwh": bias,
        "correlation": _corr(mod, obs),
        "high_hour_hit_rate_pct": hit_rate,
    }


def _flows_vs_record(day_flows: dict[str, dict]) -> dict | None:
    """Score modeled corridor flows against the operator's own per-interval
    HVDC schedule (RTDHS): an independent published record, not the
    net-import identity the demand construction uses. day_flows is
    {date: {lv: [24], vm: [24], cap_lv: [24], cap_vm: [24]}}. The binding
    pair compares the operator's CONGESTION_FLAG=Y interval share with the
    share of modeled hours at the corridor cap."""
    from market_obs import rtdhs_hourly

    hs = rtdhs_hourly()
    out = {}
    for key, label in (("lv", "Luzon to Visayas"),
                       ("vm", "Visayas to Mindanao")):
        pts = []
        at_cap = n_cap = bind_y = bind_n = 0
        for date, rec in day_flows.items():
            hrec = hs.get(date)
            if not hrec:
                continue
            bind_y += hrec["bind_y"][key]
            bind_n += hrec["bind_n"][key]
            caps = rec["cap_" + key]
            for h in range(24):
                m = rec[key][h]
                o = hrec[key][h]
                if m is None or o is None:
                    continue
                pts.append((m, o))
                n_cap += 1
                # a zero cap (fully blocked hour) cannot bind in the
                # congestion sense, so it never counts as at-cap
                if caps[h] > 0.5 and abs(m) >= caps[h] - 0.5:
                    at_cap += 1
        if not pts:
            continue
        n = len(pts)
        decisive = [(m, o) for m, o in pts if abs(o) >= 10.0]
        agree = sum(1 for m, o in decisive if m * o > 0)
        out[key] = {
            "corridor": label,
            "n_hours": n,
            "observed_mean_mw": round(sum(o for _, o in pts) / n, 1),
            "modeled_mean_mw": round(sum(m for m, _ in pts) / n, 1),
            "mae_mw": round(sum(abs(m - o) for m, o in pts) / n, 1),
            "direction_agreement_pct": (round(100 * agree / len(decisive), 1)
                                        if decisive else None),
            "n_decisive_hours": len(decisive),
            "observed_binding_share_pct": (round(100 * bind_y / bind_n, 1)
                                           if bind_n else None),
            "modeled_at_cap_share_pct": (round(100 * at_cap / n_cap, 1)
                                         if n_cap else None),
        }
    return out or None


def build_offer_backcast(profiles: dict) -> dict:
    """Replay every market day covered by the derived offer stacks
    (data/derived/offer_daily) with the OBSERVED offer books instead of the
    cost proxy: native-load demand, corridor caps, no storage, reserve, or
    water budgets (the books already embody unit behavior). Scored against
    the same three targets as the cost-mode backcast, so the two sit side
    by side and the offer premium stops being a residual."""
    import glob as _glob

    from lp_dispatch import OFFER_CAP, _highs_solve
    from lp_model import build_day_lp

    here = os.path.dirname(os.path.abspath(__file__))
    files = {os.path.basename(p)[7:15]: p for p in _glob.glob(
        os.path.join(here, "..", "data", "derived", "offer_daily",
                     "OFFERD_*.json"))}
    if not files:
        return {"available": False,
                "note": "no derived offer days; run pipeline/offers.py"}
    s_of = {"luzon": "l", "visayas": "v", "mindanao": "m"}
    pairs: dict[str, list[tuple[float, float]]] = {g: [] for g in GRID_KEYS}
    pairs_mcp: dict[str, list[tuple[float, float]]] = {
        g: [] for g in GRID_KEYS}
    flow_pairs: dict[str, list[tuple[float, float]]] = {"lv": [], "vm": []}
    day_flows: dict[str, dict] = {}
    days_used = []
    for day in profiles["days"]:
        if not day["market"]:
            continue
        stamp = day["date"].replace("-", "")
        path = files.get(stamp)
        lw = day.get("lwap") or {}
        if not path or not all(
                len(lw.get(g) or []) == 24
                and all(v is not None for v in lw[g]) for g in GRID_KEYS):
            continue
        with open(path) as fh:
            off = json.load(fh)
        stacks = {g: [] for g in GRID_KEYS}
        demand = {g: [] for g in GRID_KEYS}
        ok = True
        for h in range(24):
            for g in GRID_KEYS:
                blocks = [{"fuel": "offer", "cost": p, "mw": m}
                          for p, m in (off["hours"][g][h] or [])]
                if not blocks:
                    ok = False
                stacks[g].append(sorted(blocks, key=lambda b: b["cost"]))
                demand[g].append(day["demand"][g][h])
        if not ok:
            continue
        dearest = max(b["cost"] for g in GRID_KEYS
                      for hb in stacks[g] for b in hb)
        # the day's observed HVDC blocks scale the hour's corridor limit,
        # same as every other replay path
        o_caps: dict = {"leyte": 250.0, "mvip": 450.0}
        for key in ("leyte", "mvip"):
            frac = (day.get("corridor_caps") or {}).get(key)
            if frac:
                o_caps[key] = [round1(o_caps[key] * frac[h])
                               for h in range(24)]
        text = build_day_lp(stacks, demand, o_caps,
                            0.02, [], None, max(OFFER_CAP, dearest + 0.001))
        sol = _highs_solve(text)
        cols, duals = sol["cols"], sol["duals"]
        days_used.append(day["date"])
        mc = day.get("mcp") or {}
        nf = day.get("net_flow") or {}
        rec: dict = {"lv": [], "vm": []}
        for key, ck in (("lv", "leyte"), ("vm", "mvip")):
            c = o_caps[ck]
            rec["cap_" + key] = c if isinstance(c, list) else [c] * 24
        for h in range(24):
            f1 = cols.get(f"f1p_{h}", 0.0) - cols.get(f"f1n_{h}", 0.0)
            f2 = cols.get(f"f2p_{h}", 0.0) - cols.get(f"f2n_{h}", 0.0)
            rec["lv"].append(f1)
            rec["vm"].append(f2)
            for g in GRID_KEYS:
                price = round3(duals.get(f"bal_{s_of[g]}_{h}", 0.0))
                pairs[g].append((price, lw[g][h]))
                mcg = mc.get(g) or []
                if h < len(mcg) and mcg[h] is not None:
                    pairs_mcp[g].append((price, mcg[h]))
            for key, val in (("lv", f1), ("vm", f2)):
                obs_series = nf.get(key) or []
                if h < len(obs_series) and obs_series[h] is not None:
                    flow_pairs[key].append((val, obs_series[h]))
        day_flows[day["date"]] = rec
    per_grid = {g: _score_pairs(pairs[g]) for g in GRID_KEYS
                if _score_pairs(pairs[g])}
    per_grid_mcp = {g: _score_pairs(pairs_mcp[g]) for g in GRID_KEYS
                    if _score_pairs(pairs_mcp[g])}
    flows = {}
    for key, label in (("lv", "Luzon to Visayas"),
                       ("vm", "Visayas to Mindanao")):
        pts = flow_pairs[key]
        if not pts:
            continue
        n = len(pts)
        decisive = [(m, o) for m, o in pts if abs(o) >= 10.0]
        agree = sum(1 for m, o in decisive if m * o > 0)
        flows[key] = {
            "corridor": label,
            "n_hours": n,
            "observed_mean_mw": round(sum(o for _, o in pts) / n, 1),
            "modeled_mean_mw": round(sum(m for m, _ in pts) / n, 1),
            "mae_mw": round(sum(abs(m - o) for m, o in pts) / n, 1),
            "direction_agreement_pct": (round(100 * agree / len(decisive), 1)
                                        if decisive else None),
            "n_decisive_hours": len(decisive),
        }
    return {
        "available": bool(days_used),
        "days": len(days_used),
        "window": ({"from": days_used[0], "to": days_used[-1]}
                   if days_used else None),
        "per_grid": per_grid,
        "per_grid_mcp": per_grid_mcp or None,
        "flows": flows or None,
        "flows_rtdhs": _flows_vs_record(day_flows),
        "flows_rtdhs_note": ("The same modeled flows scored against the "
                             "operator's per-interval HVDC schedule "
                             "(RTDHS), a published record independent of "
                             "the net-import identity the demand "
                             "construction uses; the binding pair sets "
                             "the operator's CONGESTION_FLAG=Y share "
                             "against the modeled at-cap share."),
        "note": ("The same replays with the operator's own OFFER BOOKS "
                 "(RTDOE + self-scheduled nominations) instead of the cost "
                 "proxy: native-load demand, corridor caps, no storage or "
                 "reserve or water layers (the books already embody unit "
                 "behavior). Where the cost-mode tables show what a "
                 "competitive cost stack would do, these show what the "
                 "market as bid actually prices; the gap between the two "
                 "IS the offer premium, measured instead of asserted."),
    }


def build_backcast(dispatch: dict, profiles: dict,
                   observed_solar: bool = False) -> dict:
    """Replay every full-coverage market day with the BASE model and score it
    against the observed hourly LWAP, and, where the archive carries it,
    against the observed regional marginal price (MCP: the ex-ante clearing
    price, the target commensurate with a dispatch dual; LWAP additionally
    embeds nodal spread and settlement substitution). No storage cycling, no
    levers, no tuning: the residual is the finding.

    observed_solar=True replaces the flat clear-sky solar credit with each day's
    own WESM-dispatched solar energy (DIPCEF), for the item-8 measurement only
    (vre_probe): it is OFF in the shipped backcast because it worsens the price
    correlation (the flat shape misplaces the observed energy without an
    observed hourly shape)."""
    from lp_dispatch import run_chronology_lp
    from market_obs import solar_observed_by_day

    obs_solar = solar_observed_by_day() if observed_solar else {}
    solar_shape = sum(profiles.get("solar_profile") or []) or 1.0

    pairs: dict[str, list[tuple[float, float]]] = {g: [] for g in GRID_KEYS}
    pairs_mcp: dict[str, list[tuple[float, float]]] = {g: [] for g in GRID_KEYS}
    flow_pairs: dict[str, list[tuple[float, float]]] = {"lv": [], "vm": []}
    day_flows: dict[str, dict] = {}
    base_caps = {"leyte": 250.0, "mvip": 450.0}
    for c in dispatch["coupling"]["corridors"]:
        base_caps["leyte" if c["id"] == "leyte_luzon_hvdc" else "mvip"] = \
            c["limit_mw"]
    days_used = []
    for day in profiles["days"]:
        if not day["market"]:
            continue
        lw = day.get("lwap") or {}
        if not all(len(lw.get(g) or []) == 24
                   and all(v is not None for v in lw[g]) for g in GRID_KEYS):
            continue
        opts: dict = {}
        osol = obs_solar.get(day["date"])
        if osol:
            opts["solar_delta_mw"] = {
                g: round1(osol.get(g, 0.0) / solar_shape
                          - dispatch["merit_order"][g]["solar_installed_mw"])
                for g in GRID_KEYS}
        res = run_chronology_lp(dispatch, profiles, day["date"], opts)
        days_used.append(day["date"])
        mc = day.get("mcp") or {}
        nf = day.get("net_flow") or {}
        cc = day.get("corridor_caps") or {}
        rec: dict = {
            "lv": [res["hours"][h]["flow_lv"] for h in range(24)],
            "vm": [res["hours"][h]["flow_vm"] for h in range(24)],
        }
        for key, ck in (("lv", "leyte"), ("vm", "mvip")):
            frac = cc.get(ck)
            rec["cap_" + key] = ([round1(base_caps[ck] * frac[h])
                                  for h in range(24)]
                                 if frac else [base_caps[ck]] * 24)
        day_flows[day["date"]] = rec
        for g in GRID_KEYS:
            mcg = mc.get(g) or []
            for h in range(24):
                pairs[g].append((res["hours"][h]["price"][g], lw[g][h]))
                if h < len(mcg) and mcg[h] is not None:
                    pairs_mcp[g].append((res["hours"][h]["price"][g], mcg[h]))
        for key, mod_key in (("lv", "flow_lv"), ("vm", "flow_vm")):
            obs_series = nf.get(key) or []
            for h in range(24):
                if h < len(obs_series) and obs_series[h] is not None:
                    flow_pairs[key].append(
                        (res["hours"][h][mod_key], obs_series[h]))
    per_grid = {}
    per_grid_mcp = {}
    for g in GRID_KEYS:
        scored = _score_pairs(pairs[g])
        if scored:
            per_grid[g] = scored
        scored_mcp = _score_pairs(pairs_mcp[g])
        if scored_mcp:
            per_grid_mcp[g] = scored_mcp
    flows = {}
    for key, label in (("lv", "Luzon to Visayas"),
                       ("vm", "Visayas to Mindanao")):
        pts = flow_pairs[key]
        if not pts:
            continue
        n = len(pts)
        # direction agreement counts only hours where the observed flow is
        # decisively nonzero; a near-zero flow has no direction to agree on
        decisive = [(m, o) for m, o in pts if abs(o) >= 10.0]
        agree = sum(1 for m, o in decisive if m * o > 0)
        flows[key] = {
            "corridor": label,
            "n_hours": n,
            "observed_mean_mw": round(sum(o for _, o in pts) / n, 1),
            "modeled_mean_mw": round(sum(m for m, _ in pts) / n, 1),
            "mae_mw": round(sum(abs(m - o) for m, o in pts) / n, 1),
            "direction_agreement_pct": (round(100 * agree / len(decisive), 1)
                                        if decisive else None),
            "n_decisive_hours": len(decisive),
        }
    return {
        "available": bool(days_used),
        "days": len(days_used),
        "window": ({"from": days_used[0], "to": days_used[-1]}
                   if days_used else None),
        "per_grid": per_grid,
        "per_grid_mcp": per_grid_mcp or None,
        "flows": flows or None,
        "flows_rtdhs": _flows_vs_record(day_flows),
        "flows_rtdhs_note": ("The same modeled flows scored against the "
                             "operator's per-interval HVDC schedule "
                             "(RTDHS), a published record independent of "
                             "the net-import identity the demand "
                             "construction uses; the binding pair sets "
                             "the operator's CONGESTION_FLAG=Y share "
                             "against the modeled at-cap share."),
        "flows_note": ("Modeled corridor flows scored against the observed "
                       "net market imports and exports in the RTD regional "
                       "summaries (f1 is Luzon's net export southbound, f2 "
                       "is Mindanao's net import). Demand is native load, "
                       "so the replay must move real MW over the corridors "
                       "to serve it; direction agreement counts hours where "
                       "the observed flow is at least 10 MW."),
        "mcp_note": ("per_grid_mcp scores the same replays against the "
                     "observed regional marginal price (the RTD ex-ante "
                     "clearing price, IEMOP MCP files): the target "
                     "commensurate with a dispatch dual. LWAP additionally "
                     "carries nodal spread and settlement substitution, so "
                     "part of the LWAP gap is definitional, and this pair of "
                     "tables shows how much."),
        "high_hour_note": "High hours are the top decile of observed hourly "
                          "LWAP in the window; the hit rate is how often the "
                          "model also ranks that hour in its own top decile. "
                          "Rank agreement, not level agreement.",
        "note": "Hourly replay of every full-coverage market day with the base "
                "model on the HiGHS LP engine: no storage cycling, no levers, "
                "no tuning. The gap to observed prices (scarcity, offers, "
                "caps, outages the model cannot see) stays in the residual, "
                "it is the finding. Against the previous clear, the LP "
                "completes the overnight corridor arbitrage the old solver "
                "left half-done: mean error is unchanged and the already-low "
                "shape correlation drops a few hundredths; reported, not "
                "tuned.",
    }
