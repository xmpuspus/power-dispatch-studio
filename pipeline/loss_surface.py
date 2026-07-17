#!/usr/bin/env python3
"""The loss-surface validation: can network physics predict the market's
own per-node price deviations?

WESM's published nodal record decomposes every LMP into SMP + loss +
congestion, the congestion column is zero on every sampled day, and the
SMP is region-constant per interval. So the entire within-region nodal
structure the market publishes is a LOSS surface, about a thousand
observed node-deviations per clean day. That is a validation target no
closed tool can match in public, and this module runs it nightly:

  model    marginal loss factors from the OSM-geometry network: replay the
           observed injections (DC power flow), then
           MLF_n(t) = sum_l 2 r_l f_l(t) PTDF_{l,n}, with r_l from
           class-typical resistance per km scaled by real routed length
           (labeled estimates, like the reactances)
  observe  each node's hourly deviation from its regional SMP, straight
           from the derived nodal dailies
  compare  within each grid, de-meaned (the loss-reference convention is
           an affine choice, so level and slope are fitted per grid and
           REPORTED): Spearman rank correlation across nodes, and the MAE
           after the affine fit

Everything rides the resolution scoreboard: only nodes the locator placed
on a bus enter, and the artifact says how many that is.

    python3 pipeline/loss_surface.py            # recompute over clean days
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from nodal_dcopf import (
    KV,
    S_BASE_MVA,
    build_network,
    hour_injections,
    map_resources,
    solve_hour,
)

HERE = os.path.dirname(os.path.abspath(__file__))
NODAL_DIR = os.path.join(HERE, "..", "data", "derived", "nodal_daily")
OUT_PATH = os.path.join(HERE, "..", "data", "derived", "loss_surface.json")

# Class-typical series RESISTANCE per km (ohm/km): standard overhead-line
# engineering values, ESTIMATES like the reactances (bundled 500 kV EHV
# around 0.03, single-conductor 230/138 kV higher, submarine cable low).
R_OHM_KM = {"ac500": 0.028, "ac230": 0.08, "ac138": 0.12, "cable": 0.06}
CLEAN_OK_SHARE = 0.9


def clean_days() -> list[str]:
    out = []
    for name in sorted(os.listdir(NODAL_DIR)):
        if not name.startswith("NODALD_"):
            continue
        with open(os.path.join(NODAL_DIR, name)) as f:
            d = json.load(f)
        flags = d.get("pricing_flags", {})
        tot = sum(sum(v.values()) for v in flags.values())
        ok = sum(v.get("OK", 0) for v in flags.values())
        if tot and ok / tot >= CLEAN_OK_SHARE:
            out.append(name)
    return out


def _invert(mat: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse, pure python (a few hundred rows: seconds)."""
    n = len(mat)
    aug = [
        row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(mat)
    ]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv][col]) < 1e-12:
            raise ValueError("singular reduced Laplacian")
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [v / pv for v in aug[col]]
        for r in range(n):
            if r != col and aug[r][col]:
                f = aug[r][col]
                aug[r] = [a - f * b for a, b in zip(aug[r], aug[col])]
    return [row[n:] for row in aug]


