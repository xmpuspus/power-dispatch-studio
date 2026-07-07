#!/usr/bin/env python3
"""Canonical LP text for the dispatch model (the HiGHS engine's model layer).

Both engines (this pipeline via highspy, the studio via the HiGHS wasm build)
construct the SAME linear program as the SAME text, byte for byte: fixed
variable order, fixed row order, one term per line, and every coefficient
serialized from integer micro-units (round(x * 1e6)) so no float-formatting
divergence can exist between Python and JavaScript. The parity harness pins
the sha256 of this text; a model-construction drift on either side fails the
hash before any solver runs.

The program, per day (H hours, usually 24):
  min  sum(block cost * dispatch) + wheel * |corridor flows|
       + voll * unserved + tiny deterministic epsilons (uniqueness)
  s.t. per grid-hour energy balance with signed corridor flows
       (Luzon -> Visayas -> Mindanao radial, positive = southward),
       storage state of charge (charge at the round-trip efficiency,
       free terminal state: the day resets, as the heuristic did),
       optional per-grid reserve: dispatch of reserve-capable blocks plus
       storage discharge may not eat the headroom the requirement needs.

Epsilons: every dispatch variable gets +index microcost in a fixed
enumeration order, and charging gets +index microcost per hour, so the
optimum is unique on the model's flat cost plateaus and both solver builds
must land on the same vertex. The epsilons top out well below one centavo
and are stated in the methodology.
"""
from __future__ import annotations

import math

GRID_KEYS = ["luzon", "visayas", "mindanao"]
G_SHORT = {"luzon": "l", "visayas": "v", "mindanao": "m"}

# reserve is held by capacity that can actually follow dispatch instructions
RESERVE_FUELS = ("coal", "natural_gas", "oil", "geothermal", "hydro",
                 "biomass")


def micro(x: float) -> int:
    """Integer micro-units; the only float -> text gate in the model.
    floor(x + 0.5), the repo's JS-compatible rounding (Python's round()
    half-to-even would diverge from Math.round at exact halves)."""
    return int(math.floor(x * 1_000_000 + 0.5))


def mtext(k: int) -> str:
    """Serialize integer micro-units as a fixed-point decimal string."""
    sign = "-" if k < 0 else ""
    k = abs(k)
    whole, frac = divmod(k, 1_000_000)
    return f"{sign}{whole}.{frac:06d}"


