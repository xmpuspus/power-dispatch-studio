#!/usr/bin/env python3
"""Bake web/data/perspective.json: every number on the pax-silica.html scale page.

The page draws the campus's announced needs against things a reader already
knows. Each figure is either an announced number carried with its source, a
model output read from the sites bake, or arithmetic done here. The page reads
only this file, so its prose cannot drift from the arithmetic.

    python3 pipeline/perspective.py
"""
from __future__ import annotations

import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web", "data")

# --- announced figures, each with its primary source -------------------------
# BCDA (Bingcang): "Initial assessment is to be conservative, around, at full
# development, mga three gigawatts po iyan". Same piece: BCDA says the draw
# "will not cut into the current power supplies in the area".
# https://www.gmanetwork.com/news/money/economy/995915/pax-silica-ai-hub-to-consume-3-gigawatts-at-full-development-bcda/story/
CAMPUS_MW = 3000.0
# How far out "at full development" is. BCDA (Bingcang) via BusinessMirror:
# "While the construction of the site is expected to start in the first quarter
# of 2028, its full development will take another 10 to 15 years."
# https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/
BUILD_START_YEAR = 2028
FULL_BUILD_YEARS_LOW, FULL_BUILD_YEARS_HIGH = 10, 15
# Inquirer Business, 22 Jun 2026, the reporter's own sentence: an enclave
# "whose projected electricity demand could reach at least 5 gigawatts". Not
# attributed there to BCDA, and it predates BCDA's own 3 GW figure of 23 Jul.
# https://business.inquirer.net/596398/pax-silicas-mammoth-power-needs-draw-maharlika-foreign-interest
CAMPUS_MW_CEILING = 5000.0
# BCDA (Bingcang): "65 to 90 million liters of water ... per day"
# https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/
WATER_MLD_LOW, WATER_MLD_HIGH = 65.0, 90.0
# same piece: "surface water harvesting facility, which will generate 120
# million liters per day"; also https://www.manilatimes.net/2026/07/24/regions/rainwater-eyed-for-use-at-planned-pax-silica-hub/2390193
HARVEST_MLD = 120.0
# ACWA Power lease signed 2026-06-02: up to 500 MW solar + storage on 500 ha
# https://www.enerdata.net/publications/daily-energy-news/acwa-power-secures-site-500-mw-solar-bess-project-philippines.html
ACWA_MW, ACWA_HA = 500.0, 500.0
# BCDA (Bingcang): "1,620 hectares in New Clark City in Tarlac have been
# designated as an industrial area for the Pax Silica initiative"
# https://www.philstar.com/business/2026/07/24/2544359/pax-silica-investors-may-lease-new-clark-land-99-years-bcda
# Manila Bulletin puts the same footprint as a 4,000-acre economic security
# zone, which is 1,618.7 ha, so the spread in reported figures (1,618 to 1,620)
# is acre-to-hectare rounding of one area, not three different scopes.
SITE_HA = 1620.0
# Capas municipal government data, cited by the scientists' group Agham:
# "over 30 percent of its land area is considered productive agricultural land"
# https://www.philstar.com/headlines/2026/07/27/2545030/scientists-group-debunks-claims-pax-silica-project
CAPAS_FARMLAND_PCT = 30.0
# BCDA (Bingcang, Super Radyo DZBB): "there are only around 10 farmers
# affected". Kalikasan (De Guzman, via South China Morning Post) puts
# displacement from the New Clark City project as a whole at 20,000
# Indigenous people and 15,000 farmers. The two cover DIFFERENT ground: the
# first is the Pax Silica site, the second the whole city. Never subtract them.
FARMERS_BCDA = 10
DISPLACED_ADVOCACY_IP, DISPLACED_ADVOCACY_FARMERS = 20000, 15000
# BCDA's own initial list of Project Affected Persons, reported by the
# scientists' group Agham: residents of three Capas barangays are on it. This
# is the published thing that sits against the 10-farmer count, so the page
# must carry it wherever it carries the 10.
# https://www.philstar.com/headlines/2026/07/27/2545030/scientists-group-debunks-claims-pax-silica-project
PAP_BARANGAYS = ["O'Donnell", "Aranguren", "Santa Lucia"]
# BCDA's own case, carried so the land card is not one-sided. Direct jobs
# 130,000 to 190,000, per BCDA via Philstar, 24 Jul 2026.
# https://www.philstar.com/business/2026/07/24/2544359/pax-silica-investors-may-lease-new-clark-land-99-years-bcda
JOBS_DIRECT_LOW, JOBS_DIRECT_HIGH = 130000, 190000
# DENR issued an environmental compliance certificate for the MASTERPLAN, per
# BCDA (Bingcang) via BusinessMirror, 23 Jul 2026; each locator still needs its
# own. No tree inventory and no tree-cutting permit is published, which is a
# separate absence and the only one the page may claim.
# https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/
ECC_MASTERPLAN_ISSUED = True
ECC_PER_LOCATOR_PENDING = True
TREE_COUNT_PUBLISHED = False

