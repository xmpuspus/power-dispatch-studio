#!/usr/bin/env python3
"""Chronological dispatch on the HiGHS LP (the solver engine, Python side).

Same inputs and same output shape as chrono.run_chronology, different solve:
one linear program per day instead of 24 independent block clears plus the
storage heuristic. Storage becomes true inter-temporal optimisation, the
reserve toggle becomes real withheld-capacity constraints, and prices come
from the balance-row duals (the marginal system cost of one more MW of load
in that grid-hour).

The model text is built by lp_model.build_day_lp, the canonical layer both
engines share byte for byte; this module only assembles inputs (reusing
chrono.py's stack construction so the calibrated model is untouched), runs
highspy, and post-processes the solution into the familiar hour rows.

Unserved load keeps the model's documented stance (no VoLL adder: a short
grid prices at its dearest block): the LP's shedding penalty sits one
tenth-centavo above the dearest block, so shedding never beats available
capacity but a short hour still prices at the top block to display rounding.
The sourced WESM offer cap (P32/kWh, ERC, permanent since Dec 2015) is
research on file, deliberately NOT introduced here: repricing scarcity is a
product decision with map-wide blast radius, not an engine swap.
"""
from __future__ import annotations

import hashlib
import os
import tempfile

from chrono import (GRID_KEYS, build_stack, marginal, round1, round3)
from lp_model import G_SHORT, build_day_lp

FLOW_SAT_EPS = 0.5
LABEL_EPS = 0.025
STORE_EPS = 1e-3


def price_label(price: float, own_cost: float, own_fuel: str | None,
                storage_marginal: bool) -> str | None:
    """Name what sets an LMP. The dual can sit away from the grid's own stack:
    on an importing grid it is the exporter's cost plus the wheel, on an
    exporting grid the importer's cost minus the wheel, and with storage
    strictly between its bounds it is the arbitrage value. Shared verbatim by
    both engines; the goldens pin it."""
    if abs(own_cost - price) <= LABEL_EPS:
        return own_fuel
    if storage_marginal:
        return "storage"
    return "export" if price > own_cost else "import"


def _highs_solve(lp_text: str) -> dict:
    import highspy
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    # dual simplex on a fixed model text, single thread: deterministic runs
    h.setOptionValue("threads", 1)
    with tempfile.NamedTemporaryFile("w", suffix=".lp", delete=False) as f:
        f.write(lp_text)
        path = f.name
    try:
        h.readModel(path)
        h.run()
        status = h.getModelStatus()
        if h.modelStatusToString(status) != "Optimal":
            raise SystemExit(
                f"lp_dispatch: solve ended {h.modelStatusToString(status)}")
        sol = h.getSolution()
        lp = h.getLp()
        cols = {name: sol.col_value[i]
                for i, name in enumerate(lp.col_names_)}
        duals = {name: sol.row_dual[i]
                 for i, name in enumerate(lp.row_names_)}
        obj = h.getObjectiveValue()
    finally:
        os.unlink(path)
    return {"cols": cols, "duals": duals, "objective": obj}


def _assemble(dispatch: dict, profiles: dict, date: str, opts: dict) -> dict:
    """Shared input assembly: hourly stacks, demand, caps, storage, reserve.
    Mirrors chrono.run_chronology exactly up to the solve."""
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

    fuel_base: dict[str, dict[str, float]] = {}
    solar_inst: dict[str, float] = {}
    for g in GRID_KEYS:
        mo = dispatch["merit_order"][g]
        fa = dict(mo["fuel_avail_mw"])
        if hyd != 1.0 and fa.get("hydro") is not None:
            fa["hydro"] = round1(fa["hydro"] * hyd)
        for fuel, delta in ((opts.get("fuel_avail_delta") or {})
                            .get(g) or {}).items():
            fa[fuel] = max(0.0, round1((fa.get(fuel) or 0.0) + delta))
        fuel_base[g] = fa
        solar_inst[g] = (mo["solar_installed_mw"]
                         + ((opts.get("solar_delta_mw") or {}).get(g) or 0.0))

    stacks = {g: [] for g in GRID_KEYS}
    demand = {g: [] for g in GRID_KEYS}
    for h in range(24):
        for g in GRID_KEYS:
            fa = dict(fuel_base[g])
            fa["solar"] = round1(max(0.0, solar_inst[g]) * solar_profile[h])
            stacks[g].append(build_stack(fa, {}, [], params))
            demand[g].append(day["demand"][g][h]
                             + ((opts.get("demand_delta") or {}).get(g)
                                or 0.0))

    eff = profiles.get("storage_round_trip_eff", 0.8)
    storage = [{"grid": s["grid"], "power_mw": float(s["power_mw"]),
                "energy_mwh": float(s["energy_mwh"]), "eff": eff}
               for s in (opts.get("storage") or [])
               if s["power_mw"] > 0 and s["energy_mwh"] > 0]

    reserve_req = None
    if opts.get("reserve_deduction"):
        req = profiles.get("reserve_req_mean_mw") or {}
        reserve_req = {g: round1(sum((req.get(g) or {}).values()))
                       for g in GRID_KEYS}

    # unserved load prices at the dearest block (the model's documented
    # no-VoLL stance); the +0.001 makes shedding strictly worse than serving
    dearest = max((b["cost"] for g in GRID_KEYS
                   for hb in stacks[g] for b in hb), default=12.0)
    voll = max(12.0, dearest) + 0.001

    return {"stacks": stacks, "demand": demand, "caps": caps, "wheel": wheel,
            "storage": storage, "reserve_req": reserve_req, "voll": voll}


