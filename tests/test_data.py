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
# rows may sit under their published grid total (storage excluded from the
# fuel columns) but never over it: a modeled grid cannot carry more installed
# MW than the DOE's published total for that grid
for g in fl.GRIDS:
    row = sum(fl.GRID_FUEL_MW[g].values())
    check(f"fleet {g} row {row} MW stays at or under the published "
          f"{fl.GRID_TOTAL_MW[g]} MW grid total", row <= fl.GRID_TOTAL_MW[g])
check("all natural gas is on Luzon (Batangas/Malampaya, sourced)",
      fl.GRID_FUEL_MW["VISAYAS"]["natural_gas"] == 0
      and fl.GRID_FUEL_MW["MINDANAO"]["natural_gas"] == 0)
check("coal marginal cost is the sourced ERC administered P6.00/kWh",
      math.isclose(fl.FUEL_COST_PHP_KWH["coal"], 6.00))
check("Malampaya gas cost sourced at P4.80/kWh below coal",
      math.isclose(fl.FUEL_COST_PHP_KWH["natural_gas"], 4.80)
      and fl.FUEL_COST_PHP_KWH["natural_gas"] < fl.FUEL_COST_PHP_KWH["coal"])

check("dispatch model available + labeled simplified",
      disp.get("available") and "simplified merit-order" in disp.get("model", ""))
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
check("coupling section baked + labeled simplified",
      "simplified merit-order" in cp.get("model", "") and cp.get("n_coupled_intervals", 0) > 1000)
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
# item 1 (post-convergence): the 5-minute coupled replay now scales the
# corridor by the observed hourly availability (MPI), not a flat 250 MW
_occ = cp["observed_corridor_caps"]["leyte_luzon_hvdc"]
check("the coupled replay scales the corridor by the observed hourly "
      "availability, binding on the intervals it was actually blocked "
      "(not a flat static limit)",
      0 < _occ["capped_share_pct"] < 30
      and _occ["mean_applied_cap_mw"] < _occ["static_limit_mw"]
      and _occ["intervals_capped_below_static"] > 500)
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
# with NATIVE-LOAD demand (generation + net imports) the grid whose light
# load dips below the committed tranche is Mindanao, the big net exporter;
# its own-stack marginal was flat before commitment
check("commitment lifts correlation where the grid's demand dips below the "
      "committed tranche (Mindanao from flat/undefined to a real fit)",
      ucg["mindanao"]["correlation_before"] is None
      and ucg["mindanao"]["correlation_after"] > 0.1)
check("commitment lifts Luzon correlation too",
      ucg["luzon"]["correlation_after"] > ucg["luzon"]["correlation_before"])
check("commitment lowers the modeled overnight (mean drops or holds on every grid)",
      all(ucg[g]["modeled_mean_after_php_kwh"]
          <= ucg[g]["modeled_mean_before_php_kwh"] + 1e-9 for g in ucg))
# the evening-peak residual must be preserved: commitment only bites at light
# load. The residual is the scarcity/offer premium; it must stay LARGE on the
# Visayas and real on Luzon, not be absorbed by any calibration change
check("evening-peak scarcity residual survives commitment (still the honest signal)",
      cal["visayas"]["evening_peak_residual_php_kwh"] > 10
      and cal["luzon"]["evening_peak_residual_php_kwh"] > 5)

