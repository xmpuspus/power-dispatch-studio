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

# Announced load sites a scenario can place on the network, with the coordinate
# each one is measured from. These are campus locations, at the same precision
# as the map's data-centre pins. They are not the connection points NGCP will
# build, which are not public.
SITES = {
    "pax-silica": {
        "label": "Pax Silica ESZ, New Clark City (Capas, Tarlac)",
        "lon": 120.5340,
        "lat": 15.3200,
        "mw_range": [3000.0, 5000.0],
        "mw_src": (
            "BCDA (Bingcang) about 3 GW at full development, "
            "https://www.gmanetwork.com/news/money/economy/995915/"
            "pax-silica-ai-hub-to-consume-3-gigawatts-at-full-development-bcda/story/"
            " ; at least 5 GW, "
            "https://business.inquirer.net/596398/"
            "pax-silicas-mammoth-power-needs-draw-maharlika-foreign-interest"
        ),
        "precision": "site-precision (campus centroid, not a connection point)",
    },
}


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


def resolve_site(net: dict, lon: float, lat: float) -> dict:
    """Move a site coordinate to the nearest modelled bus. The distance is
    returned and reported rather than hidden. The reduced network only carries
    the lines OpenStreetMap knows about, so a site can sit tens of km from its
    nearest modelled bus, and a reader needs to see that before trusting
    anything built on it."""
    best = min(net["buses"], key=lambda b: km((lon, lat), (b["lon"], b["lat"])))
    return {
        "bus": best["id"],
        "grid": best["grid"],
        "bus_lon": best["lon"],
        "bus_lat": best["lat"],
        "snap_km": round(km((lon, lat), (best["lon"], best["lat"])), 1),
    }


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


_SOLAR_PROFILE: list[float] | None = None


def solar_profile() -> list[float]:
    """The baked 24-hour PH solar shape (fleet_ph.SOLAR_PROFILE via
    web/data/profiles.json). A labeled clear-sky-ish model assumption, not
    measured irradiance, so anything built on it is an optimistic bound on
    what solar delivers."""
    global _SOLAR_PROFILE
    if _SOLAR_PROFILE is None:
        path = os.path.join(HERE, "..", "web", "data", "profiles.json")
        with open(path) as f:
            _SOLAR_PROFILE = json.load(f)["solar_profile"]
    return _SOLAR_PROFILE


def _net_draw(site: dict, hour: int) -> float:
    """What the site actually pulls from the grid in this hour.

    A campus that builds its own generation still meets the network at one
    point, and what crosses that point is load minus whatever its own plant
    is producing right then. Firm embedded capacity produces around the
    clock; embedded solar follows the baked shape and is zero for eleven
    hours of it, which is the whole reason the split matters. A negative
    result means the site is sending power out."""
    solar = site.get("embedded_solar_mw", 0.0) * solar_profile()[hour]
    return site["mw"] - site.get("embedded_firm_mw", 0.0) - solar


def _plant_load(inj: dict[str, float], net: dict, bus: str, mw: float) -> dict[str, float]:
    """Add `mw` of load at `bus` and pay for it from the island's own observed
    generation, scaled pro-rata to what each bus was already producing.

    Sharing it out this way is what makes the change in flows mean anything.
    Letting the island's slack cover it would supply every added megawatt from
    the reference bus, so the route that lit up would only reflect where that
    bus happens to sit. Scaling the observed injections leaves the island's net
    position exactly as it was, so the only thing that moves is the delivery of
    the new load."""
    grid = next(b["grid"] for b in net["buses"] if b["id"] == bus)
    island = {b["id"] for b in net["buses"] if b["grid"] == grid}
    pos = {b: v for b, v in inj.items() if v > 0 and b in island}
    tot = sum(pos.values())
    out = dict(inj)
    out[bus] = out.get(bus, 0.0) - mw
    if tot > 0:
        for b, v in pos.items():
            out[b] += mw * v / tot
    return out