def run_chronology_lp(dispatch: dict, profiles: dict, date: str,
                      opts: dict | None = None) -> dict:
    """Replay one observed day on the LP engine. Output shape matches
    chrono.run_chronology; `lp_sha256` is added for the parity hash."""
    opts = opts or {}
    m = _assemble(dispatch, profiles, date, opts)
    text = build_day_lp(m["stacks"], m["demand"], m["caps"], m["wheel"],
                        m["storage"], m["reserve_req"], m["voll"])
    sol = _highs_solve(text)
    cols, duals = sol["cols"], sol["duals"]

    out_hours = []
    for h in range(24):
        f1 = cols.get(f"f1p_{h}", 0.0) - cols.get(f"f1n_{h}", 0.0)
        f2 = cols.get(f"f2p_{h}", 0.0) - cols.get(f"f2n_{h}", 0.0)
        price = {}
        shed = {}
        fuel_gen: dict[str, dict[str, float]] = {}
        gen = {}
        for g in GRID_KEYS:
            s = G_SHORT[g]
            price[g] = round3(duals.get(f"bal_{s}_{h}", 0.0))
            shed[g] = max(0.0, round1(cols.get(f"u_{s}_{h}", 0.0)))
            per: dict[str, float] = {}
            for i, b in enumerate(m["stacks"][g][h]):
                x = cols.get(f"x_{s}_{h}_{i}", 0.0)
                if x > 1e-6:
                    per[b["fuel"]] = per.get(b["fuel"], 0.0) + x
            fuel_gen[g] = {f: round1(v) for f, v in per.items()}
        charge = {g: 0.0 for g in GRID_KEYS}
        dis = {g: 0.0 for g in GRID_KEYS}
        soc_total = 0.0
        for k, st in enumerate(m["storage"]):
            charge[st["grid"]] += cols.get(f"ch_{k}_{h}", 0.0)
            dis[st["grid"]] += cols.get(f"dis_{k}_{h}", 0.0)
            soc_total += cols.get(f"soc_{k}_{h}", 0.0)
        for g in GRID_KEYS:
            if dis[g] > 1e-6:
                fuel_gen[g]["storage"] = round1(
                    fuel_gen[g].get("storage", 0.0) + dis[g])
        # reported demand carries the charging draw, as the heuristic did;
        # gen follows the flow identity so the own-stack read is comparable
        dem = {g: m["demand"][g][h] + charge[g] for g in GRID_KEYS}
        gen["luzon"] = dem["luzon"] + f1 - shed["luzon"]
        gen["visayas"] = dem["visayas"] + f2 - f1 - shed["visayas"]
        gen["mindanao"] = dem["mindanao"] - f2 - shed["mindanao"]
        store_marg = {g: False for g in GRID_KEYS}
        for k, st in enumerate(m["storage"]):
            d_k = cols.get(f"dis_{k}_{h}", 0.0)
            if STORE_EPS < d_k < st["power_mw"] - STORE_EPS:
                store_marg[st["grid"]] = True
        marg = {}
        for g in GRID_KEYS:
            cost, fuel = marginal(m["stacks"][g][h], gen[g])
            marg[g] = price_label(price[g], cost, fuel, store_marg[g])
        sat1 = abs(f1) >= m["caps"]["leyte"] - FLOW_SAT_EPS
        sat2 = abs(f2) >= m["caps"]["mvip"] - FLOW_SAT_EPS
        rent1 = (round3(price["visayas"] - price["luzon"] if f1 > 0
                        else price["luzon"] - price["visayas"])
                 if sat1 else 0.0)
        rent2 = (round3(price["mindanao"] - price["visayas"] if f2 > 0
                        else price["visayas"] - price["mindanao"])
                 if sat2 else 0.0)
        out_hours.append({
            "hour": h,
            "price": price,
            "marginal": marg,
            "demand": {g: round1(dem[g]) for g in GRID_KEYS},
            "shortfall": shed,
            "flow_lv": round1(f1),
            "flow_vm": round1(f2),
            "leyte": {"sat": sat1, "rent": rent1},
            "mvip": {"sat": sat2, "rent": rent2},
            "fuel_gen": fuel_gen,
            "soc_mwh": round1(soc_total),
            "charge_mw": round1(sum(charge.values())),
            "discharge_mw": round1(sum(dis.values())),
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
    return {"hours": out_hours, "summary": summary,
            "objective": sol["objective"],
            "lp_sha256": hashlib.sha256(text.encode()).hexdigest()}


def solve_snapshot_lp(stacks: dict, demand: dict, caps: dict,
                      wheel: float) -> dict:
    """Single-hour coupled clear on the LP: the snapshot engine's solve.

    stacks: {grid: cost-sorted blocks}; demand: {grid: MW}; caps {leyte,mvip}.
    Returns prices, flows, saturation/rents, shortfall, gen, and the LP hash.
    """
    hstacks = {g: [stacks[g]] for g in GRID_KEYS}
    hdemand = {g: [demand[g]] for g in GRID_KEYS}
    dearest = max((b["cost"] for g in GRID_KEYS for b in stacks[g]),
                  default=12.0)
    voll = max(12.0, dearest) + 0.001
    text = build_day_lp(hstacks, hdemand, caps, wheel, [], None, voll)
    sol = _highs_solve(text)
    cols, duals = sol["cols"], sol["duals"]
    f1 = cols.get("f1p_0", 0.0) - cols.get("f1n_0", 0.0)
    f2 = cols.get("f2p_0", 0.0) - cols.get("f2n_0", 0.0)
    price = {}
    shed = {}
    gen = {"luzon": demand["luzon"] + f1,
           "visayas": demand["visayas"] + f2 - f1,
           "mindanao": demand["mindanao"] - f2}
    for g in GRID_KEYS:
        s = G_SHORT[g]
        price[g] = round3(duals.get(f"bal_{s}_0", 0.0))
        shed[g] = max(0.0, round1(cols.get(f"u_{s}_0", 0.0)))
    sat1 = abs(f1) >= caps["leyte"] - FLOW_SAT_EPS
    sat2 = abs(f2) >= caps["mvip"] - FLOW_SAT_EPS
    rent1 = (round3(price["visayas"] - price["luzon"] if f1 > 0
                    else price["luzon"] - price["visayas"]) if sat1 else 0.0)
    rent2 = (round3(price["mindanao"] - price["visayas"] if f2 > 0
                    else price["visayas"] - price["mindanao"]) if sat2 else 0.0)
    return {"price": price, "shortfall": shed,
            "gen": {g: round1(gen[g]) for g in GRID_KEYS},
            "flow_lv": round1(f1), "flow_vm": round1(f2),
            "leyte": {"sat": sat1, "rent": rent1},
            "mvip": {"sat": sat2, "rent": rent2},
            "objective": sol["objective"],
            "lp_sha256": hashlib.sha256(text.encode()).hexdigest()}


if __name__ == "__main__":
    import json
    import sys
    web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "web", "data")
    dispatch = json.load(open(os.path.join(web, "dispatch.json")))
    profiles = json.load(open(os.path.join(web, "profiles.json")))
    date = sys.argv[1] if len(sys.argv) > 1 else profiles["default_day"]
    res = run_chronology_lp(dispatch, profiles, date, {})
    print(json.dumps(res["summary"], indent=1))
    print("objective:", round(res["objective"], 1))
    print("lp_sha256:", res["lp_sha256"])