# --- probabilistic reliability (item 3) ----------------------------------------
# Monte Carlo forced outages turn the deterministic LOLE/EUE point into a
# distribution. Sourced FOR (NERC GADS for coal/gas), seeded so the bake is stable.
mc = disp["reliability_mc"]
check("reliability MC present + labeled simplified + seeded + sourced FOR",
      "simplified" in mc.get("method", "") and mc.get("draws", 0) >= 2000
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

# --- storage as a peak-firming time-shifter (item 4) ---------------------------
st = disp["storage"]
check("storage assets sourced (batteries + Kalayaan pumped hydro, both with src)",
      st.get("src_bess") and st.get("src_pumped_hydro")
      and st["assets"]["luzon"]["bess_mw"] == 634
      and st["assets"]["luzon"]["pumped_hydro_mw"] == 685
      and st["assets"]["luzon"]["total_mw"] == 1319)
check("storage discharge offer sits above the charge floor (round-trip loss)",
      st["discharge_offer_php_kwh"] > 4.14 and st["round_trip_eff"] < 1)
pp = st["dict_wave_peak_price"]
check("storage shaves the tight-evening DICT-wave peak from oil to coal",
      pp["without_storage_marginal_fuel"] == "oil"
      and pp["with_storage_marginal_fuel"] == "coal"
      and pp["with_storage_php_kwh"] < pp["without_storage_php_kwh"])
rbk = st["reliability_buyback"]
check("storage buys back the DC-wave loss-of-load probability",
      rbk["luzon_dict_2028"]["with_storage"]["lolp_pct"]
      < rbk["luzon_dict_2028"]["without"]["lolp_pct"])
check("storage lowers the DC-wave expected unserved energy too",
      rbk["luzon_dict_2028"]["with_storage"]["eue_mwh_evening_window"]
      < rbk["luzon_dict_2028"]["without"]["eue_mwh_evening_window"])

# --- price-duration curve + marginal-block frequency (item 5) -------------------
pdur = disp["price_duration"]
check("price-duration curves baked for 3 grids (modeled + observed)",
      set(pdur) == {"luzon", "visayas", "mindanao"}
      and all(pdur[g]["modeled"] and pdur[g]["observed"] for g in pdur))
lz_dur = pdur["luzon"]
check("duration curves are sorted high to low (monotone non-increasing)", all(
    all(c[i]["price"] >= c[i + 1]["price"] - 1e-9 for i in range(len(c) - 1))
    for c in (lz_dur["modeled"], lz_dur["observed"])))
check("observed price-duration has a scarcity tail the cost stack never reaches",
      lz_dur["observed"][0]["price"] > lz_dur["modeled"][0]["price"])
check("observed price-duration spans wider than the modeled plateau",
      (lz_dur["observed"][0]["price"] - lz_dur["observed"][-1]["price"])
      > (lz_dur["modeled"][0]["price"] - lz_dur["modeled"][-1]["price"]))
mfreq = disp["marginal_frequency"]
check("marginal-frequency table baked for 3 grids, shares near 100%", all(
    abs(sum(b["share_pct"] for b in mfreq[g]["by_block"]) - 100) < 1.5 for g in mfreq))
check("coal is the dominant marginal block on Luzon",
      mfreq["luzon"]["by_block"][0]["block"].startswith("coal"))
check("the committed-coal tranche is marginal on Visayas (the commitment layer at "
      "light load)", any(b["block"] == "coal (committed)"
                         for b in mfreq["visayas"]["by_block"]))

# --- scenario engine inputs (interactivity, ported to studio/src/studio/engine.ts) -
mo = disp["merit_order"]
check("merit_order carries pre-split per-fuel availability for the client engine",
      all("fuel_avail_mw" in mo[g] and mo[g]["fuel_avail_mw"] for g in mo))
check("solar availability at the evening reference hour is ~0 (the add-solar caveat)",
      all(mo[g]["solar_avail_frac_ref"] < 0.05 for g in mo)
      and all(mo[g]["solar_avail_frac_midday"] > 0.5 for g in mo))
gold = disp["scenario_golden"]
check("scenario_golden bakes >=4 parity cases from the real coupled engine",
      len(gold["cases"]) >= 4)
_base = next(c for c in gold["cases"] if "baseline" in c["label"])
check("golden baseline clears all three grids on the coal margin (~P6)",
      all(abs(_base["expect"]["price"][g] - 6.0) < 0.5
          for g in ("luzon", "visayas", "mindanao")))
_bind = next(c for c in gold["cases"] if "binds" in c["label"])
check("golden added-Visayas-load case saturates the Leyte-Luzon link at a rent",
      _bind["expect"]["leyte_saturated"]
      and _bind["expect"]["leyte_rent_php_kwh"] > 0)
hy = disp["assumptions"]["hydrology"]
check("dry hydrology multiplier cuts hydro (below 1) and wet lifts it (above 1)",
      hy["dry_multiplier"] < 1 < hy["wet_multiplier"])
check("dry hydrology reproduces the sourced DOE 2024 El Nino hydro availability",
      abs(hy["dry_multiplier"] * hy["modeled_normal_hydro_avail_mw"]
          - hy["dry_avail_mw_national"]) < 2)

# --- reserve market layer (WESM Reserve Market, RTDRS) --------------------------
res = load("reserve.json")
check("reserve.json is available with the four reserve products",
      res["available"] and {c["category"] for c in res["categories"]}
      == {"regulation_up", "regulation_down", "contingency", "dispatchable"})
check("reserve prices are in a sane band (0 to the reserve cap)",
      all(0 <= c["mean_php_kwh"] <= res["reserve_cap_php_kwh"]
          and c["max_php_kwh"] <= res["reserve_cap_php_kwh"] + 0.1
          for c in res["categories"]))
check("regulation is the dearest reserve product (scarcest ancillary service)",
      res["categories"][0]["category"].startswith("regulation"))
check("the dearest reserve product clears above the observed energy price "
      "(the co-optimisation cost the energy-only stack omits)",
      res["categories"][0]["mean_php_kwh"]
      > disp["calibration"]["luzon"]["observed_mean_php_kwh"])
check("reserve prices baked per grid for all three grids",
      set(res["by_grid"]) == {"luzon", "visayas", "mindanao"})

# --- contract-cover / bill-impact layer (item 4) --------------------------------
bill = load("bill.json")
check("bill.json is available with the Meralco supply mix summing to 100%",
      bill["available"]
      and abs(sum(bill["supply_mix_pct"].values()) - 100) < 0.5)
check("WESM is the minority (residual) slice of the supply mix",
      bill["supply_mix_pct"]["wesm"]
      == min(bill["supply_mix_pct"].values()))
check("the WESM pass-through factor equals the WESM supply share (not full spot)",
      abs(bill["pass_through_factor"] - bill["wesm_share_pct"] / 100) < 1e-9
      and bill["pass_through_factor"] < 0.5)
check("the WESM cost sits inside the total generation charge",
      bill["wesm_cost_in_gen_charge_php_kwh"] < bill["generation_charge_php_kwh"]
      < bill["total_rate_php_kwh"])

# --- market-power / concentration layer (item 5) --------------------------------
mp = load("market_power.json")
check("market_power.json is available with the ERC capacity shares",
      mp["available"] and len(mp["companies"]) >= 5)
check("named shares plus others sum to 100%",
      abs(sum(c["share_pct"] for c in mp["companies"]) + mp["others_share_pct"] - 100)
      < 0.5)
check("HHI floor <= ceiling and the floor is the sum of squared named shares",
      mp["hhi_floor"] <= mp["hhi_ceiling"]
      and abs(mp["hhi_floor"]
              - sum(c["share_pct"] ** 2 for c in mp["companies"])) < 0.5)
check("the largest firm stays under the EPIRA market-share cap",
      mp["largest"]["share_pct"] < mp["cap_demand_pct"])
check("the two largest firms are close to half of national capacity",
      40 < mp["top2_combined_pct"] < 50)

# --- observed day profiles + chronological engine (studio maturation, phase 1) ---
prof = load("profiles.json")
check("profiles carries at least 60 replayable observed days",
      len(prof["days"]) >= 60)
check("every profile day has full 24-hour demand on all three grids", all(
    all(len(d["demand"][g]) == 24 and all(v is not None for v in d["demand"][g])
        for g in ("luzon", "visayas", "mindanao"))
    for d in prof["days"]))
dates = {d["date"] for d in prof["days"]}
check("default and stress days exist and are market days",
      prof["default_day"] in dates and prof["stress_day"] in dates
      and all(next(d for d in prof["days"] if d["date"] == x)["market"]
              for x in (prof["default_day"], prof["stress_day"])))
check("solar profile is a 24-hour shape peaking midday under 1.0",
      len(prof["solar_profile"]) == 24
      and 0 < max(prof["solar_profile"]) < 1
      and prof["solar_profile"][12] > prof["solar_profile"][19])
check("storage defaults pin the sourced powers (BESS 634, Kalayaan 685)",
      {s["id"]: s["power_mw"] for s in prof["storage_defaults"]}
      == {"bess_luzon": 634, "kalayaan": 685})
check("storage energies are labeled assumptions", all(
    "ASSUMPTION" in s["energy_note"] for s in prof["storage_defaults"]))
check("reserve requirement means are positive per grid", all(
    v > 0 for g in prof["reserve_req_mean_mw"].values() for v in g.values()))

cg = prof["chrono_golden"]
check("chrono golden has 11 cases (8 cost-mode + 3 offer-mode) of 24 hourly "
      "prices per grid",
      cg["available"] and len(cg["cases"]) == 11 and all(
          len(c["expect"]["price"][g]) == 24
          for c in cg["cases"] for g in ("luzon", "visayas", "mindanao")))
check("the offer-mode goldens carry the marker both engines resolve",
      sum(1 for c in cg["cases"] if c["input"].get("offer_mode")) == 3)
base_mean = cg["cases"][0]["expect"]["summary"]["mean_price"]["luzon"]
dc_mean = cg["cases"][1]["expect"]["summary"]["mean_price"]["luzon"]
check("flat DC load never lowers the mean Luzon price (monotonicity)",
      dc_mean >= base_mean)
check("the default storage fleet actually cycles in its golden case",
      max(cg["cases"][5]["expect"]["soc_mwh"]) > 0
      and abs(cg["cases"][5]["expect"]["soc_mwh"][23]) < 1e-9)
check("golden tolerances are the parity contract",
      math.isclose(cg["tolerance_php_kwh"], 0.02)
      and math.isclose(cg["tolerance_mw"], 1.0))

# item 6: the native 168h week golden. Seven explicit dates ride in the input
# so the studio replays the same window; the storage carries across midnight
# (a day ends with charge it hands the next), which the day engine cannot do.
wk = cg.get("week", {})
check("week golden baked with seven explicit dates and a 168-price expect",
      wk.get("available") and len(wk["input"]["dates"]) == 7
      and all(len(wk["expect"]["price"][g]) == 168
              for g in ("luzon", "visayas", "mindanao")))
check("week storage carries across midnight (a day ends with charge to spare)",
      max(d["end_soc_mwh"] for d in wk["expect"]["days"]) > 1)

bc = prof["backcast"]
check("backcast replays at least 30 market days",
      bc["available"] and bc["days"] >= 30)
check("backcast hours = days x 24 per grid", all(
    v["n_hours"] == bc["days"] * 24 for v in bc["per_grid"].values()))
check("backcast is honest: model under-prices the observed mean (negative bias)",
      all(v["bias_php_kwh"] < 0 for v in bc["per_grid"].values()))
check("backcast never fakes a hit rate from a flat model", all(
    v["high_hour_hit_rate_pct"] is None or 0 <= v["high_hour_hit_rate_pct"] <= 100
    for v in bc["per_grid"].values()))

# --- DOE per-plant fleet (studio maturation, phase 4) ----------------------------
fleet = load("fleet.json")
check("fleet parses all three grids and reconciles to the DOE subtotals",
      fleet["available"] and all(
          v["ok"] for g in fleet["editions"].values()
          for v in g["reconciliation"].values()))
check("fleet editions are the 2025 DOE lists with Wayback capture URLs", all(
    e["as_of"] >= "2025-03-31" and "web.archive.org" in e["src"]
    and "doe.gov.ph" in e["original_url"]
    for e in fleet["editions"].values()))
check("fleet section sums equal the DOE grand total per grid", all(
    abs(e["sections_total_mw"] - e["doe_total_mw"]) <= 1.0
    for e in fleet["editions"].values()))
plants = fleet["plants"]
check("both Sual units are in the fleet at 647 MW each",
      [p["installed_mw"] for p in plants if p["name"] in ("SPI U1", "SPI U2")]
      == [647.0, 647.0])
check("every plant has a known fuel and positive installed MW", all(
    p["fuel"] in ("coal", "oil", "natural_gas", "biomass", "geothermal",
                  "solar", "hydro", "wind") and p["installed_mw"] > 0
    for p in plants))
check("plant ids are unique per grid", len({(p["grid"], p["name"])
                                            for p in plants}) == len(plants))

# --- Pass D: the DOE PDP demand path (LT Plan demand trajectory) -----------------
dpath = load("demand_path.json")
check("DOE PDP demand path baked: per-grid peak forecast, labeled DOE owner",
      dpath.get("available") and dpath["owner"] == "DOE"
      and "2023-2050" in dpath["plan"] and len(dpath["years"]) >= 25)
check("every PDP year reconciles: the three grids sum to the plan's own "
      "Philippines total within 2 MW (the parse gate held)",
      all(abs(dpath["per_grid_mw"]["luzon"][i]
              + dpath["per_grid_mw"]["visayas"][i]
              + dpath["per_grid_mw"]["mindanao"][i]
              - dpath["philippines_mw"][i]) <= 2
          for i in range(len(dpath["years"]))))
check("the demand path is a monotone growing forecast at the DOE's stated "
      "~5 percent CAGR, labeled forecast not measurement",
      dpath["philippines_mw"] == sorted(dpath["philippines_mw"])
      and 4.5 <= dpath["cagr_2025_2050_pct"] <= 6.0
      and dpath["actual_years"] == [2021, 2022]
      and dpath["forecast_from_year"] == 2023)

# --- LT Plan: DOE project lists + TDP corridors (long-term plan carry-over pass) ---------
pj = load("projects.json")
check("projects available with the 2025-12-31 edition",
      pj["available"] and pj["as_of"] == "2025-12-31")
check("projects reconcile to the DOE LVM summary totals",
      math.isclose(pj["totals"]["committed"]["lvm_gen_mw"], 13839.48,
                   abs_tol=0.05)
      and math.isclose(pj["totals"]["indicative"]["lvm_gen_mw"], 119226.39,
                       abs_tol=0.05))
check("committed per-grid totals pin to the DOE summary",
      math.isclose(pj["totals"]["committed"]["luzon"]["gen_mw"], 11875.89,
                   abs_tol=0.02)
      and math.isclose(pj["totals"]["committed"]["visayas"]["gen_mw"], 1443.75,
                       abs_tol=0.02)
      and math.isclose(pj["totals"]["committed"]["mindanao"]["gen_mw"], 519.85,
                       abs_tol=0.02))
check("every project row carries grid, status, fuel, positive MW", all(
    r["grid"] in ("luzon", "visayas", "mindanao")
    and r["status"] in ("committed", "indicative")
    and r["fuel"] and r["mw"] >= 0 for r in pj["rows"]))
check("reconciled sections' rows sum to their printed subtotals", all(
    s["rows_reconciled"] is False or math.isclose(
        sum(r["mw"] for r in pj["rows"]
            if (r["grid"], r["status"], r["fuel"]) ==
               (s["grid"], s["status"], s["fuel"])),
        s["subtotal_mw"], abs_tol=0.01)
    for s in pj["sections"]))
check("every edition carries a Wayback capture of the DOE URL", all(
    "web.archive.org" in e["src"] and "doe.gov.ph" in e["original_url"]
    for st in pj["editions"].values() for e in st.values()))
check("TDP corridors: MW only where the TDP states transfer capacity", all(
    (c["adds_mw"] is None) or (c["iface"] in ("leyte_luzon_hvdc", "mvip_hvdc"))
    for c in pj["corridors"]))
check("TDP corridor MW pins: LV HVDC +440, MVIP +450",
      [c["adds_mw"] for c in pj["corridors"] if c["iface"]] == [440, 450])
check("every corridor has a source", all(c["src"] for c in pj["corridors"]))

# --- PASA: scheduled outages sized against the fleet ------------------------------
pasa = load("pasa.json")
check("pasa covers the whole OUTRTD archive",
      pasa["available"] and len(pasa["days"]) == meta["datasets"]["OUTRTD"])
check("pasa resources partition into verified/unmatched/storage",
      pasa["n_verified"] + pasa["n_unmatched"] + pasa["n_storage"]
      == pasa["n_resources"])
check("every verified pasa resource carries plant, grid, fuel, MW", all(
    r["plant"] and r["grid"] and r["fuel"] and (r["unit_mw"] or 0) > 0
    for r in pasa["resources"] if r["match"] == "verified"))
check("unmatched pasa resources carry no MW (a floor, never a guess)", all(
    r["unit_mw"] is None for r in pasa["resources"]
    if r["match"] != "verified"))
pasa_by_name = {r["resource"]: r for r in pasa["resources"]}
check("pasa day MW equals its verified resources", all(
    math.isclose(
        sum(day["matched_mw"].values()),
        sum(pasa_by_name[name]["unit_mw"] or 0 for name in day["out"]
            if pasa_by_name[name]["match"] == "verified"),
        abs_tol=0.5)
    for day in pasa["days"]))
check("pasa states its coverage and the inferred grid mapping",
      "floor" in pasa["coverage_note"] and "INFERRED" in pasa["grid_mapping_note"])

# --- emissions factors: sourced constants ------------------------------------------
em = load("emissions.json")
check("emissions factors all carry a basis and a source", all(
    f["basis"] and f["src"] for f in em["factors"]))
check("emissions fossil factors pinned to the sourced derivations",
      math.isclose(em["factor_map"]["coal"], 0.874)
      and math.isclose(em["factor_map"]["natural_gas"], 0.337)
      and math.isclose(em["factor_map"]["oil"], 0.533))
check("emissions: renewables and storage zero operational, biomass excluded",
      em["factor_map"]["hydro"] == 0 and em["factor_map"]["solar"] == 0
      and em["factor_map"]["storage"] == 0
      and "biomass" not in em["factor_map"])
check("emissions NGEF anchor present with source",
      math.isclose(em["ngef"]["luzon_visayas_tco2_per_mwh"], 0.7181)
      and "doe.gov.ph" in em["ngef"]["src"])

# --- bill: the residual moves month to month ---------------------------------------
bill = load("bill.json")
hist = bill.get("mix_history", [])
check("bill mix history carries Apr-Jun 2026 in order",
      [m["period"] for m in hist] == ["2026-04", "2026-05", "2026-06"])
check("bill mix shares sum to 100 per month", all(
    m["wesm_pct"] + m["psa_pct"] + m["ipp_pct"] == 100 for m in hist))
check("bill June row matches the standing anchors",
      bool(hist) and hist[-1]["wesm_pct"] == 10
      and math.isclose(hist[-1]["generation_charge_php_kwh"], 9.0704)
      and math.isclose(hist[-1]["total_rate_php_kwh"], 14.4833))
check("bill history rows each carry advisory + news sources", all(
    m["src"] and m["src_news"] for m in hist))

# --- observed market operations (the 2026-07-07 dataset expansion) ------------------
mo = load("market_ops.json")
ps = mo["price_setters"]
check("price setters baked from a full MCP window", ps["available"]
      and ps["days"] >= 80)
check("every grid names observed setters with shares that are shares", all(
    ps["per_grid"][g]["n_setters"] > 10
    and all(0 < r["share_pct"] <= 100 for r in ps["per_grid"][g]["top"])
    for g in ("luzon", "visayas", "mindanao")))
check("setter fuel matching is majority, never claimed complete", all(
    50 <= ps["per_grid"][g]["fuel_matched_share_pct"] < 100
    for g in ("luzon", "visayas", "mindanao")))
rp = mo["reserve_prices"]
check("official reserve prices span the window with stats", rp["available"]
      and len(rp["dates"]) >= 80 and rp["stats"]["luzon"])
adv = mo["advisories"]
check("advisory stream baked with HVDC events captured",
      adv["available"] and len(adv["days"]) >= 80
      and len(adv["hvdc_events"]) > 0)
ol = mo["outlook"]
check("week-ahead outage outlook carries matched MW and honest gaps",
      ol["available"] and ol["as_of"] >= "2026-07-01"
      and all(g in ol["matched_mw"]
              for g in ("luzon", "visayas", "mindanao")))
# item 9: the unit-commitment backcast measurement. Commitment must worsen the
# price correlation (block-level min-stable is too coarse) and the verdict must
# keep the LP as the default engine, the Phase-A gate the roadmap requires.
uc = mo["uc_probe"]
check("UC probe baked with the generic labeled min-stable and a verdict",
      uc.get("engine_default") == "lp"
      and uc["min_stable_generic"]["coal"] > 0
      and "generic" in uc["min_stable_label"])
check("commitment worsens the Luzon LWAP price correlation (LP stays default)",
      uc["corr_delta"]["lwap"]["luzon"]["delta"] < 0)

drv = load("drivers.json")
check("drivers timeline joins one row per archive day",
      drv["available"] and len(drv["days"]) >= 80)
check("drivers rows carry the observed columns", all(
    "lwap" in r and "out_matched_mw" in r and "binding" in r
    for r in drv["days"][:5]))
check("every market_ops section carries the analytics disclaimer", all(
    "disclaimer" in s for s in (ps, rp, adv, ol,
                                mo["reserve_validation"],
                                mo["flow_record"], mo["gwap_trigger"],
                                mo["constrained_on"],
                                mo["security_limits"],
                                mo["so_instructions"]))
    and "disclaimer" in drv)
no = mo["not_offered"]
check("the not-offered screen is baked, bounded, and self-disclaiming",
      no["available"] and len(no["days"]) >= 30
      and all(0 <= r[g]["not_offered_mw"] <= r[g]["registered_mw"]
              for r in no["days"] for g in r if g != "date")
      and "legitimate explanations" in no["note"])

# profiles carry the engine-facing observed layers per day
prof = load("profiles.json")
mkt_days = [d for d in prof["days"] if d["market"]]
check("market days carry the outage deviation layer", all(
    d.get("out_dev_mw") is not None for d in mkt_days))
check("hydro and storage never appear in outage deviations", all(
    f not in ("hydro", "storage")
    for d in mkt_days for g in (d.get("out_dev_mw") or {})
    for f in (d["out_dev_mw"][g] or {})))
check("most market days carry the observed MCP series", sum(
    1 for d in mkt_days if d.get("mcp")) >= 0.8 * len(mkt_days))
bc = prof["backcast"]
check("backcast scores both targets (LWAP and MCP)",
      bc["per_grid"] and bc.get("per_grid_mcp")
      and set(bc["per_grid_mcp"]) == {"luzon", "visayas", "mindanao"})
check("backcast scores the corridors (flows table)",
      bc.get("flows") and set(bc["flows"]) == {"lv", "vm"} and all(
          v["n_hours"] > 0 and "direction_agreement_pct" in v
          for v in bc["flows"].values()))
ob = prof.get("offer_backcast") or {}
check("offer-mode backcast baked from the derived offer days",
      ob.get("available") and ob["days"] >= 30
      and set(ob["per_grid"]) == {"luzon", "visayas", "mindanao"}
      and ob.get("flows"))
check("offer mode carries the no-extra-layers statement",
      "no storage" in (ob.get("note") or ""))
check("offer mode beats the cost proxy on corridor direction (the point)",
      (ob.get("flows") or {}).get("vm", {}).get(
          "direction_agreement_pct", 0)
      > (bc["flows"]["vm"]["direction_agreement_pct"] or 0))
# the mode gap the README quotes: on the golden day, the DICT wave must
# cost MORE on the observed bids than on the cost stack (the cost-mode
# delta is a floor), and the shock must reach the other grids in offer mode
gold = {c["label"]: c for c in cg["cases"]}
def _mp(label, g):
    return gold[label]["expect"]["summary"]["mean_price"][g]
cost_delta = (_mp("DICT 1.5 GW flat load on Luzon", "luzon")
              - _mp("base day, no storage", "luzon"))
offer_delta = (_mp("DICT 1.5 GW on the observed offer book", "luzon")
               - _mp("observed offer book, no levers", "luzon"))
check("the DICT-wave delta is larger on the observed bids than the cost "
      "stack (cost-mode scenario deltas are floors)",
      offer_delta > cost_delta > 0)
check("the as-bid shock reaches the other grids", all(
    (_mp("DICT 1.5 GW on the observed offer book", g)
     - _mp("observed offer book, no levers", g)) > 0.5
    for g in ("visayas", "mindanao")))

# observed HVDC blocks: days carry per-hour corridor availability fractions
capped_days = [d for d in prof["days"] if d.get("corridor_caps")]
check("days with observed HVDC blocks carry corridor availability fractions",
      len(capped_days) >= 20 and all(
          len(d["corridor_caps"]["leyte"]) == 24
          and all(0.0 <= f <= 1.0 for f in d["corridor_caps"]["leyte"])
          and any(f < 1.0 for f in d["corridor_caps"]["leyte"])
          for d in capped_days))

# --- round-7 archival: the three datasets the convergence audit surfaced ---
# (the archive is permanent, so these floors only ever grow)
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
with open(os.path.join(RAW_DIR, "manifest.json")) as _fh:
    manifest = json.load(_fh)
check("GWAPF (secondary-cap trigger series) is archived across its window",
      (manifest.get("GWAPF") or {}).get("files", 0) >= 70)
check("RTDHS (observed HVDC corridor record) is archived across its window",
      (manifest.get("RTDHS") or {}).get("files", 0) >= 85)
RES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "derived",
                       "reserve_daily")