def _headroom_gens(
    gens: list[dict], net: dict, grid: str, mw: float, margin: float = 1.25
) -> list[dict]:
    """Capacity the island does not have on the observed day, added so the OPF
    can actually serve a multi-GW site instead of pinning every dual to the
    unserved-energy cost.

    Shared across the island's existing generation buses at the island's median
    observed cost, the same way run_day already handles generation it could not
    match to a bus. This is an assumption, and the biggest one in the scenario.
    It says the megawatts get built where megawatts already are, at today's
    median cost. It answers where the power has to travel and what the network
    does to its price. It does not answer whether anyone will build it, which
    is what the zonal engine and the DOE project list are for."""
    from statistics import median

    bus_grid = {b["id"]: b["grid"] for b in net["buses"]}
    caps: dict[str, float] = defaultdict(float)
    costs = []
    for gen in gens:
        if bus_grid[gen["bus"]] != grid:
            continue
        caps[gen["bus"]] += gen["cap_mw"]
        costs.append(gen["cost_mwh"])
    tot = sum(caps.values())
    if not tot:
        return []
    cost = round(median(costs), 1) if costs else 5000.0
    return [
        {
            "res": f"headroom-{grid}",
            "bus": b,
            "cap_mw": round(margin * mw * share / tot, 1),
            "cost_mwh": cost,
            "fuel": "headroom-assumed",
        }
        for b, share in caps.items()
    ]


def reinforce_site(net: dict, bus: str, mw: float, radius_km: float = 0.0) -> list[dict]:
    """Raise the rating of the branches around the site bus to at least `mw`,
    standing in for the dedicated connection NGCP says it is building (target
    end-2028 for New Clark City).

    radius_km = 0 reinforces only the branches touching the bus. Anything
    larger reinforces every branch with an endpoint inside that radius, which
    is what the measured behaviour calls for: upgrading only the site's own
    circuits moves the binding constraint one hop out into the corridor
    instead of clearing it.

    Deliberately crude. The real upgrade is a specific set of circuits at
    specific voltages on a route nobody has published, so anything more
    detailed would be invented. What this supports is the bounding question,
    which is how much delivery capacity over how wide an area before the load
    can actually arrive."""
    pos = {b["id"]: (b["lon"], b["lat"]) for b in net["buses"]}
    here = pos[bus]

    def near(bid: str) -> bool:
        return bid == bus or (radius_km > 0 and km(here, pos[bid]) <= radius_km)

    touched = []
    for br in net["branches"]:
        if not (near(br["a"]) or near(br["b"])):
            continue
        if br["rating_mw"] >= mw:
            continue
        touched.append(
            {
                "names": br["names"] or [br["kind"]],
                "kind": br["kind"],
                "km": br["km"],
                "rating_mw_before": br["rating_mw"],
                "rating_mw_after": round(mw, 1),
                "rating_src_before": br.get("rating_src"),
            }
        )
        br["rating_mw"] = round(mw, 1)
        br["rating_src"] = "scenario-reinforced"
    return touched


def _deliverable_mw(
    net: dict,
    inj: dict[str, float],
    gens: list[dict],
    site: dict,
    cap_mw: float,
    base_unserved: float,
    tol_mw: float = 1.0,
    iters: int = 8,
) -> dict:
    """The largest load the network can actually deliver to the site bus
    before the OPF starts shedding, found by bisection on MW.

    The change in price cannot give you this number. Once the lines into a bus
    are at their limits, the bus prices at the cost of unserved energy, which
    is a penalty for shedding rather than a market price. Asking how many
    megawatts fit before that happens is the same question put in units that
    survive the model's own warnings.

    The headroom capacity is sized once, for the FULL site load, and held
    fixed across the search. Re-sizing it per probe made the thing being
    measured move with the probe (a small probe got a small supply increase,
    so its shedding could be worse than a large probe's), which is not a
    quantity bisection can find."""
    fixed = gens + _headroom_gens(gens, net, site["grid"], cap_mw)
    # the reference has to carry the same headroom, or the search scores the
    # site's load against a base that was short of supply for other reasons
    ref = solve_hour(net, inj, "opf", gens=fixed)
    ref_unserved = ref["unserved_mw"] if ref else base_unserved
    lo, hi = 0.0, cap_mw
    for _ in range(iters):
        mid = (lo + hi) / 2
        probe = dict(inj)
        probe[site["bus"]] = probe.get(site["bus"], 0.0) - mid
        sol = solve_hour(net, probe, "opf", gens=fixed)
        short = sol is None or (sol["unserved_mw"] - ref_unserved) > tol_mw
        if short:
            hi = mid
        else:
            lo = mid
    return {
        "deliverable_mw": round(lo, 0),
        "searched_to_mw": round(cap_mw, 0),
        "reference_unserved_mw": round(ref_unserved, 1),
    }


