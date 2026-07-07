#!/usr/bin/env python3
"""Bake the PASA layer: the operator's own scheduled-outage files, per archive day.

OUTRTD (RTDOS files) lists resources whose STATUS was OUT in each 5-minute RTD
run, with the outage window. The files carry resource codes and no MW, so this
module maps each code to its DOE-fleet plant through a hand-maintained alias
table, VERIFIED against fleet.json at bake time: an alias whose fleet row is
missing, or whose grid disagrees with the code's area prefix, fails loudly.
Resources with no confident alias stay in the artifact as unmatched rows with
no MW; coverage is stated, never guessed.

Grid from the resource code's area prefix (labeled INFERRED, like the reserve
code mapping): 01-03 Luzon, 04-08 Visayas, 09-14 Mindanao. Spot-checked against
known plants (03CALACA Luzon coal, 05THVI Cebu coal, 08PEDC Panay coal,
10AGUS* the Agus hydro complex).

MW per resource comes from the DOE fleet row (dependable capacity): mode "row"
takes the row as-is (the row IS the unit or the plant the code names); mode
"per_unit" divides the row's dependable MW by its unit count (the code names
one unit of an aggregated row). _BAT codes are grid batteries; the fleet list
excludes ESS, so they carry kind "storage" and no MW.
"""
from __future__ import annotations

import csv
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")

# resource code -> (fleet row name, mode). Only codes whose plant is unambiguous
# against the DOE list are here; everything else stays unmatched.
ALIAS: dict[str, tuple[str, str]] = {
    "01AMBUK": ("AMBUKLAO", "per_unit"),
    "01CASECN": ("CASECNAN (NIA)", "per_unit"),
    "01GIFT": ("GIFT", "row"),
    "01MARVEL_G01": ("MARIVELES U1", "row"),
    "01MSINLO_G02": ("MASINLOC U2", "row"),
    "01PNTBNG": ("PANTABANGAN", "per_unit"),
    "01SROQUE": ("SAN ROQUE", "per_unit"),
    "03CALACA_G01": ("CALACA U1", "row"),
    "03KAL": ("KALAYAAN PSPP", "per_unit"),
    "03SLPGC_G01": ("SLPGC U1", "row"),
    "03SLPGC_G02": ("SLPGC U2", "row"),
    "03SNGAB": ("SAN GABRIEL", "row"),
    "05EAUC": ("EAST ASIA UTILITIES (MEPZA)", "per_unit"),
    "05THVI_U01": ("TVI U1", "row"),
    "06HELIOS": ("HELIOS", "row"),
    "07BDPP": ("BOHOL DPP", "per_unit"),
    "08PEDC_U03": ("PEDC U3", "row"),
    "08TIMBA": ("TIMBABAN HEPP", "per_unit"),
    "09WMPC": ("WMPC", "per_unit"),
    "10AGUS1": ("AGUS 1", "per_unit"),
    "10AGUS2": ("AGUS 2", "per_unit"),
    "10AGUS5": ("AGUS 5", "per_unit"),
    "10AGUS6": ("AGUS 6", "per_unit"),
    "10AGUS7": ("AGUS 7", "per_unit"),
    "11FDC_U01": ("FDC MISAMIS U1", "row"),
    "11MANFOR_G01": ("MANOLO FORTICH U1", "row"),
    "11MANFOR_G02": ("MANOLO FORTICH U2", "row"),
    "11PULA4": ("PULANGI 4", "per_unit"),
    "12ASIGA": ("ASIGA", "row"),
    "14SARANG_U02": ("SEC U2", "row"),
    "14SIGHYDRO": ("SIGUIL HEPP", "row"),
}

GRIDS = ("luzon", "visayas", "mindanao")


def grid_of_prefix(resource: str) -> str | None:
    m = re.match(r"^(\d{2})", resource)
    if not m:
        return None
    n = int(m.group(1))
    if 1 <= n <= 3:
        return "luzon"
    if 4 <= n <= 8:
        return "visayas"
    if 9 <= n <= 14:
        return "mindanao"
    return None


def _alias_for(resource: str) -> tuple[str, str] | None:
    if resource in ALIAS:
        return ALIAS[resource]
    core = resource.split("_")[0]
    return ALIAS.get(core)