class LossModel:
    """Per-island PTDFs + branch resistances over the reduced backbone."""

    def __init__(self, net: dict):
        self.net = net
        self.branches = net["branches"]
        for br in self.branches:
            br["r_pu"] = (
                R_OHM_KM[br["kind"]]
                * max(br["km"], 0.5)
                / (KV[br["kind"]] ** 2 / S_BASE_MVA)
            )
        buses_by_grid: dict[str, list[str]] = defaultdict(list)
        for b in net["buses"]:
            buses_by_grid[b["grid"]].append(b["id"])
        self.col_of: dict[str, tuple[str, int]] = {}
        self.ptdf: dict[str, list[list[float]]] = {}
        self.rows_of: dict[str, list[int]] = {}
        for g, members in buses_by_grid.items():
            members = sorted(members)
            ref = members[0]
            keep = [m for m in members if m != ref]
            idx = {m: i for i, m in enumerate(keep)}
            n = len(keep)
            lap = [[0.0] * n for _ in range(n)]
            rows = [
                bi
                for bi, br in enumerate(self.branches)
                if br["a"] in idx or br["b"] in idx or br["a"] == ref or br["b"] == ref
            ]
            grid_rows = []
            for bi in rows:
                br = self.branches[bi]
                in_a = br["a"] in idx or br["a"] == ref
                in_b = br["b"] in idx or br["b"] == ref
                if not (in_a and in_b):
                    continue
                grid_rows.append(bi)
                bsus = 1.0 / br["x_pu"]
                for u in (br["a"], br["b"]):
                    if u in idx:
                        lap[idx[u]][idx[u]] += bsus
                if br["a"] in idx and br["b"] in idx:
                    lap[idx[br["a"]]][idx[br["b"]]] -= bsus
                    lap[idx[br["b"]]][idx[br["a"]]] -= bsus
            x = _invert(lap)
            # PTDF row per branch: (X[a,:] - X[b,:]) / x_l, ref rows zero
            pt = []
            for bi in grid_rows:
                br = self.branches[bi]
                ra = x[idx[br["a"]]] if br["a"] in idx else [0.0] * n
                rb = x[idx[br["b"]]] if br["b"] in idx else [0.0] * n
                pt.append([(a - b) / br["x_pu"] for a, b in zip(ra, rb)])
            for m in members:
                self.col_of[m] = (g, idx.get(m, -1))  # ref -> -1
            self.ptdf[g] = pt
            self.rows_of[g] = grid_rows

    def mlfs(self, flows_mw: list[float]) -> dict[str, float]:
        """Marginal loss factor per bus from an hour's branch flows."""
        out: dict[str, float] = {}
        for g, pt in self.ptdf.items():
            rows = self.rows_of[g]
            coef = [
                2.0 * self.branches[bi]["r_pu"] * flows_mw[bi] / S_BASE_MVA
                for bi in rows
            ]
            ncols = len(pt[0]) if pt else 0
            col_sums = [0.0] * ncols
            for c, row in zip(coef, pt):
                if not c:
                    continue
                for j, v in enumerate(row):
                    col_sums[j] += c * v
            for bus, (bg, j) in self.col_of.items():
                if bg != g:
                    continue
                out[bus] = col_sums[j] if j >= 0 else 0.0
        return out


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 8:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx <= 0 or syy <= 0:
        return None
    return round(sxy / (sxx * syy) ** 0.5, 3)