res_days = sorted(n for n in os.listdir(RES_DIR) if n.startswith("RESD_"))
check("reserve books (RTDOR) derived across the offer window",
      len(res_days) >= 55)
with open(os.path.join(RES_DIR, res_days[-1])) as _fh:
    resd = json.load(_fh)
check("newest reserve book: four commodities x three grids x 24 hours",
      all(len(resd["hours"][g][c]) == 24
          for g in ("luzon", "visayas", "mindanao")
          for c in ("Fr", "Dr", "Ru", "Rd")))
check("newest reserve book prices sit inside the published reserve cap",
      all(0.0 <= p <= res["reserve_cap_php_kwh"] + 0.001
          for g in resd["hours"].values() for c in g.values()
          for h in c for p, _ in (h or [])))
# the deriver gates RAW pooled MW against the FIRST interval's schedule
# (like-for-like: the book is the hour's opening interval); the committed
# book is compacted (0.1 MW rounding, slivers dropped), so ~3 MW slack
check("newest reserve book honors the gate (book covers opening schedule)",
      all(sum(m for _, m in (resd["hours"][g][c][h] or []))
          >= (resd["sched_open_mw"][g][c][h] or 0) - 3.0
          for g in ("luzon", "visayas", "mindanao")
          for c in ("Fr", "Dr", "Ru", "Rd") for h in range(24)))

