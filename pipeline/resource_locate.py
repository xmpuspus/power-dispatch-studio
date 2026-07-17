#!/usr/bin/env python3
"""Locate WESM resources on the map: the resolution lift behind the nodal
stack.

A DIPCEF resource code resolves to a coordinate through a PRIORITY of
public evidence, each hit tagged with its source so every surface can say
how the dot was placed:

  osm-substation   the station token matches a named OSM substation on the
                   HV network (exact site)
  osm-plant        the token matches a named OSM power=plant (exact site)
  named-plant      the token matches the repo's named-generator layer
                   (city-precision pins)
  doe-centroid     the token matches a DOE plant-list row, whose location
                   column names the municipality; placed at the OSM place
                   centroid (city-precision)

Region must agree in every path: a candidate only counts when it sits in
the resource's own grid (grid of the nearest network bus). Ambiguity is a
miss, never a guess, and the artifact reports resolved MW share per grid
so this number is public and its drift visible.
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict

from grid_geometry import _norm, km

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw", "OSMGRID")
DOE_DIR = os.path.join(HERE, "..", "data", "external", "doe")

SNAP_BUS_KM = 60.0  # located site -> nearest in-grid network bus

# DIPCEF station-code aliases verified against the DOE plant list, the OSM
# plant/substation inventories, and the named-generator layer. Prefixes are
# tried against normalized names; region consistency still gates every hit.
RESOURCE_ALIASES = {
    "SUAL": ["sual"],
    "GNPD": ["gnpowerdinginin", "dinginin"],
    "MSINLO": ["masinloc"],
    "MARVEL": ["gnpowermariveles", "mariveles"],
    "PAGBIL": ["pagbilao"],
    "SBPL": ["sanbuenaventura"],
    "QPPL": ["quezonpower", "mauban"],
    "STA-RI": ["santarita"],
    "STROS": ["santarosa"],
    "SNGAB": ["sangabriel"],
    "EERI": ["ilijan", "excellent"],
    "SNJOS": ["sanjose"],
    "BALNT": ["balintawak"],
    "ARANE": ["araneta", "quezoncity"],
    "SUCAT": ["sucat", "muntinlupa"],
    "LEYTE": ["tongonan", "leytegeothermal", "ormoc"],
    "ILIJAN": ["ilijan"],
    "CALACA": ["calaca"],
    "MKBN": ["makban", "makiling"],
    "TIWI": ["tiwi"],
    "KAL": ["kalayaan"],
    "CAPARI": ["caparispisan"],
    "BURGOS": ["burgos"],
    "TMO": ["malaya"],
    "PGBLO": ["pagbilao"],
    "TGEGA": ["tuguegarao"],
    # sprint 2 (2026-07-17), each verified against the DOE list or OSM:
    "BUGSOL": ["bugallon"],  # Bugallon solar, Pangasinan
    "SNMARSOL": ["sanmarcelino"],  # San Marcelino solar, Zambales
    "FDC": ["fdcmisamis", "villanueva"],  # FDC Misamis sits at Villanueva
    "GNPK": ["gnpowerkauswagan", "kauswagan"],
    "MCTAN": ["lapulapu", "mactan"],  # Mactan delivery = Lapu-Lapu GIS
    "LGPP": ["tongonan", "leytegeothermal"],  # Leyte Geothermal
    # region gating separates the two SMC fleets: Limay (Bataan) in Luzon,
    # SMGP Malita in Mindanao
    "SMC": ["smgpmalita", "smclimay", "limaypower"],
    "MINBAL": ["balingasag"],  # Minergy Balingasag thermal
    "STEAG": ["steag", "villanueva"],  # STEAG State Power, PHIVIDEC estate
    "KSPC": ["kepco", "naga"],  # KEPCO SPC, Naga, Cebu (region-gated)
    "SARANG": ["sarangani", "maasim"],  # Sarangani Energy, Maasim
    # delivery points named for their barangay/district: the locality is a
    # public fact, placed at the city centroid (city-precision)
    "QUIOT": ["cebucity"],
}

_RES_TOK = re.compile(r"^\d{0,2}([A-Z][A-Z-]*)")

# pdftotext -layout separates columns with runs of 2+ spaces, so a row
# parses structurally: split on the gaps, the plant name is the first
# chunk, and the address is the chunk with commas whose tail is
# ", <Municipality>, <Province>" ("Tiwi, Albay" and "Sitio Dinginin,
# Barangay Alasasin, Mariveles, Bataan" both occur)
_GAP_RE = re.compile(r"\s{2,}")
_NUMISH = re.compile(r"^[\d,.\s-]+$")


def resource_token(res: str) -> str:
    m = _RES_TOK.match(res.split("_")[0])
    return m.group(1) if m else ""


def token_prefixes(tok: str) -> list[str]:
    return RESOURCE_ALIASES.get(tok, [tok.lower()])


def load_osm_named(fname: str) -> list[dict]:
    """Named OSM elements as {name, norm, lon, lat}."""
    path = os.path.join(RAW, fname)
    if not os.path.isfile(path):
        return []
    out = []
    with open(path) as f:
        for e in json.load(f)["elements"]:
            t = e.get("tags", {})
            name = t.get("name")
            if not name:
                continue
            if "lat" in e:
                lat, lon = e["lat"], e["lon"]
            elif "center" in e:
                lat, lon = e["center"]["lat"], e["center"]["lon"]
            else:
                continue
            if lon < 119.4 and lat < 7.5:  # Sabah corner of any bbox pulls
                continue
            out.append(
                {
                    "name": name,
                    "norm": _norm(name),
                    "lon": round(lon, 5),
                    "lat": round(lat, 5),
                }
            )
    return out


def load_doe_locations() -> dict[str, tuple[str, str]]:
    """Normalized DOE plant name -> (municipality, province)."""
    out: dict[str, tuple[str, str]] = {}
    if not os.path.isdir(DOE_DIR):
        return out
    for fn in sorted(os.listdir(DOE_DIR)):
        if not fn.endswith(".txt") or "pdp" in fn or "summary" in fn:
            continue
        with open(os.path.join(DOE_DIR, fn), encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if " Grid " not in line and " Embedded " not in line:
                    continue
                chunks = [c.strip() for c in _GAP_RE.split(line.strip()) if c.strip()]
                if len(chunks) < 3 or not re.match(r"^[A-Z0-9]", chunks[0]):
                    continue
                addr = next(
                    (
                        c
                        for c in chunks[1:]
                        if "," in c
                        and not _NUMISH.match(c)
                        and re.match(r"^[A-Za-z]", c)
                    ),
                    None,
                )
                if not addr:
                    continue
                parts = [p.strip() for p in addr.split(",") if p.strip()]
                if len(parts) < 2:
                    continue
                muni, prov = parts[-2], parts[-1]
                if _NUMISH.match(muni) or _NUMISH.match(prov):
                    continue
                name = re.sub(r"\s+U\d+$|\s+UNIT\s*\d+$", "", chunks[0].strip())
                key = _norm(name)
                if key and key not in out:
                    out[key] = (muni, prov)
    return out


class Locator:
    """Resolve resource codes to coordinates + network buses."""

    def __init__(self, net: dict):
        self.net = net
        self.buses = net["buses"]
        self.subs_index = [
            (s["norm"] if "norm" in s else _norm(s.get("name") or ""), i)
            for i, s in enumerate(net["subs"])
            if s.get("name")
        ]
        self.plants = load_osm_named("plants.json")
        self.places = load_osm_named("places.json")
        self.doe = load_doe_locations()
        gen_path = os.path.join(HERE, "..", "web", "data", "generators.geojson")
        self.named = []
        if os.path.isfile(gen_path):
            with open(gen_path) as f:
                for ft in json.load(f)["features"]:
                    p = ft["properties"]
                    lon, lat = ft["geometry"]["coordinates"]
                    self.named.append(
                        {
                            "name": p.get("name", ""),
                            "norm": _norm(p.get("name", "")),
                            "lon": lon,
                            "lat": lat,
                            "grid": p.get("grid"),
                        }
                    )

    def grid_of_point(self, lon: float, lat: float) -> str | None:
        b = self.nearest_bus(lon, lat, grid=None, max_km=150.0)
        return b["grid"] if b else None

    def nearest_bus(
        self, lon: float, lat: float, grid: str | None, max_km: float = SNAP_BUS_KM
    ) -> dict | None:
        best, bestd = None, max_km
        for b in self.buses:
            if grid and b["grid"] != grid:
                continue
            d = km([lon, lat], [b["lon"], b["lat"]])
            if d < bestd:
                best, bestd = b, d
        return best

    def _unique_in_grid(self, cands: list[dict], grid: str) -> dict | None:
        hits = []
        for c in cands:
            g = c.get("grid") or self.grid_of_point(c["lon"], c["lat"])
            if g == grid:
                hits.append(c)
        if not hits:
            return None
        first = hits[0]
        for h in hits[1:]:
            if km([h["lon"], h["lat"]], [first["lon"], first["lat"]]) > 25.0:
                return None  # genuinely different places share the token
        return first

    def locate(self, res: str, grid: str) -> dict | None:
        """{lon, lat, src, label, bus} or None. Priority: OSM substation,
        OSM plant, named-generator pin, DOE municipality centroid."""
        tok = resource_token(res)
        prefixes = [p for p in token_prefixes(tok) if len(p) >= 3]
        if not prefixes:
            return None

        def starts(norm: str) -> bool:
            # prefix match; long tokens (6+) may also sit mid-name
            # ("Quezon/San Buenaventura Power Plant")
            return any(
                norm.startswith(p) or (len(p) >= 6 and p in norm) for p in prefixes
            )

        # 1) OSM substation on the network (exact site, on the grid)
        graph = self.net["graph"]
        bus_grid = {b["id"]: b["grid"] for b in self.buses}
        sub_hit = None
        for norm, i in self.subs_index:
            if not starts(norm):
                continue
            node = graph.node_of_sub.get(i)
            if node and bus_grid.get(node) == grid:
                if sub_hit and sub_hit[1] != node:
                    sub_hit = None
                    break
                sub_hit = (i, node)
        if sub_hit:
            s = self.net["subs"][sub_hit[0]]
            lon, lat = s["coords"]
            return {
                "lon": lon,
                "lat": lat,
                "src": "osm-substation",
                "label": s.get("name"),
                "bus": sub_hit[1],
            }

        # 2) OSM power=plant (exact site)
        hit = self._unique_in_grid([p for p in self.plants if starts(p["norm"])], grid)
        if hit:
            b = self.nearest_bus(hit["lon"], hit["lat"], grid)
            if b:
                return {
                    "lon": hit["lon"],
                    "lat": hit["lat"],
                    "src": "osm-plant",
                    "label": hit["name"],
                    "bus": b["id"],
                }

        # 3) the repo's named-generator layer (city-precision pins)
        hit = self._unique_in_grid([p for p in self.named if starts(p["norm"])], grid)
        if hit:
            b = self.nearest_bus(hit["lon"], hit["lat"], grid)
            if b:
                return {
                    "lon": hit["lon"],
                    "lat": hit["lat"],
                    "src": "named-plant",
                    "label": hit["name"],
                    "bus": b["id"],
                }

        # 4) load-side codes that name the locality itself (CALAMBA, MCTAN):
        # the municipality/city centroid, city-precision. Load and delivery
        # suffixes only, so a plant code never mistakes a same-named town.
        if re.search(r"_(L|T)\w*$", res):
            hit = self._unique_in_grid(
                [p for p in self.places if starts(p["norm"])], grid
            )
            if hit:
                b = self.nearest_bus(hit["lon"], hit["lat"], grid)
                if b:
                    return {
                        "lon": hit["lon"],
                        "lat": hit["lat"],
                        "src": "place-centroid",
                        "label": f"{hit['name']} (locality centroid)",
                        "bus": b["id"],
                    }

        # 5) DOE plant list -> municipality centroid (city-precision)
        doe_hits = {k: v for k, v in self.doe.items() if starts(k)}
        if doe_hits:
            munis = {v for v in doe_hits.values()}
            if len({m for m, _ in munis}) == 1:
                muni = next(iter(munis))[0]
                mn = _norm(muni)
                hit = self._unique_in_grid(
                    [p for p in self.places if p["norm"] == mn], grid
                )
                if hit:
                    b = self.nearest_bus(hit["lon"], hit["lat"], grid)
                    if b:
                        return {
                            "lon": hit["lon"],
                            "lat": hit["lat"],
                            "src": "doe-centroid",
                            "label": f"{muni} (municipality centroid)",
                            "bus": b["id"],
                        }
        return None


def resolve_all(day: dict, net: dict) -> tuple[dict, dict]:
    """Resolve every resource in a nodal daily.

    Returns (res -> location dict, stats). Stats carry resolved MW share
    per grid and per source: the public scoreboard."""
    loc = Locator(net)
    out: dict[str, dict] = {}
    mw_res: dict[str, float] = defaultdict(float)
    mw_tot: dict[str, float] = defaultdict(float)
    n_by_src: dict[str, int] = defaultdict(int)
    for res, nd in day["nodes"].items():
        mws = [abs(v) for v in nd["mw"] if v]
        mw = sum(mws) / len(mws) if mws else 0.0
        mw_tot[nd["grid"]] += mw
        got = loc.locate(res, nd["grid"])
        if got:
            out[res] = got
            mw_res[nd["grid"]] += mw
            n_by_src[got["src"]] += 1
    stats = {
        "resolved": len(out),
        "total": len(day["nodes"]),
        "by_src": dict(sorted(n_by_src.items())),
        "per_grid_mw_share": {
            g: round(mw_res[g] / mw_tot[g], 3) if mw_tot[g] else None
            for g in ("luzon", "visayas", "mindanao")
        },
        "mw_share": round(sum(mw_res.values()) / sum(mw_tot.values()), 3)
        if sum(mw_tot.values())
        else None,
    }
    return out, stats
