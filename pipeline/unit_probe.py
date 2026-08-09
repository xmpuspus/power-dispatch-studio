#!/usr/bin/env python3
"""Dispatch named units instead of fuel blocks, and measure what that changes.

The engine holds one block per fuel per grid, so it cannot name the plant that
ran. The obvious next step is one variable per unit, and the obvious question is
what that buys. This probe answers it by measurement rather than by argument.

The method keeps the system identical and changes only its shape. Every plant in
the DOE fleet list becomes its own variable, and each grid's per-fuel capacity is
scaled to match `merit_order[g].fuel_avail_mw` exactly. So the unit run and the
block run hold the same MW at the same costs, cut into 355 pieces instead of 7.
Anything else would measure the difference between two fleets rather than the
difference between two model shapes.

The measured finding, and the reason the engine keeps its blocks: named units
burn the same energy of the same fuels every day, to the MWh. Only the hour an
energy-limited fuel lands in moves, across hours that cost the same, because the
epsilon that breaks that tie rides the variable index and the two models number
their variables differently. So a unit-level LP buys attribution and not
accuracy. What would move a price is a per-unit heat rate or a per-unit offer,
and no public Philippine source publishes either.

    python3 pipeline/unit_probe.py --derive   # remeasure, write the finding
    python3 pipeline/unit_probe.py            # print the delta table
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os

from chrono import GRID_KEYS, _score_pairs, round3
from lp_dispatch import _assemble, _highs_solve
from lp_model import G_SHORT, micro, mtext

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "derived", "unit_probe.json")
WEB = os.path.join(HERE, "..", "web", "data")

# a plant under this is noise against a 16 GW grid, and the fleet list carries
# hundreds of them; the same floor the studio's generator table uses
MIN_DEPENDABLE_MW = 20.0


def _load(name):
    with open(os.path.join(WEB, name)) as fh:
        return json.load(fh)


def unit_stacks(dispatch: dict, fleet: dict) -> dict:
    """Per-grid unit lists whose per-fuel totals equal the block model's.

    Returns {grid: [{name, fuel, share}]} where share is the unit's fraction of
    its fuel's grid capacity. The hourly stack then multiplies share by whatever
    that fuel's availability is on the day, so every scenario lever still lands.
    """
    per_grid: dict[str, list[dict]] = {g: [] for g in GRID_KEYS}
    for p in fleet.get("plants") or []:
        g = (p.get("grid") or "").lower()
        mw = float(p.get("dependable_mw") or 0.0)
        if g not in per_grid or mw < MIN_DEPENDABLE_MW:
            continue
        per_grid[g].append({"name": p["name"], "fuel": p["fuel"], "mw": mw})

    out: dict[str, list[dict]] = {}
    for g in GRID_KEYS:
        avail = dispatch["merit_order"][g]["fuel_avail_mw"]
        rows = []
        for fuel in avail:
            units = [u for u in per_grid[g] if u["fuel"] == fuel]
            total = sum(u["mw"] for u in units)
            if not units or total <= 0:
                # a fuel the list does not resolve to plants stays one block, so
                # the capacity is never lost
                rows.append({"name": f"{fuel} (unnamed)", "fuel": fuel, "share": 1.0})
                continue
            for u in units:
                rows.append({"name": u["name"], "fuel": fuel, "share": u["mw"] / total})
        # a stable order: fuel, then descending share, then name. The LP's
        # epsilon tie-break rides the variable index, so the order has to be
        # deterministic or two runs of the same day could land on two vertices.
        rows.sort(key=lambda r: (r["fuel"], -r["share"], r["name"]))
        out[g] = rows
    return out


def _unit_text(m: dict, units: dict) -> str:
    """The same program, one variable per named unit.

    Mirrors build_day_lp row for row: the same balance rows, the same corridor
    variables, the same unserved-load penalty, the same hydro budget. Only the
    generation variables change shape, so a price difference can come from
    nothing else.
    """
    stacks, demand, caps = m["stacks"], m["demand"], m["caps"]
    wheel_m, voll_m = micro(m["wheel"]), micro(m["voll"])
    H = len(demand["luzon"])
    obj, rows, bounds = [], [], []

    # per hour and grid, expand each fuel block across its units by share
    idx: dict[tuple[str, int], list[tuple[str, str, float, float]]] = {}
    eps = 0
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            entries = []
            for b in stacks[g][h]:
                same = [u for u in units[g] if u["fuel"] == b["fuel"]]
                if not same:
                    same = [{"name": f"{b['fuel']} (unnamed)", "share": 1.0}]
                for u in same:
                    mw = b["mw"] * u["share"]
                    if mw <= 0:
                        continue
                    eps += 1
                    v = f"x_{s}_{h}_{len(entries)}"
                    obj.append(f" + {mtext(micro(b['cost']) + eps)} {v}")
                    bounds.append(f" 0 <= {v} <= {mtext(micro(mw))}")
                    entries.append((v, b["fuel"], mw, b["cost"]))
            idx[(g, h)] = entries

    for h in range(H):
        for f, cap in (("f1", caps["leyte"]), ("f2", caps["mvip"])):
            cap_h = cap[h] if isinstance(cap, (list, tuple)) else cap
            for dsgn in ("p", "n"):
                obj.append(f" + {mtext(wheel_m)} {f}{dsgn}_{h}")
                bounds.append(f" 0 <= {f}{dsgn}_{h} <= {mtext(micro(cap_h))}")

    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            obj.append(f" + {mtext(voll_m)} u_load_{s}_{h}")
            bounds.append(f" 0 <= u_load_{s}_{h} <= {mtext(micro(demand[g][h]))}")

    flow_terms = {
        "luzon": [("f1n", "+"), ("f1p", "-")],
        "visayas": [("f1p", "+"), ("f1n", "-"), ("f2n", "+"), ("f2p", "-")],
        "mindanao": [("f2p", "+"), ("f2n", "-")],
    }
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            terms = [f" + {v}" for v, _f, _mw, _c in idx[(g, h)]]
            for name, sign in flow_terms[g]:
                terms.append(f" {sign} {name}_{h}")
            terms.append(f" + u_load_{s}_{h}")
            rows.append(
                f" bal_{s}_{h}:" + "".join(terms) + f" = {mtext(micro(demand[g][h]))}"
            )

    hydro_budget = m.get("hydro_budget")
    if hydro_budget:
        for g in GRID_KEYS:
            budget = hydro_budget.get(g)
            if budget is None:
                continue
            s = G_SHORT[g]
            terms = [
                f" + {v}" for h in range(H) for v, f, _mw, _c in idx[(g, h)] if f == "hydro"
            ]
            if terms:
                rows.append(
                    f" hyd_{s}:" + "".join(terms) + f" <= {mtext(micro(budget))}"
                )

    return (
        "Minimize\n obj:"
        + "".join(obj)
        + "\nSubject To\n"
        + "\n".join(rows)
        + "\nBounds\n"
        + "\n".join(bounds)
        + "\nEnd\n"
    )


def run_chronology_units(dispatch: dict, profiles: dict, date: str, units: dict) -> dict:
    m = _assemble(dispatch, profiles, date, {})
    text = _unit_text(m, units)
    sol = _highs_solve(text)
    duals = sol["duals"]
    H = len(m["demand"]["luzon"])
    hours = [
        {
            "hour": h,
            "price": {
                g: round3(duals.get(f"bal_{G_SHORT[g]}_{h}", 0.0)) for g in GRID_KEYS
            },
        }
        for h in range(H)
    ]
    return {"hours": hours, "lp_sha256": hashlib.sha256(text.encode()).hexdigest()}


def _pairs(dispatch: dict, profiles: dict, units: dict | None) -> dict:
    from lp_dispatch import run_chronology_lp

    lw_pairs = {g: [] for g in GRID_KEYS}
    mcp_pairs = {g: [] for g in GRID_KEYS}
    for day in profiles["days"]:
        if not day["market"]:
            continue
        lw = day.get("lwap") or {}
        if not all(
            len(lw.get(g) or []) == 24 and all(v is not None for v in lw[g])
            for g in GRID_KEYS
        ):
            continue
        res = (
            run_chronology_units(dispatch, profiles, day["date"], units)
            if units
            else run_chronology_lp(dispatch, profiles, day["date"], {})
        )
        mc = day.get("mcp") or {}
        for g in GRID_KEYS:
            for h in range(24):
                lw_pairs[g].append((res["hours"][h]["price"][g], lw[g][h]))
            mg = mc.get(g) or []
            if len(mg) == 24 and all(v is not None for v in mg):
                for h in range(24):
                    mcp_pairs[g].append((res["hours"][h]["price"][g], mg[h]))
    return {
        "lwap": {g: _score_pairs(lw_pairs[g]) for g in GRID_KEYS},
        "mcp": {g: _score_pairs(mcp_pairs[g]) for g in GRID_KEYS},
    }


def generation_gap(dispatch: dict, profiles: dict, units: dict, dates: list[str]) -> dict:
    """How far the two runs differ, measured two ways over the given days.

    `daily_mwh` is the load-bearing number: the largest difference in a fuel's
    energy across a whole day. Zero means the two models burn the same fuel in
    the same amount, so no economics changed.

    `hourly_mw` is the largest difference in one hour. An energy-limited fuel
    can move between hours that cost the same, and the epsilon that breaks that
    tie rides the variable index, which the two models number differently. So a
    nonzero hourly gap with a zero daily gap is a tie-break, not a result.
    """
    from lp_dispatch import run_chronology_lp

    worst = 0.0
    worst_daily = 0.0
    for date in dates:
        day_u: dict[tuple[str, str], float] = {}
        day_b: dict[tuple[str, str], float] = {}
        m = _assemble(dispatch, profiles, date, {})
        sol = _highs_solve(_unit_text(m, units))
        blk = run_chronology_lp(dispatch, profiles, date, {})
        H = len(m["demand"]["luzon"])
        for h in range(H):
            for g in GRID_KEYS:
                s = G_SHORT[g]
                per_fuel: dict[str, float] = {}
                k = 0
                for b in m["stacks"][g][h]:
                    same = [u for u in units[g] if u["fuel"] == b["fuel"]] or [
                        {"share": 1.0}
                    ]
                    for u in same:
                        if b["mw"] * u["share"] <= 0:
                            continue
                        v = f"x_{s}_{h}_{k}"
                        k += 1
                        per_fuel[b["fuel"]] = per_fuel.get(b["fuel"], 0.0) + sol[
                            "cols"
                        ].get(v, 0.0)
                blkf = (blk["hours"][h].get("fuel_gen") or {}).get(g, {})
                for fuel in set(list(per_fuel) + list(blkf)):
                    u_mw = per_fuel.get(fuel, 0.0)
                    b_mw = blkf.get(fuel, 0.0)
                    worst = max(worst, abs(u_mw - b_mw))
                    day_u[(g, fuel)] = day_u.get((g, fuel), 0.0) + u_mw
                    day_b[(g, fuel)] = day_b.get((g, fuel), 0.0) + b_mw
        for key in set(list(day_u) + list(day_b)):
            worst_daily = max(
                worst_daily, abs(day_u.get(key, 0.0) - day_b.get(key, 0.0))
            )
    return {"hourly_mw": round(worst, 3), "daily_mwh": round(worst_daily, 3)}


def derive(dispatch: dict, profiles: dict, fleet: dict) -> dict:
    units = unit_stacks(dispatch, fleet)
    n_units = {g: len(units[g]) for g in GRID_KEYS}
    block = _pairs(dispatch, profiles, None)
    unit = _pairs(dispatch, profiles, units)

    deltas = {}
    worst = 0.0
    for tgt in ("lwap", "mcp"):
        deltas[tgt] = {}
        for g in GRID_KEYS:
            b, u = block[tgt][g], unit[tgt][g]
            if not b or not u:
                deltas[tgt][g] = None
                continue
            d = {
                "block_corr": b["correlation"],
                "unit_corr": u["correlation"],
                "block_mae": b["mae_php_kwh"],
                "unit_mae": u["mae_php_kwh"],
                "corr_delta": round3((u["correlation"] or 0) - (b["correlation"] or 0)),
                "mae_delta": round3(u["mae_php_kwh"] - b["mae_php_kwh"]),
            }
            worst = max(worst, abs(d["mae_delta"]), abs(d["corr_delta"]))
            deltas[tgt][g] = d

    # the decisive check: do the two models run the same plants for the same
    # hours? Ten days spread across the window, which is 720 grid-hours.
    market_days = [d["date"] for d in profiles["days"] if d["market"]]
    sample = market_days[:: max(1, len(market_days) // 10)][:10]
    gap = generation_gap(dispatch, profiles, units, sample)
    # the daily energy is what economics decides. The hourly placement of an
    # energy-limited fuel can move between hours that cost the same.
    same = gap["daily_mwh"] < 0.5

    return {
        "generated_by": "pipeline/unit_probe.py",
        "n_units_dispatched": n_units,
        "min_dependable_mw": MIN_DEPENDABLE_MW,
        "generation_gap": gap,
        "generation_gap_days": len(sample),
        "method": (
            "every plant in the DOE fleet list becomes its own variable, with "
            "each grid's per-fuel capacity scaled to match the block model's "
            "fuel_avail_mw exactly, so the two runs hold the same MW at the "
            "same costs"
        ),
        "block": block,
        "unit": unit,
        "delta": deltas,
        "largest_absolute_change": round3(worst),
        "verdict": (
            "named units burn the same energy of the same fuels every day as "
            "the blocks do. Only the hour an energy-limited fuel lands in "
            "moves, on hours that cost the same, so the score differences are "
            "a tie-break and not a result"
            if same
            else "named units burn different daily energy from the blocks; "
            "read the generation gap before reading either score"
        ),
        "what_would_change_it": (
            "a per-unit heat rate or a per-unit offer. Every unit of a fuel "
            "carries that fuel's cost here, so splitting a block into units "
            "cannot reorder the stack. No public Philippine source publishes "
            "either, so a unit-level run buys attribution and not accuracy."
        ),
        "engine_default": "block",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true", help="remeasure and write")
    args = ap.parse_args()

    dispatch = _load("dispatch.json")
    profiles = _load("profiles.json")
    fleet = _load("fleet.json")
    out = derive(dispatch, profiles, fleet)

    print(f"units dispatched: {out['n_units_dispatched']}")
    g = out["generation_gap"]
    print(
        f"over {out['generation_gap_days']} days: daily energy gap "
        f"{g['daily_mwh']} MWh, largest hourly gap {g['hourly_mw']} MW"
    )
    print(f"largest absolute score change: {out['largest_absolute_change']}")
    print(f"{'series':<22} {'block':>8} {'units':>8} {'change':>8}")
    for tgt in ("lwap", "mcp"):
        for g in GRID_KEYS:
            d = out["delta"][tgt][g]
            if not d:
                continue
            print(
                f"{g + ' ' + tgt:<22} {d['block_corr']:>8.3f} "
                f"{d['unit_corr']:>8.3f} {d['corr_delta']:>+8.3f}"
            )
    print(out["verdict"])

    if args.derive:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
