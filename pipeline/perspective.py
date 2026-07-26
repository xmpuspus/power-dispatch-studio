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
# BCDA (Bingcang): "around, at full development, mga three gigawatts po iyan"
# https://www.gmanetwork.com/news/money/economy/995915/pax-silica-ai-hub-to-consume-3-gigawatts-at-full-development-bcda/story/
CAMPUS_MW = 3000.0
# Inquirer: projected demand "could reach at least 5 gigawatts"
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
# NGCP dedicated 230 kV substation for New Clark City, P6.95B, end-2028 target
# https://mb.com.ph/2026/05/25/us-pax-silica-alliance-prompts-7-billion-power-expansion-in-new-clark-city
SUBSTATION_PHP_B, SUBSTATION_KV, SUBSTATION_YEAR = 6.95, 230, 2028

# --- external anchors, each with its primary source --------------------------
# Meralco computes the "typical residential customer" on 200 kWh a month
# https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-july-2026
HOME_KWH_MONTH = 200.0
DAYS_PER_MONTH = 30.4166  # 365 / 12, so the homes figure is a monthly average
# Makati after the ten Embo barangays moved to Taguig (2023):
# 309,770 people (2024 census), 18.17 km2. https://en.wikipedia.org/wiki/Makati
MAKATI_POP, MAKATI_KM2 = 309770, 18.17
# MWSS planning standard for domestic use, liters per person per day
# https://esmart.nhrc.upd.edu.ph/?p=1422
LITERS_PER_PERSON_DAY = 150.0
# NWRB allocation to MWSS from Angat, mid-2026: 46 CMS, about 4,000 MLD
# https://www.philstar.com/nation/2026/07/20/2543243/mwss-water-allocation-reduced-anew
ANGAT_MLD = 4000.0
# FAO/IRRI: a paddy season takes 1,200-1,500 mm, i.e. 12-15 ML per hectare,
# over a roughly 120-day season. https://www.fao.org/4/u5835e/u5835e04.htm
RICE_ML_HA_SEASON_LOW, RICE_ML_HA_SEASON_HIGH, RICE_SEASON_DAYS = 12.0, 15.0, 120
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
# Hermosa-San Jose 500 kV: 8,000 MW full capacity 2024-06-23, first circuit
# at 2,000 MW 2023-05-27, a Supreme Court TRO froze towers 170-178 from
# July 2023 to April 2024, P10.2B. https://ngcp.ph/article?cid=16897
HSJ = {"full_mw": 8000, "full_date": "2024-06-23", "line1_mw": 2000,
       "line1_date": "2023-05-27", "tro": "2023-07 to 2024-04",
       "php_b": 10.2}
# Mindanao-Visayas link: P52B, 450 MW, first load 2023-04-30, commercial
# 2024-01-26. https://www.ngcp.ph/article?cid=16636
MVIP = {"mw": 450, "php_b": 52.0, "first_load": "2023-04-30",
        "commercial": "2024-01-26"}
# island-group populations, 2020 census (PSA), for the who-is-served line
# https://en.wikipedia.org/wiki/Luzon https://en.wikipedia.org/wiki/Visayas https://en.wikipedia.org/wiki/Mindanao
ISLAND_POP_M = {"luzon": 62.0, "visayas": 20.6, "mindanao": 26.3}
# an Olympic pool holds 2,500 cubic meters = 2.5 million liters (FR standard)
# https://en.wikipedia.org/wiki/Olympic-size_swimming_pool
POOL_ML = 2.5
# NGCP Visayas alert bulletins, June 2026: peak demand 2,384-2,482 MW against
# 2,581-2,691 MW available.
# https://www.gmanetwork.com/news/money/economy/991469/ngcp-visayas-grid-yellow-alert-june-15-2026/story/
VISAYAS_BULLETIN = {"peak_lo": 2384, "peak_hi": 2482,
                    "avail_lo": 2581, "avail_hi": 2691}
# WESM's published nodal congestion component, from the DIPCEF sweep this
# project archives; the numbers are stated and oracle-guarded in
# web/methodology.html (small and intermittent after 2026-05-01)
DIPCEF = {"days_nonzero": 28, "days_sampled": 70, "median_php_kwh": 0.56,
          "max_php_kwh": 19.0, "max_day": "2026-05-26"}


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
    demand = mo["typical_evening_demand_mw"]
    return {"blocks": blocks, "avail_mw": round(cum, 0),
            "evening_demand_mw": demand,
            "demand_with_campus_mw": demand + int(CAMPUS_MW)}


