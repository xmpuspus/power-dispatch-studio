#!/usr/bin/env python3
"""Bake the real grid geometry layers from data/raw/OSMGRID/ and pin the
observed binding constraints (RTDCV/DAPCV equipment) onto them.

Two outputs for the map, one shared graph for the nodal model:
  web/data/grid_lines.geojson  500/230 kV AC lines + the two HVDC links +
                               transmission-level cables, real routed
                               geometry, each feature tagged with any
                               binding-constraint receipts matched to it
  web/data/grid_nodes.geojson  transmission substations (69 kV+ tagged, or
                               NGCP-operated, or substation=transmission),
                               transformer constraints pinned to stations

Matching is evidence-first: an RTDCV equipment code (3BINA_3DAS1 =
Binan-Dasmarinas circuit 1; 1EHVNGS_TR2 = a transformer at EHV Nagsaag)
matches only when its station tokens resolve uniquely to named OSM
substations and, for lines, a connected path exists between them in the
snapped graph. Anything that fails stays in the unmatched list, shown as
such; no geometry is invented. The data is community-mapped (ODbL): every
surface labels it "as mapped in OpenStreetMap", never "NGCP official".
"""

from __future__ import annotations

import heapq
import json
import math
import os
import re
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw", "OSMGRID")

TX_VOLTS = ("500000", "350000", "230000", "138000", "115000", "69000")
SNAP_KM = 1.5  # line endpoint -> substation
STATION_KM = 3.0  # matched substation -> nearest graph node
GRID_DP = 3  # endpoint hash grid (~110 m)

# Station-code aliases the prefix matcher cannot derive from spelling alone,
# each verified against the OSM substation inventory (data/raw/OSMGRID) and
# public station lists. A code maps to one or more normalized-name PREFIXES;
# ambiguity that survives is settled by voltage (transformers) or by the
# shortest plausible graph path (lines), never by guessing.
ALIASES = {
    "EHVNGS": ["nagsaag"],  # EHV Nagsaag, San Manuel, Pangasinan
    "EHVNAG": ["nagsaag"],
    "NGS": ["nagsaag"],
    "SJO": ["sanjose"],  # San Jose del Monte EHV disambiguates by voltage
    "SRAF": ["sanrafael"],
    "TGERAO": ["tuguegarao"],
    "MNDUE": ["mandaue"],
    "MRAWI": ["marawi"],
    # NGCP drops vowels: CLA can be Clark, Calaca, or Calamba; the graph
    # path picks the geographically plausible one per equipment
    "CLA": ["clark", "cala"],
}

# Interface-style equipment codes (no station tokens). LEYTE_TO_CEBU is the
# Cebu-Leyte interconnection, which lands at Daanbantayan (Cebu) and Tabango
# (Leyte); RTDCV names the same corridor as 5DAAN_4TABx at circuit level.
EQUIPMENT_ALIASES = {
    "LEYTE_TO_CEBU": ("daanbantayan", "tabango"),
}


def _load(name: str) -> list[dict]:
    with open(os.path.join(RAW, name)) as f:
        return json.load(f)["elements"]


def _in_ph(lat: float, lon: float) -> bool:
    # the cable query is bbox-based and the bbox corner includes Sabah (MY)
    return not (lon < 119.4 and lat < 7.5)


def _centroid(e: dict) -> tuple[float, float]:
    g = e.get("geometry") or []
    if not g:
        return (e.get("lat", 0.0), e.get("lon", 0.0))
    return (sum(p["lat"] for p in g) / len(g), sum(p["lon"] for p in g) / len(g))