# --- round-7b consumption: the three archived datasets are now scored ---
mo = load("market_ops.json")
rv = mo.get("reserve_validation") or {}
check("reserve replay scored across the derived window (80+ days)",
      rv.get("available") and rv["days"] >= 80)
_rv_pools = [rv["pools"][g][c] for g in ("luzon", "visayas", "mindanao")
             for c in ("Fr", "Dr", "Ru", "Rd")]
check("reserve replay covers all 12 grid-commodity pools",
      len(_rv_pools) == 12 and all(p["n_hours"] > 1500 for p in _rv_pools))
check("the co-optimisation wedge is one-signed: every pool's bias is "
      "negative (the book-only replay under-prices reserves everywhere)",
      all(p["bias_php_kwh"] < 0 for p in _rv_pools))
check("the wedge dominates to aggregate precision (MAE equals -bias "
      "within half a centavo in every pool)",
      all(abs(p["mae_php_kwh"] + p["bias_php_kwh"]) <= 0.005
          for p in _rv_pools))
check("hours where the marginal offer sits above the official price "
      "stay noise-level (the prose's quantified concession)",
      rv["hours_model_above_pct"] <= 10.0
      and rv["max_model_above_php_kwh"] <= 0.05)
check("Luzon dispatchable reserve reproduces the official price "
      "(exact-hour share and calm MAE, the quoted anchors)",
      rv["pools"]["luzon"]["Dr"]["exact_hours_pct"] >= 70.0
      and rv["pools"]["luzon"]["Dr"]["mae_nonscarcity_php_kwh"] <= 0.8)