def build_day_lp(stacks: dict, demand: dict, caps: dict, wheel: float,
                 storage: list[dict], reserve_req: dict | None,
                 voll: float) -> str:
    """The canonical LP text.

    stacks:  {grid: [blocks per hour]} with blocks [{fuel, cost, mw}, ...]
             already merit-sorted (build_stack output)
    demand:  {grid: [MW per hour]} the balance right-hand sides
    caps:    {leyte, mvip} corridor limits (MW)
    storage: [{grid, power_mw, energy_mwh, eff}]
    reserve_req: {grid: MW} or None (the co-optimisation toggle)
    voll:    unserved-load penalty, PhP/kWh
    """
    H = len(demand["luzon"])
    wheel_m = micro(wheel)
    voll_m = micro(voll)

    obj: list[str] = []
    rows: list[str] = []
    bounds: list[str] = []

    # dispatch variables, one per block per grid-hour, epsilon by enumeration
    eps = 0
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            for i, b in enumerate(stacks[g][h]):
                eps += 1
                obj.append(f" + {mtext(micro(b['cost']) + eps)} x_{s}_{h}_{i}")
                bounds.append(f" 0 <= x_{s}_{h}_{i} <= {mtext(micro(b['mw']))}")

    # corridor flows, split by direction, wheeling cost on each
    for h in range(H):
        for f, cap in (("f1", caps["leyte"]), ("f2", caps["mvip"])):
            for d in ("p", "n"):
                obj.append(f" + {mtext(wheel_m)} {f}{d}_{h}")
                bounds.append(f" 0 <= {f}{d}_{h} <= {mtext(micro(cap))}")

    # storage: charge (with a per-hour epsilon so ties resolve to the earliest
    # hour), discharge, state of charge
    for k, st in enumerate(storage):
        for h in range(H):
            obj.append(f" + {mtext(k * H + h + 1)} ch_{k}_{h}")
            bounds.append(f" 0 <= ch_{k}_{h} <= {mtext(micro(st['power_mw']))}")
            bounds.append(
                f" 0 <= dis_{k}_{h} <= {mtext(micro(st['power_mw']))}")
            bounds.append(
                f" 0 <= soc_{k}_{h} <= {mtext(micro(st['energy_mwh']))}")

    # unserved load
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            obj.append(f" + {mtext(voll_m)} u_{s}_{h}")
            bounds.append(f" 0 <= u_{s}_{h} <= {mtext(micro(demand[g][h]))}")

    # energy balance per grid-hour. Flows are signed southward:
    #   luzon:    gen - f1 + u = d
    #   visayas:  gen + f1 - f2 + u = d
    #   mindanao: gen + f2 + u = d
    flow_terms = {
        "luzon": [("f1n", "+"), ("f1p", "-")],
        "visayas": [("f1p", "+"), ("f1n", "-"), ("f2n", "+"), ("f2p", "-")],
        "mindanao": [("f2p", "+"), ("f2n", "-")],
    }
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            terms = [f" + x_{s}_{h}_{i}"
                     for i in range(len(stacks[g][h]))]
            for name, sign in flow_terms[g]:
                terms.append(f" {sign} {name}_{h}")
            for k, st in enumerate(storage):
                if st["grid"] == g:
                    terms.append(f" + dis_{k}_{h}")
                    terms.append(f" - ch_{k}_{h}")
            terms.append(f" + u_{s}_{h}")
            rows.append(f" bal_{s}_{h}:" + "".join(terms)
                        + f" = {mtext(micro(demand[g][h]))}")

    # state of charge: soc_h - soc_(h-1) - eff * ch_h + dis_h = 0
    for k, st in enumerate(storage):
        eff_m = mtext(micro(st["eff"]))
        for h in range(H):
            prev = f" - soc_{k}_{h - 1}" if h > 0 else ""
            rows.append(f" soc_{k}_{h}: soc_{k}_{h}{prev}"
                        f" - {eff_m} ch_{k}_{h} + dis_{k}_{h} = 0")

    # reserve: dispatch on reserve-capable blocks plus storage discharge must
    # leave headroom >= requirement. Written with a constant right side:
    #   sum(x_capable) + sum(dis) <= capable_capacity + storage_power - R
    if reserve_req:
        for h in range(H):
            for g in GRID_KEYS:
                s = G_SHORT[g]
                req = reserve_req.get(g) or 0.0
                if req <= 0:
                    continue
                terms = []
                cap_m = 0
                for i, b in enumerate(stacks[g][h]):
                    if b["fuel"] in RESERVE_FUELS:
                        terms.append(f" + x_{s}_{h}_{i}")
                        cap_m += micro(b["mw"])
                for k, st in enumerate(storage):
                    if st["grid"] == g:
                        terms.append(f" + dis_{k}_{h}")
                        cap_m += micro(st["power_mw"])
                if not terms:
                    continue
                # a requirement beyond what the grid can hold clamps to zero
                # headroom (all capable capacity withheld) instead of writing
                # an infeasible row
                rhs = max(0, cap_m - micro(req))
                rows.append(f" res_{s}_{h}:" + "".join(terms)
                            + f" <= {mtext(rhs)}")

    return ("\\ power-dispatch-studio day LP v1\n"
            "minimize\n obj:" + "".join(obj) + "\n"
            "subject to\n" + "\n".join(rows) + "\n"
            "bounds\n" + "\n".join(bounds) + "\n"
            "end\n")


if __name__ == "__main__":
    import hashlib
    stacks = {g: [[{"fuel": "coal", "cost": 4.14, "mw": 1000.0},
                   {"fuel": "oil", "cost": 12.0, "mw": 200.0}]]
              for g in GRID_KEYS}
    demand = {"luzon": [900.0], "visayas": [300.0], "mindanao": [200.0]}
    text = build_day_lp(stacks, demand, {"leyte": 250.0, "mvip": 450.0},
                        0.02, [{"grid": "luzon", "power_mw": 100.0,
                                "energy_mwh": 200.0, "eff": 0.8}],
                        {"luzon": 500.0}, 12.0)
    print(text)
    print("sha256:", hashlib.sha256(text.encode()).hexdigest())
