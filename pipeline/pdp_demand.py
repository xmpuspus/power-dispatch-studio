#!/usr/bin/env python3
"""Bake the DOE demand path: the Power Development Plan 2023-2050 peak-demand
forecast, per grid, year by year (Table 28 of the plan).

The map and studio lean on a single-month Q1 demand baseline; the round-10/11
convergence critics named the DOE PDP's long-term demand outlook as the input
for a demand PATH in the LT Plan view (which today shows only the supply-side
committed and indicative build pipeline). This parses that outlook.

Source: DOE PDP 2023-2050, Table 28 "Peak Demand Forecast (2021-2050) in MW",
per grid. doe.gov.ph 403s non-PH requests, so the file is the Internet
Archive's capture of the DOE's own URL (see data/external/doe/SOURCES.md); the
pdftotext extraction is committed so the parse is reproducible without poppler,
mirroring the fleet_doe plant-list parse.

Gate, like fleet_doe: every year's three grid values must reconcile to the
plan's own Philippines total within 2 MW (rounding), or the build refuses. The
2021 and 2022 rows are the plan's actuals (starred); the rest is forecast,
labeled owner=DOE with the plan and its horizon.

    python3 pipeline/pdp_demand.py   # prints the parsed path
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TXT = os.path.join(HERE, "..", "data", "external", "doe",
                   "pdp_2023-2050.txt")
# Table 28 rows: Year[*]  Luzon  Visayas  Mindanao  Philippines (comma thousands)
_ROW = re.compile(
    r"^\s*(20[2-5][0-9])(\*?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$",
    re.M)
RECON_TOL_MW = 2.0
SRC = ("https://web.archive.org/web/20250423153601/https://doe.gov.ph/sites/"
       "default/files/pdf/electric_power/development_plans/"
       "Power%20Development%20Plan%202023-2050.pdf")


def _n(s: str) -> int:
    return int(s.replace(",", ""))


def build_demand_path() -> dict:
    if not os.path.isfile(TXT):
        return {"available": False,
                "note": "no PDP extraction; see data/external/doe/SOURCES.md"}
    txt = open(TXT, encoding="utf-8", errors="replace").read()
    seen: set[int] = set()
    years: list[int] = []
    grids: dict[str, list[int]] = {g: [] for g in
                                   ("luzon", "visayas", "mindanao")}
    national: list[int] = []
    actual_years: list[int] = []
    for y, star, lz, vs, mn, ph in _ROW.findall(txt):
        yi = int(y)
        if yi in seen:
            continue
        lzv, vsv, mnv, phv = _n(lz), _n(vs), _n(mn), _n(ph)
        # reconciliation gate: the three grids sum to the plan's own total
        if abs((lzv + vsv + mnv) - phv) > RECON_TOL_MW:
            raise RuntimeError(
                f"PDP demand: {yi} grids sum {lzv + vsv + mnv} != national "
                f"{phv}; refused")
        seen.add(yi)
        years.append(yi)
        grids["luzon"].append(lzv)
        grids["visayas"].append(vsv)
        grids["mindanao"].append(mnv)
        national.append(phv)
        if star:
            actual_years.append(yi)
    order = sorted(range(len(years)), key=lambda i: years[i])
    years = [years[i] for i in order]
    for g in grids:
        grids[g] = [grids[g][i] for i in order]
    national = [national[i] for i in order]
    if len(years) < 20:
        raise RuntimeError(
            f"PDP demand: only {len(years)} year-rows parsed; expected the "
            "full 2021-2050 table")
    forecast_from = max(actual_years) + 1 if actual_years else years[0]
    return {
        "available": True,
        "owner": "DOE",
        "plan": "Power Development Plan 2023-2050",
        "table": "Table 28. Peak Demand Forecast (2021-2050) in MW",
        "unit": "MW peak demand",
        "years": years,
        "per_grid_mw": grids,
        "philippines_mw": national,
        "actual_years": actual_years,
        "forecast_from_year": forecast_from,
        "cagr_2025_2050_pct": round(
            100 * ((national[years.index(2050)] / national[years.index(2025)])
                   ** (1 / 25) - 1), 2)
        if 2025 in years and 2050 in years else None,
        "note": ("The DOE Power Development Plan 2023-2050 peak-demand "
                 "forecast, per grid, year by year (the plan's Table 28). A "
                 "LABELED forecast owned by the DOE, not a measurement and "
                 "not this model's own projection; the 2021 and 2022 rows are "
                 "the plan's stated actuals. Each year's three grid values "
                 "reconcile to the plan's own Philippines total within 2 MW "
                 "or the build refuses. It gives the LT Plan view a demand "
                 "trajectory beside the supply-side committed and indicative "
                 "build pipeline; the data-center anchors (DICT, DOE, "
                 "Meralco) sit on top of this baseline growth."),
        "src": SRC,
    }


if __name__ == "__main__":
    import json
    d = build_demand_path()
    if d.get("available"):
        print(f"years {d['years'][0]}..{d['years'][-1]} "
              f"({len(d['years'])} rows); actuals {d['actual_years']}; "
              f"CAGR 2025-2050 {d['cagr_2025_2050_pct']}%")
        print("PH 2025/2030/2040/2050:",
              [d["philippines_mw"][d["years"].index(y)]
               for y in (2025, 2030, 2040, 2050)])
    else:
        print(json.dumps(d))