def price_effect(day: str) -> dict:
    """Replay one recorded day with and without the campus, on the same
    calibrated cost stack the studio runs. Two LP solves, ~a minute."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import power_dispatch as pkg

    base = pkg.run_scenario({"date": day, "opts": {}})["summary"]
    wave = pkg.run_scenario(
        {"date": day, "opts": {"demand_delta": {"luzon": 3000}}})["summary"]

    def rent(s):
        return s["leyte_rent_m_php"] + s["mvip_rent_m_php"]

    passthrough = round((12.0 - 6.0) * HOME_KWH_MONTH)
    return {
        "merit": merit_ladder(),
        "passthrough_php_month": passthrough,
        "day": day,
        "luzon_mean": [round(base["mean_price"]["luzon"], 2),
                       round(wave["mean_price"]["luzon"], 2)],
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
    rice_ha_lo = WATER_MLD_LOW / (RICE_ML_HA_SEASON_HIGH / RICE_SEASON_DAYS)
    rice_ha_hi = WATER_MLD_HIGH / (RICE_ML_HA_SEASON_LOW / RICE_SEASON_DAYS)

    out = {
        "generated_from": "pipeline/perspective.py",
        "campus": {
            "mw": CAMPUS_MW, "mw_ceiling": CAMPUS_MW_CEILING,
            "energy_gwh_day": round(energy_gwh_day, 1),
            "water_mld": [WATER_MLD_LOW, WATER_MLD_HIGH],
            "harvest_mld": HARVEST_MLD,
            "zone_ha": 1620,
            "src": {
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
            "n_circuits": len(pax["circuits"]),
            "class_rating_mw": pax["circuits"][0]["rating_mw"],
            # how many more circuits of the same class the shortfall would take.
            # The rating is a class default, so this is an order-of-size answer,
            # not an engineering design.
            "more_circuits": int(
                -(-(CAMPUS_MW - limit_7pm) // pax["circuits"][0]["rating_mw"])),
            "outages": outage_record(),
            "own_gap_homes_million": round(
                (CAMPUS_MW - 1900 - limit_7pm) * 24 * 1000
                / (HOME_KWH_MONTH / DAYS_PER_MONTH) / 1e6, 1),
            "day": sites["day"],
            "substation": {"php_b": SUBSTATION_PHP_B, "kv": SUBSTATION_KV,
                           "year": SUBSTATION_YEAR},
            "hsj": HSJ, "mvip": MVIP,
            "src": {
                "limit": "https://github.com/xmpuspus/power-dispatch-studio/blob/main/pipeline/nodal_dcopf.py (solved on OpenStreetMap-mapped routes, https://www.openstreetmap.org/copyright ; ratings are class defaults, NGCP does not publish them)",
                "substation": "https://mb.com.ph/2026/05/25/us-pax-silica-alliance-prompts-7-billion-power-expansion-in-new-clark-city",
                "hsj": "https://ngcp.ph/article?cid=16897",
                "mvip": "https://www.ngcp.ph/article?cid=16636",
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
            "angat_mld": ANGAT_MLD,
            "angat_share_pct": [round(WATER_MLD_LOW / ANGAT_MLD * 100, 1),
                                round(WATER_MLD_HIGH / ANGAT_MLD * 100, 1)],
            "harvest_mld": HARVEST_MLD,
            "pools_per_day": [round(WATER_MLD_LOW / POOL_ML), round(WATER_MLD_HIGH / POOL_ML)],
            "src": {
                "announced": "https://businessmirror.com.ph/2026/07/23/bcda-pax-silica-development-to-proceed-under-marcos-admin-creating-up-to-190k-jobs/",
                "standard": "https://esmart.nhrc.upd.edu.ph/?p=1422 (MWSS 150 liters per person per day planning standard)",
                "makati": "https://en.wikipedia.org/wiki/Makati (2024 census, after the Embo transfer)",
                "angat": "https://www.philstar.com/nation/2026/07/20/2543243/mwss-water-allocation-reduced-anew",
                "rice": "https://www.fao.org/4/u5835e/u5835e04.htm (1,200-1,500 mm a season)",
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