# The Capas 230 kV substation. The cost and the facility are NGCP's, from its
# Transmission Development Plan 2024 to 2050: "According to the plan, NGCP will
# allocate P6.95 billion to develop the facility." The end-2028 date is BCDA's
# target, not NGCP's commitment: Bingcang said "Our target with them is by [the]
# end of 2028, the dedicated power connection should be already installed in New
# Clark City." Keep the two owners apart wherever the page prints them.
# https://mb.com.ph/2026/05/25/us-pax-silica-alliance-prompts-7-billion-power-expansion-in-new-clark-city
SUBSTATION_PHP_B, SUBSTATION_KV, SUBSTATION_YEAR = 6.95, 230, 2028
SUBSTATION_COST_OWNER = "NGCP transmission development plan"
SUBSTATION_DATE_OWNER = "BCDA target"

# --- external anchors, each with its primary source --------------------------
# Meralco's July 2026 rate advisory works its example bill at 200 kWh a month:
# "For residential customers consuming 200 kWh, this adjustment translates to
# an increase of P69". Meralco does not call 200 kWh typical, so the page must
# say "the 200 kWh a month Meralco works its example bill on".
# https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-july-2026
HOME_KWH_MONTH = 200.0
DAYS_PER_MONTH = 30.4166  # 365 / 12, so the homes figure is a monthly average
# Makati after the ten Embo barangays moved to Taguig (2023):
# 309,770 people (2024 census), 18.17 km2. https://en.wikipedia.org/wiki/Makati
MAKATI_POP, MAKATI_KM2 = 309770, 18.17
# Domestic water demand for Metro Manila, liters per person per day. The
# source is UP's National Hydraulic Research Center project e-SMART, which
# calls it a projection, not a standard: "medium domestic water demand
# projections at 150 liters per day per capita". It covers households only, so
# it is not a measurement of any city's total draw. The live site stopped
# answering in July 2026, so the archived copy is the citation.
# https://web.archive.org/web/20251231151725/https://esmart.nhrc.upd.edu.ph/?p=1422
LITERS_PER_PERSON_DAY = 150.0
LITERS_SRC = ("https://web.archive.org/web/20251231151725/"
              "https://esmart.nhrc.upd.edu.ph/?p=1422")
# NWRB's allocation to MWSS from Angat, cut from 48 to 46 cubic meters per
# second for 16 to 30 Jul 2026 while the dam sat at a record low 152.85 m.
# 46 CMS x 86,400 s = 3,974 MLD, which this file rounds to 4,000. It is an
# allocation to MWSS for Metro Manila and Rizal, not a measured withdrawal.
# https://www.philstar.com/nation/2026/07/20/2543243/mwss-water-allocation-reduced-anew
ANGAT_CMS = 46.0
ANGAT_MLD = 4000.0
ANGAT_WINDOW = "16 to 30 Jul 2026"
# The watershed New Clark City itself draws on, named so the Angat comparison
# cannot read as a shared tap. Manila Bulletin, 22 Jul 2026: "The Sacobia
# watershed, the primary water source for New Clark City, has reportedly shown
# signs of strain since 2020." https://mb.com.ph/2026/07/22/pax-silica-explained
LOCAL_WATERSHED = "Sacobia"
# FAO irrigation manual, Table 1, "APPROXIMATE AVERAGE IN net VALUES FOR
# DIFFERENT CLIMATES AND RICE": paddy rice takes 1.5 liters per second per
# hectare as an average net irrigation need across the season. That is 129.6
# cubic meters a hectare a day, or 13 mm a day. Use the figure that page prints;
# it carries no season-total in millimeters.
# https://www.fao.org/4/u5835e/u5835e04.htm
RICE_L_S_HA = 1.5
RICE_ML_HA_DAY = RICE_L_S_HA * 86400 / 1e6  # 0.1296 ML per hectare per day
# MTerra Solar, Nueva Ecija-Bulacan: 3,500 MWp on 3,500 ha with a 4,500 MWh
# battery, the largest single solar-plus-storage build anywhere; first grid
# sync Feb 2026. https://en.wikipedia.org/wiki/Meralco_Terra_Solar_Farm
TERRA_MW, TERRA_HA, TERRA_BESS_MWH = 3500.0, 3500.0, 4500.0
TERRA_HA_PER_MW = TERRA_HA / TERRA_MW  # 1.0, measured on a real PH build
# City footprints for the land comparison
# https://en.wikipedia.org/wiki/Bonifacio_Global_City
BGC_KM2 = 2.4
# https://en.wikipedia.org/wiki/New_Clark_City
NCC_KM2 = 94.5
# Hermosa-San Jose 500 kV, the line component NGCP names inside its
# Mariveles-Hermosa-San Jose facility. Milestones and the TRO come from
# cid=16897; the P10.2B is the ERC's provisional approval for the
# Hermosa-San Jose line and comes from cid=16649, NOT from cid=16897, which
# prints PhP 20.94B for the whole Mariveles-Hermosa-San Jose project.
# https://ngcp.ph/article?cid=16897 and https://www.ngcp.ph/article?cid=16649
HSJ = {"name": "Hermosa-San Jose", "full_mw": 8000, "full_date": "2024-06-23",
       "line1_mw": 2000, "line1_date": "2023-05-27",
       "tro": "2023-07 to 2024-04", "php_b": 10.2,
       "cost_src": "https://www.ngcp.ph/article?cid=16649",
       "milestone_src": "https://ngcp.ph/article?cid=16897"}
