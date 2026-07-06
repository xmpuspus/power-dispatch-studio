#!/usr/bin/env python3
"""Verified constants for gridbill-ph. Every value carries its primary source in
a comment or a `src` field. Nothing here is estimated by us; contested figures
appear as labeled ranges with both sources. Coordinates for corridors and data
centers are SCHEMATIC / CITY-PRECISION anchors for map display, never asserted
as exact routes or addresses (each feature carries a `precision` field).
"""
from __future__ import annotations

# --- Grid choke points (named in primary sources) -----------------------------
# Binding evidence: IEMOP December 2025 monthly report (Leyte-Luzon HVDC at its
# 250 MW Luzon-to-Visayas limit or offline 69% of the billing period; 230 kV
# Leyte-Cebu congestion), IEMOP May 2026 report via powerphilippines (both HVDC
# links frequently at maximum or security-limited transfer levels), NGCP TDP
# 2025-2050 + PIA (Cebu corridor relief targeted 2026).
# https://www.iemop.ph/news/december-2025-power-market-luzon-prices-ease-as-supply-improves-visayas-and-mindanao-experience-tighter-conditions/
# https://powerphilippines.com/wesm-prices-rise-38-5-in-may-as-demand-growth-outpaces-supply/
# https://www.ngcp.ph/Attachment-Uploads/TDP%202025-2050%20REPORT-2025-03-11-10-38-56.pdf
# https://pia.gov.ph/news/major-ngcp-projects-set-to-ease-power-congestion-in-cebu-by-2026/
CHOKEPOINTS = [
    {
        "id": "leyte_luzon_hvdc",
        "name": "Leyte-Luzon HVDC",
        "kind": "hvdc",
        # Converter stations: Ormoc, Leyte and Naga, Camarines Sur; 440 MW,
        # 350 kV, 451 km (21 km submarine). Wikipedia (fetched 2026-07-05):
        # https://en.wikipedia.org/wiki/HVDC_Leyte%E2%80%93Luzon
        "coords": [[124.6392, 11.0886], [123.2386, 13.6111]],
        "capacity_mw": 440,
        "operating_limit_mw": 250,  # Luzon-to-Visayas transfer limit, IEMOP Dec 2025
        "evidence": "At its 250 MW Luzon-to-Visayas limit or offline 69% of the Dec 2025 billing period (IEMOP)",
        "src": "https://www.iemop.ph/news/december-2025-power-market-luzon-prices-ease-as-supply-improves-visayas-and-mindanao-experience-tighter-conditions/",
        "precision": "schematic",
    },
    {
        "id": "mvip_hvdc",
        "name": "Mindanao-Visayas HVDC (MVIP)",
        "kind": "hvdc",
        # Cable terminals: Santander, Cebu and Dapitan, Zamboanga del Norte;
        # 450 MW expandable to 900 MW; 184 ckm submarine; first energized
        # 2023-04-30. T&D World (fetched 2026-07-05):
        # https://www.tdworld.com/intelligent-undergrounding/article/21265779/
        "coords": [[123.3380, 9.4177], [123.4243, 8.6549]],
        "capacity_mw": 450,
        "operating_limit_mw": None,
        "evidence": "Frequently at maximum or security-limited transfer levels in May 2026 (IEMOP monthly report)",
        "src": "https://powerphilippines.com/wesm-prices-rise-38-5-in-may-as-demand-growth-outpaces-supply/",
        "precision": "schematic",
    },
    {
        "id": "leyte_cebu_230kv",
        "name": "230 kV Leyte-Cebu corridor",
        "kind": "ac",
        # Schematic anchors: Ormoc (Leyte) to metro Cebu. Congestion named in
        # IEMOP Dec 2025 report ("congestion along the 230 kV Leyte-Cebu
        # transmission corridor").
        "coords": [[124.6392, 11.0886], [123.9000, 10.3200]],
        "capacity_mw": None,
        "operating_limit_mw": None,
        "evidence": "Named congested corridor limiting internal Visayas transfers, elevating Leyte nodal prices (IEMOP Dec 2025)",
        "src": "https://www.iemop.ph/news/december-2025-power-market-luzon-prices-ease-as-supply-improves-visayas-and-mindanao-experience-tighter-conditions/",
        "precision": "schematic",
        # Join receipts from the congestions-manifesting files onto this line.
        # Matched by name: the LEYTE_TO_CEBU interface row, plus the Tabango
        # (Leyte) to Daanbantayan (Cebu) 230 kV lines that carry the corridor
        # (station names 04TABANG / 05DAANBN in the same files).
        "equipment_match": ["LEYTE_TO_CEBU", "5DAAN_4TAB"],
    },
    {
        "id": "cebu_import",
        "name": "Cebu import corridor (Cebu-Lapu-Lapu 230 kV)",
        "kind": "ac",
        "coords": [[123.9000, 10.3200], [123.9494, 10.3103]],
        "capacity_mw": None,
        "operating_limit_mw": None,
        "evidence": "Congestion relief targeted by NGCP projects due 2026 (TDP project list; PIA)",
        "src": "https://pia.gov.ph/news/major-ngcp-projects-set-to-ease-power-congestion-in-cebu-by-2026/",
        "precision": "schematic",
    },
    {
        "id": "cnp_backbone",
        "name": "Cebu-Negros-Panay 230 kV backbone",
        "kind": "ac",
        # Chain: Cebu -> Amlan (Negros Oriental) -> Bacolod -> Iloilo. Last
        # stage completed 2024-03-27 (NGCP via NegrosNow; DOE stage PDF).
        "coords": [[123.8000, 10.2500], [123.2000, 9.4000],
                   [122.9500, 10.6600], [122.5500, 10.7000]],
        "capacity_mw": None,
        "operating_limit_mw": None,
        "evidence": "Backbone reinforced 2024 to relieve Region 6 constraints; the Visayas grid ran a 52-day daily yellow-alert streak that ended Jul 1, 2026",
        "src": "https://www.sunstar.com.ph/cebu/visayas-grid-exits-daily-yellow-alerts",
        "precision": "schematic",
    },
]

