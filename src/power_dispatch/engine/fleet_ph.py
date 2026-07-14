# GENERATED from pipeline/fleet_ph.py by tools/sync_engine.py -- do not edit.
# Edit the pipeline source and re-run the sync; tests/test_engine_sync.py enforces identity.
#!/usr/bin/env python3
"""PH generator fleet reference for the simplified merit-order dispatch model.

This is the sourced input layer for pipeline/dispatch.py. Two kinds of number live
here and they are kept apart on purpose:

  SOURCED (primary source in a comment or `src`):
    - installed capacity by fuel, nationally (DOE, via REGlobal, Feb 2025 snapshot)
    - installed capacity by grid, total (DOE: Luzon 21,742 MW / 74%)
    - geothermal by grid (DOE)
    - natural gas is entirely on Luzon (the Batangas / Malampaya complex)
    - marginal-cost proxies: coal P6.00/kWh (ERC administered price during the
      2026 WESM suspension; power producers backed P6), Malampaya gas P4.80/kWh,
      imported LNG P10.30/kWh
    - the named price-mover units come from constants_ph.GENERATORS (each sourced)

  MODEL ASSUMPTION (labeled, not asserted as data):
    - the split of coal / oil / solar / wind / biomass ACROSS grids. Only grid
      TOTALS and national FUEL totals are published as aggregates; GRID_FUEL_MW
      reconciles to both exactly (column sums == national fuel totals) while
      honouring the sourced anchors (all gas on Luzon; geothermal split
      published; hydro derived from the DOE plant lists, see below). It is not
      a claim about which unnamed plant sits on which grid.
    - EXCEPTION, hydro: the DOE existing-plants lists (fleet_doe.py) name every
      grid-connected hydro plant per grid, so the hydro row is DERIVED from
      that fleet, not allocated. Installed shares Luzon 66.7% / Visayas 1.4% /
      Mindanao 31.8% (fleet total 3,840.6 MW, within 0.2% of the national
      anchor), prorated onto the 3,836 MW anchor so the column pin still holds.
      Recalibrated 2026-07-07 after observed WESM hydro dispatch (DIPCEF, see
      fuelmix.py) contradicted the old allocation: Visayas hydro cleared up to
      377 MWh/day against a modeled 5.5 MW of available capacity.
    - fuel availability derates and the solar time-of-day profile
    - the oil / peaker marginal cost (sets the scarcity price; the calibration
      residual, not this number, carries the scarcity premium)
    - CO2 emission factors by fuel (IPCC/EIA typical values)

Nothing here is a production-cost optimiser. It is a transparent economic-dispatch approximation whose
honesty gate is the calibration residual against observed LWAP (see dispatch.py).

Sources:
  https://reglobal.org/philippines-grid-expansion-ngcp-focuses-on-renewables-integration/
  https://bilyonaryo.com/2026/03/31/power-producers-back-p6-kwh-coal-price-during-wesm-suspension/
  https://www.foi.gov.ph/requests/malampaya-natural-gas-price/
"""
from __future__ import annotations

GRIDS = ["LUZON", "VISAYAS", "MINDANAO"]

# --- national installed capacity by fuel (MW) ---------------------------------
# DOE, as of 2026-02-28 (via REGlobal), total 30,487 MW incl 634 MW storage which
# is excluded from the energy dispatch stack here.
NATIONAL_FUEL_MW = {
    "coal": 13006,
    "natural_gas": 3732,
    "oil": 3448,
    "hydro": 3836,
    "geothermal": 1952,
    "solar": 2857,
    "wind": 427,
    "biomass": 595,
}
# Published per-grid TOTALS (DOE, same snapshot): Luzon 21,742 (74%), Mindanao ~16%,
# Visayas ~14%. Used to sanity-check the row sums below, not to override them.
GRID_TOTAL_MW = {"LUZON": 21742, "VISAYAS": 4267, "MINDANAO": 4878}