check("reserve replay states its scarcity accounting and observes "
      "scarcity somewhere in the window",
      "scarcity" in (rv.get("scarcity_note") or "")
      and any(p["n_scarcity_hours"] > 0 for p in _rv_pools))

# --- post-convergence Pass B: the settlement-side and reserve-results finals ---
# item 6: per-resource cleared reserve (DIPCRF), the tighter reserve target
# and the joint-clear input
rr = mo.get("reserve_results") or {}
check("per-resource reserve results are consumed (DIPCRF: 70+ days, the "
      "resource identity the pooled replay and RSVPR both drop)",
      rr.get("available") and rr["days"] >= 70
      and rr["resources_named"] >= 150)
_rr_pools = [rr["pools"][g][c]
             for g in ("luzon", "visayas", "mindanao")
             for c in ("Fr", "Dr", "Ru", "Rd")
             if c in (rr.get("pools", {}).get(g) or {})]
check("the book replay under-prices the FINAL cleared price on every pool "
      "too: the co-optimisation wedge holds against the authoritative target",
      len(_rr_pools) == 12
      and all(p["replay_vs_final"]["bias_php_kwh"] < 0
              for p in _rr_pools if "replay_vs_final" in p))
_rr_grids = ("luzon", "visayas", "mindanao")
check("the final re-solve's reserve-schedule revision stays a few MW across "
      "all pools (reported, not gated): near zero on Luzon "
      "contingency/dispatchable, a few MW on regulation and the tight island "
      "dispatchable reserve",
      all(abs(rr["pools"][g][c]["final_vs_rtd_schedule_mw"]
              ["mean_daily_revision"]) < 8.0
          for g in _rr_grids for c in ("Fr", "Dr", "Ru", "Rd"))
      and abs(rr["pools"]["luzon"]["Fr"]["final_vs_rtd_schedule_mw"]
              ["mean_daily_revision"]) < 1.0
      and abs(rr["pools"]["visayas"]["Dr"]["final_vs_rtd_schedule_mw"]
              ["mean_daily_revision"]) > 2.0)