def run_day(date: str, sited: dict | None = None) -> dict:
    """One observed day on the reduced backbone.

    sited (optional) plants an announced load on the network and returns the
    counterfactual as a DELTA against the same day's base solve:
        {"site": <key in SITES, or {"label","lon","lat"}>, "mw": float}
    Everything the scenario reports is a difference between two solves of the
    same network at the same resolution on the same day. That is deliberate:
    this model's price LEVELS are not usable (see opf_finding), and a paired
    difference cancels most of what makes them unusable. Cancels most, not
    all, and that is an argument rather than a validated result, so the
    scenario block says so in its own note."""
    net = build_network()
    day = _load_day(date)
    res_bus, res_stats = map_resources(day, net)
    branches = net["branches"]

    site = None
    if sited:
        spec = sited["site"]
        if isinstance(spec, str):
            spec = SITES[spec]
        site = dict(spec)
        site.update(resolve_site(net, spec["lon"], spec["lat"]))
        site["mw"] = float(sited["mw"])
        site["reinforce_mw"] = float(sited.get("reinforce_mw") or 0.0)
        site["reinforce_km"] = float(sited.get("reinforce_km") or 0.0)
        site["embedded_firm_mw"] = float(sited.get("embedded_firm_mw") or 0.0)
        site["embedded_solar_mw"] = float(sited.get("embedded_solar_mw") or 0.0)
        site["net_draw_mw"] = [round(_net_draw(site, h), 1) for h in range(24)]

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
    sited_load = [[0.0] * len(branches) for _ in hours]
    slack_series = []
    for hr in hours:
        inj = hour_injections(day, res_bus, net, hr)
        sol = solve_hour(net, inj, "replay")
        if sol is None:
            continue
        for bi, f in enumerate(sol["flows_mw"]):
            replay_load[hr][bi] = abs(f) / branches[bi]["rating_mw"]
        slack_series.append(sol["slack_mw"])
        if site:
            s2 = solve_hour(
                net,
                _plant_load(inj, net, site["bus"], _net_draw(site, hr)),
                "replay",
            )
            if s2 is not None:
                for bi, f in enumerate(s2["flows_mw"]):
                    sited_load[hr][bi] = abs(f) / branches[bi]["rating_mw"]

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
    # the replay loading fractions above were divided by the ratings as they
    # stood BEFORE this block raises them, so anything reporting those
    # fractions has to quote the same vintage or the divisor and the printed
    # rating come from two different networks
    replay_ratings = [(br["rating_mw"], br.get("rating_src")) for br in branches]
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
    sited_opf = {}
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

        if not site:
            continue
        # the counterfactual: same hour, same network, same resolution, with
        # the site's load placed on its bus and assumed spare capacity to serve it.
        # Reinforcement (if asked for) applies only to the scenario solves and
        # is rolled back afterwards, so the base it is compared against is
        # always the unreinforced network.
        # the base binding set has to be read off the ORIGINAL ratings, before
        # any reinforcement touches them, or the comparison silently scores
        # base flows against upgraded lines
        base_binding = {
            bi
            for bi in range(len(branches))
            if abs(sol["flows_mw"][bi]) >= 0.999 * branches[bi]["rating_mw"]
        }
        saved = [(br, br["rating_mw"], br.get("rating_src")) for br in net["branches"]]
        reinforced = (
            reinforce_site(
                net, site["bus"], site["reinforce_mw"], site["reinforce_km"]
            )
            if site["reinforce_mw"] > 0
            else []
        )
        draw = _net_draw(site, hr)
        s_inj = dict(inj)
        s_inj[site["bus"]] = s_inj.get(site["bus"], 0.0) - draw
        s_gens = hour_gens + _headroom_gens(
            hour_gens, net, site["grid"], max(draw, 0.0)
        )
        s_sol = solve_hour(net, s_inj, "opf", gens=s_gens)
        if s_sol is None:
            for br, rating, src in saved:
                br["rating_mw"], br["rating_src"] = rating, src
            continue
        s_lmps = s_sol["lmp_mwh"]
        island = [b["id"] for b in net["buses"] if b["grid"] == site["grid"]]
        base_mean = sum(lmps[b] for b in island) / len(island)
        s_mean = sum(s_lmps[b] for b in island) / len(island)
        base_site_dev = lmps[site["bus"]] - base_mean
        s_site_dev = s_lmps[site["bus"]] - s_mean
        s_binding = {
            bi
            for bi in range(len(branches))
            if abs(s_sol["flows_mw"][bi]) >= 0.999 * branches[bi]["rating_mw"]
        }
        # shedding at the site turns every price at that bus into the
        # unserved-energy cost, which is a penalty parameter and not a
        # price. When that happens the deltas below are reported but
        # explicitly marked not-a-price, and the deliverable-MW search is
        # the number to read instead.
        added_unserved = round(s_sol["unserved_mw"] - sol["unserved_mw"], 1)
        shed = added_unserved > 1.0
        sited_opf[str(hr)] = {
            # what the whole island's price does: the system effect
            "island_mean_lmp_delta_mwh": round(s_mean - base_mean, 1),
            # what the site's own bus does relative to its island: the
            # network effect, which is the part a region model cannot see
            "site_lmp_delta_mwh": round(s_lmps[site["bus"]] - lmps[site["bus"]], 1),
            "site_deviation_base_mwh": round(base_site_dev, 1),
            "site_deviation_sited_mwh": round(s_site_dev, 1),
            "site_deviation_change_mwh": round(s_site_dev - base_site_dev, 1),
            "price_delta_is_a_price": not shed,
            "price_note": (
                "The network cannot deliver the full site load to this bus, "
                "so the site bus prices at the cost of unserved energy. The "
                "LMP deltas above are that penalty, NOT a market price. Read "
                "deliverable_mw instead."
                if shed else
                "The site load is delivered without shedding, so the LMP "
                "deltas are the model's marginal costs."
            ),
            "site_unserved_mw": added_unserved,
            "net_draw_mw": round(draw, 1),
            **_deliverable_mw(
                net, inj, hour_gens, site, max(draw, 0.0), sol["unserved_mw"]
            ),
            "unserved_mw": s_sol["unserved_mw"],
            "newly_binding": [
                {
                    "names": branches[bi]["names"] or [branches[bi]["kind"]],
                    "kind": branches[bi]["kind"],
                    "km": branches[bi]["km"],
                    "flow_mw": s_sol["flows_mw"][bi],
                    "rating_mw_est": branches[bi]["rating_mw"],
                    "rating_src": branches[bi].get("rating_src"),
                }
                for bi in sorted(s_binding - base_binding)
            ],
            "n_binding_base": len(base_binding),
            "n_binding_sited": len(s_binding),
            "reinforced_branches": reinforced,
        }
        for br, rating, src in saved:
            br["rating_mw"], br["rating_src"] = rating, src

    sited_out = None
    if site:
        peak_base = [max(replay_load[hr][bi] for hr in hours)
                     for bi in range(len(branches))]
        peak_sited = [max(sited_load[hr][bi] for hr in hours)
                      for bi in range(len(branches))]
        delta = [peak_sited[bi] - peak_base[bi] for bi in range(len(branches))]
        moved = sorted(range(len(branches)), key=lambda bi: -delta[bi])[:15]
        sited_out = {
            "site": site,
            "replay_delta": {
                "most_loaded_by_the_site": [
                    {
                        "names": branches[bi]["names"] or [branches[bi]["kind"]],
                        "kind": branches[bi]["kind"],
                        "km": branches[bi]["km"],
                        # the rating the loading fractions were divided by,
                        # not the later replay-floor value
                        "rating_mw_est": replay_ratings[bi][0],
                        "rating_src": replay_ratings[bi][1],
                        "peak_loading_base": round(peak_base[bi], 3),
                        "peak_loading_sited": round(peak_sited[bi], 3),
                        "loading_delta": round(delta[bi], 3),
                    }
                    for bi in moved
                    if delta[bi] > 0.001
                ],
                "n_branches_over_rating_base": sum(1 for v in peak_base if v > 1.0),
                "n_branches_over_rating_sited": sum(1 for v in peak_sited if v > 1.0),
            },
            "opf_delta": sited_opf,
            "supply_assumption": (
                "The replay pays for the site out of the island's own "
                "observed generation, sharing the extra across buses in "
                "proportion to what each was already producing that hour. "
                "The OPF adds assumed spare capacity across the island's "
                "existing generation buses at the island's median observed "
                "cost. Neither one says that capacity will ever be built. "
                "The DOE project list and the zonal engine answer that."
            ),
            "read_this_as": (
                "Differences between two solves of the same network on the "
                "same day, never levels. The warning about levels in "
                "opf_finding still applies. A paired difference cancels much "
                "of it, because both solves carry the same resolution bias. "
                "Much, but not all. That cancellation is an argument rather "
                "than a tested result, and there is no observed equivalent "
                "to score it against. The site coordinate is the middle of "
                "the campus, moved to the nearest modelled bus (see "
                "snap_km), which is not the connection NGCP will build."
            ),
            "deliverable_mw_caveat": (
                "deliverable_mw compares scenarios. It is not a rating of "
                "the site. Its reference solve already fails to serve the "
                "megawatts in reference_unserved_mw, over a gigawatt on a "
                "typical hour, because the OPF puts each grid's unmatched "
                "generation on its few matched plant buses and leaves "
                "pockets of load short. So compare it only across scenarios "
                "sharing one reference, such as one width of line upgrade "
                "against another. Never read it as 'the site can take N MW'. "
                "Closing that gap needs more of the published resource codes "
                "matched to buses, and no extra option will do it."
            ),
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
        "sited_scenario": sited_out,
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
    ap.add_argument("--site", choices=sorted(SITES), help="plant an announced load site")
    ap.add_argument("--site-mw", type=float, help="site load (MW), flat")
    ap.add_argument("--reinforce-mw", type=float, default=0.0,
                    help="raise the ratings of the site bus's branches to this "
                         "MW (the announced dedicated connection)")
    ap.add_argument("--reinforce-km", type=float, default=0.0,
                    help="reinforce every branch with an endpoint within this "
                         "radius of the site bus, not just the incident ones")
    ap.add_argument("--embedded-firm-mw", type=float, default=0.0,
                    help="the site's own round-the-clock generation (MW)")
    ap.add_argument("--embedded-solar-mw", type=float, default=0.0,
                    help="the site's own solar (MW), follows the baked shape")
    a = ap.parse_args()
    sited = None
    if a.site:
        if not a.site_mw:
            ap.error("--site needs --site-mw")
        sited = {"site": a.site, "mw": a.site_mw,
                 "reinforce_mw": a.reinforce_mw, "reinforce_km": a.reinforce_km,
                 "embedded_firm_mw": a.embedded_firm_mw,
                 "embedded_solar_mw": a.embedded_solar_mw}
    result = run_day(a.day, sited=sited)
    with open(a.out, "w") as f:
        json.dump(result, f, indent=1)
    slim = {k: v for k, v in result.items() if k not in ("replay", "opf")}
    print(json.dumps(slim, indent=1))
    print("top loaded (replay):")
    for t in result["replay"]["top_loaded"][:8]:
        print(f"  {t['peak_loading']:5.2f}  {t['kind']:6s} {t['names'][:2]}")
    for hr, o in result["opf"].items():
        print(f"opf h{hr}:", json.dumps(o["per_grid"], indent=1)[:400])
    sc = result.get("sited_scenario")
    if sc:
        s = sc["site"]
        print(f"\nsited: {s['label']} {s['mw']:,.0f} MW -> bus {s['bus']} "
              f"({s['grid']}, snapped {s['snap_km']} km)")
        if s["embedded_firm_mw"] or s["embedded_solar_mw"]:
            nd = s["net_draw_mw"]
            print(f"  embedded: {s['embedded_firm_mw']:,.0f} MW firm + "
                  f"{s['embedded_solar_mw']:,.0f} MW solar -> net grid draw "
                  f"{min(nd):,.0f} to {max(nd):,.0f} MW over the day")
        for r in sc["replay_delta"]["most_loaded_by_the_site"][:8]:
            print(f"  +{r['loading_delta']:5.2f} loading  {r['kind']:6s} "
                  f"{r['names'][:2]}  ({r['peak_loading_base']:.2f} -> "
                  f"{r['peak_loading_sited']:.2f} of rating)")
        for hr, o in sc["opf_delta"].items():
            if o["price_delta_is_a_price"]:
                print(f"  opf h{hr}: island mean "
                      f"{o['island_mean_lmp_delta_mwh']:+.1f} PhP/MWh, site bus "
                      f"{o['site_lmp_delta_mwh']:+.1f}, site-vs-island deviation "
                      f"{o['site_deviation_change_mwh']:+.1f}, newly binding "
                      f"{len(o['newly_binding'])}")
            else:
                print(f"  opf h{hr}: network sheds {o['site_unserved_mw']:,.0f} MW "
                      f"at the site, so no price. Deliverable to this bus: "
                      f"{o['deliverable_mw']:,.0f} MW of the "
                      f"{o['net_draw_mw']:,.0f} MW it draws. "
                      f"Newly binding {len(o['newly_binding'])}")