# --- installed capacity by grid AND fuel (MW) ---------------------------------
# MODEL ALLOCATION. Column sums equal NATIONAL_FUEL_MW exactly. Anchored on sourced
# facts: all natural gas on Luzon (Batangas/Malampaya complex); geothermal split
# Luzon 865 / Visayas 975 / Mindanao 112 (DOE); hydro DERIVED from the DOE
# grid-connected plant lists (fleet_doe.py installed shares 66.7 / 1.4 / 31.8%,
# prorated onto the 3,836 MW national anchor; recalibrated 2026-07-07 against
# observed DIPCEF hydro dispatch, never against prices). The remaining fuels are
# distributed to match each grid's published total and each fuel's national total,
# with coal concentrated where the named units (constants_ph.GENERATORS) actually
# sit. Rows may sit UNDER their published grid total (storage and vintage gaps
# are excluded from the fuel columns) but never over it: a grid cannot carry
# more installed MW than the DOE says it has. Tests assert both the column
# reconciliation and the row ceiling. The hydro correction is absorbed in the
# oil proxy (the only fuel with no per-grid anchor: no named Mindanao units,
# no published split), keeping Mindanao exactly at its published total.
GRID_FUEL_MW = {
    "LUZON":    {"coal": 8850, "natural_gas": 3732, "oil": 2461, "hydro": 2560,
                 "geothermal": 865, "solar": 1800, "wind": 350, "biomass": 350},
    "VISAYAS":  {"coal": 1550, "natural_gas": 0, "oil": 500, "hydro": 55,
                 "geothermal": 975, "solar": 700, "wind": 77, "biomass": 150},
    "MINDANAO": {"coal": 2606, "natural_gas": 0, "oil": 487, "hydro": 1221,
                 "geothermal": 112, "solar": 357, "wind": 0, "biomass": 95},
}

# --- marginal-cost proxy by fuel (PHP/kWh) ------------------------------------
# Coal and gas are SOURCED (ERC administered price; Malampaya gas price). The rest
# are labelled proxies ordered so the merit order is realistic: zero-fuel renewables
# at the bottom, oil peakers at the top setting the scarcity price.
FUEL_COST_PHP_KWH = {
    "solar": 0.00,        # no fuel cost (assumption: bid at floor)
    "wind": 0.00,         # no fuel cost
    "hydro": 0.50,        # near-zero fuel; small O&M proxy
    "geothermal": 3.50,   # steam-field O&M proxy (must-run in practice)
    "natural_gas": 4.80,  # SOURCED: Malampaya gas ~P4.80/kWh (FOI)
    "biomass": 5.00,      # feedstock proxy
    "coal": 6.00,         # SOURCED: ERC administered coal price P6,000/MWh (2026)
    "lng": 10.30,         # SOURCED: imported LNG ~P10.30/kWh (marginal gas as
                          # Malampaya depletes; used only by the LNG scenario lever)
    "oil": 12.00,         # ASSUMPTION: bunker/diesel peaker proxy; scarcity setter
}

# SOURCED: the WESM offer price ceiling, P32/kWh (WESM Tripartite Committee
# Joint Resolution No. 2 s.2013, permanent since Dec 2015). Short hours price
# here in every engine: the market's own ceiling is where administrative
# shortage pricing lands. https://resaph.com/p32kwh-price-ceiling-on-power-trade-permanent-wesm/
WESM_OFFER_CAP_PHP_KWH = 32.0

# --- availability derate by fuel (fraction of installed that can be dispatched) -
# LABELLED ASSUMPTIONS. Solar is handled separately by SOLAR_PROFILE (time of day).
FUEL_AVAIL = {
    "coal": 0.85, "natural_gas": 0.90, "oil": 0.92, "geothermal": 0.90,
    "hydro": 0.55, "biomass": 0.70, "wind": 0.30, "solar": 1.00,
}

# Normalised clear-sky-ish PH solar output by hour (0..1). LABELLED ASSUMPTION;
# multiplies installed solar to approximate midday depression of the price curve.
SOLAR_PROFILE = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.05, 7: 0.20, 8: 0.40,
    9: 0.58, 10: 0.70, 11: 0.76, 12: 0.78, 13: 0.75, 14: 0.66, 15: 0.52,
    16: 0.34, 17: 0.14, 18: 0.02, 19: 0.0, 20: 0.0, 21: 0.0, 22: 0.0, 23: 0.0,
}