def _classify(t: dict) -> str:
    v = t.get("voltage") or ""
    if t.get("frequency") == "0" or "350000" in v:
        return "hvdc"
    if "500000" in v:
        return "ac500"
    if "230000" in v:
        return "ac230"
    if "138000" in v:
        return "ac138"
    return "cable"


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine, km. Points are (lon, lat)."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_features() -> tuple[list[dict], list[dict]]:
    """(line features, substation features) with the dry-run filters."""
    lines: list[dict] = []
    seen: set[int] = set()
    for e in _load("lines_hv.json"):
        seen.add(e["id"])
        t = e["tags"]
        lines.append(
            {
                "osm_id": e["id"],
                "name": t.get("name"),
                "voltage": t.get("voltage"),
                "kind": _classify(t),
                "circuits": t.get("circuits"),
                "operator": t.get("operator"),
                "coords": [
                    [round(p["lon"], 5), round(p["lat"], 5)] for p in e["geometry"]
                ],
            }
        )
    for e in _load("hvdc_cables.json"):
        if e["id"] in seen:
            continue
        t = e["tags"]
        v = t.get("voltage") or ""
        hvdc = t.get("frequency") == "0" or "350000" in v
        if not (hvdc or any(x in v for x in TX_VOLTS)):
            continue  # distribution-level cable
        lat, lon = _centroid(e)
        if not _in_ph(lat, lon):
            continue
        lines.append(
            {
                "osm_id": e["id"],
                "name": t.get("name"),
                "voltage": t.get("voltage"),
                "kind": "hvdc" if hvdc else _classify(t),
                "circuits": t.get("circuits"),
                "operator": t.get("operator"),
                "submarine": (
                    t.get("location") == "underwater" or t.get("submarine") == "yes"
                )
                or None,
                "coords": [
                    [round(p["lon"], 5), round(p["lat"], 5)] for p in e["geometry"]
                ],
            }
        )
    # a substation belongs on the layer if its tags say transmission-level
    # (voltage 69 kV+, NGCP operator, substation=transmission) OR the HV
    # network physically lands on it: stations like Tabango (the Cebu-Leyte
    # cable terminal) are mapped with no voltage tag at all, and dropping
    # them severs the corridor the binding constraints name most
    endpoints = [c for ln in lines for c in (ln["coords"][0], ln["coords"][-1])]

    def on_network(lon: float, lat: float) -> bool:
        return any(km([lon, lat], ep) < 1.0 for ep in endpoints)

    subs: list[dict] = []
    for e in _load("substations.json"):
        t = e.get("tags", {})
        v = t.get("voltage") or ""
        op = (t.get("operator") or "").lower()
        ngcp = "national grid" in op or "ngcp" in op
        if "lat" in e:
            lat, lon = e["lat"], e["lon"]
        elif "center" in e:
            lat, lon = e["center"]["lat"], e["center"]["lon"]
        else:
            continue
        if not _in_ph(lat, lon):
            continue
        if not (
            any(x in v for x in TX_VOLTS)
            or ngcp
            or t.get("substation") == "transmission"
            or on_network(lon, lat)
        ):
            continue
        subs.append(
            {
                "osm_id": e["id"],
                "name": t.get("name"),
                "voltage": v or None,
                "operator": t.get("operator"),
                "hv": ("500000" in v or "350000" in v) or None,
                "coords": [round(lon, 5), round(lat, 5)],
            }
        )
    return lines, subs