# Mindanao-Visayas link: P52B and 450 MW transfer capacity from cid=16636,
# which also dates the 30 Apr 2023 energisation (an initial 22.5 MW load). The
# full commercial operation date is from cid=16899, the ceremonial switch-on:
# "On 26 January 2024, the energization ceremony was held at Malacanan Palace".
# https://www.ngcp.ph/article?cid=16636 and https://www.ngcp.ph/article?cid=16899
MVIP = {"mw": 450, "php_b": 52.0, "first_load": "2023-04-30",
        "first_load_mw": 22.5, "commercial": "2024-01-26",
        "energize_src": "https://www.ngcp.ph/article?cid=16636",
        "commercial_src": "https://www.ngcp.ph/article?cid=16899"}
# island-group populations, 2020 census (PSA), for the who-is-served line
# https://en.wikipedia.org/wiki/Luzon https://en.wikipedia.org/wiki/Visayas https://en.wikipedia.org/wiki/Mindanao
ISLAND_POP_M = {"luzon": 62.0, "visayas": 20.6, "mindanao": 26.3}
# an Olympic pool holds 2,500 cubic meters = 2.5 million liters (FR standard)
# https://en.wikipedia.org/wiki/Olympic-size_swimming_pool
POOL_ML = 2.5
# Two NGCP Visayas yellow-alert bulletins, June 2026, each carrying one
# peak/available pair. 15 Jun: available 2,581 MW, peak demand 2,482 MW.
# 16 Jun: available 2,587 MW, peak demand 2,384 MW. Both figures per bulletin,
# never mixed across days.
# https://www.gmanetwork.com/news/money/economy/991469/ngcp-visayas-grid-yellow-alert-june-15-2026/story/
# https://www.gmanetwork.com/news/money/economy/991590/ngcp-visayas-grid-yellow-alert-june-16-2026/story/
VISAYAS_BULLETIN = {"peak_lo": 2384, "peak_hi": 2482,
                    "avail_lo": 2581, "avail_hi": 2587,
                    "src_hi": "https://www.gmanetwork.com/news/money/economy/991469/ngcp-visayas-grid-yellow-alert-june-15-2026/story/",
                    "src_lo": "https://www.gmanetwork.com/news/money/economy/991590/ngcp-visayas-grid-yellow-alert-june-16-2026/story/"}
# WESM's published nodal congestion component, from the DIPCEF sweep this
# project archives; the numbers are stated and oracle-guarded in
# web/methodology.html (small and intermittent after 2026-05-01)
# The median is taken over the node-hours where the component fires, not over
# the 70 sampled days: nodal_prices.py collects a value only "if c". A median
# over all 70 days would be zero. The page must say which.
DIPCEF = {"days_nonzero": 28, "days_sampled": 70, "median_php_kwh": 0.56,
          "median_basis": "node-hours where it fires",
          "max_php_kwh": 19.28, "max_day": "2026-05-26"}
# The own-station illustration. Neither figure is announced: 2,500 MW is a
# chosen station size and 600 MW a chosen unit size, close to one of the two
# 647 MW units at Sual. Every place the page prints them reads from here.
OWN_STATION_MW = 2500.0
TRIP_UNIT_MW = 600.0