# --- forced outage rate by fuel (probability a unit is unexpectedly unavailable) -
# Used by the Monte Carlo reliability model. Coal and gas are SOURCED to NERC GADS
# (coal weighted EFOR ~10-12%, gas ~2-5%); the rest are LABELED industry-typical
# values (IEEE-RTS-style) with no clean PH-specific published rate. Solar and wind
# carry no forced-outage rate here: their variability is already in SOLAR_PROFILE
# and the availability derate, not an unplanned-trip model.
# https://www.nerc.com/programs/reliability-assessment--performance-analysis/generating-availability-data-system/gads-conventional/general-availability-review-weighted-efor-dashboard
FORCED_OUTAGE_RATE = {
    "coal": 0.10,         # SOURCED: NERC GADS coal EFOR ~10-12%
    "natural_gas": 0.05,  # SOURCED: NERC GADS gas ~2-5%
    "oil": 0.10,          # LABELED: diesel/bunker peaker typical
    "geothermal": 0.08,   # LABELED: steam-field/well outages, typical
    "hydro": 0.04,        # LABELED: industry-typical
    "biomass": 0.08,      # LABELED: industry-typical
    "solar": 0.0, "wind": 0.0,
}

# --- storage: batteries + pumped hydro (peak-firming time-shifters) -----------
# Excluded from the energy dispatch stack (they store, they do not generate net
# energy), storage charges off-peak and discharges at the evening peak. For the
# adequacy and reliability model, what matters at the tight evening interval is the
# discharge POWER (MW), assuming the store is charged. SOURCED:
#   - Battery ESS 634 MW national (DOE, as of 2025-03-31). Placed on Luzon here as a
#     labeled simplification (most PH BESS, the SMC fleet, sits on Luzon).
#     https://legacy.doe.gov.ph/electric-power/list-existing-power-plants-march-2025
#   - Kalayaan pumped storage 685 MW (KPSPP I 336 + KPSPP II 348.6 MW GNCC, CBK
#     Power), Laguna, on Luzon. Southeast Asia's first pumped-storage plant.
#     http://www.cbkpower.com/project/kalayaan-pumped-storage-power-plant-kpspp/
# Energy is limited (BESS ~1-4h, pumped hydro longer), so this firms the peak
# interval, not a multi-day event. Round-trip efficiency ~80% (labeled).
STORAGE_MW = {
    "LUZON": {"bess": 634, "pumped_hydro": 685},
    "VISAYAS": {"bess": 0, "pumped_hydro": 0},
    "MINDANAO": {"bess": 0, "pumped_hydro": 0},
}
STORAGE_ROUND_TRIP_EFF = 0.80

# --- CO2 emission factors (tCO2 per MWh) --------------------------------------
# LABELLED ASSUMPTIONS (IPCC/EIA typical direct-combustion factors).
FUEL_CO2_T_PER_MWH = {
    "coal": 0.95, "natural_gas": 0.42, "lng": 0.42, "oil": 0.75,
    "geothermal": 0.0, "hydro": 0.0, "solar": 0.0, "wind": 0.0, "biomass": 0.0,
}

# Cost order for stacking (low to high); solar/wind first as zero-fuel must-take.
MERIT_ORDER = ["solar", "wind", "hydro", "geothermal", "natural_gas",
               "biomass", "coal", "lng", "oil"]