def build_loss_surface() -> dict:
    days = clean_days()
    if not days:
        return {"available": False, "note": "no clean nodal dailies yet"}
    net = build_network()
    model = LossModel(net)

    # per-node accumulators over the window
    obs_acc: dict[str, list[float]] = defaultdict(list)
    mod_acc: dict[str, list[float]] = defaultdict(list)
    node_grid: dict[str, str] = {}
    per_day = []
    res_bus = None
    for name in days:
        with open(os.path.join(NODAL_DIR, name)) as f:
            day = json.load(f)
        if res_bus is None:
            res_bus, _ = map_resources(day, net)
        day_obs: dict[str, list[float]] = defaultdict(list)
        day_mod: dict[str, list[float]] = defaultdict(list)
        for hr in range(24):
            inj = hour_injections(day, res_bus, net, hr)
            sol = solve_hour(net, inj, "replay")
            if sol is None:
                continue
            mlf = model.mlfs(sol["flows_mw"])
            for res, nd in day["nodes"].items():
                bus = res_bus.get(res)
                if bus is None:
                    continue
                o = nd["dev_php_kwh"][hr]
                if o is None:
                    continue
                smp = day["regions"][nd["grid"]]["smp_php_kwh"][hr]
                if smp is None:
                    continue
                # delivered-to-load orientation: injecting where delivery
                # is lossy REDUCES system losses, and that node's observed
                # price sits ABOVE its region; the sign flip makes positive
                # correlation mean agreement
                m = -mlf.get(bus, 0.0) * smp
                day_obs[res].append(o)
                day_mod[res].append(m)
                node_grid[res] = nd["grid"]
        row = {"date": day["date"]}
        for g in ("luzon", "visayas", "mindanao"):
            xs = [
                sum(v) / len(v)
                for r, v in day_mod.items()
                if node_grid.get(r) == g and v
            ]
            ys = [
                sum(v) / len(v)
                for r, v in day_obs.items()
                if node_grid.get(r) == g and v
            ]
            row[g] = _spearman(xs, ys)
        per_day.append(row)
        for r, v in day_obs.items():
            obs_acc[r].append(sum(v) / len(v))
        for r, v in day_mod.items():
            mod_acc[r].append(sum(v) / len(v))

    window = {}
    scatter = {}
    for g in ("luzon", "visayas", "mindanao"):
        rs = [r for r in obs_acc if node_grid.get(r) == g]
        xs = [sum(mod_acc[r]) / len(mod_acc[r]) for r in rs]
        ys = [sum(obs_acc[r]) / len(obs_acc[r]) for r in rs]
        n = len(rs)
        if n < 8:
            continue
        # affine fit y = a x + b (the loss-reference convention is a per-grid
        # affine choice; slope and intercept are REPORTED, not hidden)
        mx, my = sum(xs) / n, sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx > 0 else 0.0
        b = my - a * mx
        mae = sum(abs(y - (a * x + b)) for x, y in zip(xs, ys)) / n
        spread = sorted(ys)
        window[g] = {
            "n_nodes": n,
            "spearman": _spearman(xs, ys),
            "affine_slope": round(a, 3),
            "affine_intercept_php_kwh": round(b, 4),
            "mae_after_affine_php_kwh": round(mae, 4),
            "observed_p5_php_kwh": round(spread[int(0.05 * n)], 3),
            "observed_p95_php_kwh": round(spread[int(0.95 * n)], 3),
        }
        # the per-node points behind the stats: (modeled MLF deviation,
        # observed deviation) per node, for the validation figure + the
        # studio card. Both plots draw the SAME numbers the window row
        # summarises, so a viewer can see the fit, not just the correlation.
        scatter[g] = [[round(x, 4), round(y, 4)] for x, y in zip(xs, ys)]

    validated = [g for g, w in window.items() if (w["spearman"] or 0) >= 0.4]
    failing = [g for g in window if g not in validated]
    finding = (
        "Network physics ranks the market's own per-node deviations in "
        + ", ".join(validated)
        + (
            "; " + ", ".join(failing) + " fails the same test at the "
            "current resolution (suspects: resolved-MW share, inter-island "
            "exchange structure) and is reported as failing, not hidden"
            if failing
            else ""
        )
        + "."
    )
    return {
        "available": True,
        "clean_days": len(days),
        "n_nodes_compared": len(obs_acc),
        "validated_grids": validated,
        "failing_grids": failing,
        "finding": finding,
        "per_day": per_day,
        "window": window,
        "scatter": scatter,
        "assumptions": {
            "r_ohm_per_km": R_OHM_KM,
            "note": (
                "Resistances are class-typical per-km values scaled by "
                "real routed length: labeled estimates, like the "
                "reactances. MLFs come from the replay of observed "
                "injections on the reduced OSM backbone; the loss "
                "reference is a per-grid affine convention, so slope "
                "and intercept are fitted and reported."
            ),
        },
        "reading": (
            "Spearman is the claim: does network physics rank the "
            "market's own per-node deviations? MAE after the affine "
            "fit says how far each node sits from the fitted "
            "surface, in PhP/kWh."
        ),
    }


if __name__ == "__main__":
    out = build_loss_surface()
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    slim = {k: v for k, v in out.items() if k != "per_day"}
    print(json.dumps(slim, indent=1))
