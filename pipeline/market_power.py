#!/usr/bin/env python3
"""Bake the market-power / concentration layer.

The dispatch model prices energy from a merit-order stack; it says nothing about who
OWNS the stack. The WESM's own market-assessment reports track structural indices
(HHI, price-setting frequency, pivotal-supplier, residual-supply index) because a
concentrated fleet can move price even when the physics has headroom. This bakes the
concentration picture from the ERC's published 2024 generation-capacity shares so the
studio can show it, and frames the pivotal-supplier idea against the thin reserve
margin the dispatch model already computes.

NOT a model: these are the regulator's own published capacity shares. The HHI is
computed from them here (with its method stated); the caveats (national capacity
shares, not per-grid or energy-weighted) are carried in the output.

Sources:
  ERC 2024 generation market shares (released 17 March 2025), via BusinessWorld /
  The Electricity Hub:
    https://bworldonline.com/corporate/2025/03/18/659948/smc-leads-power-generation-with-22-44-market-share-erc/
  EPIRA market-share and capacity caps (30% of installed capacity, 25% of a grid's
  demand): Republic Act 9136.
    https://www.doe.gov.ph/sites/default/files/pdf/issuances/ra-9136.pdf
"""
from __future__ import annotations

# ERC 2024 generation-capacity market shares (national, released 17 March 2025).
# name, installed MW, share of national capacity (%).
COMPANIES = [
    ("San Miguel Corporation", 6079.6, 22.44),
    ("Aboitiz Equity Ventures", 5894.5, 21.75),
    ("First Gen Corporation", 3582.9, 13.22),
    ("Manila Electric Co. (Meralco)", 1467.3, 5.42),
    ("Ayala Corporation", 1431.3, 5.28),
]
SRC = "https://bworldonline.com/corporate/2025/03/18/659948/smc-leads-power-generation-with-22-44-market-share-erc/"

# EPIRA (RA 9136) market-power caps: a firm may not control more than 30% of the
# installed capacity of a grid, nor 25% of the national demand.
CAP_INSTALLED_PCT = 30
CAP_DEMAND_PCT = 25
SRC_CAP = "https://www.doe.gov.ph/sites/default/files/pdf/issuances/ra-9136.pdf"

# ERC 2025 annual cap on national installed generating capacity (context for shares).
NATIONAL_CAP_MW_2025 = 27096.04


def build_market_power() -> dict:
    named = sum(s for _, _, s in COMPANIES)
    others = round(100 - named, 2)
    companies = [{"name": n, "mw": mw, "share_pct": s} for n, mw, s in COMPANIES]

    # HHI is the sum of squared percentage shares. The full market's individual
    # "others" firms are not published, so we bracket it:
    #   floor  = named firms squared + "others" treated as perfectly fragmented (0)
    #   ceiling = named firms squared + "others" treated as a single firm
    # The true HHI sits between. US DOJ bands: <1500 unconcentrated, 1500-2500
    # moderately concentrated, >2500 highly concentrated.
    hhi_named = sum(s * s for _, _, s in COMPANIES)
    hhi_floor = round(hhi_named, 1)
    hhi_ceiling = round(hhi_named + others * others, 1)
    top2 = round(COMPANIES[0][2] + COMPANIES[1][2], 2)
    largest = COMPANIES[0]

    if hhi_floor >= 2500:
        band = "highly concentrated"
    elif hhi_floor >= 1500:
        band = "moderately concentrated"
    else:
        band = "at least moderately concentrated once the unlisted firms are counted"

    return {
        "available": True,
        "as_of": "2024 (ERC report, 17 March 2025)",
        "national_cap_mw_2025": NATIONAL_CAP_MW_2025,
        "companies": companies,
        "others_share_pct": others,
        "hhi_floor": hhi_floor,
        "hhi_ceiling": hhi_ceiling,
        "hhi_band": band,
        "top2_combined_pct": top2,
        "largest": {"name": largest[0], "mw": largest[1], "share_pct": largest[2]},
        "cap_installed_pct": CAP_INSTALLED_PCT,
        "cap_demand_pct": CAP_DEMAND_PCT,
        "pivotal_supplier_note": "A generator is a pivotal supplier when the system cannot "
                        "meet demand without it: its residual-supply index, (total "
                        "supply minus that supplier) over demand, falls below 1. The "
                        "largest generator holds " + f"{largest[2]:.1f}%" + " of "
                        "national capacity, far more than the thin peak reserve "
                        "margin, so at the peak the grid is not served without it. "
                        "That is the market power the merit-order price cannot show.",
        "rsi_note": "HHI, price-setting frequency, pivotal-supplier and the "
                    "residual-supply index are the WESM's own published structural "
                    "indices (PEMC and ERC market-assessment reports). This view "
                    "reconstructs the concentration picture from the ERC's capacity "
                    "shares; it does not recompute the interval-level RSI.",
        "note": "These are national installed-CAPACITY shares from the ERC, not "
                "per-grid shares and not energy-weighted generation. Capacity share "
                "sets the ceiling on market power; actual price-setting depends on "
                "who is on the margin hour to hour.",
        "disclaimer": "Statistical indicators derived from public data. Patterns may "
                      "have legitimate explanations.",
        "src": SRC,
        "src_cap": SRC_CAP,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_market_power(), indent=1))