# --- minimal unit commitment (labeled) ----------------------------------------
# The static cost stack over-prices the overnight trough: it sets the coal block at
# the full P6.00 administered price, but committed baseload coal offers far below
# that overnight to avoid a costly shutdown and restart. We split coal into a
# committed must-run tranche and a marginal tranche:
#   - COAL_MIN_LOAD_FRAC of available coal is the minimum stable load a committed
#     unit cannot drop below (~40% for thermal units; the fleet stays online rather
#     than cycle daily). SOURCED: coal technical minimum load ~40%.
#     https://powerline.net.in/2023/04/04/flexibilisation-roadmap-aiming-for-tpps-to-operate-at-40-per-cent-minimum-technical-load/
#     https://www.intechopen.com/chapters/58563
#   - that tranche offers at COAL_COMMIT_PHP_KWH, the level committed coal bids down
#     to overnight. Anchored on the observed normal-market clearing level, the H1
#     2025 WESM average of P4.14/kWh (lowest since 2020, below the P6 administered
#     ceiling), NOT tuned to the overnight trough.
#     https://www.philstar.com/business/2026/01/05/2498730/wesm-prices-hit-fresh-lows-2025
# The marginal (cycling) coal tranche keeps the P6.00 administered price. This lowers
# the modeled overnight price where demand is light without touching the evening
# peak (still on the P6 tranche or oil), so the scarcity residual is preserved.
COAL_MIN_LOAD_FRAC = 0.40
COAL_COMMIT_PHP_KWH = 4.14


def avail_mw(grid: str, fuel: str, hour: int) -> float:
    """Dispatchable MW for a fuel on a grid at a given hour."""
    installed = GRID_FUEL_MW[grid].get(fuel, 0)
    if fuel == "solar":
        return installed * SOLAR_PROFILE.get(hour, 0.0)
    return installed * FUEL_AVAIL.get(fuel, 1.0)


def stack(grid: str, hour: int, removed: dict | None = None,
          commitment: bool = True) -> list[dict]:
    """Merit-order supply stack for a grid at an hour: blocks sorted by cost.

    `removed` optionally subtracts MW from a fuel (an N-1 trip or a de-rate).
    `commitment` splits coal into a committed must-run tranche (at the low
    commitment offer) and a marginal tranche (at the P6 administered price); set
    False for the static before-commitment comparison. Each block: {fuel, cost, mw}.
    """
    removed = removed or {}
    blocks = []
    for fuel in MERIT_ORDER:
        if fuel == "lng":
            continue  # LNG is a scenario lever, not base installed capacity
        mw = avail_mw(grid, fuel, hour) - removed.get(fuel, 0.0)
        if mw <= 0:
            continue
        if fuel == "coal" and commitment:
            # committed min-load tranche offers below the administered price; the
            # rest (cycling coal) stays at P6. Same total MW, same fuel key.
            must_run = round(mw * COAL_MIN_LOAD_FRAC, 1)
            blocks.append({"fuel": "coal", "cost": COAL_COMMIT_PHP_KWH,
                           "mw": must_run})
            blocks.append({"fuel": "coal", "cost": FUEL_COST_PHP_KWH["coal"],
                           "mw": round(mw - must_run, 1)})
        else:
            blocks.append({"fuel": fuel, "cost": FUEL_COST_PHP_KWH[fuel],
                           "mw": round(mw, 1)})
    blocks.sort(key=lambda b: b["cost"])
    return blocks


def clear(blocks: list[dict], demand_mw: float,
          imports: list[dict] | None = None) -> dict:
    """Clear a demand against a merit-order stack (plus optional import blocks).

    Returns {price, served_mw, avail_mw, shortfall_mw, marginal_fuel}. If
    demand exceeds available supply the hour is short: it prices at the
    sourced WESM offer cap (P32/kWh, the market's own ceiling; see
    constants_ph.MARKET_ANCHORS) and the shortfall is reported (the model's
    LOLE/EUE signal). A published market rule, not a fitted value.
    """
    merged = sorted((blocks or []) + (imports or []), key=lambda b: b["cost"])
    total = sum(b["mw"] for b in merged)
    cum = 0.0
    price = merged[-1]["cost"] if merged else 0.0
    marginal = merged[-1]["fuel"] if merged else None
    for b in merged:
        cum += b["mw"]
        if cum >= demand_mw:
            price, marginal = b["cost"], b["fuel"]
            break
    shortfall = max(0.0, demand_mw - total)
    if shortfall > 0:
        price, marginal = WESM_OFFER_CAP_PHP_KWH, "shortage"
    return {"price": round(price, 3), "served_mw": round(min(demand_mw, total), 1),
            "avail_mw": round(total, 1), "shortfall_mw": round(shortfall, 1),
            "marginal_fuel": marginal}