# --- Sual (the fragility example) ---------------------------------------------
# Sual coal-fired power station, Sual, Pangasinan: 2 x 647 MW, the largest
# single generating units on the Luzon grid. Unit trips are a recurring driver
# of yellow/red alerts (ICSC Power Outlook 2026; news record).
# https://en.wikipedia.org/wiki/Sual_Power_Station
# https://icsc.ngo/wp-content/uploads/2026/03/ICSC_Power-Outlook-2026.pdf
SUAL = {
    "name": "Sual coal plant",
    "location": "Sual, Pangasinan",
    "coords": [120.0970, 16.1170],  # city-precision
    "unit_mw": 647,
    "units": 2,
    "src": "https://en.wikipedia.org/wiki/Sual_Power_Station",
    "precision": "city",
}

# --- Named generators: the units that move price (contingency layer) ----------
# The plants large enough that a single trip is felt on the grid. Each carries a
# public source for its capacity; coordinates are CITY-PRECISION anchors on the
# named municipality, never the exact plant footprint. `fuel` keys into
# fleet_ph.FUEL_COST_PHP_KWH. These are a labeled subset of the full fleet in
# fleet_ph.GRID_FUEL_MW (their MW is already inside their grid's fuel total), used
# for the N-1 contingency picker and the map's generator layer.
GENERATORS = [
    # Luzon
    {"name": "Ilijan", "grid": "LUZON", "fuel": "natural_gas",
     "capacity_mw": 1200, "units": 2, "city": "Batangas City",
     "coords": [121.0700, 13.7400], "owner": "SMC Global Power",
     "note": "2x600 MW combined-cycle on Malampaya gas, the largest gas plant on "
             "the grid; the May 13 2026 line event took 2,462 MW of Batangas gas "
             "offline (not this plant's rating alone)",
     "src": "https://en.wikipedia.org/wiki/Ilijan_Combined-Cycle_Power_Plant",
     "precision": "city"},
    {"name": "Sual", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 1294, "units": 2, "city": "Sual, Pangasinan",
     "coords": [120.0970, 16.1170], "owner": "San Miguel (SMC Global Power)",
     "note": "2x647 MW, the largest single units on the Luzon grid",
     "src": "https://en.wikipedia.org/wiki/Sual_Power_Station",
     "precision": "city"},
    {"name": "GNPower Dinginin", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 1336, "units": 2, "city": "Mariveles, Bataan",
     "coords": [120.4833, 14.4333], "owner": "AC Energy + AboitizPower",
     "note": "2x668 MW supercritical; Unit 1 grid-connected Feb 2021, Unit 2 2022",
     "src": "https://www.nsenergybusiness.com/projects/dinginin-coal-fired-power-project/",
     "precision": "city"},
    {"name": "Pagbilao", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 1155, "units": 3, "city": "Pagbilao, Quezon",
     "coords": [121.6833, 13.9667], "owner": "TeaM Energy / AboitizPower",
     "note": "735 MW (Units 1-2) plus a 420 MW Unit 3 (2014)",
     "src": "https://en.wikipedia.org/wiki/Pagbilao_Power_Station",
     "precision": "city"},
    {"name": "Masinloc", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 1340, "units": 4, "city": "Masinloc, Zambales",
     "coords": [119.9333, 15.5333], "owner": "SMC Global Power (MPPCL)",
     "note": "Units 1-4 operating; about 1,578 MW at full expansion",
     "src": "https://www.gem.wiki/Masinloc_power_station",
     "precision": "city"},
    {"name": "Quezon Power", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 511, "units": 1, "city": "Mauban, Quezon",
     "coords": [121.7270, 14.1910], "owner": "Quezon Power (Philippines)",
     "note": "Pulverised-coal unit at Cagsiay, Mauban (2000)",
     "src": "https://www.gem.wiki/Quezon_power_station",
     "precision": "city"},
    {"name": "San Buenaventura", "grid": "LUZON", "fuel": "coal",
     "capacity_mw": 455, "units": 1, "city": "Mauban, Quezon",
     "coords": [121.7300, 14.1900], "owner": "San Buenaventura Power (MGen)",
     "note": "Supercritical unit alongside Quezon Power (2019)",
     "src": "https://www.power-technology.com/projects/san-buenaventura-supercritical-power-project/",
     "precision": "city"},
    # Visayas
    {"name": "Therma Visayas (TVI)", "grid": "VISAYAS", "fuel": "coal",
     "capacity_mw": 340, "units": 2, "city": "Toledo City, Cebu",
     "coords": [123.6330, 10.3670], "owner": "AboitizPower",
     "note": "2x170 MW; a 150 MW Unit 3 is targeted for 2027-2028",
     "src": "https://www.gem.wiki/Therma_Visayas_Energy_Project",
     "precision": "city"},
    {"name": "KSPC (Kepco SPC)", "grid": "VISAYAS", "fuel": "coal",
     "capacity_mw": 200, "units": 2, "city": "Naga City, Cebu",
     "coords": [123.7580, 10.2090], "owner": "KEPCO SPC / SPC Power",
     "note": "2x100 MW circulating fluidised-bed coal",
     "src": "https://www.kepcospc.com/",
     "precision": "city"},
    {"name": "PEDC", "grid": "VISAYAS", "fuel": "coal",
     "capacity_mw": 314, "units": 3, "city": "Iloilo City",
     "coords": [122.5850, 10.7200], "owner": "Global Business Power (MGen)",
     "note": "164 MW plus a 150 MW Unit 3; the return of Unit 3 on Jul 1 2026 "
             "ended the Visayas 52-day yellow-alert streak",
     "src": "https://www.meralcopowergen.com.ph/about/facilities/visayas/pedc/",
     "precision": "city"},
    {"name": "CEDC", "grid": "VISAYAS", "fuel": "coal",
     "capacity_mw": 246, "units": 3, "city": "Toledo City, Cebu",
     "coords": [123.6400, 10.3750], "owner": "Global Business Power (MGen)",
     "note": "Cebu Energy Development Corp, clean-coal CFB",
     "src": "https://www.gem.wiki/Cebu_power_station",
     "precision": "city"},
]

