#!/usr/bin/env python3
"""MILP unit commitment vs the LP dispatch, measured on the backcast (roadmap
item 9).

PLEXOS runs a mixed-integer unit commitment: each thermal unit is either
committed (and must then run at or above its minimum-stable level) or off, with
start costs and minimum up/down times. The studio dispatches LP blocks, so a
committed coal tranche can idle to zero instead of holding a must-run floor.
This probe adds binary commitment and a generic minimum-stable level to the
thermal blocks, prices the committed schedule (solve the MIP, fix the binaries,
re-solve the LP for the balance duals, the standard dispatch-based pricing an
ISO uses), and scores the resulting hourly prices against the observed LWAP and
MCP exactly as the shipped backcast does.

The minimum-stable levels are GENERIC, labeled: NREL ATB / typical thermal
values applied at the fuel-block level (no public per-PH-unit registry; that is
the item-2 path). RTDSL is archived and carries per-resource MIN/MAX operating
limits, but its resources are coded and most floors are VRE self-schedule pins
(MIN==MAX), so it does not de-fabricate thermal min-stable at the fleet level
without a unit registry; the generic levels stay the labeled input, RTDSL is
noted as examined.

The engine is NOT changed. This is the Phase-A measurement the roadmap requires
before any swap: if commitment worsens the price backcast, the LP stays the
default and the number is the finding.

    python3 pipeline/uc_probe.py --derive   # remeasure, write the finding
    python3 pipeline/uc_probe.py            # print the delta table
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
OUT = os.path.join(HERE, "..", "data", "derived", "uc_probe.json")

# generic minimum-stable fraction of block capacity when committed, from NREL
# ATB / typical thermal operating ranges; applied at the fuel-block level and
# LABELED generic. Fuels absent here (wind, solar, hydro, offer) stay fully
# flexible with no commitment.
MIN_STABLE = {
    "coal": 0.40,
    "natural_gas": 0.30,
    "geothermal": 0.85,
    "oil": 0.40,
    "biomass": 0.50,
}
# a small overgeneration (curtailment) penalty so hours whose must-run floor
# exceeds load price near zero instead of going infeasible, matching the
# observed deep off-peak collapses
OVERGEN_PENALTY = 0.001


def _uc_text(m: dict, fixed: dict | None = None) -> str:
    """The commitment model text. fixed=None emits the MILP (binary section);
    fixed={varname: 0/1} emits the LP with the commitments pinned, whose balance
    duals are the committed-schedule prices."""
    stacks, demand, caps = m["stacks"], m["demand"], m["caps"]
    wheel_m, voll_m = micro(m["wheel"]), micro(m["voll"])
    H = len(demand["luzon"])
    obj, rows, bounds, binaries = [], [], [], []

    eps = 0
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            for i, b in enumerate(stacks[g][h]):
                eps += 1
                obj.append(f" + {mtext(micro(b['cost']) + eps)} x_{s}_{h}_{i}")
                bounds.append(f" 0 <= x_{s}_{h}_{i} <= {mtext(micro(b['mw']))}")
                # committable thermal block: a binary gate plus a min-stable floor
                if b["fuel"] in MIN_STABLE and b["mw"] > 0:
                    u = f"u_{s}_{h}_{i}"
                    ms = micro(MIN_STABLE[b["fuel"]] * b["mw"])
                    cap = micro(b["mw"])
                    rows.append(f" cg_{s}_{h}_{i}: x_{s}_{h}_{i}"
                                f" - {mtext(cap)} {u} <= 0.0")
                    rows.append(f" ms_{s}_{h}_{i}: x_{s}_{h}_{i}"
                                f" - {mtext(ms)} {u} >= 0.0")
                    if fixed is None:
                        binaries.append(f" {u}")
                    else:
                        bounds.append(f" {u} = {fixed[u]}")

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
            bounds.append(
                f" 0 <= u_load_{s}_{h} <= {mtext(micro(demand[g][h]))}")
            # overgeneration slack absorbs must-run beyond load
            obj.append(f" + {mtext(micro(OVERGEN_PENALTY))} o_{s}_{h}")
            bounds.append(f" 0 <= o_{s}_{h} <= {mtext(micro(1e6))}")

    flow_terms = {
        "luzon": [("f1n", "+"), ("f1p", "-")],
        "visayas": [("f1p", "+"), ("f1n", "-"), ("f2n", "+"), ("f2p", "-")],
        "mindanao": [("f2p", "+"), ("f2n", "-")],
    }
    for h in range(H):
        for g in GRID_KEYS:
            s = G_SHORT[g]
            terms = [f" + x_{s}_{h}_{i}" for i in range(len(stacks[g][h]))]
            for name, sign in flow_terms[g]:
                terms.append(f" {sign} {name}_{h}")
            terms.append(f" + u_load_{s}_{h}")
            terms.append(f" - o_{s}_{h}")
            rows.append(f" bal_{s}_{h}:" + "".join(terms)
                        + f" = {mtext(micro(demand[g][h]))}")

    text = ("\\ uc probe\nminimize\n obj:" + "".join(obj) + "\n"
            "subject to\n" + "\n".join(rows) + "\n"
            "bounds\n" + "\n".join(bounds) + "\n")
    if binaries:
        text += "binary\n" + "\n".join(binaries) + "\n"
    return text + "end\n"


def run_chronology_uc(dispatch: dict, profiles: dict, date: str,
                      opts: dict | None = None) -> dict:
    """Two-stage commitment: solve the MIP for the schedule, fix the binaries,
    re-solve the LP for the balance-dual prices. Output carries hourly prices
    the same way run_chronology_lp does, for the backcast scorer."""
    m = _assemble(dispatch, profiles, date, opts or {})
    mip = _highs_solve(_uc_text(m, None))
    fixed = {k: round(v) for k, v in mip["cols"].items() if k.startswith("u_")
             and not k.startswith("u_load_")}
    lp = _highs_solve(_uc_text(m, fixed))
    duals = lp["duals"]
    hours = []
    H = len(m["demand"]["luzon"])
    for h in range(H):
        price = {g: round3(duals.get(f"bal_{G_SHORT[g]}_{h}", 0.0))
                 for g in GRID_KEYS}
        hours.append({"hour": h, "price": price})
    committed = sum(fixed.values())
    return {"hours": hours, "committed_blocks": committed,
            "lp_sha256": hashlib.sha256(
                _uc_text(m, None).encode()).hexdigest()}


def _backcast_pairs(dispatch: dict, profiles: dict, use_uc: bool) -> dict:
    """(modeled, observed) price pairs per grid over the full-coverage days,
    against LWAP (settlement) and MCP (ex-ante clear), scored like the shipped
    backcast. use_uc picks the commitment engine or the LP."""
    from lp_dispatch import run_chronology_lp
    pairs = {g: [] for g in GRID_KEYS}
    pairs_mcp = {g: [] for g in GRID_KEYS}
    for day in profiles["days"]:
        if not day["market"]:
            continue
        lw = day.get("lwap") or {}
        if not all(len(lw.get(g) or []) == 24
                   and all(v is not None for v in lw[g]) for g in GRID_KEYS):
            continue
        res = (run_chronology_uc(dispatch, profiles, day["date"])
               if use_uc else
               run_chronology_lp(dispatch, profiles, day["date"], {}))
        mc = day.get("mcp") or {}
        for g in GRID_KEYS:
            for h in range(24):
                pairs[g].append((res["hours"][h]["price"][g], lw[g][h]))
            mg = mc.get(g) or []
            if len(mg) == 24 and all(v is not None for v in mg):
                for h in range(24):
                    pairs_mcp[g].append((res["hours"][h]["price"][g], mg[h]))
    return {"lwap": {g: _score_pairs(pairs[g]) for g in GRID_KEYS},
            "mcp": {g: _score_pairs(pairs_mcp[g]) for g in GRID_KEYS}}


def derive(dispatch: dict, profiles: dict) -> dict:
    lp = _backcast_pairs(dispatch, profiles, use_uc=False)
    uc = _backcast_pairs(dispatch, profiles, use_uc=True)

    def corr(block, g):
        v = block[g]
        return v.get("correlation") if v else None

    deltas = {}
    for tgt in ("lwap", "mcp"):
        deltas[tgt] = {}
        for g in GRID_KEYS:
            cl, cu = corr(lp[tgt], g), corr(uc[tgt], g)
            deltas[tgt][g] = {
                "lp_corr": cl, "uc_corr": cu,
                "delta": round3(cu - cl) if (cl is not None
                                             and cu is not None) else None}
    # the verdict: commitment must beat the LP on the Luzon LWAP correlation
    # (the deepest market) to justify a swap; otherwise the LP stays default
    lz = deltas["lwap"]["luzon"]
    improves = (lz["delta"] is not None and lz["delta"] > 0.0)
    return {
        "generated_by": "pipeline/uc_probe.py",
        "min_stable_generic": MIN_STABLE,
        "min_stable_label": "generic NREL ATB / typical thermal, fuel-block "
                            "level; RTDSL examined but VRE-pinned and coded, "
                            "no thermal de-fabrication without a unit registry",
        "overgen_penalty_php_kwh": OVERGEN_PENALTY,
        "lp": lp, "uc": uc, "corr_delta": deltas,
        "verdict": ("commitment improves the Luzon LWAP correlation"
                    if improves else
                    "commitment does not improve the price backcast; the LP "
                    "stays the default engine"),
        "engine_default": "uc" if improves else "lp",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    args = ap.parse_args()
    dispatch = json.load(open(os.path.join(HERE, "..", "web", "data",
                                           "dispatch.json")))
    profiles = json.load(open(os.path.join(HERE, "..", "web", "data",
                                            "profiles.json")))
    out = derive(dispatch, profiles)
    if args.derive:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(out, f, indent=2)
        print(f"wrote {OUT}")
    d = out["corr_delta"]
    print("\nprice-correlation, LP vs unit commitment (higher is better):")
    print(f"{'target/grid':22s}{'LP':>8s}{'UC':>8s}{'delta':>8s}")
    for tgt in ("lwap", "mcp"):
        for g in GRID_KEYS:
            r = d[tgt][g]
            lp = "None" if r["lp_corr"] is None else f"{r['lp_corr']:.3f}"
            uc = "None" if r["uc_corr"] is None else f"{r['uc_corr']:.3f}"
            dl = "None" if r["delta"] is None else f"{r['delta']:+.3f}"
            print(f"{tgt+'/'+g:22s}{lp:>8s}{uc:>8s}{dl:>8s}")
    print("\nverdict:", out["verdict"])


if __name__ == "__main__":
    main()