def island(region: str) -> str | None:
    r = region.strip().upper()
    if r.endswith("LUZ"):
        return "luzon"
    if r.endswith("VIS"):
        return "visayas"
    if r.endswith("MIN"):
        return "mindanao"
    return None


def archive_peaks() -> dict:
    """Highest 5-minute market energy requirement per island in the archive.

    MKT_REQT on the En rows of the RTD regional summary is the energy the
    market had to meet that interval. The max over the window is the closest
    thing the archive holds to 'the grid at its biggest recorded moment'.
    """
    files = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "RTDSUM",
                                          "RTDREG_*.csv")))
    peak: dict[str, float] = {}
    when: dict[str, str] = {}
    for path in files:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("COMMODITY_TYPE") or "").strip() != "En":
                    continue
                isl = island(row.get("REGION_NAME") or "")
                if not isl:
                    continue
                try:
                    v = float(row["MKT_REQT"])
                except (TypeError, ValueError, KeyError):
                    continue
                if v > peak.get(isl, 0.0):
                    peak[isl] = v
                    when[isl] = row.get("TIME_INTERVAL", "")
    days = len(files)
    lo = os.path.basename(files[0])[7:15] if files else ""
    hi = os.path.basename(files[-1])[7:15] if files else ""
    return {"days": days, "window": f"{lo}..{hi}",
            "mw": {k: round(v) for k, v in peak.items()},
            "at": when}


