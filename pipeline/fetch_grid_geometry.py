#!/usr/bin/env python3
"""Pull the PH transmission grid's real geometry from OpenStreetMap into
data/raw/OSMGRID/, committed like every other raw dataset.

NGCP publishes no public GIS (the TDP maps are PDF raster) and the World
Bank catalogs carry no PH grid dataset, so OSM is the only public source
of real routed line geometry. Coverage verified 2026-07-16: 3,468
power=line ways inside the PH bbox (163 tagged 500 kV, 909 tagged
230 kV), 924 substations (176 operator=NGCP), both HVDC links mapped by
name with their submarine segments. This is community-mapped data under
ODbL: every consumer must label it "as mapped in OpenStreetMap", never
"NGCP official".

Three raw pulls, one file each (committed, so the bake is reproducible
without hitting Overpass):
  lines_hv.json    power=line tagged 500/230/138 kV (PH area query; 138 kV
                   is in scope because the Mindanao grid and the
                   Bohol-Leyte crossing run at 138 kV and their
                   constraints bind in RTDCV)
  hvdc_cables.json power=line tagged 350 kV + all power=cable (bbox
                   query: area queries fail first under Overpass load;
                   build_data.py clips the Sabah corner)
  substations.json all power=substation nodes/ways/relations (PH area)

The grid changes slowly: this is a manual/monthly refresh, NOT a cron
job. Overpass etiquette: sequential queries, mirror fallback, generous
sleeps between retries.

    python3 pipeline/fetch_grid_geometry.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw", "OSMGRID")

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# PH bbox for the cable query: area filters are the expensive part of
# OverpassQL and fail first under server load; the bbox includes Sabah
# (Malaysia), which the bake clips by centroid (lon < 119.4 and lat < 7.5).
BBOX = "4.5,116.5,21.5,127.2"

QUERIES = {
    "lines_hv.json": """
[out:json][timeout:300];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  way["power"="line"]["voltage"~"500000|230000|138000"](area.ph);
);
out geom tags;
""",
    "hvdc_cables.json": f"""
[out:json][timeout:120][bbox:{BBOX}];
(
  way["power"="line"]["voltage"~"350000"];
  way["power"="cable"];
);
out geom tags;
""",
    "substations.json": """
[out:json][timeout:300];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  node["power"="substation"](area.ph);
  way["power"="substation"](area.ph);
  relation["power"="substation"](area.ph);
);
out center tags;
""",
    # power plants: the resource-to-bus resolution lift. DIPCEF codes name
    # plants far more often than substations, and OSM maps plant sites the
    # substation pull never sees.
    "plants.json": """
[out:json][timeout:300];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  node["power"="plant"](area.ph);
  way["power"="plant"](area.ph);
  relation["power"="plant"](area.ph);
);
out center tags;
""",
    # municipality/city centroids: the geocode for DOE fleet rows, whose
    # location columns name the municipality (placed city-precision, the
    # same label the data-center pins carry)
    "places.json": """
[out:json][timeout:300];
area["ISO3166-1"="PH"][admin_level=2]->.ph;
(
  node["place"~"^(city|town|municipality)$"](area.ph);
);
out center tags;
""",
}


def run_query(query: str) -> dict | None:
    for attempt in range(6):
        endpoint = ENDPOINTS[attempt % len(ENDPOINTS)]
        p = subprocess.run(
            [
                "curl",
                "-s",
                "--max-time",
                "330",
                "-X",
                "POST",
                "--data-binary",
                query,
                endpoint,
            ],
            capture_output=True,
        )
        if p.returncode == 0 and p.stdout:
            try:
                data = json.loads(p.stdout)
                if data.get("elements") is not None:
                    return data
            except json.JSONDecodeError:
                pass  # OSM3S "server busy" HTML page
        print(f"  busy/failed on {endpoint}, retrying", flush=True)
        time.sleep(20)
    return None


def write_manifest() -> None:
    """Manifest always describes what is ON DISK, so a partial refresh
    (Overpass mirrors go busy for hours) still records reality."""
    manifest = {}
    for fname in QUERIES:
        dest = os.path.join(OUT, fname)
        if not os.path.isfile(dest):
            continue
        with open(dest) as f:
            data = json.load(f)
        manifest[fname] = {
            "elements": len(data.get("elements", [])),
            "bytes": os.path.getsize(dest),
            "osm3s_timestamp": (data.get("osm3s") or {}).get("timestamp_osm_base"),
        }
    manifest["written_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest["license"] = "ODbL; data (c) OpenStreetMap contributors"
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    if "--manifest-only" in sys.argv:
        write_manifest()
        return 0
    failed = 0
    for fname, query in QUERIES.items():
        print(f"fetching {fname}", flush=True)
        data = run_query(query)
        if data is None:
            print(
                f"FAILED: {fname} (all endpoints busy; the on-disk pull "
                "stays; try again later)"
            )
            failed += 1
            continue
        dest = os.path.join(OUT, fname)
        with open(dest, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print(
            f"  {len(data['elements'])} elements, {os.path.getsize(dest) / 1e6:.2f} MB",
            flush=True,
        )
        time.sleep(10)
    write_manifest()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