def build_pasa(fleet: dict) -> dict:
    files = sorted(
        os.path.join(RAW, "OUTRTD", n)
        for n in os.listdir(os.path.join(RAW, "OUTRTD"))
        if not n.startswith(".")
    ) if os.path.isdir(os.path.join(RAW, "OUTRTD")) else []
    if not files:
        return {"available": False,
                "note": "OUTRTD absent; scheduled-outage layer unavailable."}

    rows_by_name = {p["name"]: p for p in fleet.get("plants", [])}

    def resolve(resource: str) -> dict:
        grid = grid_of_prefix(resource)
        if resource.endswith("_BAT"):
            return {"resource": resource, "grid": grid, "plant": None,
                    "fuel": "storage", "unit_mw": None, "match": "storage"}
        alias = _alias_for(resource)
        if not alias:
            return {"resource": resource, "grid": grid, "plant": None,
                    "fuel": None, "unit_mw": None, "match": "unmatched"}
        row_name, mode = alias
        row = rows_by_name.get(row_name)
        if row is None:
            raise SystemExit(f"pasa: alias {resource} -> {row_name!r} not in fleet.json")
        if grid and row["grid"] != grid:
            raise SystemExit(f"pasa: alias {resource} grid {grid} != fleet "
                             f"{row['grid']} for {row_name!r}")
        units = max(1, int(row.get("units") or 1))
        mw = row["dependable_mw"] / units if mode == "per_unit" else row["dependable_mw"]
        return {"resource": resource, "grid": row["grid"], "plant": row_name,
                "fuel": row["fuel"], "unit_mw": round(mw, 1), "match": "verified"}

    resolved: dict[str, dict] = {}
    days = []
    for path in files:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", os.path.basename(path))
        date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        seen: set[str] = set()
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                name = (r.get("RESOURCE_NAME") or "").strip()
                if name:
                    seen.add(name)
        out = []
        matched_mw = {g: 0.0 for g in GRIDS}
        n_unmatched = 0
        for name in sorted(seen):
            if name not in resolved:
                resolved[name] = resolve(name)
            rr = resolved[name]
            out.append(name)
            if rr["match"] == "verified" and rr["grid"] in matched_mw:
                matched_mw[rr["grid"]] += rr["unit_mw"]
            elif rr["match"] == "unmatched":
                n_unmatched += 1
        days.append({
            "date": date,
            "out": out,
            "matched_mw": {g: round(v, 1) for g, v in matched_mw.items()},
            "n_out": len(out),
            "n_unmatched": n_unmatched,
        })

    resources = sorted(resolved.values(), key=lambda r: r["resource"])
    n_verified = sum(1 for r in resources if r["match"] == "verified")
    n_unmatched = sum(1 for r in resources if r["match"] == "unmatched")
    n_storage = sum(1 for r in resources if r["match"] == "storage")
    return {
        "available": True,
        "days": days,
        "resources": resources,
        "n_resources": len(resources),
        "n_verified": n_verified,
        "n_unmatched": n_unmatched,
        "n_storage": n_storage,
        "grid_mapping_note": (
            "Grid per resource comes from the WESM code's numeric area prefix "
            "(01-03 Luzon, 04-08 Visayas, 09-14 Mindanao), an INFERRED mapping "
            "spot-checked against named plants; IEMOP does not publish a code "
            "key on this dataset."),
        "coverage_note": (
            f"{n_verified} of {len(resources)} outage codes in this window map "
            f"to a DOE-fleet plant with a dependable MW; {n_unmatched} stay "
            f"unmatched and carry no MW (their outage is listed, not sized), "
            f"and {n_storage} are grid batteries outside the generation list. "
            "Matched MW is therefore a floor on the true scheduled-outage MW."),
        "note": (
            "The operator's own outage schedules used in real-time dispatch "
            "(IEMOP OUTRTD), one row per resource out per day. This is the "
            "observed maintenance-plus-forced outage state, not a forecast."),
        "src": "https://www.iemop.ph/market-data/outage-schedules-used-in-rtd/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


if __name__ == "__main__":
    import json
    fleet = json.load(open(os.path.join(HERE, "..", "web", "data", "fleet.json")))
    out = build_pasa(fleet)
    print(json.dumps({k: v for k, v in out.items() if k != "days"}, indent=1)[:3000])