def outage_record() -> dict:
    """Which big units were on outage, and on how many of the archived days.

    IEMOP's outage schedules used in real-time dispatch (OUTRTD) list every
    resource marked OUT per day; capacities come from the registered-capacity
    files (CAPEG). This mixes planned maintenance with forced outages, because
    the published status column does not separate them, so the wording on the
    page says "on outage" and never "tripped".
    """
    import collections

    days: dict[str, set] = collections.defaultdict(set)
    files = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "OUTRTD",
                                          "RTDOS_*.csv")))
    for path in files:
        day = os.path.basename(path)[6:14]
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("STATUS") or "").strip().upper() == "OUT":
                    days[(row.get("RESOURCE_NAME") or "").strip()].add(day)
    cap: dict[str, float] = {}
    cfiles = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "CAPEG", "*.csv")))
    if cfiles:
        with open(cfiles[-1], newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    cap[(row.get("RESOURCE_NAME") or "").strip()] = float(
                        row["MAXIMUM_CAPACITY"])
                except (TypeError, ValueError, KeyError):
                    pass
    # the resource codes the page is allowed to name, with the plant each one
    # belongs to (checked against web/data/generators.geojson)
    NAMED = {
        "03SNGAB_G01": "San Gabriel, a gas unit in Batangas",
        "01MSINLO_G02": "the second unit at Masinloc, a coal plant in Zambales",
        "01MARVEL_G01": "a unit at GNPower Dinginin, a coal plant in Bataan",
    }
    out = []
    for code, label in NAMED.items():
        if code in days:
            out.append({"code": code, "label": label,
                        "mw": round(cap.get(code, 0)),
                        "days_out": len(days[code])})
    out.sort(key=lambda r: -r["days_out"])
    return {"days_in_window": len(files), "units": out,
            "src": "https://www.iemop.ph/market-data/outage-schedules-used-in-rtd/"
                   " and https://www.iemop.ph/market-data/registered-capacity-generation/"}


def merit_ladder() -> dict:
    """The baked Luzon supply curve at the 7pm reference hour, plus where
    evening demand lands with and without the campus. Same source the map's
    Simulate mode draws from."""
    mo = json.load(open(os.path.join(WEB, "dispatch.json")))["merit_order"]["luzon"]
    blocks, cum = [], 0.0
    for b in mo["blocks"]:
        blocks.append({"fuel": b["fuel"], "mw": round(b["mw"], 0),
                       "cost": b["cost"], "cum_from": round(cum, 0),
                       "cum_to": round(cum + b["mw"], 0)})
        cum += b["mw"]
    # this demand is the TYPICAL evening, the mean of hour-19 demand across the
    # archive window, not the recorded day the price solve replays. The card
    # must say so, because the two differ by a few hundred megawatts.
    demand = mo["typical_evening_demand_mw"]
    return {"blocks": blocks, "avail_mw": round(cum, 0),
            "evening_demand_mw": demand,
            "evening_demand_basis": "mean hour-19 demand across the archive window",
            "headroom_with_campus_mw": round(cum - demand - CAMPUS_MW, 0),
            "demand_with_campus_mw": demand + int(CAMPUS_MW)}


def price_effect(day: str) -> dict:
    """Replay one recorded day with and without the campus, on the same
    calibrated cost stack the studio runs. Two LP solves, ~a minute."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import power_dispatch as pkg

    import collections

    base_run = pkg.run_scenario({"date": day, "opts": {}})
    wave_run = pkg.run_scenario(
        {"date": day, "opts": {"demand_delta": {"luzon": 3000}}})
    base, wave = base_run["summary"], wave_run["summary"]

    def marginal_hours(run):
        c = collections.Counter(h["marginal"]["luzon"] for h in run["hours"])
        return {"top": c.most_common(1)[0][0], "top_hours": c.most_common(1)[0][1],
                "counts": dict(c), "hours": 24}

    def rent(s):
        return s["leyte_rent_m_php"] + s["mvip_rent_m_php"]

    lz = [round(base["mean_price"]["luzon"], 2),
          round(wave["mean_price"]["luzon"], 2)]
    passthrough = round((lz[1] - lz[0]) * HOME_KWH_MONTH)
    return {
        "merit": merit_ladder(),
        "passthrough_php_month": passthrough,
        "passthrough_delta_php_kwh": round(lz[1] - lz[0], 2),
        "day": day,
        # which fuel sets the price each hour, counted rather than asserted:
        # adding the wave does not put oil on the margin in every hour
        "marginal_base": marginal_hours(base_run),
        "marginal_wave": marginal_hours(wave_run),
        "luzon_mean": lz,
        "visayas_peak": [round(base["peak_price"]["visayas"], 2),
                         round(wave["peak_price"]["visayas"], 2)],
        "links_rent_m_php": [round(rent(base), 1), round(rent(wave), 1)],
        "unserved_mwh": [base["unserved_mwh"]["luzon"],
                         wave["unserved_mwh"]["luzon"]],
        "dipcef": DIPCEF,
        "src": {
            "engine": "https://github.com/xmpuspus/power-dispatch-studio/blob/main/pipeline/dispatch.py (the cost stack; P6.00 coal is the administered price IEMOP publishes at https://www.iemop.ph/market-data/indicative-administered-prices/ , gas is https://www.foi.gov.ph/requests/malampaya-natural-gas-price/ , and P12.00 oil is a labelled assumption in https://github.com/xmpuspus/power-dispatch-studio/blob/main/pipeline/fleet_ph.py)",
            "dipcef": "https://www.iemop.ph/market-data/dipc-energy-results-final/ (the LMP_CONGESTION column, swept over the archived sample)",
        },
    }


def main() -> None:
    sites = json.load(open(os.path.join(WEB, "sites.json")))
    pax = next(s for s in sites["sites"] if s["id"] == "pax-silica")
    limit_7pm = pax["limit_mw_by_hour"][19]
    profiles = json.load(open(os.path.join(WEB, "profiles.json")))
    solar = profiles["solar_profile"]
    cf_cloudless = sum(solar) / 24.0

    peaks = archive_peaks()
    energy_gwh_day = CAMPUS_MW * 24 / 1000.0
    homes = CAMPUS_MW * 24 * 1000 / (HOME_KWH_MONTH / DAYS_PER_MONTH)

    # sun-alone lower bound: cloudless model day, Terra's real land density
    sun_alone_mw = CAMPUS_MW / cf_cloudless
    sun_alone_km2 = sun_alone_mw * TERRA_HA_PER_MW / 100.0
    dark_hours = sum(1 for x in solar if x < 0.01)
    bridge_gwh = dark_hours * CAMPUS_MW / 1000.0
    acwa_share = ACWA_MW * sum(solar) / (CAMPUS_MW * 24)

    # water equivalences from the announced 65-90 MLD
    people_lo = WATER_MLD_LOW * 1e6 / LITERS_PER_PERSON_DAY
    people_hi = WATER_MLD_HIGH * 1e6 / LITERS_PER_PERSON_DAY
    rice_ha_lo = WATER_MLD_LOW / RICE_ML_HA_DAY
    rice_ha_hi = WATER_MLD_HIGH / RICE_ML_HA_DAY

    out = {
        "generated_from": "pipeline/perspective.py",
        "campus": {
            "mw": CAMPUS_MW, "mw_ceiling": CAMPUS_MW_CEILING,
            "energy_gwh_day": round(energy_gwh_day, 1),
            "water_mld": [WATER_MLD_LOW, WATER_MLD_HIGH],
            "harvest_mld": HARVEST_MLD,
            "zone_ha": SITE_HA,
            "build_start_year": BUILD_START_YEAR,
            "full_build_years": [FULL_BUILD_YEARS_LOW, FULL_BUILD_YEARS_HIGH],
            "jobs_direct": [JOBS_DIRECT_LOW, JOBS_DIRECT_HIGH],
            "src": {
                "horizon": "https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/",
                "jobs": "https://www.philstar.com/business/2026/07/24/2544359/pax-silica-investors-may-lease-new-clark-land-99-years-bcda",
                "mw": "https://www.gmanetwork.com/news/money/economy/995915/pax-silica-ai-hub-to-consume-3-gigawatts-at-full-development-bcda/story/",
                "mw_ceiling": "https://business.inquirer.net/596398/pax-silicas-mammoth-power-needs-draw-maharlika-foreign-interest",
                "water": "https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/",
                "harvest": "https://www.manilatimes.net/2026/07/24/regions/rainwater-eyed-for-use-at-planned-pax-silica-hub/2390193",
            },
        },
        "power": {
            "archive_peaks_mw": peaks["mw"],
            "archive_days": peaks["days"],
            "archive_window": peaks["window"],
            "archive_peak_at": peaks["at"],
            "visayas_bulletin": VISAYAS_BULLETIN,
            "campus_vs_visayas": round(CAMPUS_MW / peaks["mw"]["visayas"], 2),
            "campus_vs_luzon": round(CAMPUS_MW / peaks["mw"]["luzon"], 3),
            "homes_million": round(homes / 1e6, 1),
            "home_kwh_month": HOME_KWH_MONTH,
            "island_pop_m": ISLAND_POP_M,
            "src": {
                "peaks": "https://www.iemop.ph/market-data/rtd-regional-summaries/ (archived at https://github.com/xmpuspus/power-dispatch-studio/tree/main/data/raw/RTDSUM)",
                "island_pop": "https://en.wikipedia.org/wiki/Luzon ; https://en.wikipedia.org/wiki/Visayas ; https://en.wikipedia.org/wiki/Mindanao",
                "bulletin": "https://www.gmanetwork.com/news/money/economy/991469/ngcp-visayas-grid-yellow-alert-june-15-2026/story/",
                "home_kwh": "https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-july-2026",
            },
        },
        "sun": {
            "acwa_mw": ACWA_MW, "acwa_ha": ACWA_HA,
            "acwa_share_pct": round(acwa_share * 100, 1),
            "profile": solar,
            "hourly_cover_pct": [round(ACWA_MW * s / CAMPUS_MW * 100, 1)
                                 for s in solar],
            "cf_cloudless": round(cf_cloudless, 4),
            "sun_alone_mw": round(sun_alone_mw, -2),
            "sun_alone_km2": round(sun_alone_km2, 0),
            "dark_hours": dark_hours,
            "bridge_gwh": round(bridge_gwh, 0),
            "terra": {"mw": TERRA_MW, "ha": TERRA_HA,
                      "bess_mwh": TERRA_BESS_MWH},
            "vs_makati": round(sun_alone_km2 / MAKATI_KM2, 1),
            "vs_bgc": round(sun_alone_km2 / BGC_KM2, 0),
            "vs_ncc": round(sun_alone_km2 / NCC_KM2, 2),
            "vs_terra": round(sun_alone_mw * TERRA_HA_PER_MW / TERRA_HA, 1),
            "vs_terra_bess": round(bridge_gwh * 1000 / TERRA_BESS_MWH, 1),
            "makati_km2": MAKATI_KM2, "bgc_km2": BGC_KM2, "ncc_km2": NCC_KM2,
            "src": {
                "acwa": "https://www.enerdata.net/publications/daily-energy-news/acwa-power-secures-site-500-mw-solar-bess-project-philippines.html",
                "terra": "https://en.wikipedia.org/wiki/Meralco_Terra_Solar_Farm",
                "profile": "https://github.com/xmpuspus/power-dispatch-studio/blob/main/web/data/profiles.json (cloudless model day, favourable to solar)",
                "areas": "https://en.wikipedia.org/wiki/Makati ; https://en.wikipedia.org/wiki/Bonifacio_Global_City ; https://en.wikipedia.org/wiki/New_Clark_City",
            },
        },
        "wires": {
            "limit_7pm_mw": round(limit_7pm, 0),
            "limit_min_mw": pax["limit_min_mw"],
            "limit_max_mw": pax["limit_max_mw"],
            "gap_mw": round(CAMPUS_MW - limit_7pm, 0),
            "radially_fed": pax["radially_fed"],
            # each "circuit" in the sites bake is a merged branch: the network
            # builder sums RATING_MW["ac230"] = 400 MW per circuit over the
            # circuits it merges, so a rating of 800 is a double-circuit route
            # and the drawn rows are routes, not single circuits
            "n_routes": len(pax["circuits"]),
            "route_rating_mw": pax["circuits"][0]["rating_mw"],
            "circuit_rating_mw": 400.0,
            "circuits_per_route": int(pax["circuits"][0]["rating_mw"] / 400.0),
            # how many more circuits of the same class the shortfall would take.
            # The rating is a class default, so this is an order-of-size answer,
            # not an engineering design.
            "more_routes": int(
                -(-(CAMPUS_MW - limit_7pm) // pax["circuits"][0]["rating_mw"])),
            "outages": outage_record(),
            "own_station_mw": OWN_STATION_MW,
            "trip_unit_mw": TRIP_UNIT_MW,
            "own_gap_mw": round(CAMPUS_MW - (OWN_STATION_MW - TRIP_UNIT_MW)
                                - limit_7pm),
            "own_gap_homes_million": round(
                (CAMPUS_MW - (OWN_STATION_MW - TRIP_UNIT_MW) - limit_7pm)
                * 24 * 1000 / (HOME_KWH_MONTH / DAYS_PER_MONTH) / 1e6, 1),
            "day": sites["day"],
            "substation": {"php_b": SUBSTATION_PHP_B, "kv": SUBSTATION_KV,
                           "year": SUBSTATION_YEAR,
                           "cost_owner": SUBSTATION_COST_OWNER,
                           "date_owner": SUBSTATION_DATE_OWNER},
            "hsj": HSJ, "mvip": MVIP,
            "src": {
                "limit": "https://github.com/xmpuspus/power-dispatch-studio/blob/main/pipeline/nodal_dcopf.py (solved on OpenStreetMap-mapped routes, https://www.openstreetmap.org/copyright ; ratings are class defaults, NGCP does not publish them)",
                "substation": "https://mb.com.ph/2026/05/25/us-pax-silica-alliance-prompts-7-billion-power-expansion-in-new-clark-city",
                "hsj": "https://ngcp.ph/article?cid=16897",
                "mvip": "https://www.ngcp.ph/article?cid=16636",
            },
        },
        "site": {
            "ha": SITE_HA,
            "km2": round(SITE_HA / 100, 2),
            "ncc_ha": round(NCC_KM2 * 100),
            "makati_ha": round(MAKATI_KM2 * 100),
            "bgc_ha": round(BGC_KM2 * 100),
            "acwa_ha": ACWA_HA,
            "share_of_ncc_pct": round(SITE_HA / (NCC_KM2 * 100) * 100, 1),
            "vs_makati": round(SITE_HA / (MAKATI_KM2 * 100), 2),
            "vs_bgc": round(SITE_HA / (BGC_KM2 * 100), 1),
            "vs_acwa": round(SITE_HA / ACWA_HA, 1),
            "capas_farmland_pct": CAPAS_FARMLAND_PCT,
            "farmers_bcda": FARMERS_BCDA,
            "displaced_advocacy": [DISPLACED_ADVOCACY_IP,
                                   DISPLACED_ADVOCACY_FARMERS],
            # what nobody has published. These stay in the bake so the card
            # cannot quietly start claiming a number that does not exist.
            "tree_count_published": TREE_COUNT_PUBLISHED,
            "ecc_masterplan_issued": ECC_MASTERPLAN_ISSUED,
            "ecc_per_locator_pending": ECC_PER_LOCATOR_PENDING,
            "pap_barangays": PAP_BARANGAYS,
            "local_watershed": LOCAL_WATERSHED,
            "src": {
                "area": "https://www.philstar.com/business/2026/07/24/2544359/pax-silica-investors-may-lease-new-clark-land-99-years-bcda (BCDA president Joshua Bingcang, 1,620 ha designated as an industrial area)",
                "zone": "https://mb.com.ph/2026/07/22/pax-silica-explained (\"a proposed 4,000-acre (about 1,620-hectare) Economic Security Zone\"; separately, under the article's list of critics' objections, \"Much of the land under discussion supports rice, coconut, and other food production\", which is the critics' characterisation of the wider land at issue and not Manila Bulletin describing these 1,620 hectares)",
                "watershed": "https://mb.com.ph/2026/07/22/pax-silica-explained (\"The Sacobia watershed, the primary water source for New Clark City, has reportedly shown signs of strain since 2020\")",
                "farmland": "https://www.philstar.com/headlines/2026/07/27/2545030/scientists-group-debunks-claims-pax-silica-project (Capas municipal government data via Agham)",
                "displacement": "https://philstarlife.com/news-and-views/314814-what-exactly-is-pax-silica (Kalikasan via South China Morning Post, for the New Clark City project as a whole)",
                "farmers": "https://www.gmanetwork.com/news/topstories/regions/996145/explainer-how-would-pax-silica-sustain-its-water-demand/story/ (BCDA counters that about 10 farmers are directly affected)",
                "assessment": "https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/ (BCDA says DENR issued an environmental compliance certificate for the masterplan and each locator still needs its own; DENR was still running the impact assessment three days earlier, https://businessmirror.com.ph/2026/07/20/denr-assesses-pax-silicas-environmental-impact/ ; no tree inventory or tree-cutting permit is published)",
                "pap": "https://www.philstar.com/headlines/2026/07/27/2545030/scientists-group-debunks-claims-pax-silica-project (BCDA's initial list of Project Affected Persons covers three Capas barangays, per Agham)",
                "jobs": "https://www.philstar.com/business/2026/07/24/2544359/pax-silica-investors-may-lease-new-clark-land-99-years-bcda (BCDA estimates 130,000 to 190,000 direct jobs)",
                "areas": "https://en.wikipedia.org/wiki/New_Clark_City ; https://en.wikipedia.org/wiki/Makati ; https://en.wikipedia.org/wiki/Bonifacio_Global_City",
            },
        },
        "price": price_effect(sites["day"]),
        "water": {
            "mld": [WATER_MLD_LOW, WATER_MLD_HIGH],
            "people_equiv": [round(people_lo, -3), round(people_hi, -3)],
            "makati_pop_2024": MAKATI_POP,
            "vs_makati_people": [round(people_lo / MAKATI_POP, 1),
                                 round(people_hi / MAKATI_POP, 1)],
            "liters_per_person_day": LITERS_PER_PERSON_DAY,
            "rice_ha": [round(rice_ha_lo, -1), round(rice_ha_hi, -1)],
            "rice_l_s_ha": RICE_L_S_HA,
            "angat_mld": ANGAT_MLD,
            "angat_cms": ANGAT_CMS,
            "angat_window": ANGAT_WINDOW,
            "local_watershed": LOCAL_WATERSHED,
            "angat_share_pct": [round(WATER_MLD_LOW / ANGAT_MLD * 100, 1),
                                round(WATER_MLD_HIGH / ANGAT_MLD * 100, 1)],
            "harvest_mld": HARVEST_MLD,
            "pools_per_day": [round(WATER_MLD_LOW / POOL_ML), round(WATER_MLD_HIGH / POOL_ML)],
            "src": {
                "announced": "https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/",
                "standard": LITERS_SRC + " (UP National Hydraulic Research Center project e-SMART: \"medium domestic water demand projections at 150 liters per day per capita\", households only; the live page stopped answering in July 2026, so this is the archived copy)",
                "makati": "https://en.wikipedia.org/wiki/Makati (2024 census, after the Embo transfer)",
                "angat": "https://www.philstar.com/nation/2026/07/20/2543243/mwss-water-allocation-reduced-anew (NWRB cut the MWSS allocation from 48 to 46 cubic meters per second for 16 to 30 Jul 2026; 46 CMS is 3,974 million liters a day, rounded here to 4,000, and it is an allocation for Metro Manila and Rizal rather than a measured withdrawal)",
                "rice": "https://www.fao.org/4/u5835e/u5835e04.htm (Table 1, paddy rice at 1.5 liters per second per hectare as the average net irrigation need over a season, which is 129.6 cubic meters a hectare a day)",
                "nwrb": "https://businessmirror.com.ph/2026/07/22/local-water-source-enough-to-supply-pax-silica-operation-water-board/",
                "dispute": "https://www.gmanetwork.com/news/topstories/regions/996145/explainer-how-would-pax-silica-sustain-its-water-demand/story/",
            },
        },
    }
    path = os.path.join(WEB, "perspective.json")
    json.dump(out, open(path, "w"), indent=1)
    print("wrote", path)
    print(f"  homes {out['power']['homes_million']}M, "
          f"sun-alone {out['sun']['sun_alone_mw']:,.0f} MW / "
          f"{out['sun']['sun_alone_km2']:.0f} km2, "
          f"water people {out['water']['people_equiv']}, "
          f"limit 7pm {out['wires']['limit_7pm_mw']:,.0f} MW")


if __name__ == "__main__":
    main()