check("the final-vs-RTD reserve-price gap concentrates on the regulation "
      "products (Ru/Rd), not contingency (the corrected framing)",
      max(abs(rr["pools"][g][c]["vs_rtd_price"]["bias_php_kwh"])
          for g in _rr_grids for c in ("Ru", "Rd"))
      > max(abs(rr["pools"][g]["Fr"]["vs_rtd_price"]["bias_php_kwh"])
            for g in _rr_grids))
# item 8: registered ancillary-services capacity (CAPER), the reserve
# book's registration denominator
rreg = mo.get("reserve_registration") or {}
check("registered ancillary-services capacity gives the reserve book a "
      "registration base (CAPER: 3 grids x 4 commodities, 80+ days)",
      rreg.get("available") and len(rreg["days"]) >= 80
      and all(c in (rreg.get("stats", {}).get(g) or {})
              for g in ("luzon", "visayas", "mindanao")
              for c in ("Fr", "Dr", "Ru", "Rd")))
check("the tight Visayas dispatchable reserve offers most of its "
      "registration: a low not-offered share, neutral framing",
      rreg["stats"]["visayas"]["Dr"]["median_share_of_registered_pct"]
      < rreg["stats"]["luzon"]["Ru"]["median_share_of_registered_pct"])
# items 5 and 7: the sampled settlement-side record (administered, settlement,
# day-ahead), measured not built into the replay
ss = mo.get("settlement_side") or {}
_ssg = ss.get("per_grid") or {}
check("the settlement-side sample is consumed (administered, settlement, "
      "and day-ahead on market days)",
      ss.get("available") and len(ss.get("sample_days") or []) >= 3
      and all(g in _ssg for g in ("luzon", "visayas", "mindanao")))
