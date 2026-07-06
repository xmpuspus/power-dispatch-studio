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

# --- named generators + dispatch model -----------------------------------------
gens = load("generators.geojson")
disp = load("dispatch.json")

check("11 named generators", len(gens["features"]) == 11)
check("every generator has src + fuel + capacity + city precision + marginal cost",
      all(p.get("src") and p.get("fuel") and p.get("capacity_mw")
          and p.get("precision") == "city"
          and p.get("marginal_cost_php_kwh") is not None
          for p in (f["properties"] for f in gens["features"])))
gnames = {f["properties"]["name"] for f in gens["features"]}
check("named movers include Ilijan, Sual, Dinginin, TVI, PEDC",
      {"Ilijan", "Sual", "GNPower Dinginin", "Therma Visayas (TVI)", "PEDC"}
      <= gnames)

# fleet reconciliation: the per-grid fuel split is a MODEL allocation, but its
# columns must sum EXACTLY to the sourced national fuel totals (the honesty pin)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))
import fleet_ph as fl  # noqa: E402
for fuel, nat in fl.NATIONAL_FUEL_MW.items():
    col = sum(fl.GRID_FUEL_MW[g].get(fuel, 0) for g in fl.GRIDS)
    check(f"fleet {fuel} column reconciles to national {nat} MW", col == nat)
check("all natural gas is on Luzon (Batangas/Malampaya, sourced)",
      fl.GRID_FUEL_MW["VISAYAS"]["natural_gas"] == 0
      and fl.GRID_FUEL_MW["MINDANAO"]["natural_gas"] == 0)
check("coal marginal cost is the sourced ERC administered P6.00/kWh",
      math.isclose(fl.FUEL_COST_PHP_KWH["coal"], 6.00))
check("Malampaya gas cost sourced at P4.80/kWh below coal",
      math.isclose(fl.FUEL_COST_PHP_KWH["natural_gas"], 4.80)
      and fl.FUEL_COST_PHP_KWH["natural_gas"] < fl.FUEL_COST_PHP_KWH["coal"])

check("dispatch model available + labeled not-PLEXOS",
      disp.get("available") and "not PLEXOS" in disp.get("model", ""))
# the price calibration must be market-window only (regime separation, like prices.json)
cw = disp.get("calibration_window", {})
check("calibration is market-window only (WESM resumed 2026-05-01)",
      cw.get("regime") == "market-only"
      and cw.get("from") == anchors["wesm_resumed"] and cw.get("days", 0) >= 40)
cal = disp["calibration"]
check("calibration covers 3 grids", set(cal) == {"luzon", "visayas", "mindanao"})
check("model under-predicts on average (cost stack < observed LWAP)",
      all(cal[g]["modeled_mean_php_kwh"] < cal[g]["observed_mean_php_kwh"]
          for g in cal))
check("evening-peak residual positive on every grid (one-directional scarcity)",
      all((cal[g]["evening_peak_residual_php_kwh"] or 0) > 0 for g in cal))
check("Visayas residual is the largest (the 52-day constrained grid)",
      cal["visayas"]["evening_peak_residual_php_kwh"]
      > cal["luzon"]["evening_peak_residual_php_kwh"])
check("merit_order stack baked for 3 grids with cost-ordered blocks", all(
    disp["merit_order"][g]["blocks"]
    and [b["cost"] for b in disp["merit_order"][g]["blocks"]]
    == sorted(b["cost"] for b in disp["merit_order"][g]["blocks"])
    for g in ("luzon", "visayas", "mindanao")))
check("N-1 table covers all 11 named units",
      len(disp["n1"]) == 11 and all("shortfall_at_peak_mw" in n for n in disp["n1"]))
check("N-1 orders by peak shortfall; the biggest units shed the most",
      disp["n1"][0]["shortfall_at_peak_mw"] >= disp["n1"][-1]["shortfall_at_peak_mw"])
adq = disp["adequacy"]["dict_2028"]
check("DICT 1.5 GW scenario is a labeled DICT forecast with src",
      adq["owner"] == "DICT" and adq["added_mw"] == 1500 and adq.get("src"))
check("adding the DICT wave erodes the Luzon reserve margin",
      adq["reserve_margin_with_dc_pct"] < adq["reserve_margin_now_pct"])

# --- inter-island coupled dispatch (item 1) ------------------------------------
# The coupled solver's trust gate is optimality (KKT) on a radial path, not the
# algorithm: across an UNSATURATED corridor adjacent grids clear at the same price
# (within the wheeling dead-band); across a SATURATED one the exporter is strictly
# cheaper and the congestion rent equals the price gap. Verify on live cases.
import coupled_dispatch as cd  # noqa: E402