# --- Data-center sites (public sources only; NOT a complete inventory) --------
# Cushman & Wakefield counts 24 operational facilities (73 MW) with 22 MW under
# development and 89 MW in planning (APAC DC Update, 2025):
# https://www.cushmanwakefield.com/en/singapore/insights/apac-data-centre-update
# DataCenterMap lists 44 PH facilities. The rows below are the named facilities
# with a citable source; mw=None means no public MW figure found. Coordinates
# are CITY-PRECISION (the named city/municipality), never street addresses.
DC_SITES = [
    {"name": "ePLDT VITRO Sta. Rosa", "city": "Santa Rosa, Laguna",
     "coords": [121.1114, 14.3122], "mw": 50, "status": "operational",
     "src": "https://www.datacenterdynamics.com/en/news/pldt-subsidiary-vitro-tops-off-50mw-data-center-in-sta-rosa-philippines/"},
    {"name": "STT GDC Fairview campus", "city": "Quezon City",
     "coords": [121.0610, 14.7340], "mw": 124, "status": "under_construction",
     "note": "124 MW design; about 32 MW built as of April 2026",
     "src": "https://www.bworldonline.com/corporate/2026/04/23/744800/"},
    {"name": "STT GDC Makati", "city": "Makati",
     "coords": [121.0240, 14.5540], "mw": 3, "status": "operational",
     "src": "https://www.datacenterdynamics.com/en/news/stt-gdc-philippines-to-expand-three-data-centers/"},
    {"name": "STT GDC Quezon City", "city": "Quezon City",
     "coords": [121.0430, 14.6760], "mw": 5.5, "status": "operational",
     "src": "https://www.datacenterdynamics.com/en/news/stt-gdc-philippines-to-expand-three-data-centers/"},
    {"name": "STT GDC Cavite 1 and 2", "city": "Cavite",
     "coords": [120.9820, 14.3480], "mw": 10.8, "status": "operational",
     "note": "4.8 MW existing plus 6 MW expansion",
     "src": "https://www.datacenterdynamics.com/en/news/stt-gdc-philippines-to-expand-three-data-centers/"},
    {"name": "STT GDC Davao", "city": "Davao City",
     "coords": [125.6130, 7.0700], "mw": None, "status": "planned",
     "src": "https://www.sttelemediagdc.com/ph-en/locations"},
    {"name": "Digital Edge NARRA1", "city": "Metro Manila",
     "coords": [121.0000, 14.5500], "mw": 10, "status": "operational",
     "src": "https://www.datacentermap.com/philippines/manila/digital-edge-manila-narra1/"},
    {"name": "YCO Malvar One", "city": "Malvar, Batangas",
     "coords": [121.1580, 14.0450], "mw": 12, "status": "under_construction",
     "src": "https://www.datacenterdynamics.com/en/news/cloud-centers-developing-12mw-data-center-in-batangas-the-philippines/"},
    {"name": "Evolution DC + Megawide campus", "city": "Cavite",
     "coords": [120.9500, 14.3000], "mw": 69, "status": "planned",
     "note": "Phase 1 is 23 MW",
     "src": "https://www.datacenterdynamics.com/en/news/megawide-partners-with-evolution-data-centres-for-69mw-campus-outside-manila-philippines/"},
    {"name": "EdgeConneX + Aboitiz Manila", "city": "Manila",
     "coords": [120.9850, 14.5830], "mw": None, "status": "announced",
     "src": "https://www.edgeconnex.com/locations/asia-pacific/manila/"},
    {"name": "Converge Caloocan", "city": "Caloocan",
     "coords": [120.9830, 14.6570], "mw": 3, "status": "operational",
     "note": "Reported 300 racks; MW figure via directory listing",
     "src": "https://baxtel.com/data-center/philippines"},
    {"name": "Equinix MN2", "city": "Carmona, Cavite",
     "coords": [121.0570, 14.3160], "mw": 4, "status": "operational",
     "src": "https://baxtel.com/data-center/equinix-carmona-1"},
    {"name": "Equinix MN1/MN3", "city": "Makati",
     "coords": [121.0300, 14.5560], "mw": None, "status": "operational",
     "src": "https://newsroom.equinix.com/2025-10-22-Equinix-Connects-Philippine-Businesses"},
    {"name": "Narra Technology Park", "city": "New Clark City, Capas, Tarlac",
     "coords": [120.5560, 15.3190], "mw": 300, "status": "planned",
     "note": "3 x 100 MW, Phase 1 targeted Q4 2026, USD 2.7B",
     "src": "https://www.datacenterdynamics.com/en/news/300mw-data-center-campus-proposed-in-the-philippines/"},
]

