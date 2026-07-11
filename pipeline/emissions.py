#!/usr/bin/env python3
"""Bake CO2 emission factors per generation technology, with sources.

Operational (combustion) factors only; lifecycle is out of scope and said so.
Fossil factors are the IPCC 2006 fuel-combustion defaults converted at the
Philippine average heat efficiencies the EMB publishes (coal 39%, CCGT 60%);
oil-based uses the EMB's own diesel-plant figure. Geothermal carries a small
nonzero factor (dissolved CO2 in the working fluid); hydro, solar, wind and
storage discharge carry zero operational CO2 (their lifecycle emissions are
real and out of scope). Biomass is EXCLUDED from the sum: its carbon
accounting is contested, so it is not counted either way.

The DOE's published National Grid Emission Factor is baked alongside as an
order-of-magnitude cross-check, never used in the per-fuel math.
"""
from __future__ import annotations

SRC_IPCC = ("https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/2_Volume2/"
            "V2_2_Ch2_Stationary_Combustion.pdf")
SRC_EMB = ("https://emb.gov.ph/wp-content/uploads/2019/11/"
           "3.-Add-information-for-solar-PV-systems_Philippines_final.pdf")
SRC_NGEF = ("https://doe.gov.ph/site/epimb/articles/group/statistics?"
            "category=National+Grid+Emission+Factor+(NGEF)&display_type=Card")
SRC_GEO = "https://www.ipcc.ch/site/assets/uploads/2018/03/Chapter-4-Geothermal-Energy-1.pdf"

# tCO2 per MWh generated, operational. None = excluded from the sum, reason in
# the row note.
FACTORS = [
    {"fuel": "coal", "tco2_per_mwh": 0.874,
     "basis": "IPCC 94.6 tCO2/TJ at the EMB's 39% PH average coal efficiency",
     "src": SRC_IPCC, "src2": SRC_EMB},
    {"fuel": "natural_gas", "tco2_per_mwh": 0.337,
     "basis": "IPCC 56.1 tCO2/TJ at the EMB's 60% PH average CCGT efficiency",
     "src": SRC_IPCC, "src2": SRC_EMB},
    {"fuel": "oil", "tco2_per_mwh": 0.533,
     "basis": "EMB Philippines diesel-plant emission factor",
     "src": SRC_EMB},
    {"fuel": "geothermal", "tco2_per_mwh": 0.040,
     "basis": "midpoint of the IPCC 6-79 gCO2/kWh geothermal range "
              "(dissolved CO2 in the working fluid; field-specific)",
     "src": SRC_GEO},
    {"fuel": "hydro", "tco2_per_mwh": 0.0,
     "basis": "zero operational; lifecycle (construction, reservoirs) out of scope",
     "src": SRC_GEO},
    {"fuel": "solar", "tco2_per_mwh": 0.0,
     "basis": "zero operational; lifecycle (manufacturing) out of scope",
     "src": SRC_GEO},
    {"fuel": "wind", "tco2_per_mwh": 0.0,
     "basis": "zero operational; lifecycle (manufacturing) out of scope",
     "src": SRC_GEO},
    {"fuel": "storage", "tco2_per_mwh": 0.0,
     "basis": "discharge carries no factor of its own; the charging energy was "
              "already counted at the generating fuel",
     "src": SRC_EMB},
    {"fuel": "biomass", "tco2_per_mwh": None,
     "basis": "excluded: biogenic carbon accounting is contested; biomass MWh "
              "is reported uncounted rather than assigned a factor",
     "src": SRC_IPCC},
]


def build_emissions() -> dict:
    factor_map = {f["fuel"]: f["tco2_per_mwh"] for f in FACTORS
                  if f["tco2_per_mwh"] is not None}
    return {
        "available": True,
        "unit": "tCO2 per MWh generated, operational (combustion) only",
        "factors": FACTORS,
        "factor_map": factor_map,
        "ngef": {
            "luzon_visayas_tco2_per_mwh": 0.7181,
            "mindanao_tco2_per_mwh": 0.8173,
            "vintage": "2019-2021 (most recent DOE publication)",
            "src": SRC_NGEF,
            "note": ("The DOE's published National Grid Emission Factor, the "
                     "grid-average across all technologies. A cross-check "
                     "anchor for the per-fuel math, not an input to it."),
        },
        "note": ("Per-technology operational factors: IPCC 2006 fuel defaults "
                 "at the EMB's published Philippine heat efficiencies, plus "
                 "the EMB diesel figure. Lifecycle emissions (manufacturing, "
                 "dams, upstream fuel) are real and out of scope; renewable "
                 "rows would be nonzero on a lifecycle basis."),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_emissions(), indent=1))
