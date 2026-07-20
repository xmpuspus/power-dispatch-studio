#!/usr/bin/env python3
"""Reduced-backbone DC power flow + DC-OPF over the real (OSM) grid geometry,
validated against the market's own record.

What this is: the honest tier of nodal modeling that public data supports.
NGCP's actual network model (impedances, ratings) is distributed to WESM
members only, so this module builds a REDUCED backbone from the OSM geometry
(data/raw/OSMGRID via grid_geometry.py) with class-typical reactances scaled
by real routed length, class-default ratings overridden by observed operating
limits (RTDCV BINDING_LIMIT where the equipment matched, HVDC observed
limits), and observed injections from the derived nodal dailies
(data/derived/nodal_daily/, DIPCEF per-node scheduled MW). Every estimated
number is labeled estimated; every observed number carries its source.

Two solves per validation hour, both B-theta linear programs on HiGHS
(highspy, the same solver the day LP uses; this module is pipeline-only and
never touches the byte-parity day-LP text):

  replay  observed injections, flows free: where does the observed dispatch
          load the network? Validation: the most-loaded branches should
          include the equipment RTDCV says actually bound.
  opf     re-dispatch within each unit's observed-day capability at
          grid-fuel proxy costs, flows capped at ratings: nodal LMPs from
          the bus-balance duals. Validation: regional means vs the observed
          regional SMPs; the binding set vs RTDCV. The published nodal
          LMP_CONGESTION column is zero through the market suspension window
          and small and intermittent afterward (1.18 percent of
          clean-day node-hours), so within-region modeled congestion has no
          reliable like-for-like observed target; the replay's binding-set
          match is the defensible test.

    python3 pipeline/nodal_dcopf.py --day 2026-05-20
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

from grid_geometry import Graph, _station_index, km, load_features

HERE = os.path.dirname(os.path.abspath(__file__))
NODAL_DIR = os.path.join(HERE, "..", "data", "derived", "nodal_daily")
RAW = os.path.join(HERE, "..", "data", "raw")
OUT_PATH = os.path.join(HERE, "..", "data", "derived", "nodal_dcopf.json")

S_BASE_MVA = 100.0

# Class-typical series reactance per km (ohm/km) and per-circuit thermal
# ratings (MW). ESTIMATES: standard overhead-line engineering values for
# these voltage classes (bundled 500 kV EHV lines around 0.28 ohm/km,
# single-conductor 230/138 kV around 0.45-0.50; submarine XLPE cable
# reactance is far lower). Ratings are conservative class defaults and are
# overridden by observed operating limits wherever RTDCV named the
# equipment (BINDING_LIMIT) or the corridor has an observed HVDC limit.
X_OHM_KM = {"ac500": 0.28, "ac230": 0.48, "ac138": 0.50, "cable": 0.12}
RATING_MW = {"ac500": 1400.0, "ac230": 400.0, "ac138": 120.0, "cable": 400.0}
KV = {"ac500": 500.0, "ac230": 230.0, "ac138": 138.0, "cable": 230.0}

# Observed HVDC operating limits (chokepoints, primary-sourced): Leyte-Luzon
# 250 MW Luzon-import limit; MVIP 450 MW design capacity.
HVDC_CAP_MW = {"leyte": 250.0, "mvip": 450.0}


def _hvdc_cap(name: str | None, lat: float) -> float:
    n = (name or "").lower()
    if "leyte" in n or "luzon" in n or lat > 11.5:
        return HVDC_CAP_MW["leyte"]
    return HVDC_CAP_MW["mvip"]


def build_network() -> dict:
    """Buses, AC branches, and HVDC links from the OSM pull, with per-branch
    x (pu on 100 MVA) and rating. Parallel circuits between the same bus
    pair combine (x halves, rating doubles)."""
    lines, subs = load_features()
    graph = Graph(lines, subs)
    branches: dict[tuple[str, str, str], dict] = {}
    hvdc: list[dict] = []
    seen_hvdc: set[tuple[str, str]] = set()
    for u, nbrs in graph.adj.items():
        for v, li, w in nbrs:
            if u >= v:
                continue
            ln = lines[li]
            kind = ln["kind"]
            if kind == "hvdc":
                pair = (u, v)
                if pair not in seen_hvdc:
                    seen_hvdc.add(pair)
                    lat = float(u.split(",")[1])
                    hvdc.append(
                        {
                            "a": u,
                            "b": v,
                            "name": ln.get("name"),
                            "cap_mw": _hvdc_cap(ln.get("name"), lat),
                            "osm_ids": [ln["osm_id"]],
                        }
                    )
                continue
            key = (u, v, kind)
            x_pu = X_OHM_KM[kind] * max(w, 0.5) / (KV[kind] ** 2 / S_BASE_MVA)
            ncirc = 1
            try:
                ncirc = max(1, int((ln.get("circuits") or "1").split(";")[0]))
            except ValueError:
                pass
            b = branches.get(key)
            if b is None:
                branches[key] = {
                    "a": u,
                    "b": v,
                    "kind": kind,
                    "km": round(w, 1),
                    "x_pu": x_pu / ncirc,
                    "rating_mw": RATING_MW[kind] * ncirc,
                    "rating_src": "class-default",
                    "osm_ids": [ln["osm_id"]],
                    "names": [ln["name"]] if ln.get("name") else [],
                }
            else:
                # a parallel circuit mapped as its own way
                b["x_pu"] = 1.0 / (1.0 / b["x_pu"] + 1.0 / (x_pu / ncirc))
                b["rating_mw"] += RATING_MW[kind] * ncirc
                b["osm_ids"].append(ln["osm_id"])
                if ln.get("name") and ln["name"] not in b["names"]:
                    b["names"].append(ln["name"])
    # connected components over AC branches + HVDC (HVDC joins islands
    # electrically but not synchronously; components are AC-only)
    adj_ac: dict[str, set[str]] = defaultdict(set)
    for b in branches.values():
        adj_ac[b["a"]].add(b["b"])
        adj_ac[b["b"]].add(b["a"])
    comp_of: dict[str, int] = {}
    comps: list[set[str]] = []
    for start in adj_ac:
        if start in comp_of:
            continue
        stack, comp = [start], set()
        while stack:
            u = stack.pop()
            if u in comp_of:
                continue
            comp_of[u] = len(comps)
            comp.add(u)
            stack.extend(adj_ac[u])
        comps.append(comp)
    # name the three grids by anchor substations resolved onto components
    index = _station_index(subs)
    anchors = {"luzon": "nagsaag", "visayas": "cebu", "mindanao": "davao"}
    grid_of_comp: dict[int, str] = {}
    for g, tok in anchors.items():
        for n, i in index:
            if n.startswith(tok):
                node = graph.node_of_sub.get(i)
                if node in comp_of:
                    grid_of_comp[comp_of[node]] = g
                    break
    buses = []
    bus_grid: dict[str, str] = {}
    for node in adj_ac:
        cid = comp_of[node]
        g = grid_of_comp.get(cid)
        if g is None:
            continue  # off-grid islet (Palawan-class); not in WESM
        lon, lat = map(float, node.split(","))
        buses.append({"id": node, "lon": lon, "lat": lat, "grid": g})
        bus_grid[node] = g
    kept = set(bus_grid)

    def bridge(node: str) -> str | None:
        """HVDC converter nodes often hang off hvdc-kind edges only and so
        sit on no AC component; snap them to the nearest kept AC bus (the
        converter stations stand beside their AC substations)."""
        if node in kept:
            return node
        pt = [float(x) for x in node.split(",")]
        best, bestd = None, 20.0
        for b in kept:
            d = km(pt, [float(x) for x in b.split(",")])
            if d < bestd:
                best, bestd = b, d
        return best

    kept_hvdc = []
    for link in hvdc:
        a, b = bridge(link["a"]), bridge(link["b"])
        if a and b and a != b:
            kept_hvdc.append({**link, "a": a, "b": b})
    return {
        "buses": buses,
        "branches": [b for b in branches.values() if b["a"] in kept and b["b"] in kept],
        "hvdc": kept_hvdc,
        "graph": graph,
        "subs": subs,
        "index": index,
        "n_components_dropped": len(comps) - len(grid_of_comp),
    }


# --- observed injections: DIPCEF resource codes -> buses ---------------------
# Resolution lives in pipeline/resource_locate.py (OSM substations, OSM
# plants, the named-generator layer, DOE municipality centroids; region
# gated, ambiguity is a miss). This wrapper keeps the bus-only contract the
# solver needs and reports the resolved-MW scoreboard.


def map_resources(day: dict, net: dict) -> tuple[dict, dict]:
    """Resolve each DIPCEF resource to a network bus.

    Returns (res -> bus id, stats); stats carry resolved MW share per grid
    (the public scoreboard)."""
    from resource_locate import resolve_all

    locs, stats = resolve_all(day, net)
    res_bus = {res: loc["bus"] for res, loc in locs.items()}
    # legacy fields some callers report
    stats["resolved_mw_share"] = stats.pop("mw_share")
    return res_bus, stats


def map_resources_full(day: dict, net: dict) -> tuple[dict, dict]:
    """Full location records (lon/lat/src/label/bus) plus the scoreboard."""
    from resource_locate import resolve_all

    return resolve_all(day, net)


def hour_injections(day: dict, res_bus: dict, net: dict, hour: int) -> dict[str, float]:
    """Bus -> net MW at the hour. Resolved resources land on their buses;
    each grid's UNRESOLVED tail spreads across that grid's resolved load
    buses pro-rata, keeping the grid's observed net position (losses +
    inter-island exchange) intact for the LP's HVDC variables and slack
    to absorb."""
    inj: dict[str, float] = defaultdict(float)
    grid_unres: dict[str, float] = defaultdict(float)
    grid_load: dict[str, dict[str, float]] = defaultdict(dict)
    for res, nd in day["nodes"].items():
        mw = nd["mw"][hour]
        if not mw:
            continue
        bus = res_bus.get(res)
        if bus is None:
            grid_unres[nd["grid"]] += mw
            continue
        inj[bus] += mw
        if mw < 0:
            grid_load[nd["grid"]][bus] = grid_load[nd["grid"]].get(bus, 0) + mw
    for g, extra in grid_unres.items():
        loads = grid_load[g]
        tot = sum(loads.values())
        if not loads or not tot:
            continue
        for b, lmw in loads.items():
            inj[b] += extra * (lmw / tot)
    return dict(inj)


# --- B-theta linear programs on HiGHS ----------------------------------------


def _islands(net: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for b in net["buses"]:
        out[b["grid"]].append(b["id"])
    return out


def solve_hour(
    net: dict,
    inj: dict[str, float],
    mode: str,
    gens: list[dict] | None = None,
    slack_cost: float = 50000.0,
) -> dict | None:
    """One B-theta LP. mode='replay': injections fixed, flows free, HVDC +
    per-island slack absorb exchange and losses. mode='opf': gen dispatch
    variable at proxy costs, flows capped at ratings; bus-balance duals are
    the nodal prices (PhP/MWh)."""
    import highspy

    buses = [b["id"] for b in net["buses"]]
    nbus = {b: i for i, b in enumerate(buses)}
    branches = net["branches"]
    hvdc = net["hvdc"]
    islands = _islands(net)

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    inf = highspy.kHighsInf

    # variables: theta per bus, flow per hvdc link, slack+/- per island,
    # then (opf) one dispatch var per gen
    col_cost, col_lo, col_up = [], [], []

    def add_col(cost, lo, up):
        col_cost.append(cost)
        col_lo.append(lo)
        col_up.append(up)
        return len(col_cost) - 1

    th = {b: add_col(0.0, -inf, inf) for b in buses}
    for g, members in islands.items():
        ref = min(members)
        col_lo[th[ref]] = col_up[th[ref]] = 0.0
    fv = {i: add_col(0.001, -lk["cap_mw"], lk["cap_mw"]) for i, lk in enumerate(hvdc)}
    sp = {g: add_col(slack_cost, 0.0, inf) for g in islands}
    sn = {g: add_col(slack_cost, 0.0, inf) for g in islands}
    gv = {}
    ue = {}
    us = {}
    if mode == "opf":
        for k, gen in enumerate(gens or []):
            gv[k] = add_col(gen["cost_mwh"], 0.0, gen["cap_mw"])
        # per-bus unserved energy (supply of last resort) and surplus
        # absorption (forced curtailment), both at the slack cost: a load
        # pocket isolated behind a binding limit prices at the cap instead
        # of going infeasible, and a fixed-injection surplus curtails
        # instead of blowing the dual to -cap (the island slack sits at the
        # reference bus and cannot reach across a binding line)
        for b in buses:
            ue[b] = add_col(slack_cost, 0.0, inf)
            us[b] = add_col(slack_cost, 0.0, inf)

    # rows: bus balance (=inj or =load), then (opf) branch flow limits
    rows = []  # (lo, up, [(col, coef), ...])
    ref_of = {g: min(m) for g, m in islands.items()}
    entries: dict[int, dict[int, float]] = defaultdict(dict)

    def put(r, c, v):
        entries[r][c] = entries[r].get(c, 0.0) + v

    for b in buses:
        rows.append([inj.get(b, 0.0), inj.get(b, 0.0)])
    for li, br in enumerate(branches):
        ra, rb = nbus[br["a"]], nbus[br["b"]]
        bsus = S_BASE_MVA / br["x_pu"]  # MW per rad
        put(ra, th[br["a"]], bsus)
        put(ra, th[br["b"]], -bsus)
        put(rb, th[br["b"]], bsus)
        put(rb, th[br["a"]], -bsus)
    for i, lk in enumerate(hvdc):
        put(nbus[lk["a"]], fv[i], 1.0)  # flow a->b leaves a
        put(nbus[lk["b"]], fv[i], -1.0)
    for g in islands:
        r = nbus[ref_of[g]]
        put(r, sp[g], -1.0)
        put(r, sn[g], 1.0)
    if mode == "opf":
        for k, gen in enumerate(gens or []):
            put(nbus[gen["bus"]], gv[k], -1.0)
        for b in buses:
            put(nbus[b], ue[b], -1.0)
            put(nbus[b], us[b], 1.0)
        for br in branches:
            r = len(rows)
            rows.append([-br["rating_mw"], br["rating_mw"]])
            bsus = S_BASE_MVA / br["x_pu"]
            put(r, th[br["a"]], bsus)
            put(r, th[br["b"]], -bsus)

    ncol = len(col_cost)
    astart, aindex, avalue = [0], [], []
    # build column-wise from row entries
    bycol: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for r, cols in entries.items():
        for c, v in cols.items():
            bycol[c].append((r, v))
    for c in range(ncol):
        for r, v in sorted(bycol.get(c, [])):
            aindex.append(r)
            avalue.append(v)
        astart.append(len(aindex))
    lp = highspy.HighsLp()
    lp.num_col_ = ncol
    lp.num_row_ = len(rows)
    lp.col_cost_ = col_cost
    lp.col_lower_ = col_lo
    lp.col_upper_ = col_up
    lp.row_lower_ = [r[0] for r in rows]
    lp.row_upper_ = [r[1] for r in rows]
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = astart
    lp.a_matrix_.index_ = aindex
    lp.a_matrix_.value_ = avalue
    h.passModel(lp)
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return None
    sol = h.getSolution()
    theta = {b: sol.col_value[th[b]] for b in buses}
    flows = []
    for br in branches:
        f = (theta[br["a"]] - theta[br["b"]]) * S_BASE_MVA / br["x_pu"]
        flows.append(round(f, 1))
    out = {
        "flows_mw": flows,
        "hvdc_mw": [round(sol.col_value[fv[i]], 1) for i in fv],
        "slack_mw": {
            g: round(sol.col_value[sp[g]] - sol.col_value[sn[g]], 1) for g in islands
        },
    }
    if mode == "opf":
        # HiGHS reports the equality-row dual with the opposite sign to the
        # marginal value of injection (pinned by the 2-bus toy: cheapest-gen
        # cost comes back negated), so the LMP is the negated dual
        out["lmp_mwh"] = {b: round(-sol.row_dual[nbus[b]], 2) for b in buses}
        out["gen_mw"] = {k: round(sol.col_value[c], 1) for k, c in gv.items()}
        out["unserved_mw"] = round(sum(sol.col_value[c] for c in ue.values()), 1)
    return out


# --- day runner + validation --------------------------------------------------


def _load_day(date: str) -> dict:
    p = os.path.join(NODAL_DIR, f"NODALD_{date.replace('-', '')}.json")
    with open(p) as f:
        return json.load(f)


def _rtdcv_day(date: str) -> dict[str, int]:
    """Observed binding equipment that day -> interval count (RTDCV)."""
    import csv

    p = os.path.join(RAW, "RTDCV", f"RTDCV_{date.replace('-', '')}.csv")
    out: dict[str, int] = defaultdict(int)
    if not os.path.isfile(p):
        return out
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            name = (r.get("EQUIPMENT_NAME") or "").strip()
            if name:
                out[name] += 1
    return dict(out)


def observed_limits() -> dict[str, float]:
    """Max observed BINDING_LIMIT per equipment across the whole archived
    RTDCV/DAPCV window: the operator's own operating limit for that
    equipment, the truth layer over the class-default ratings."""
    import csv
    import glob

    out: dict[str, float] = defaultdict(float)
    for key in ("RTDCV", "DAPCV"):
        for path in sorted(glob.glob(os.path.join(RAW, key, "*.csv"))):
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                for r in csv.DictReader(f):
                    name = (r.get("EQUIPMENT_NAME") or "").strip()
                    try:
                        lim = float(r.get("BINDING_LIMIT") or 0)
                    except ValueError:
                        continue
                    if name and lim > 0:
                        out[name] = max(out[name], lim)
    return dict(out)


def _gens_for_opf(day: dict, res_bus: dict) -> list[dict]:
    """One dispatchable unit per resolved GEN resource: capability = max
    observed MW that day, cost = the grid-fuel proxy from the baked merit
    order (PhP/MWh), unclassified fuels at the grid median."""
    from offers import classify_fuel

    dispatch_path = os.path.join(HERE, "..", "web", "data", "dispatch.json")
    with open(dispatch_path) as f:
        merit = json.load(f)["merit_order"]
    fuel_cost: dict[tuple[str, str], float] = {}
    grid_median: dict[str, float] = {}
    for g, mo in merit.items():
        costs = []
        for blk in mo["blocks"]:
            fuel_cost[(g, blk["fuel"])] = blk["cost"] * 1000.0
            costs.append(blk["cost"] * 1000.0)
        costs.sort()
        grid_median[g] = costs[len(costs) // 2] if costs else 5000.0
    gens = []
    for res, nd in day["nodes"].items():
        bus = res_bus.get(res)
        if bus is None:
            continue
        cap = max((v for v in nd["mw"] if v), default=0.0)
        if cap <= 1.0:
            continue  # load node or dormant unit
        g = nd["grid"]
        fuel = classify_fuel(res)
        cost = fuel_cost.get((g, fuel), grid_median[g])
        gens.append(
            {
                "res": res,
                "bus": bus,
                "cap_mw": round(cap, 1),
                "cost_mwh": round(cost, 1),
                "fuel": fuel,
            }
        )
    return gens


def _loads_only(
    day: dict, res_bus: dict, net: dict, hour: int
) -> tuple[dict[str, float], dict[str, float]]:
    """OPF injections: observed loads only, as fixed negative MW; every
    megawatt of generation stays dispatchable. Unresolved LOAD spreads
    over the grid's resolved load buses pro-rata; unresolved GENERATION
    is returned per grid so run_day can hand it to the solver as
    dispatchable aggregate units on the grid's known plant buses (mixing
    it into fixed injections forces surpluses the re-dispatch cannot
    move)."""
    inj: dict[str, float] = defaultdict(float)
    unres_load: dict[str, float] = defaultdict(float)
    unres_gen: dict[str, float] = defaultdict(float)
    grid_load: dict[str, dict[str, float]] = defaultdict(dict)
    for res, nd in day["nodes"].items():
        mw = nd["mw"][hour]
        if not mw:
            continue
        bus = res_bus.get(res)
        if bus is None:
            if mw < 0:
                unres_load[nd["grid"]] += mw
            else:
                unres_gen[nd["grid"]] += mw
            continue
        if mw < 0:
            inj[bus] += mw
            grid_load[nd["grid"]][bus] = grid_load[nd["grid"]].get(bus, 0) + mw
    for g, extra in unres_load.items():
        loads = grid_load[g]
        tot = sum(loads.values())
        if not loads or not tot:
            continue
        for b, lmw in loads.items():
            inj[b] += extra * (lmw / tot)
    return dict(inj), dict(unres_gen)


def run_day(date: str) -> dict:
    net = build_network()
    day = _load_day(date)
    res_bus, res_stats = map_resources(day, net)
    branches = net["branches"]

    # equipment RTDCV says bound that day, pinned to branch geometry with
    # the same matcher the map layer uses (line-feature hits bridge to the
    # combined branches through their osm ids)
    from build_data import build_congestion
    from grid_geometry import match_equipment

    graph = net["graph"]
    cong = build_congestion()
    line_hits, sub_hits, _report = match_equipment(
        cong["league_full"], graph.lines, net["subs"], graph
    )
    osm_to_branch = {oid: bi for bi, br in enumerate(branches) for oid in br["osm_ids"]}
    eq_branches: dict[str, set[int]] = defaultdict(set)
    for li, hits in line_hits.items():
        bi = osm_to_branch.get(graph.lines[li]["osm_id"])
        if bi is None:
            continue
        for hit in hits:
            eq_branches[hit["equipment"]].add(bi)
    station_eq = {hit["equipment"] for hits in sub_hits.values() for hit in hits}
    # the operator's own operating limits, where the equipment matched:
    # authoritative over class defaults, in either direction
    limits = observed_limits()
    rated_observed = 0
    for eq, bis in eq_branches.items():
        lim = limits.get(eq)
        if not lim:
            continue
        for bi in bis:
            branches[bi]["rating_mw"] = round(lim, 1)
            branches[bi]["rating_src"] = "observed-rtdcv"
            rated_observed += 1
    observed = _rtdcv_day(date)

    hours = list(range(24))
    replay_load = [[0.0] * len(branches) for _ in hours]
    slack_series = []
    for hr in hours:
        inj = hour_injections(day, res_bus, net, hr)
        sol = solve_hour(net, inj, "replay")
        if sol is None:
            continue
        for bi, f in enumerate(sol["flows_mw"]):
            replay_load[hr][bi] = abs(f) / branches[bi]["rating_mw"]
        slack_series.append(sol["slack_mw"])

    peak = [max(replay_load[hr][bi] for hr in hours) for bi in range(len(branches))]
    ranked = sorted(range(len(branches)), key=lambda bi: -peak[bi])
    top = [
        {
            "names": branches[bi]["names"] or [branches[bi]["kind"]],
            "kind": branches[bi]["kind"],
            "km": branches[bi]["km"],
            "rating_mw_est": branches[bi]["rating_mw"],
            "peak_loading": round(peak[bi], 3),
        }
        for bi in ranked[:15]
    ]

    # the defensible test: for each piece of equipment RTDCV says bound
    # that day, where does its branch sit in the modeled loading ranking?
    rank_of = {bi: r for r, bi in enumerate(ranked)}
    binder_check = []
    for eq, n_int in sorted(observed.items(), key=lambda kv: -kv[1]):
        row = {"equipment": eq, "rtd_intervals": n_int}
        if eq in eq_branches:
            bis = eq_branches[eq]
            best = min(rank_of[bi] for bi in bis)
            row["modeled"] = {
                "peak_loading": round(max(peak[bi] for bi in bis), 3),
                "rank": best + 1,
                "rank_pctile": round(100 * (1 - best / len(branches)), 1),
            }
        elif eq in station_eq:
            row["modeled"] = (
                "station constraint (transformer): outside the branch model"
            )
        else:
            row["modeled"] = "equipment not matched to geometry"
        binder_check.append(row)

    # ratings for the OPF: class defaults, raised wherever the observed
    # replay flow exceeded them. A line cannot be rated below what the
    # observed dispatch visibly carried, so the replay self-calibrates the
    # floors (class defaults badly under-rate multi-circuit delivery
    # corridors); the binder ranking above stays on raw class ratings,
    # where only the RELATIVE ordering is used.
    raised = 0
    for bi, br in enumerate(branches):
        if br.get("rating_src") == "observed-rtdcv":
            continue
        pk = max(abs(replay_load[hr][bi]) * br["rating_mw"] for hr in hours)
        if pk > br["rating_mw"]:
            br["rating_mw"] = round(1.05 * pk, 1)
            br["rating_src"] = "replay-floor"
            raised += 1

    # opf at a midday hour + the evening peak
    gens = _gens_for_opf(day, res_bus)
    # the unresolved generation tail becomes dispatchable aggregate units
    # split across the grid's RESOLVED gen buses pro-rata to their observed
    # capability (geography follows the known plants; a stated approximation)
    from statistics import median

    gen_cap_by_bus: dict[str, dict[str, float]] = defaultdict(dict)
    grid_costs: dict[str, list[float]] = defaultdict(list)
    bus_grid_of = {b["id"]: b["grid"] for b in net["buses"]}
    for gen in gens:
        g = bus_grid_of[gen["bus"]]
        gen_cap_by_bus[g][gen["bus"]] = (
            gen_cap_by_bus[g].get(gen["bus"], 0) + gen["cap_mw"]
        )
        grid_costs[g].append(gen["cost_mwh"])
    opf_hours = [11, 19]
    opf_out = {}
    for hr in opf_hours:
        inj, unres_gen = _loads_only(day, res_bus, net, hr)
        hour_gens = list(gens)
        for g, mw_avail in unres_gen.items():
            caps = gen_cap_by_bus.get(g)
            if not caps or mw_avail <= 0:
                continue
            tot = sum(caps.values())
            cost = median(grid_costs[g]) if grid_costs[g] else 5000.0
            for b, share in caps.items():
                hour_gens.append(
                    {
                        "res": f"unresolved-{g}",
                        "bus": b,
                        "cap_mw": round(1.15 * mw_avail * share / tot, 1),
                        "cost_mwh": round(cost, 1),
                        "fuel": "aggregate",
                    }
                )
        sol = solve_hour(net, inj, "opf", gens=hour_gens)
        if sol is None:
            continue
        lmps = sol["lmp_mwh"]
        by_grid: dict[str, list[float]] = defaultdict(list)
        bus_grid = {b["id"]: b["grid"] for b in net["buses"]}
        for b, v in lmps.items():
            by_grid[bus_grid[b]].append(v)
        gstats = {}
        for g, vs in by_grid.items():
            vs.sort()
            n = len(vs)
            obs = day["regions"].get(g, {}).get("smp_php_kwh", [None] * 24)[hr]
            gstats[g] = {
                "modeled_mean_mwh": round(sum(vs) / n, 1),
                "modeled_p5_mwh": round(vs[int(0.05 * n)], 1),
                "modeled_p95_mwh": round(vs[int(0.95 * n)], 1),
                "observed_smp_mwh": round(obs * 1000, 1) if obs else None,
            }
        binding = [
            {
                "names": branches[bi]["names"] or [branches[bi]["kind"]],
                "kind": branches[bi]["kind"],
                "flow_mw": sol["flows_mw"][bi],
                "rating_mw_est": branches[bi]["rating_mw"],
            }
            for bi in range(len(branches))
            if abs(sol["flows_mw"][bi]) >= 0.999 * branches[bi]["rating_mw"]
        ]
        opf_out[str(hr)] = {
            "per_grid": gstats,
            "binding_est": binding,
            "hvdc_mw": sol["hvdc_mw"],
            "unserved_mw": sol["unserved_mw"],
            "slack_mw": sol["slack_mw"],
        }

    return {
        "date": date,
        "network": {
            "buses": len(net["buses"]),
            "branches": len(branches),
            "hvdc_links": len(net["hvdc"]),
            "components_dropped": net["n_components_dropped"],
            "note": (
                "Reduced backbone from OSM geometry; reactances are "
                "class-typical per-km values scaled by real routed "
                "length, ratings are class defaults (both labeled "
                "estimates). NGCP's actual network model is not "
                "public."
            ),
        },
        "resource_mapping": res_stats,
        "opf_ratings_raised_to_replay_flow": raised,
        "rating_provenance": {
            "observed-rtdcv": rated_observed,
            "replay-floor": raised,
            "class-default": len(branches) - rated_observed - raised,
        },
        "opf_finding": (
            "A measured probe, not a shipped price surface: at the current "
            "resource-to-bus resolution (share of MW in resource_mapping) "
            "the re-dispatch concentrates each grid's unresolved generation "
            "onto its few resolved plant buses, so modeled price LEVELS are "
            "not usable; what the probe reports is the geography (which "
            "corridors the re-dispatch pushes to their estimated limits) "
            "and the honest gap. The zonal engine remains the price model."
        ),
        "replay": {
            "top_loaded": top,
            "binder_check": binder_check,
            "slack_note": (
                "Per-island slack absorbs losses and the "
                "unresolved-injection tail; see slack_mw_series "
                "for size."
            ),
            "slack_mw_series": slack_series,
        },
        "opf": opf_out,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True, help="YYYY-MM-DD (must be derived)")
    ap.add_argument("--out", default=OUT_PATH)
    a = ap.parse_args()
    result = run_day(a.day)
    with open(a.out, "w") as f:
        json.dump(result, f, indent=1)
    slim = {k: v for k, v in result.items() if k not in ("replay", "opf")}
    print(json.dumps(slim, indent=1))
    print("top loaded (replay):")
    for t in result["replay"]["top_loaded"][:8]:
        print(f"  {t['peak_loading']:5.2f}  {t['kind']:6s} {t['names'][:2]}")
    for hr, o in result["opf"].items():
        print(f"opf h{hr}:", json.dumps(o["per_grid"], indent=1)[:400])