# --- Demand-side anchors (labeled forecasts and commitments) -------------------
DEMAND_ANCHORS = [
    {"label": "DICT forecast: PH data-center capacity by 2028", "mw": 1500,
     "kind": "forecast", "owner": "DICT", "date": "2025-10",
     "src": "https://www.bworldonline.com/corporate/2025/10/23/707346/"},
    {"label": "DOE range: added peak demand from incoming data centers",
     "mw_low": 300, "mw_high": 1500, "kind": "forecast", "owner": "DOE",
     "date": "2026-01",
     "src": "https://pcij.org/2026/01/11/data-centers-raise-concerns/"},
    {"label": "Meralco committed capacity for 10 data centers", "mw": 1000,
     "kind": "commitment", "owner": "Meralco", "date": "2026-01",
     "src": "https://pcij.org/2026/01/11/data-centers-raise-concerns/"},
    {"label": "Data Center Philippines alliance pipeline", "mw": 473,
     "kind": "pipeline", "owner": "DCPH", "date": "2026-02",
     "src": "https://thephilbiznews.com/2026/02/22/data-center-alliance-unveils-473mw-to-power-phs-digital-rise/"},
    {"label": "Operational today (contested range)", "mw_low": 200,
     "mw_high": 630, "kind": "contested", "owner": "DICT vs Mordor Intelligence",
     "date": "2025",
     "src": "https://pcij.org/2026/01/11/data-centers-raise-concerns/"},
]