_KKT_CASES = [
    # (demand dict, removed) chosen to span: all-coal tie, Visayas outage bind,
    # everyone on oil.
    ({"LUZON": 12000, "VISAYAS": 1800, "MINDANAO": 2800}, None),
    ({"LUZON": 12000, "VISAYAS": 1800, "MINDANAO": 2800}, {"VISAYAS": {"coal": 935}}),
    ({"LUZON": 12000, "VISAYAS": 2900, "MINDANAO": 2800}, None),
    ({"LUZON": 15500, "VISAYAS": 2700, "MINDANAO": 3300}, None),
]
opt_ok = rent_ok = True
lim = {c["id"]: c["limit_mw"] for c in cd.CORRIDORS}
c1, c2 = lim["leyte_luzon_hvdc"], lim["mvip_hvdc"]
for dem, rem in _KKT_CASES:
    r = cd.clear_coupled(dem, 19, removed=rem)
    solved = cd.system_cost(dem, 19, r["flow_lv_mw"], r["flow_vm_mw"], removed=rem)
    # brute-force the min-cost flow pair on a fine grid; the solver must match it
    best = min(cd.system_cost(dem, 19, x1, x2, removed=rem)
               for x1 in range(-int(c1), int(c1) + 1, 5)
               for x2 in range(-int(c2), int(c2) + 1, 5))
    if solved > best + 1.0:  # PhP: within a rounding margin of the true minimum
        opt_ok = False
    p = {g: r["grids"][g]["price"] for g in r["grids"]}
    for c in r["corridors"]:
        # a congestion rent is reported only on a saturated corridor, and equals
        # the price gap across it (the exporter is the cheaper side)
        if c["saturated"]:
            gap = abs(p[c["to"]] - p[c["from"]])
            if not math.isclose(c["congestion_rent_php_kwh"], gap, abs_tol=1e-6):
                rent_ok = False
        elif c["congestion_rent_php_kwh"] != 0:
            rent_ok = False
check("coupled solver lands on the min-cost flow (optimality vs brute force)",
      opt_ok)
check("congestion rent only on a saturated corridor, and equals the price gap",
      rent_ok)
# no phantom flow when all three grids tie on the coal margin
tie = cd.clear_coupled({"LUZON": 12000, "VISAYAS": 1800, "MINDANAO": 2800}, 19)
check("no phantom corridor flow when grids tie on coal",
      abs(tie["flow_lv_mw"]) < 1 and abs(tie["flow_vm_mw"]) < 1
      and all(not c["saturated"] for c in tie["corridors"]))
# an unrelieved grid still prices at its top block (oil), never a VOLL adder
oiled = cd.clear_coupled({"LUZON": 12000, "VISAYAS": 2900, "MINDANAO": 2800}, 19)
check("no VOLL adder: an oil-margin grid caps at the oil cost P12",
      oiled["grids"]["visayas"]["price"] <= fl.FUEL_COST_PHP_KWH["oil"] + 1e-6)

cp = disp["coupling"]
check("coupling section baked + labeled not-PLEXOS",
      "not PLEXOS" in cp.get("model", "") and cp.get("n_coupled_intervals", 0) > 1000)
check("coupling couples only all-three-grid market intervals",
      cp["calibration_window"]["regime"] == "market-only")
sd = cp["spread_decomposition"]
# the honest finding: on baseline demand the corridor almost never binds, so the
# coupled model reproduces almost none of the observed Visayas-Luzon spread
check("observed Visayas-Luzon spread is real (>3 PhP/kWh)",
      sd["visayas_vs_luzon"]["observed_php_kwh"] > 3)
check("baseline coupling explains almost none of the V-L spread (the finding: "
      "the spread is scarcity, not transmission)",
      abs(sd["visayas_vs_luzon"]["explained_fraction"]) < 0.1)
leyte_stat = next(c for c in cp["corridors"] if c["id"] == "leyte_luzon_hvdc")
check("Leyte-Luzon rarely binds on baseline demand (<5% of intervals)",
      leyte_stat["saturated_pct"] < 5)
check("MVIP cap is labeled nameplate-as-operating-limit (distinct from Leyte's "
      "sourced 250)", leyte_stat["limit_kind"] == "sourced_operating_limit"
      and next(c for c in cp["corridors"] if c["id"] == "mvip_hvdc")["limit_kind"]
      == "nameplate_as_operating_limit")
# the labeled outage scenario is where the mechanism shows: the corridor binds and
# prices the islands apart endogenously. Kept separate from calibration.
osc = cp["outage_scenario"]
check("outage scenario is a labeled, sourced Visayas outage",
      osc.get("src") and osc["outage_mw"] > 500 and osc["n_intervals"] > 1000)