check("the settlement congestion component is empty at regional "
      "granularity (no receipt beyond the flows table)",
      all(_ssg[g]["settlement_congestion_max_abs_php_kwh"] <= 0.01
          for g in ("luzon", "visayas", "mindanao")))
check("the administered price carries the island premium (Visayas and "
      "Mindanao administered prices run above Luzon's, a cost-based "
      "counterfactual not the flat cost floor)",
      _ssg["visayas"]["admin_lmp_mean_php_kwh"]
      > _ssg["luzon"]["admin_lmp_mean_php_kwh"]
      and _ssg["mindanao"]["admin_lmp_mean_php_kwh"]
      > _ssg["luzon"]["admin_lmp_mean_php_kwh"])
check("the day-ahead projection spread is both-signed (a projection "
      "diagnostic, out of the replay's dispatch scope)",
      _ssg["luzon"]["dap_vs_rt_spread_range_php_kwh"][0] < 0
      < _ssg["luzon"]["dap_vs_rt_spread_range_php_kwh"][1])
# item 2 (post-convergence): observed dispatched solar/wind per grid, and the
# honest measurement that the observed/model ratio flips by grid (the model's
# solar SPLIT is approximate, not a single curtailment gap)
sw = mo["solar_wind_observed"]
check("observed dispatched solar/wind consumed per grid (DIPCEF); the "
      "observed/model solar ratio flips by grid, so the model's national "
      "solar split is approximate, not a curtailment gap",
      sw.get("available") and sw["days"] >= 40
      and sw["per_grid"]["luzon"]["observed_over_model_solar"] > 1.0
      and sw["per_grid"]["mindanao"]["observed_over_model_solar"] < 1.0)
check("solar dominates observed dispatched renewables (Luzon solar many "
      "times its wind)",
      sw["per_grid"]["luzon"]["observed_solar_mwh_day"]
      > 5 * (sw["per_grid"]["luzon"]["observed_wind_mwh_day"] or 1))

fr = mo.get("flow_record") or {}
check("the two observed corridor records agree (identity vs RTDHS "
      "within 1 MW on hourly means)",
      fr.get("available")
      and set(fr["corridors"]) == {"lv", "vm"}
      and all(v["mae_mw"] <= 1.0 for v in fr["corridors"].values()))
check("the operator's binding shares are real fractions of the record",
      all(v["binding_share_pct"] is not None
          and 20.0 <= v["binding_share_pct"] <= 80.0
          and v["n_intervals"] > 20000 for v in fr["corridors"].values()))

for _mode in ("backcast", "offer_backcast"):
    _fx = (prof.get(_mode) or {}).get("flows_rtdhs") or {}
    check(f"{_mode} scores its corridor flows against the operator's "
          "HVDC record (RTDHS), both corridors",
          set(_fx) == {"lv", "vm"} and all(
              v["n_hours"] > 1000
              and v["observed_binding_share_pct"] is not None
              and v["modeled_at_cap_share_pct"] is not None
              for v in _fx.values()))
_ofx = prof["offer_backcast"]["flows_rtdhs"]
check("offer mode keeps the corridor story against the independent "
      "record (vm direction 95%+, MAE under 80 MW)",
      _ofx["vm"]["direction_agreement_pct"] >= 95.0
      and _ofx["vm"]["mae_mw"] <= 80.0)
check("the under-binding gap is published: the operator flagged the "
      "corridors binding more often than the replay hits the cap",
      all(_ofx[k]["observed_binding_share_pct"]
          > _ofx[k]["modeled_at_cap_share_pct"] for k in ("lv", "vm")))

gt = mo.get("gwap_trigger") or {}
check("the secondary-cap trigger series is computed on all four "
      "published series with full-coverage windows",
      gt.get("available")
      and abs(gt["trigger_php_kwh"] - 12.413) < 1e-9
      and abs(gt["cap_php_kwh"] - 7.423) < 1e-9
      and set(gt["per_region"]) == {"luzon", "visayas", "mindanao",
                                    "system"}
      and all(v["max_rolling_72h"] is not None
              for v in gt["per_region"].values()))
check("the trigger arithmetic crossed its threshold inside the window "
      "(the methodology's both-directions finding, first half)",
      all(v["n_breach_windows"] > 0 for v in gt["per_region"].values()))
check("the clamp scan found no day pinned at either cap level "
      "(the both-directions finding, second half)",
      gt.get("clamp_scan_days_pinned") == {"7.423": 0, "6.245": 0})
check("the marquee as-bid day is flagged against the stated trigger "
      "numbers, and the flag is the SCENARIO's (the same windows "
      "unlifted stay under the threshold)",
      (gt.get("marquee") or {}).get("trips_trigger") is True
      and gt["marquee"]["baseline_trips"] is False
      and gt["marquee"]["scenario_max_rolling_72h"]["rolling_php_kwh"]
      > gt["trigger_php_kwh"]
      >= gt["marquee"]["baseline_max_rolling_72h"]["rolling_php_kwh"])
check("the trigger block disclaims its own mechanism gap",
      "does not reproduce" in (gt.get("mechanism_note") or ""))

# the README quotes the offer-mode Visayas settlement bias at -P0.60
# (also registered in verify_claims as offer_vis_bias so --write keeps README synced)
check("README's quoted Visayas offer-mode settlement bias matches the bake",
      abs(prof["offer_backcast"]["per_grid"]["visayas"]["bias_php_kwh"]
          - (-0.60)) <= 0.01)

# --- round-8 consumption: the constrained-on roster and security limits ---
co = mo.get("constrained_on") or {}
check("constrained-on roster baked across its published window",
      co.get("available") and co["n_days"] >= 70
      and co["n_resources"] >= 100)
check("constrained-on names units in all three grids with prices "
      "inside the offer cap",
      all(co["per_grid_intervals"][g] > 0
          for g in ("luzon", "visayas", "mindanao"))
      and all(0 < r["mean_price_php_kwh"] <= 32.0
              and r["max_price_php_kwh"] <= 32.0
              and r["n_intervals"] > 0 for r in co["top"]))