# --- Market and bill anchors ----------------------------------------------------
MARKET_ANCHORS = {
    # IEMOP May 2026 report via powerphilippines (first full post-resumption month)
    "wesm_may2026_system_avg_php_kwh": 7.79,
    "wesm_may2026_vs_april_pct": 38.5,
    "wesm_may2026_luzon": 7.02,
    "wesm_may2026_visayas": 10.20,
    "wesm_may2026_mindanao": 9.28,
    "wesm_may2026_supply_mw": 21374,
    "wesm_may2026_demand_mw": 15755,
    "wesm_may2026_margin_mw": 3629,
    "src_may2026": "https://powerphilippines.com/wesm-prices-rise-38-5-in-may-as-demand-growth-outpaces-supply/",
    # Suspension window (ERC; national energy emergency EO 110)
    "wesm_suspended_from": "2026-03-26",
    "wesm_resumed": "2026-05-01",
    "src_suspension": "https://tribune.net.ph/2026/05/01/wesm-restart-restores-market-driven-power-prices",
    # Meralco June 2026 advisory (typical 200 kWh household)
    "meralco_june2026_rate_php_kwh": 14.4833,
    "meralco_june2026_delta_php_kwh": 0.1488,
    "meralco_june2026_generation_charge": 9.0704,
    "meralco_june2026_wesm_cost_php_kwh": 7.0281,
    "src_meralco_june": "https://www.bworldonline.com/top-stories/2026/06/12/756242/meralco-rates-climb-p0-15-kwh-in-june/",
    # Visayas alert streak (grid fragility in-window). The daily yellow-alert
    # streak ran May 11 to Jul 1, 2026 (52 days) and ended at 2:40 pm Jul 1 when
    # PEDC Unit 3 returned 150 MW; TVI Units 1 and 2 (169 MW each) stayed out.
    # On Jul 1 the grid ran 2,599 MW available against a 2,411 MW peak with
    # 935.3 MW unavailable. Both sources fetched 2026-07-05.
    "visayas_yellow_streak_days": 52,
    "visayas_yellow_streak_from": "2026-05-11",
    "visayas_yellow_streak_to": "2026-07-01",
    "visayas_streak_end_return_mw": 150,
    "visayas_unavailable_mw_jul1": 935.3,
    "src_visayas_streak_end": "https://www.sunstar.com.ph/cebu/visayas-grid-exits-daily-yellow-alerts",
    "src_visayas_jul1": "https://www.gmanetwork.com/news/money/economy/993308/ngcp-visayas-grid-on-yellow-alert-on-wednesday-july-1-2026/story/",
    # Mid-streak forced-outage snapshot (late June 2026)
    "visayas_forced_outage_mw": 1001.5,
    "src_visayas": "https://cebudailynews.inquirer.net/740334/visayas-grid-enters-7th-straight-week-of-yellow-alerts",
    # IEMOP Dec 2025 (choke-point binding share)
    "hvdc_binding_share_dec2025_pct": 69,
    "src_dec2025": "https://www.iemop.ph/news/december-2025-power-market-luzon-prices-ease-as-supply-improves-visayas-and-mindanao-experience-tighter-conditions/",
}

REGIONS = ["LUZON", "VISAYAS", "MINDANAO"]
