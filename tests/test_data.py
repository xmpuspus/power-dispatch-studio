#!/usr/bin/env python3
"""Data-integrity checks on the baked artifacts. Pins verified constants and
structural invariants so a pipeline change that drifts from the sources fails
loudly. Plain python, no pytest dependency. Run: python3 tests/test_data.py
"""
import json
import math
import os
import sys

WEB = os.path.join(os.path.dirname(__file__), "..", "web", "data")
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def load(name):
    with open(os.path.join(WEB, name)) as f:
        return json.load(f)


ck = load("chokepoints.geojson")
dc = load("dc_sites.geojson")
sual = load("sual.geojson")
cong = load("congestion.json")
rel = load("reliability.json")
prices = load("prices.json")
ans = load("answers.json")
anchors = load("market_anchors.json")
demand = load("demand_anchors.json")
meta = load("meta.json")
findings = load("findings.json")

# chokepoints: the five named corridors, each schematic + sourced
check("5 chokepoints", len(ck["features"]) == 5)
ids = {f["properties"]["id"] for f in ck["features"]}
check("chokepoint ids", ids == {"leyte_luzon_hvdc", "mvip_hvdc",
                                "leyte_cebu_230kv", "cebu_import",
                                "cnp_backbone"})
check("every chokepoint has evidence + src + schematic label", all(
    f["properties"].get("evidence") and f["properties"].get("src")
    and f["properties"].get("precision") == "schematic"
    for f in ck["features"]))
hvdc = next(f["properties"] for f in ck["features"]
            if f["properties"]["id"] == "leyte_luzon_hvdc")
check("Leyte-Luzon HVDC 440 MW nameplate / 250 MW limit",
      hvdc["capacity_mw"] == 440 and hvdc["operating_limit_mw"] == 250)

# dc sites: sourced, city-precision, named MW total pinned
check("14 DC sites", len(dc["features"]) == 14)
check("every DC site has src + city precision", all(
    f["properties"].get("src") and f["properties"].get("precision") == "city"
    for f in dc["features"]))
named_mw = round(sum(f["properties"]["mw"] or 0 for f in dc["features"]), 1)
check("named public MW total = 591.3", math.isclose(named_mw, 591.3))
check("meta named_dc_mw_total matches",
      math.isclose(meta["named_dc_mw_total"], named_mw))
statuses = {f["properties"]["status"] for f in dc["features"]}
check("dc statuses valid", statuses <= {"operational", "under_construction",
                                        "planned", "announced"})

# sual
sp = sual["features"][0]["properties"]
check("Sual 2 x 647 MW", sp["unit_mw"] == 647 and sp["units"] == 2)

# congestion league from the archive
check("congestion window present", bool(cong.get("window")))
check("congestion covers 80+ days", cong.get("days_covered", 0) >= 80)
check("league non-empty", len(cong.get("league", [])) >= 10)
check("league rows have equipment+station+day count", all(
    e.get("equipment") and e.get("station") and e.get("days", 0) > 0
    for e in cong["league"]))
# league ranks by days (a re-run cannot inflate a day), not raw row count, and
# keeps the real-time and day-ahead counts separate (the DAP market re-prices
# hourly, so its rows are re-run persistence, not time at the limit)
league_days = [e["days"] for e in cong["league"]]
check("league sorted by days descending",
      league_days == sorted(league_days, reverse=True))
check("league keeps RTD and DAP counts separate", all(
    "rtd_intervals" in e and "dap_rows" in e for e in cong["league"]))

# corridor receipts joined onto the Leyte-Cebu line
receipts = cong.get("corridor_receipts", {})
lc = receipts.get("leyte_cebu_230kv", {})
check("Leyte-Cebu corridor receipts present", lc.get("days", 0) >= 60)
check("Leyte-Cebu receipts name LEYTE_TO_CEBU", any(
    m["name"] == "LEYTE_TO_CEBU" for m in lc.get("matched_equipment", [])))
lc_feat = next(f["properties"] for f in ck["features"]
               if f["properties"]["id"] == "leyte_cebu_230kv")
check("Leyte-Cebu line carries its receipts on the geojson",
      lc_feat.get("receipts", {}).get("days", 0) >= 60)

# findings drawer: computed cards, each with a map focus
fnd = findings["findings"]
check("findings drawer has >= 5 cards", len(fnd) >= 5)
check("every finding complete + has a map focus", all(
    all(f.get(k) for k in ("id", "tag", "title", "stat", "blurb", "source"))
    and f.get("focus", {}).get("center") and f["focus"].get("mode")
    for f in fnd))