check("constrained-on states what it is (administered, not market "
      "clearing; two-week lag)",
      "administered" in (co.get("note") or "")
      and "two weeks" in (co.get("note") or ""))
sl = mo.get("security_limits") or {}
check("security limits baked across their published window",
      sl.get("available") and sl["n_days"] >= 85
      and sl["n_windows"] > 10000 and sl["n_resources"] >= 10)
check("the security limits are pinned operating points (MAX equals MIN "
      "in nearly every archived window, the note's claim)",
      sl["pinned_share_pct"] is not None
      and sl["pinned_share_pct"] >= 90.0
      and all(r["max_mw"] > 0 and r["n_windows"] > 0 for r in sl["top"]))
check("security-limit resources resolve to a grid (RTDSL region codes "
      "mapped, the round-8 review's dead-field catch)",
      all(r["grid"] in ("luzon", "visayas", "mindanao")
          for r in sl["top"]))

# --- round-9 consumption: the SO dispatch-instruction family ---
so = mo.get("so_instructions") or {}
mot = so.get("motrd") or {}
check("MOT-raise record baked across its weekly window",
      so.get("available") and len(mot["weeks"]) >= 10
      and mot["n_rows"] > 50000 and mot["n_resources"] >= 100)
check("the full out-of-merit record is not inert (median several times "
      "the must-run subset's, the rescoped boundary)",
      mot["median_mw"] >= 5 * (so["mru_contrast"]["mru_median_mw"] or 1)
      and mot["max_mw"] > (so["mru_contrast"]["mru_max_mw"] or 0))
check("MOT-raise resources resolve to a grid (REGION codes mapped)",
      all(r["grid"] in ("luzon", "visayas", "mindanao")
          for r in mot["top"]))
sod = so.get("sodir") or {}
check("the daily instruction log spans the window with the operator's "
      "own categories (weekly compilations archived, never counted)",
      sod["n_files"] >= 260 and sod["n_days"] >= 85
      and sod["n_weekly_files_archived"] >= 30
      and sod["n_instructions"] > 50000 and len(sod["categories"]) >= 5)
check("the operator names the map's marquee corridor as the dispatch "
      "cause (the README's Leyte-Cebu remark counts; the round-10 "
      "matcher fix holds all spellings)",
      sod["n_limitation_remarks"] > 1000
      and sod["limitation_causes"]["leyte-cebu"] > 1000
      and 100 * sod["limitation_causes"]["leyte-cebu"]
      / sod["n_limitation_remarks"] >= 95.0)
check("the discrepancy list travels with the family (newest revision "
      "per week)",
      (so.get("discrepancies") or {}).get("n_weeks", 0) >= 5
      and so["discrepancies"]["n_rows_newest_revisions"] > 0)
# Pass E: the administered-dispatch overlay was MEASURED, and the measurement
# killed the per-fuel engine build (material MW but price-inert: coal is the
# marginal fuel on ~90 percent of raise hours)
ad = mo.get("admin_dispatch") or {}
check("the administered-dispatch overlay is measured: material in MW but "
      "price-inert in the per-fuel engines (coal marginal on ~90 pct of "
      "raise hours; every raise hour already prices at coal's floor so a "
      "floor cannot lift it), documented not built",
      ad.get("available")
      and ad["verdict"] == "measured_material_but_per_fuel_inert"
      and ad["coal_marginal_share_pct"] >= 80.0
      and ad["max_modeled_price_on_raise_hours_php_kwh"] < 6.1
      and ad["raised_mw_fuel_mix_pct"]["coal"] > 50.0
      and ad["mw_weighted_fraction_of_dispatch"]["mindanao"]["mw_weighted_pct"]
      > ad["mw_weighted_fraction_of_dispatch"]["luzon"]["mw_weighted_pct"])
check("the administered raises are material (several percent of dispatch on "
      "every grid's raise hours, not the inert must-run subset)",
      all(ad["mw_weighted_fraction_of_dispatch"][g]["mw_weighted_pct"] >= 3.0
          for g in ("luzon", "visayas", "mindanao")))
# Pass F: the per-resource joint energy+reserve LP was prototyped and does NOT
# reproduce the official reserve price, so the wedge stays measured not closed
jl = mo.get("joint_lp_probe") or {}
check("the joint energy+reserve LP was prototyped and diagnosed: the wedge is "
      "administered reserve scarcity on the requirement-short hours, not "
      "recoverable from the offers (documented boundary, not a build)",
      jl.get("available")
      and jl["verdict"] == "wedge_is_administered_reserve_scarcity_not_in_offers"
      and jl["n_samples"] >= 4
      and jl["n_requirement_short"] >= 2)
check("on the requirement-met hours the offer stack cleared to the scheduled "
      "reserve reproduces the official price (small gap); on the short hours "
      "the official is a large administered scarcity uplift above the stack",
      jl["max_offer_stack_gap_on_met_hours_php_kwh"] <= 3.0
      and jl["max_scarcity_uplift_on_short_hours_php_kwh"] >= 10.0)
# Pass G: the negative-price sign flips are a knife-edge; sub-hourly resolution
# is necessary (hour-mean cannot cross) but not sufficient (margin finer than
# the offers pin down)
sh = mo.get("subhourly_probe") or {}
check("the negative-price sign flips are a measured knife-edge: floor-priced "
      "supply within a few percent of native load, observed regional price "
      "crosses negative, but the margin is finer than the offers resolve",
      sh.get("available")
      and sh["verdict"]
      == "sign_flips_are_a_knife_edge_needing_finer_supply_than_offers"
      and sh["min_margin_pct"] < 1.0
      and sh["n_days_with_observed_negatives"] >= 3)
check("the deep negatives are structurally nodal: at the deepest interval "
      "physical load exceeds the aggregate floor supply, so the per-grid "
      "clear must price positive there (no per-grid replay reproduces it)",
      (sh.get("deep_negative_structural") or {}).get("aggregate_must_price_positive")
      is True
      and sh["deep_negative_structural"]["observed_price_php_kwh"] < -5.0)

print(f"\n{len(fails)} failures" if fails else "\nall green")
sys.exit(1 if fails else 0)
