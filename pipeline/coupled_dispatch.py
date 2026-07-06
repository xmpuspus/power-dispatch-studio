#!/usr/bin/env python3
"""Inter-island coupled economic dispatch for the three PH grids.

Still NOT PLEXOS. Where pipeline/dispatch.py clears each grid ALONE against its own
demand, this couples them: cheap Luzon energy flows south to Visayas and Mindanao
over the two HVDC corridors, up to each corridor's operating limit, and the three
clearing prices are solved together. If a corridor saturates, the downstream grid
prices above the upstream grid by the congestion rent (the price gap across the
binding link). That is the project's central claim, made endogenous.

The network is a radial path:  LUZON --(Leyte-Luzon HVDC, 250 MW)-- VISAYAS
--(MVIP HVDC, 450 MW)-- MINDANAO. On a path with convex (merit-order) supply
stacks, the cost-minimising dispatch is where adjacent grids' marginal costs are
equal across any UNSATURATED corridor, and the exporter is strictly cheaper across
a SATURATED one. We solve that condition directly by coordinate descent on the two
corridor flows with a per-corridor bisection, and pin the optimality (KKT) with a
test rather than trusting the algorithm (tests/test_data.py).

No scarcity / VOLL adder: an unserved grid still prices at its top block (oil P12),
and the shortfall is reported. The gap to the far higher observed price stays the
residual, exactly as in the standalone model.
"""
from __future__ import annotations

from fleet_ph import FUEL_COST_PHP_KWH, stack

# The two HVDC corridors as a radial path. limit_kind distinguishes the sourced
# operating limit (Leyte-Luzon: 250 MW Luzon->Visayas, IEMOP Dec 2025, below the
# 440 MW nameplate) from the nameplate-as-operating-limit proxy (MVIP: only the
# 450 MW nameplate is public; used as the cap and labelled as such).
CORRIDORS = [
    {
        "id": "leyte_luzon_hvdc",
        "name": "Leyte-Luzon HVDC",
        "from": "LUZON", "to": "VISAYAS",
        "limit_mw": 250,
        "nameplate_mw": 440,
        "limit_kind": "sourced_operating_limit",
        "src": "https://www.iemop.ph/news/december-2025-power-market-luzon-prices-ease-as-supply-improves-visayas-and-mindanao-experience-tighter-conditions/",
    },
    {
        "id": "mvip_hvdc",
        "name": "Mindanao-Visayas HVDC (MVIP)",
        "from": "VISAYAS", "to": "MINDANAO",
        "limit_mw": 450,
        "nameplate_mw": 450,
        "limit_kind": "nameplate_as_operating_limit",
        "src": "https://powerphilippines.com/wesm-prices-rise-38-5-in-may-as-demand-growth-outpaces-supply/",
    },
]

_OIL = FUEL_COST_PHP_KWH["oil"]
# A small HVDC wheeling cost (PhP/kWh). Two purposes: it is a real (if tiny) cost of
# moving power over a converter link, and it breaks the merit-order tie when two
# grids sit on the same coal block (a whole band of flows costs the same) toward the
# physical answer of NOT shipping power you do not need to. Without it the solve
# picks an arbitrary point in that band and reports phantom saturated corridors.
WHEEL = 0.02


def _marg(blocks: list[dict], g: float) -> tuple[float, str | None]:
    """Marginal cost and fuel serving the g-th MW on a cost-sorted stack.

    If g exceeds the stack's total (a shortfall), the top block sets the price;
    the shortfall itself is reported by the caller, not priced with a VOLL adder.
    """
    if not blocks:
        return _OIL, None
    if g <= 0:
        return blocks[0]["cost"], blocks[0]["fuel"]
    cum = 0.0
    for b in blocks:
        cum += b["mw"]
        if cum >= g:
            return b["cost"], b["fuel"]
    return blocks[-1]["cost"], blocks[-1]["fuel"]