class Graph:
    """Snapped transmission graph: nodes are endpoint grid keys (substations
    absorb endpoints within SNAP_KM), edges carry line-feature indices."""

    def __init__(self, lines: list[dict], subs: list[dict]):
        self.lines = lines
        self.subs = subs
        self.node_of_sub: dict[int, str] = {}
        self.adj: dict[str, list[tuple[str, int, float]]] = defaultdict(list)
        subkeys: dict[str, list[int]] = defaultdict(list)
        for i, s in enumerate(subs):
            subkeys[self._key(s["coords"])].append(i)
        for li, ln in enumerate(lines):
            a, b = ln["coords"][0], ln["coords"][-1]
            ka = self._snap(a, subs, subkeys)
            kb = self._snap(b, subs, subkeys)
            length = sum(km(p, q) for p, q in zip(ln["coords"], ln["coords"][1:]))
            ln["length_km"] = round(length, 2)
            if ka == kb:
                continue  # degenerate stub after snapping
            self.adj[ka].append((kb, li, length))
            self.adj[kb].append((ka, li, length))
        for i, s in enumerate(subs):
            self.node_of_sub[i] = self._nearest_node(s["coords"])

    @staticmethod
    def _key(pt: list[float]) -> str:
        return f"{pt[0]:.{GRID_DP}f},{pt[1]:.{GRID_DP}f}"

    def _snap(
        self, pt: list[float], subs: list[dict], subkeys: dict[str, list[int]]
    ) -> str:
        best, bestd = None, SNAP_KM
        for s in subs:
            d = km(pt, s["coords"])
            if d < bestd:
                best, bestd = s, d
        return self._key(best["coords"]) if best else self._key(pt)

    def _nearest_node(self, pt: list[float]) -> str | None:
        best, bestd = None, STATION_KM
        for k in self.adj:
            lon, lat = map(float, k.split(","))
            d = km(pt, [lon, lat])
            if d < bestd:
                best, bestd = k, d
        return best

    def dijkstra(self, ka: str, kb: str) -> tuple[list[int], float] | None:
        """Shortest path by km between two graph nodes: (line-feature
        indices from kb back to ka, path km), or None when disconnected."""
        if ka == kb or ka not in self.adj or kb not in self.adj:
            return None
        dist = {ka: 0.0}
        prev: dict[str, tuple[str, int]] = {}
        pq = [(0.0, ka)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == kb:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, li, w in self.adj[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, li)
                    heapq.heappush(pq, (nd, v))
        if kb not in prev:
            return None
        edges = []
        u = kb
        while u != ka:
            u, li = prev[u]
            edges.append(li)
        return edges, round(dist[kb], 1)

    def path_edges(self, sub_a: int, sub_b: int) -> tuple[list[int], float] | None:
        """Dijkstra between two substations, capped: line constraints name
        single circuits between electrically adjacent stations, so a detour
        beyond 3x straight-line (or an absolute 200 km) means the tokens
        resolved to the wrong station pair."""
        ka, kb = self.node_of_sub.get(sub_a), self.node_of_sub.get(sub_b)
        if ka is None or kb is None:
            return None
        got = self.dijkstra(ka, kb)
        if got is None:
            return None
        straight = km(self.subs[sub_a]["coords"], self.subs[sub_b]["coords"])
        if got[1] > min(max(3.0 * straight, straight + 60.0), 200.0):
            return None
        return got


# --- RTDCV/DAPCV equipment -> geometry ---------------------------------------

_EQ_LINE = re.compile(r"^\d{0,2}([A-Z]+?)\d*_\d{0,2}([A-Z]+?)(\d+)?$")
_EQ_TRAFO = re.compile(r"^\d{0,2}([A-Z]+?)\d*_TR\d*$")


def _station_index(subs: list[dict]) -> list[tuple[str, int]]:
    return [(_norm(s["name"]), i) for i, s in enumerate(subs) if s.get("name")]


def _candidates(code: str, index: list[tuple[str, int]]) -> list[int]:
    """OSM substations whose normalized name starts with the code token or a
    verified alias prefix. May be several; the caller disambiguates."""
    toks = ALIASES.get(code, [code.lower()])
    hits: set[int] = set()
    for tok in toks:
        if len(tok) < 3:
            continue
        hits |= {i for n, i in index if n.startswith(tok)}
    return sorted(hits)


def _by_voltage(cands: list[int], subs: list[dict], level: str) -> list[int]:
    """Narrow candidates to those whose OSM voltage tag carries the RTDCV
    VOLTAGE_LEVEL (e.g. '230' -> '230000'); no-ops when nothing matches."""
    if not level:
        return cands
    kv = f"{level}000"
    narrowed = [i for i in cands if kv in (subs[i].get("voltage") or "")]
    return narrowed or cands


def _aggregate(league: list[dict]) -> list[dict]:
    """One entry per equipment name. build_congestion keys the league on
    (equipment, station, voltage), so the same circuit appears once per
    monitored end: days take the max (the sets overlap; summing would
    overcount), intervals sum (distinct rows), voltage keeps the modal."""
    by_eq: dict[str, dict] = {}
    for e in league:
        a = by_eq.setdefault(
            e["equipment"],
            {
                "equipment": e["equipment"],
                "days": 0,
                "rtd_intervals": 0,
                "max_overload_mw": 0.0,
                "voltages": [],
            },
        )
        a["days"] = max(a["days"], e["days"])
        a["rtd_intervals"] += e["rtd_intervals"]
        a["max_overload_mw"] = max(a["max_overload_mw"], e["max_overload_mw"])
        if e.get("voltage"):
            a["voltages"].append(e["voltage"])
    out = []
    for a in by_eq.values():
        v = a.pop("voltages")
        a["voltage"] = max(set(v), key=v.count) if v else ""
        out.append(a)
    out.sort(key=lambda a: (-a["days"], -a["rtd_intervals"], a["equipment"]))
    return out


def _best_pair(
    cands_a: list[int], cands_b: list[int], graph: Graph
) -> tuple[int, int, list[int], float] | None:
    """The candidate station pair with the shortest plausible path. A
    DIFFERENT pair within 20 percent is genuine ambiguity (no match), but
    a tied pair whose endpoints sit within 3 km of the best pair's is the
    same physical answer under two station names (cable terminals are
    mapped beside their substations) and does not block the match."""
    scored = []
    for sa in cands_a:
        for sb in cands_b:
            got = graph.path_edges(sa, sb)
            if got:
                scored.append((got[1], sa, sb, got[0]))
    if not scored:
        return None
    scored.sort()
    d, sa, sb, edges = scored[0]
    for d2, sa2, sb2, _ in scored[1:]:
        if d2 >= 1.2 * d:
            break
        same = (
            km(graph.subs[sa]["coords"], graph.subs[sa2]["coords"]) < 3.0
            and km(graph.subs[sb]["coords"], graph.subs[sb2]["coords"]) < 3.0
        )
        if not same:
            return None
    return sa, sb, edges, d


def match_equipment(
    league: list[dict], lines: list[dict], subs: list[dict], graph: Graph
) -> tuple[dict, dict, list[dict]]:
    """Pin each binding equipment onto geometry.

    Returns (per-line-idx receipts, per-sub-idx receipts, match report).
    """
    index = _station_index(subs)
    line_hits: dict[int, list[dict]] = defaultdict(list)
    sub_hits: dict[int, list[dict]] = defaultdict(list)
    report: list[dict] = []

    def line_match(
        stats: dict, cands_a: list[int], cands_b: list[int], why_none: str
    ) -> None:
        best = _best_pair(cands_a, cands_b, graph)
        if best is None:
            report.append({**stats, "matched": False, "why": why_none})
            return
        sa, sb, edges, d = best
        for li in edges:
            line_hits[li].append(stats)
        report.append(
            {
                **stats,
                "matched": True,
                "kind": "line",
                "stations": [subs[sa]["name"], subs[sb]["name"]],
                "path_km": d,
                "path_edges": len(edges),
            }
        )

    for e in _aggregate(league):
        eq = e["equipment"]
        stats = {
            "equipment": eq,
            "days": e["days"],
            "rtd_intervals": e["rtd_intervals"],
            "max_overload_mw": e["max_overload_mw"],
        }
        if eq in EQUIPMENT_ALIASES:
            pa, pb = EQUIPMENT_ALIASES[eq]
            line_match(
                stats,
                [i for n, i in index if n.startswith(pa)],
                [i for n, i in index if n.startswith(pb)],
                "interface endpoints not in the graph",
            )
            continue
        mt = _EQ_TRAFO.match(eq)
        if mt:
            cands = _by_voltage(_candidates(mt.group(1), index), subs, e["voltage"])
            if len(cands) != 1:
                report.append(
                    {
                        **stats,
                        "matched": False,
                        "why": (
                            "station token unresolved"
                            if not cands
                            else "station token ambiguous"
                        ),
                    }
                )
                continue
            si = cands[0]
            sub_hits[si].append(stats)
            report.append(
                {
                    **stats,
                    "matched": True,
                    "kind": "station",
                    "station": subs[si]["name"],
                }
            )
            continue
        ml = _EQ_LINE.match(eq)
        if ml:
            ca = _candidates(ml.group(1), index)
            cb = _candidates(ml.group(2), index)
            if not ca or not cb:
                report.append(
                    {**stats, "matched": False, "why": "station token unresolved"}
                )
                continue
            line_match(stats, ca, cb, "no plausible path in the graph")
            continue
        report.append({**stats, "matched": False, "why": "unparsed code"})
    return line_hits, sub_hits, report


def corridor_route(
    graph: Graph, coords: list[list[float]], max_end_km: float = 25.0
) -> list[list[float]] | None:
    """Real routed coordinates for a schematic corridor: snap each schematic
    endpoint to the nearest graph node (schematic ends are imprecise, so the
    snap radius is generous) and chain shortest paths leg by leg. None when
    any leg has no plausible route, so the caller keeps the schematic."""
    nodes = []
    for pt in coords:
        best, bestd = None, max_end_km
        for k in graph.adj:
            lon, lat = map(float, k.split(","))
            d = km(pt, [lon, lat])
            if d < bestd:
                best, bestd = k, d
        if best is None:
            return None
        nodes.append(best)
    out: list[list[float]] = []
    for a, b in zip(nodes, nodes[1:]):
        if a == b:
            return None
        got = graph.dijkstra(a, b)
        if got is None:
            return None
        straight = km(
            [float(x) for x in a.split(",")], [float(x) for x in b.split(",")]
        )
        if got[1] > max(4.0 * straight, straight + 80.0):
            return None  # a detour, not the corridor
        # walk the edges in path order, orienting each feature's coords
        cur = [float(x) for x in a.split(",")]
        for li in reversed(got[0]):
            c = graph.lines[li]["coords"]
            seg = c if km(c[0], cur) <= km(c[-1], cur) else list(reversed(c))
            if out and seg[0] == out[-1]:
                seg = seg[1:]
            out.extend(seg)
            cur = seg[-1] if seg else cur
    return out if len(out) >= 2 else None


def build_grid(
    league: list[dict], out_dir: str, chokepoints: list[dict] | None = None
) -> dict:
    """Bake grid_lines.geojson + grid_nodes.geojson; return the summary
    (plus real routed geometry per chokepoint id when resolvable)."""
    lines, subs = load_features()
    graph = Graph(lines, subs)
    line_hits, sub_hits, report = match_equipment(league, lines, subs, graph)

    def receipts(hits: list[dict]) -> dict:
        return {
            "days": max(h["days"] for h in hits),
            "rtd_intervals": sum(h["rtd_intervals"] for h in hits),
            "equipment": sorted({h["equipment"] for h in hits}),
        }

    lf = []
    for i, ln in enumerate(lines):
        props = {k: v for k, v in ln.items() if k != "coords" and v is not None}
        if i in line_hits:
            props["binding"] = receipts(line_hits[i])
        lf.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "LineString", "coordinates": ln["coords"]},
            }
        )
    nf = []
    for i, s in enumerate(subs):
        props = {k: v for k, v in s.items() if k != "coords" and v is not None}
        if i in sub_hits:
            props["binding"] = receipts(sub_hits[i])
        nf.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": s["coords"]},
            }
        )
    attribution = (
        "Grid geometry as mapped in OpenStreetMap; data (c) "
        "OpenStreetMap contributors, ODbL. Community-mapped, "
        "not NGCP-official; geometry only, no ratings."
    )
    for name, feats in (("grid_lines.geojson", lf), ("grid_nodes.geojson", nf)):
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(
                {
                    "type": "FeatureCollection",
                    "attribution": attribution,
                    "features": feats,
                },
                fh,
                separators=(",", ":"),
            )
    routes: dict[str, list[list[float]]] = {}
    for c in chokepoints or []:
        got = corridor_route(graph, c["coords"])
        if got:
            routes[c["id"]] = [[round(x, 5) for x in p] for p in got]
    matched = [r for r in report if r["matched"]]
    kinds = defaultdict(int)
    for ln in lines:
        kinds[ln["kind"]] += 1
    return {
        "corridor_routes": routes,
        "lines": len(lf),
        "nodes": len(nf),
        "kinds": dict(kinds),
        "bound_line_features": len(line_hits),
        "bound_stations": len(sub_hits),
        "equipment_total": len(report),
        "equipment_matched": len(matched),
        "match_report": report,
    }


if __name__ == "__main__":
    # standalone smoke run against the current congestion league
    from build_data import build_congestion

    cong = build_congestion()
    league = cong.get("league_full") or cong["league"]
    out = os.path.join(HERE, "..", "web", "data")
    summary = build_grid(league, out)
    slim = {k: v for k, v in summary.items() if k != "match_report"}
    print(json.dumps(slim, indent=1))
    for r in summary["match_report"]:
        flag = "MATCH" if r["matched"] else "MISS "
        print(
            f"{flag} {r['equipment']:16s} days={r['days']:<3} "
            f"{r.get('stations') or r.get('station') or r.get('why')}"
        )