check("under the documented outage the Leyte corridor binds and prices a rent",
      osc["leyte_luzon_saturated_pct"] > 10
      and osc["leyte_luzon_mean_rent_php_kwh"] > 1)
check("outage scenario explains materially more of the spread than baseline",
      osc["explained_fraction"] > 0.1
      > abs(sd["visayas_vs_luzon"]["explained_fraction"]))
bt = cp["dc_binding_threshold"]
check("DC-wave lever: added Visayas load that binds Leyte is below the DICT 1.5 GW",
      bt["available"] and 0 < bt["added_visayas_load_to_bind_leyte_mw"] < 1500)

# --- minimal unit commitment (item 2) ------------------------------------------
# The committed must-run coal tranche lowers the modeled overnight price. Its inputs
# are sourced (40% min stable load; the H1 2025 WESM average offer), not tuned. The
# honest bar: it must not worsen MAE, it must lift correlation somewhere, and it must
# NOT touch the evening-peak residual (the scarcity signal stays put).
uc = disp["unit_commitment"]
check("unit-commitment layer sourced (min-load + offer both carry a src)",
      uc.get("src_min_load") and uc.get("src_offer")
      and math.isclose(uc["min_load_frac"], 0.40)
      and math.isclose(uc["commit_offer_php_kwh"], 4.14))
ucg = uc["per_grid"]
check("commitment never worsens MAE on any grid", all(
    ucg[g]["mae_after_php_kwh"] <= ucg[g]["mae_before_php_kwh"] + 1e-9 for g in ucg))
check("commitment lifts correlation where the grid's demand dips below the "
      "committed tranche (Visayas from flat/undefined to a real fit)",
      ucg["visayas"]["correlation_before"] is None
      and ucg["visayas"]["correlation_after"] > 0.3)
check("commitment lifts Luzon correlation too",
      ucg["luzon"]["correlation_after"] > ucg["luzon"]["correlation_before"])
check("commitment lowers the modeled overnight (mean drops or holds on every grid)",
      all(ucg[g]["modeled_mean_after_php_kwh"]
          <= ucg[g]["modeled_mean_before_php_kwh"] + 1e-9 for g in ucg))
# the evening-peak residual must be preserved: commitment only bites at light load
check("evening-peak scarcity residual survives commitment (still the honest signal)",
      cal["visayas"]["evening_peak_residual_php_kwh"] > 15
      and cal["luzon"]["evening_peak_residual_php_kwh"] > 5)

# --- probabilistic reliability (item 3) ----------------------------------------
# Monte Carlo forced outages turn the deterministic LOLE/EUE point into a
# distribution. Sourced FOR (NERC GADS for coal/gas), seeded so the bake is stable.
mc = disp["reliability_mc"]
check("reliability MC present + labeled not-PLEXOS + seeded + sourced FOR",
      "not PLEXOS" in mc.get("method", "") and mc.get("draws", 0) >= 2000
      and mc.get("seed") is not None and mc.get("src_for")
      and math.isclose(mc["forced_outage_rates"]["coal"], 0.10)
      and math.isclose(mc["forced_outage_rates"]["natural_gas"], 0.05))
mcg = mc["per_grid"]
check("MC reports a distribution per grid (LOLP + expected + tail shortfall)", all(
    all(k in mcg[g] for k in ("lolp_pct", "expected_shortfall_mw",
                              "shortfall_mw_p99", "shortfall_mw_max",
                              "eue_mwh_evening_window")) for g in mcg))
check("MC LOLP is a probability in [0, 100] on every grid",
      all(0 <= mcg[g]["lolp_pct"] <= 100 for g in mcg))
check("baseline evening-peak grid is adequate (Luzon LOLP under 1% in the window)",
      mcg["luzon"]["lolp_pct"] < 1)
mcd = mc["dict_2028_luzon"]
check("DICT wave scenario is a labeled 1.5 GW DICT forecast with src",
      mcd["added_mw"] == 1500 and mcd["owner"] == "DICT" and mcd.get("src"))
check("the DICT wave raises loss-of-load probability well above baseline",
      mcd["distribution"]["lolp_pct"] > 2 * mcg["luzon"]["lolp_pct"]
      and mcd["distribution"]["lolp_pct"] > mcg["luzon"]["lolp_pct"])
check("the DICT wave has a real shortfall tail (p99 or max above zero)",
      mcd["distribution"]["shortfall_mw_p99"] > 0
      or mcd["distribution"]["shortfall_mw_max"] > 500)

print(f"\n{len(fails)} failures" if fails else "\nall green")
sys.exit(1 if fails else 0)