check("a finding names the LEYTE_TO_CEBU receipt", any(
    "LEYTE_TO_CEBU" in f["stat"] or "LEYTE_TO_CEBU" in f["blurb"] for f in fnd))

# reliability from RTDSUM
check("reliability has 3 grids", set(rel.get("series", {})) ==
      {"luzon", "visayas", "mindanao"})
check("reliability covers 80+ days", len(rel.get("dates", [])) >= 80)
check("curtailment observed in window (May 2026 red alerts)", any(
    rel["totals"][g]["curtailment_days"] > 0 for g in rel["totals"]))

# prices from LWAPF (PhP/kWh after /1000)
check("price series 3 grids", set(prices.get("series", {})) ==
      {"luzon", "visayas", "mindanao"})
check("price days 70+", len(prices.get("dates", [])) >= 70)
sane = [v for g in prices["series"].values() for v in g if v is not None]
check("prices in sane PhP/kWh band (0-33)", sane and
      all(0 <= v <= 33 for v in sane))
check("max spread recorded", prices.get("max_spread", {}).get("php") is not None)

# price vs load: dispatched generation (grid-scale, thousands of MW) joined to price
pl = load("price_load.json")
lz_curve = pl.get("curve", {}).get("luzon", [])
check("price-load curve has Luzon bins", len(lz_curve) >= 10)
check("Luzon load axis is grid-scale (thousands of MW, not bid-in load)",
      lz_curve and lz_curve[-1]["gen_mw"] > 8000)
check("price rises with load (the shape)",
      lz_curve and lz_curve[-1]["mean_price"] > lz_curve[0]["mean_price"])
rep = pl.get("representative_day", {})
check("representative day has a full Luzon interval series",
      len(rep.get("series", {}).get("luzon", [])) >= 200)
# regime split: WESM was suspended (administered prices) before 2026-05-01, so
# every mean the site shows must say which regime it covers. The administered
# window's regional spread is near-zero; the market window's is not.
reg = prices.get("regimes", {})
check("price regimes split administered vs market",
      set(reg) == {"administered", "market"})
check("administered window prices are near-flat across grids",
      (reg.get("administered", {}).get("max_spread") or 99) < 0.2)
check("market window shows real regional spread",
      (reg.get("market", {}).get("mean_spread") or 0) > 1)
check("prices carry an as_of date", bool(prices.get("as_of")))

# HVDC: no RTD limit events landed in-window; the bake records that honestly
# rather than inventing a series
hvdc_j = load("hvdc.json")
check("hvdc bake records the in-window limit-row count",
      "limit_rows" in hvdc_j)

# answers: the three questions, fully assembled and sourced
for q in ("q1", "q2", "q3"):
    check(f"answers.{q} complete", all(
        ans.get(q, {}).get(k) for k in ("title", "verdict", "stat", "blurb", "src")))
check("q1 cites the margin figure", str(anchors["wesm_may2026_margin_mw"])
      .split(".")[0][:1] in ans["q1"]["stat"] and "3,629" in ans["q1"]["stat"])
check("q2 mentions Sual arithmetic", "647" in ans["q2"]["blurb"])
check("q3 carries the three regional prices", all(
    str(anchors[k]) in ans["q3"]["stat"] for k in
    ("wesm_may2026_luzon", "wesm_may2026_visayas", "wesm_may2026_mindanao")))

# anchors pinned to their sources
check("May 2026 system avg 7.79 +38.5%",
      math.isclose(anchors["wesm_may2026_system_avg_php_kwh"], 7.79)
      and math.isclose(anchors["wesm_may2026_vs_april_pct"], 38.5))
check("Meralco June pins",
      math.isclose(anchors["meralco_june2026_generation_charge"], 9.0704)
      and math.isclose(anchors["meralco_june2026_wesm_cost_php_kwh"], 7.0281))
check("HVDC Dec 2025 binding share 69", anchors["hvdc_binding_share_dec2025_pct"] == 69)
# Visayas streak is the dated 52-day fact (ended Jul 1), not "7 straight weeks"
check("Visayas streak is the dated 52-day fact",
      anchors.get("visayas_yellow_streak_days") == 52
      and anchors.get("visayas_yellow_streak_to") == "2026-07-01")
check("Visayas streak carries both first-party sources",
      anchors.get("src_visayas_streak_end") and anchors.get("src_visayas_jul1"))
check("every demand anchor has src + owner + kind", all(
    a.get("src") and a.get("owner") and a.get("kind") for a in demand))
check("forecasts labeled (no bare-fact 1.5 GW)", all(
    a["kind"] in ("forecast", "commitment", "pipeline", "contested")
    for a in demand))

print(f"\n{len(fails)} failures" if fails else "\nall green")
sys.exit(1 if fails else 0)