def _root_decr(phi, lo: float, hi: float, target: float,
               tol: float = 0.25) -> float:
    """x in [lo, hi] where a non-increasing phi(x) meets `target`."""
    for _ in range(40):
        if hi - lo <= tol:
            break
        mid = (lo + hi) / 2
        if phi(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _opt_flow(phi, lo: float, hi: float) -> float:
    """Optimal signed corridor flow x in [lo, hi] for a radial cost min.

    phi(x) = (import-side marginal cost) - (export-side marginal cost), the gain
    per MW shipped before wheeling; it is non-increasing in x. Ship power in the
    direction that beats the wheeling cost, and stop when the marginal gain falls
    to WHEEL. Inside the dead band (|phi| <= WHEEL) it is not worth moving power,
    so the flow is the no-trade point nearest zero: this is the minimum-flow
    tie-break that kills phantom flows when both grids sit on the same block.
    """
    if hi <= lo:
        return lo
    zero = min(max(0.0, lo), hi)
    p0 = phi(zero)
    if p0 > WHEEL:  # worth exporting (increase x) until the gain drops to WHEEL
        if phi(hi) >= WHEEL:
            return hi
        return _root_decr(phi, zero, hi, WHEEL)
    if p0 < -WHEEL:  # worth importing (decrease x) until the reverse gain drops
        if phi(lo) <= -WHEEL:
            return lo
        return _root_decr(phi, lo, zero, -WHEEL)
    return zero


def clear_coupled(demand: dict[str, float], hour: int,
                  removed: dict[str, dict] | None = None,
                  caps: dict[str, float] | None = None) -> dict:
    """Couple the three grids and clear them together.

    demand: {grid -> MW} for LUZON/VISAYAS/MINDANAO at one interval.
    removed: optional {grid -> {fuel -> MW}} outage/derate per grid.
    caps: optional {corridor_id -> MW} override of the corridor limits (the map's
          "relieve a choke point" lever and the uncapped counterfactual use this).

    Returns per-grid price/gen/shortfall/marginal_fuel, the two corridor flows
    (signed toward `to`), and each corridor's saturation and congestion rent.
    """
    removed = removed or {}
    caps = caps or {}
    dL = demand.get("LUZON", 0.0)
    dV = demand.get("VISAYAS", 0.0)
    dM = demand.get("MINDANAO", 0.0)
    bL = stack("LUZON", hour, removed.get("LUZON"))
    bV = stack("VISAYAS", hour, removed.get("VISAYAS"))
    bM = stack("MINDANAO", hour, removed.get("MINDANAO"))
    availL = sum(b["mw"] for b in bL)
    availV = sum(b["mw"] for b in bV)
    availM = sum(b["mw"] for b in bM)

    c1 = caps.get("leyte_luzon_hvdc", CORRIDORS[0]["limit_mw"])
    c2 = caps.get("mvip_hvdc", CORRIDORS[1]["limit_mw"])

    def mcL(f1):
        return _marg(bL, dL + f1)[0]

    def mcV(f1, f2):
        return _marg(bV, dV + f2 - f1)[0]

    def mcM(f2):
        return _marg(bM, dM - f2)[0]

    f1 = f2 = 0.0
    for _ in range(60):
        # f1 = LUZON -> VISAYAS. phi1 = (Visayas cost) - (Luzon cost): ship south
        # while cheap Luzon power beats dear Visayas power by more than the wheel.
        lo = max(-c1, -dL)
        hi = min(c1, dV + f2)
        nf1 = _opt_flow(lambda x: mcV(x, f2) - mcL(x), lo, hi)
        # f2 = VISAYAS -> MINDANAO. phi2 = (Mindanao cost) - (Visayas cost).
        lo2 = max(-c2, nf1 - dV)
        hi2 = min(c2, dM)
        nf2 = _opt_flow(lambda x: mcM(x) - mcV(nf1, x), lo2, hi2)
        if abs(nf1 - f1) + abs(nf2 - f2) < 0.25:
            f1, f2 = nf1, nf2
            break
        f1, f2 = nf1, nf2

    gen = {"LUZON": dL + f1, "VISAYAS": dV + f2 - f1, "MINDANAO": dM - f2}
    avail = {"LUZON": availL, "VISAYAS": availV, "MINDANAO": availM}
    grids = {}
    for g in ("LUZON", "VISAYAS", "MINDANAO"):
        blocks = {"LUZON": bL, "VISAYAS": bV, "MINDANAO": bM}[g]
        cost, fuel = _marg(blocks, gen[g])
        short = max(0.0, gen[g] - avail[g])
        grids[g.lower()] = {
            "price": round(cost, 3),
            "gen_mw": round(gen[g], 1),
            "shortfall_mw": round(short, 1),
            "marginal_fuel": fuel,
        }

    pL = grids["luzon"]["price"]
    pV = grids["visayas"]["price"]
    pM = grids["mindanao"]["price"]
    eps = 0.5
    corridors = [
        _corridor(CORRIDORS[0], f1, c1, pL, pV, eps),
        _corridor(CORRIDORS[1], f2, c2, pV, pM, eps),
    ]
    return {"grids": grids, "corridors": corridors,
            "flow_lv_mw": round(f1, 1), "flow_vm_mw": round(f2, 1)}


def _gen_cost(blocks: list[dict], g: float) -> float:
    """Cost to produce g MW from the cheapest blocks first; any shortfall is
    priced at the top block (oil), matching the no-VOLL price cap."""
    rem, c = g, 0.0
    for b in blocks:
        if rem <= 0:
            break
        take = min(b["mw"], rem)
        c += take * b["cost"]
        rem -= take
    if rem > 0:
        c += rem * _OIL
    return c


def system_cost(demand: dict[str, float], hour: int, f1: float, f2: float,
                removed: dict[str, dict] | None = None) -> float:
    """Total generation cost (+ wheeling) of a given flow pair. The optimality
    test brute-forces this to confirm clear_coupled lands on the minimum."""
    removed = removed or {}
    dL = demand.get("LUZON", 0.0)
    dV = demand.get("VISAYAS", 0.0)
    dM = demand.get("MINDANAO", 0.0)
    gL, gV, gM = dL + f1, dV + f2 - f1, dM - f2
    if gL < 0 or gV < 0 or gM < 0:
        return float("inf")
    return (_gen_cost(stack("LUZON", hour, removed.get("LUZON")), gL)
            + _gen_cost(stack("VISAYAS", hour, removed.get("VISAYAS")), gV)
            + _gen_cost(stack("MINDANAO", hour, removed.get("MINDANAO")), gM)
            + WHEEL * (abs(f1) + abs(f2)))


def _corridor(meta: dict, flow: float, cap: float,
              p_from: float, p_to: float, eps: float) -> dict:
    """Report one corridor's flow, saturation, and congestion rent."""
    sat = abs(flow) >= cap - eps
    rent = 0.0
    if sat:
        rent = round(p_to - p_from if flow > 0 else p_from - p_to, 3)
    return {
        "id": meta["id"], "name": meta["name"],
        "from": meta["from"].lower(), "to": meta["to"].lower(),
        "limit_mw": cap, "flow_mw": round(flow, 1),
        "saturated": sat, "congestion_rent_php_kwh": rent,
    }
