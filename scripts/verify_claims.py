#!/usr/bin/env python3
"""Keep the hand-written public prose in lockstep with the bake.

The map reads findings.json/answers.json, which build_data.py recomputes every
bake, so the on-screen numbers are always current. The README, the OG card
caption, and the montage are hand-typed and freeze at whatever bake last touched
them; the archive window rolls a day forward every night, so every window-derived
count in that prose silently drifts. A journalist who checks the README against
the live map finds them disagreeing.

This is the oracle that closes that gap. It reads the same baked artifacts the
map reads, derives the canonical value for every rolling number the prose
carries, and either checks the prose against them (--check, run by `make qa` and
CI, fails on drift) or rewrites the prose to match (--write, run by `make data`
so the nightly rebake keeps README + OG in lockstep with the map).

Numbers that do not move with the window (the 3,629 MW May margin, the 41
percent, the Meralco split, the 87.8 percent outage backcast) are NOT registered
here: they are pinned by tests/test_data.py and change only when their source
does. This file owns exactly the window-derived counts, including the MOT-raise
and line-limitation instruction totals, which grow with the archive every night.
"""
import argparse
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")


def _load(name):
    with open(os.path.join(WEB, name)) as fh:
        return json.load(fh)


_RES_NAMES = {"Fr": "contingency (Fr)", "Dr": "dispatchable (Dr)",
              "Ru": "regulation up (Ru)", "Rd": "regulation down (Rd)"}


def _reserve_table_md(rv):
    """Regenerate the studio reserve-validation table from the baked pools."""
    def peso(x):
        return f"-P{abs(x):.2f}" if x < 0 else f"P{x:.2f}"
    rows = ["| Pool | Hours | Observed mean | Modeled mean | Bias | Exact hours "
            "| Scarcity hours | MAE outside scarcity |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for grid in ("luzon", "visayas", "mindanao"):
        for cm in ("Fr", "Dr", "Ru", "Rd"):
            p = rv["pools"][grid][cm]
            rows.append(
                f"| {grid.capitalize()} {_RES_NAMES[cm]} | {p['n_hours']:,} | "
                f"P{p['observed_mean_php_kwh']:.2f} | P{p['modeled_mean_php_kwh']:.2f} | "
                f"{peso(p['bias_php_kwh'])} | {p['exact_hours_pct']:.1f}% | "
                f"{p['n_scarcity_hours']} | P{p['mae_nonscarcity_php_kwh']:.2f} |")
    return "\n".join(rows)


# The studio BackcastView renders these tables from profiles.json with
# Intl.NumberFormat (halfExpand rounding). Python's round() is banker's rounding,
# so use Decimal ROUND_HALF_UP to reproduce the app's cells exactly; the README
# then matches what the live studio shows, not just the raw bake fields.
def _q(v, dp):
    return Decimal(str(v)).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)


def _n(v, dp=0):
    return f"{_q(v, dp):,.{dp}f}"


def _p(v, kwh=False):          # peso mean/MAE, README P-convention
    return f"P{_q(v, 2):.2f}" + ("/kWh" if kwh else "")


def _pb(v):                    # signed peso bias, +P / -P
    return ("-" if v < 0 else "+") + f"P{_q(abs(v), 2):.2f}"


def _hit(s):
    v = s.get("high_hour_hit_rate_pct")
    return "n/a (flat model)" if v is None else f"{_n(v, 0)}%"


def _mw(v):
    return f"{_n(v, 0)} MW"


def _bc_grid_table(pg, window_pg=None, coverage=False):
    cols = ("| Grid | Coverage | Observed mean | Modeled mean | MAE | Bias | "
            "Correlation | High-hour hit |") if coverage else (
            "| Grid | Observed mean | Modeled mean | MAE | Bias | Correlation "
            "| High-hour hit |")
    dash = "| " + " | ".join(["---"] * (8 if coverage else 7)) + " |"
    rows = [cols, dash]
    for g in ("luzon", "visayas", "mindanao"):
        s = pg[g]
        cov = (f" {int(s['n_hours']):,} of {int(window_pg[g]['n_hours']):,} h |"
               if coverage else "")
        rows.append(
            f"| {g.capitalize()} |{cov} {_p(s['observed_mean_php_kwh'], True)} | "
            f"{_p(s['modeled_mean_php_kwh'], True)} | {_p(s['mae_php_kwh'])} | "
            f"{_pb(s['bias_php_kwh'])} | {_n(s['correlation'], 2)} | {_hit(s)} |")
    return "\n".join(rows)


def _bc_flows_table(flows, header):
    rows = [f"| {header} | Observed mean | Modeled mean | MAE | Direction agreement |",
            "| --- | --- | --- | --- | --- |"]
    for k in ("lv", "vm"):
        f = flows[k]
        rows.append(f"| {f['corridor']} | {_mw(f['observed_mean_mw'])} | "
                    f"{_mw(f['modeled_mean_mw'])} | {_mw(f['mae_mw'])} | "
                    f"{_n(f['direction_agreement_pct'], 0)}% |")
    return "\n".join(rows)


def _bc_offer_target(ob):
    rows = ["| Grid | Target | MAE | Bias | Correlation | High-hour hit |",
            "| --- | --- | --- | --- | --- | --- |"]
    for tgt, key in (("LWAP", "per_grid"), ("MCP", "per_grid_mcp")):
        for g in ("luzon", "visayas", "mindanao"):
            s = ob[key][g]
            rows.append(f"| {g.capitalize()} | {tgt} | {_p(s['mae_php_kwh'])} | "
                        f"{_pb(s['bias_php_kwh'])} | {_n(s['correlation'], 2)} | "
                        f"{_hit(s)} |")
    return "\n".join(rows)


def _bc_rtdhs(bc, ob):
    rows = ["| Corridor (vs operator record) | Observed mean | Modeled mean | MAE "
            "| Direction | Observed binding share | Modeled at-cap share |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for mode, src in (("cost mode", bc["flows_rtdhs"]),
                      ("offer mode", ob["flows_rtdhs"])):
        for k in ("lv", "vm"):
            f = src[k]
            rows.append(
                f"| {f['corridor']}, {mode} | {_mw(f['observed_mean_mw'])} | "
                f"{_mw(f['modeled_mean_mw'])} | {_mw(f['mae_mw'])} | "
                f"{_n(f['direction_agreement_pct'], 0)}% | "
                f"{_n(f['observed_binding_share_pct'], 0)}% | "
                f"{_n(f['modeled_at_cap_share_pct'], 0)}% |")
    return "\n".join(rows)


def _ci(w, i):
    """CI bound i for a loss-surface grid, falling back to the point estimate if
    the Fisher CI is unavailable (guards a None subscript on a degenerate grid)."""
    ci = w.get("spearman_ci95")
    return ci[i] if ci else w["spearman"]


def canonical():
    """Every rolling count the public prose carries, straight from the bake."""
    cg = _load("congestion.json")
    mo = _load("market_ops.json")
    fnd = {f["id"]: f for f in _load("findings.json")["findings"]}

    league = cg["league"]

    def _corridor(sub, field):
        # the day-ahead / real-time day counts for a named corridor element
        rows = [r for r in league if sub in (r.get("equipment") or "")]
        return max((r.get(field, 0) for r in rows), default=0)

    def _leyte_cebu(field):
        rows = [r for r in league if r.get("equipment") == "LEYTE_TO_CEBU"]
        return max((r.get(field, 0) for r in rows), default=0)

    sodir = mo["so_instructions"]["sodir"]
    rv = mo["reserve_validation"]
    disp = _load("dispatch.json")
    rel = disp["reliability_mc"]
    rel_lu = rel["per_grid"]["luzon"]
    rel_dc = rel["dict_2028_luzon"]["distribution"]
    cal = disp["calibration"]
    frc = mo["flow_record"]["corridors"]
    profiles = _load("profiles.json")
    bc = profiles["backcast"]
    ob = profiles["offer_backcast"]
    _cg = {c["label"]: c for c in profiles["chrono_golden"]["cases"]}
    ls = _load("loss_surface.json")["window"]
    noc = _load("nodal_obs.json")["congestion"]

    def _delta(wave_lbl, base_lbl, g):
        # DICT-wave daily-mean uplift per grid, straight from the golden cases
        return (_cg[wave_lbl]["expect"]["summary"]["mean_price"][g]
                - _cg[base_lbl]["expect"]["summary"]["mean_price"][g])

    _WAVE_C, _BASE_C = "DICT 1.5 GW flat load on Luzon", "base day, no storage"
    _WAVE_O, _BASE_O = ("DICT 1.5 GW on the observed offer book",
                        "observed offer book, no levers")

    # reserve-shortfall days are baked into the findings blurb; read the number
    # build_data.py already computed rather than recomputing the series here.
    thin = fnd["thin-normal"]["stat"]
    m = re.search(r"below the stated requirement on (\d+) of (\d+)", thin)
    luzon_short, _thin_days = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    # curtailment grid-days and MWh come from the same findings card the map shows
    blurb = fnd["thin-normal"]["blurb"]
    mc = re.search(r"curtailed on (\d+) grid-days? in this window \(([\d,]+\.\d+) MWh\)",
                   blurb)
    curtail_days, curtail_mwh = (int(mc.group(1)), mc.group(2)) if mc else (0, "0")

    return {
        "days_covered": cg["days_covered"],
        "distinct_equipment": cg["distinct_equipment"],
        "leyte_cebu_dap_days": _leyte_cebu("dap_days"),
        "top_corridor_dap_days": _corridor("5DAAN_4TAB2", "dap_days"),
        "top_corridor_rtd_days": _corridor("5DAAN_4TAB2", "rtd_days"),
        "luzon_reserve_short_days": luzon_short,
        "curtail_grid_days": curtail_days,
        "curtail_mwh": curtail_mwh,
        "sodir_days": sodir["n_days"],
        "limitation_remarks": _n(sodir["n_limitation_remarks"], 0),
        "leyte_cebu_remarks": _n(sodir["limitation_causes"]["leyte-cebu"], 0),
        "limitation_pct": _n(
            sodir["limitation_causes"]["leyte-cebu"]
            / sodir["n_limitation_remarks"] * 100, 0),
        "motrd_rows": _n(mo["so_instructions"]["motrd"]["n_rows"], 0),
        "motrd_median": _n(mo["so_instructions"]["motrd"]["median_mw"], 0),
        # methodology.html rounds the count to thousands ("97 thousand")
        "motrd_thousands": _n(round(mo["so_instructions"]["motrd"]["n_rows"] / 1000), 0),
        # reliability Monte Carlo, base + DICT-wave (dispatch.json reliability_mc)
        "rel_base_lolp": _n(rel_lu["lolp_pct"], 2),
        "rel_base_worst": _n(rel_lu["shortfall_mw_max"], 0),
        "rel_dict_lolp": _n(rel_dc["lolp_pct"], 1),
        "rel_dict_p99": _n(rel_dc["shortfall_mw_p99"], 0),
        "rel_dict_eue": _n(rel_dc["eue_mwh_evening_window"], 0),
        # offer-book backcast Mindanao clearing-price (MCP) correlation
        "offer_min_mcp_corr": _n(ob["per_grid_mcp"]["mindanao"]["correlation"], 2),
        # The headline range must span EVERY scored grid on both targets. It was
        # hand-written as "0.73 to 0.88" and silently dropped the minimum, which
        # was Visayas LWAP, the grid this project is about. Compute both ends.
        "offer_corr_lo": _n(min(v["correlation"] for d in ("per_grid", "per_grid_mcp")
                                for v in ob[d].values()), 2),
        "offer_corr_hi": _n(max(v["correlation"] for d in ("per_grid", "per_grid_mcp")
                                for v in ob[d].values()), 2),
        # layered (unit-commitment) calibration correlations + MAE per grid
        "cal_luz_corr": _n(cal["luzon"]["correlation"], 2),
        "cal_vis_corr": _n(cal["visayas"]["correlation"], 2),
        "cal_min_corr": _n(cal["mindanao"]["correlation"], 2),
        "cal_luz_mae": _n(cal["luzon"]["mae_php_kwh"], 2),
        "cal_vis_mae": _n(cal["visayas"]["mae_php_kwh"], 2),
        "cal_luz_modeled": _n(cal["luzon"]["modeled_mean_php_kwh"], 2),
        "cal_luz_observed": _n(cal["luzon"]["observed_mean_php_kwh"], 2),
        # observed corridor binding share (flow_record CONGESTION_FLAG)
        "bind_visluz": _n(frc["lv"]["binding_share_pct"], 0),
        "bind_minvis": _n(frc["vm"]["binding_share_pct"], 0),
        # reserve-price exact-match share, Luzon dispatchable pool
        "reserve_luz_dr_exact": _n(rv["pools"]["luzon"]["Dr"]["exact_hours_pct"], 1),
        # Visayas settlement bias, cost mode -> offer mode (README "collapsing from")
        "cost_vis_bias": _n(abs(bc["per_grid"]["visayas"]["bias_php_kwh"]), 2),
        "offer_vis_bias": _n(abs(ob["per_grid"]["visayas"]["bias_php_kwh"]), 2),
        # storage reliability buyback under the DICT wave (without -> with storage)
        "buyback_lolp_wo": _n(disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["without"]["lolp_pct"], 2),
        "buyback_lolp_w": _n(disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["with_storage"]["lolp_pct"], 2),
        "buyback_eue_wo": _n(disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["without"]["eue_mwh_evening_window"], 0),
        "buyback_eue_w": _n(disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["with_storage"]["eue_mwh_evening_window"], 0),
        # added Visayas load that binds the Leyte-Luzon corridor (dc_binding_threshold)
        "dc_knee": _n(disp["coupling"]["dc_binding_threshold"]["added_visayas_load_to_bind_leyte_mw"], 0),
        # backcast narrative scalars quoted in studio/README prose next to the tables
        "vis_lwap_hit": _n(bc["per_grid"]["visayas"]["high_hour_hit_rate_pct"], 0),
        "vis_mcp_hit": _n(bc["per_grid_mcp"]["visayas"]["high_hour_hit_rate_pct"], 0),
        "luz_lwap_corr": _n(bc["per_grid"]["luzon"]["correlation"], 2),
        "offer_vismin_mae": _n(ob["flows"]["vm"]["mae_mw"], 0),
        # Visayas evening-peak residual (evening-hours, moves with hour bucketing)
        "evening_residual_vis": _n(cal["visayas"]["evening_peak_residual_php_kwh"], 2),
        # marginal-block shares + corridor availability + price-duration spike
        "coal_margin_luz": _n(next(b["share_pct"] for b in disp["marginal_frequency"]["luzon"]["by_block"] if b["block"].startswith("coal (marginal)")), 0),
        "mindanao_overnight": _n(next(b["share_pct"] for b in disp["marginal_frequency"]["mindanao"]["by_block"] if "committed" in b["block"]), 1),
        "corridor_blocked": _n(disp["coupling"]["observed_corridor_caps"]["leyte_luzon_hvdc"]["capped_share_pct"], 1),
        "corridor_saturated": _n(next(c["saturated_pct"] for c in disp["coupling"]["corridors"] if "leyte" in c["id"]), 1),
        "duration_max": _n(max(x["price"] for x in disp["price_duration"]["luzon"]["observed"]), 0),
        # offer-book biases + the marquee widest-swing DICT-wave deltas (cost vs offer)
        "offer_luz_lwap_bias": _n(ob["per_grid"]["luzon"]["bias_php_kwh"], 2),
        "offer_vis_mcp_bias": _n(abs(ob["per_grid_mcp"]["visayas"]["bias_php_kwh"]), 2),
        "cost_luz_delta": _n(_delta(_WAVE_C, _BASE_C, "luzon"), 2),
        "offer_luz_delta": _n(_delta(_WAVE_O, _BASE_O, "luzon"), 2),
        "offer_vis_delta": _n(_delta(_WAVE_O, _BASE_O, "visayas"), 2),
        "offer_min_delta": _n(_delta(_WAVE_O, _BASE_O, "mindanao"), 2),
        "marquee_rolling": _n(mo["gwap_trigger"]["marquee"]["scenario_max_rolling_72h"]["rolling_php_kwh"], 2),
        "pinned_share": _n(mo["security_limits"]["pinned_share_pct"], 1),
        # The boundaries prose carries market_ops-derived scalars that nothing
        # guarded, and every one of them had drifted by the round-10 audit:
        # "five of the six" days (bake said four), "about 90 percent" coal
        # marginal share (95.2), 9,833 MW floor supply (9,834). Guard them.
        # the ramp measurement: the fleet figures are registration data but
        # the worst observed demand rise grows with the archive, so the
        # ratios move nightly and the prose must move with them
        "ramp_luz_fleet": f'{mo["ramp_probe"]["fleet_ramp_mw_per_hour"]["luzon"]:,.0f}',
        "ramp_luz_worst": f'{mo["ramp_probe"]["worst_observed_demand_rise_mw_per_hour"]["luzon"]:,.0f}',
        # "about one percent of clean-day node-hours" rides on six public
        # surfaces and was hand-written; it is 1.18% and now computed
        "mot_headroom_luz": _n(mo["mot_dispatch_cut"]["per_grid"]["luzon"]
                               ["headroom_mw"]["mean"], 1),
        "mot_headroom_vis_min": _n(mo["mot_dispatch_cut"]["per_grid"]["visayas"]
                                   ["headroom_mw"]["min"], 1),
        "cong_clean_share": _n(_load("nodal_obs.json")["congestion"]
                               ["clean_day_nonzero_share_pct"], 2),
        "ramp_headroom_lo": _n(mo["ramp_probe"]["headroom_min"], 1),
        "ramp_headroom_hi": _n(mo["ramp_probe"]["headroom_max"], 1),
        "subhourly_neg_days": mo["subhourly_probe"]["n_days_with_observed_negatives"],
        "subhourly_neg_days_word": ("one two three four five six seven eight"
                                    .split()[mo["subhourly_probe"]
                                             ["n_days_with_observed_negatives"] - 1]),
        "coal_marginal_share": _n(mo["admin_dispatch"]["coal_marginal_share_pct"], 0),
        "floor_supply_mw": f'{mo["subhourly_probe"]["deep_negative_structural"]["aggregate_floor_supply_mw"]:,}',
        "reserve_days": rv["days"],
        "reserve_above_pct": f'{rv["hours_model_above_pct"]:.1f}',
        "scored_hours": f"{sum(c['n_hours'] for g in rv['pools'].values() for c in g.values()):,}",
        "reserve_table": _reserve_table_md(rv),
        "bc_lwap": _bc_grid_table(bc["per_grid"]),
        "bc_mcp": _bc_grid_table(bc["per_grid_mcp"], bc["per_grid"], coverage=True),
        "bc_flows": _bc_flows_table(bc["flows"], "Corridor"),
        "bc_offer_target": _bc_offer_target(ob),
        "bc_offer_flows": _bc_flows_table(ob["flows"], "Corridor (offer mode)"),
        "bc_rtdhs": _bc_rtdhs(bc, ob),
        "vis_lwap_corr": _n(bc["per_grid"]["visayas"]["correlation"], 2),
        "vis_mcp_corr": _n(bc["per_grid_mcp"]["visayas"]["correlation"], 2),
        "profiles_days": len(profiles["days"]),
        # loss-surface validation (recomputes nightly; guards the README
        # "validated" claim and the methodology bus-count caveat) (F4)
        "loss_luz_spearman": _n(ls["luzon"]["spearman"], 2),
        "loss_min_spearman": _n(ls["mindanao"]["spearman"], 2),
        "loss_vis_spearman": _n(ls["visayas"]["spearman"], 2),
        "loss_luz_nodes": ls["luzon"]["n_nodes"],
        "loss_vis_nodes": ls["visayas"]["n_nodes"],
        "loss_min_nodes": ls["mindanao"]["n_nodes"],
        "loss_luz_bus": ls["luzon"]["n_bus"],
        "loss_vis_bus": ls["visayas"]["n_bus"],
        "loss_min_bus": ls["mindanao"]["n_bus"],
        "loss_luz_ci_lo": _n(_ci(ls["luzon"], 0), 2),
        "loss_luz_ci_hi": _n(_ci(ls["luzon"], 1), 2),
        "loss_min_ci_lo": _n(_ci(ls["mindanao"], 0), 2),
        "loss_min_ci_hi": _n(_ci(ls["mindanao"], 1), 2),
        # published-congestion summary over the static DIPCEF sample (F1 guard)
        "cong_days_nonzero": noc["days_nonzero"],
        "cong_days_sampled": noc["days_sampled"],
        "cong_max": _n(noc["max_php_kwh"], 0),
        "window_from": cg["window"]["from"],
        "window_to": cg["window"]["to"],
    }


# Each registry entry: a unique anchor regex over the README with ONE capture
# group holding the number, and the canonical key it must equal. The anchor
# carries enough surrounding words to match exactly one place.
# Each entry: (file, anchor regex with ONE capture group per key, keys). The
# anchor carries enough surrounding words to match exactly one place. --write
# rewrites the captured number(s) in place; --check fails on any mismatch. The
# studio reserve TABLE's 96 cells are handled as a regenerated BLOCK below, not
# as scalars here.
REGISTRY = [
    # --- README.md (the LinkedIn-facing surface; --write auto-syncs it nightly)
    ("README.md",
     re.compile(r"day-ahead runs on \*\*(\d+) of the window's (\d+) days\*\*"),
     ["leyte_cebu_dap_days", "days_covered"]),
    ("README.md",
     re.compile(r"binding limit in the hourly day-ahead runs on \*\*(\d+) of (\d+)"),
     ["top_corridor_dap_days", "days_covered"]),
    ("README.md",
     re.compile(r"the run settlement\s*\n?\s*actually sees, on \*\*(\d+) days\*\*"),
     ["top_corridor_rtd_days"]),
    ("README.md",
     re.compile(r"Across the (\d+)-day window, \*\*(\d+) distinct pieces of equipment\*\*"),
     ["days_covered", "distinct_equipment"]),
    ("README.md",
     re.compile(r"below the stated requirement on (\d+) of the window's (\d+) days\*\*"),
     ["luzon_reserve_short_days", "days_covered"]),
    ("README.md",
     re.compile(r"dispatch schedules on \*\*(\d+) grid-days \(([\d,]+\.\d) MWh\)\*\*"),
     ["curtail_grid_days", "curtail_mwh"]),
    ("README.md",
     re.compile(r"Across the (\d+)\s*\n?\s*daily logs the System Operator"),
     ["sodir_days"]),
    ("README.md",
     re.compile(r"citing a line limitation \*\*([\d,]+) times, and ([\d,]+) of those name the"),
     ["limitation_remarks", "leyte_cebu_remarks"]),
    ("README.md",
     re.compile(r"one corridor carries (\d+) percent of\s*\n?\s*every line-limitation"),
     ["limitation_pct"]),
    ("README.md",
     re.compile(r"\*\*([\d,]+) MOT-raise instructions\*\* across the window at a \*\*(\d+)\s*\n?\s*MW\*\* median"),
     ["motrd_rows", "motrd_median"]),
    # --- studio/README.md scalars (reserve replay + data table)
    ("studio/README.md",
     re.compile(r"at the same interval: (\d+) days, twelve"),
     ["reserve_days"]),
    ("studio/README.md",
     re.compile(r"noise-level \((\d+\.\d) percent of the ~([\d,]+) scored"),
     ["reserve_above_pct", "scored_hours"]),
    ("studio/README.md",
     re.compile(r"Hourly demand and observed prices \((\d+) observed days\)"),
     ["profiles_days"]),
    # the two backcast correlations quoted in the narrative prose (they must
    # agree with the tables above them, which drifted apart before this)
    ("studio/README.md",
     re.compile(r"settlement-price shape \(correlation\s*\n?\s*(0\.\d+)"),
     ["vis_lwap_corr"]),
    ("studio/README.md",
     re.compile(r"agreement \(correlation 0\.\d+ to (0\.\d+), hit"),
     ["vis_mcp_corr"]),
    # --- web/methodology.html scalars
    ("web/methodology.html",
     re.compile(r"same interval, (\d+) days by 12 grid-commodity pools"),
     ["reserve_days"]),
    ("web/methodology.html",
     re.compile(r"noise-level \((\d+\.\d) percent of scored hours"),
     ["reserve_above_pct"]),
    # the MOT-raise count rounded to thousands, quoted in two methodology places
    ("web/methodology.html",
     re.compile(r"must-run subset: (\d+)\s*\n?\s*thousand instructions across the archived window"),
     ["motrd_thousands"]),
    ("web/methodology.html",
     re.compile(r"re-dispatch record carries (\d+) thousand instructions across the"),
     ["motrd_thousands"]),
    ("web/methodology.html",
     re.compile(r"bound in (\d+) percent of VISLUZ1 and (\d+) percent of MINVIS1"),
     ["bind_visluz", "bind_minvis"]),
    ("web/methodology.html",
     re.compile(r"within half a centavo in (\d+\.\d) percent of hours"),
     ["reserve_luz_dr_exact"]),
    # --- README reliability Monte Carlo (base + DICT wave)
    ("README.md",
     re.compile(r"loses load in only \*\*(0\.\d+)%\*\* of tight evenings"),
     ["rel_base_lolp"]),
    ("README.md",
     re.compile(r"worst draw shedding\s*\n?\s*\*\*([\d,]+) MW\*\*"),
     ["rel_base_worst"]),
    ("README.md",
     re.compile(r"climbs more than tenfold to \*\*(\d\.\d+)%\*\*"),
     ["rel_dict_lolp"]),
    ("README.md",
     re.compile(r"1-in-100 draw sheds\s*\n?\s*\*\*([\d,]+) MW\*\*"),
     ["rel_dict_p99"]),
    ("README.md",
     re.compile(r"evening-peak window is\s*\n?\s*\*\*([\d,]+) MWh\*\*"),
     ["rel_dict_eue"]),
    # --- README layered-calibration correlations + MAE + means
    ("README.md",
     re.compile(r"correlation of \*\*(0\.\d+)\*\* with an MAE\s*\n?\s*of \*\*P(\d+\.\d+)\*\*"),
     ["cal_vis_corr", "cal_vis_mae"]),
    ("README.md",
     re.compile(r"Luzon at \*\*(0\.\d+)\*\* with an MAE of \*\*P(\d+\.\d+)\*\*"),
     ["cal_luz_corr", "cal_luz_mae"]),
    ("README.md",
     re.compile(r"undefined correlation to \*\*(0\.\d+)\*\*\. After the layer"),
     ["cal_min_corr"]),
    ("README.md",
     re.compile(r"modeled \*\*P(\d+\.\d+)/kWh\*\* against an observed \*\*P(\d+\.\d+)/kWh\*\*"),
     ["cal_luz_modeled", "cal_luz_observed"]),
    # --- README offer-book backcast Mindanao MCP correlation (two mentions)
    ("README.md",
     re.compile(r"Mindanao clearing-price correlation \*\*(0\.\d+)\*\*"),
     ["offer_min_mcp_corr"]),
    ("README.md",
     re.compile(r"reaching \*\*(0\.\d+) to (0\.\d+) correlation\*\*"),
     ["offer_corr_lo", "offer_corr_hi"]),
    ("README.md",
     re.compile(r"collapsing from\s*\n?\s*\*\*-P(\d+\.\d+)\*\* to \*\*-P(\d+\.\d+)/kWh\*\*"),
     ["cost_vis_bias", "offer_vis_bias"]),
    # --- studio/README.md carries the same bias + Mindanao-correlation prose
    ("studio/README.md",
     re.compile(r"settlement bias collapses from -P(\d+\.\d+) to -P(\d+\.\d+)"),
     ["cost_vis_bias", "offer_vis_bias"]),
    ("studio/README.md",
     re.compile(r"clearing-price\s*\n?\s*correlation reaches (0\.\d+)"),
     ["offer_min_mcp_corr"]),
    # storage buyback (README) + the corridor knee (README + studio)
    ("README.md",
     re.compile(r"loss-of-load probability falls from \*\*(\d+\.\d+)%\*\* to \*\*(\d+\.\d+)%\*\*"),
     ["buyback_lolp_wo", "buyback_lolp_w"]),
    ("README.md",
     re.compile(r"unserved energy from \*\*([\d,]+) MWh\*\* to \*\*(\d+) MWh\*\*"),
     ["buyback_eue_wo", "buyback_eue_w"]),
    ("README.md",
     re.compile(r"just \*\*(\d+) MW\*\* of added Visayas load binds the"),
     ["dc_knee"]),
    ("studio/README.md",
     re.compile(r"puts the knee at (\d+) MW"),
     ["dc_knee"]),
    ("studio/README.md",
     re.compile(r"the (\d+) MW threshold, and the"),
     ["dc_knee"]),
    # studio narrative scalars that must agree with the regenerated backcast tables
    ("studio/README.md",
     re.compile(r"hit rate (\d+) percent, from unrankable"),
     ["vis_lwap_hit"]),
    ("studio/README.md",
     re.compile(r"hit 93 to (\d+) percent"),
     ["vis_mcp_hit"]),
    ("studio/README.md",
     re.compile(r"(\d+) MW MAE against a 375 MW mean flow"),
     ["offer_vismin_mae"]),
    ("studio/README.md",
     re.compile(r"Luzon tracks at (0\.\d+) correlation"),
     ["luz_lwap_corr"]),
    # README coupling/marginal narrative scalars
    ("README.md",
     re.compile(r"evening residual runs \*\*P(\d+\.\d+)/kWh\*\* above the cost stack"),
     ["evening_residual_vis"]),
    ("README.md",
     re.compile(r"coal is on the margin \*\*(\d+)%\*\* of"),
     ["coal_margin_luz"]),
    ("README.md",
     re.compile(r"\*\*(\d+\.\d+)%\*\* of Mindanao"),
     ["mindanao_overnight"]),
    ("README.md",
     re.compile(r"blocked for \*\*(\d+\.\d+)%\*\* of intervals"),
     ["corridor_blocked"]),
    ("README.md",
     re.compile(r"saturates on\s*\n?\s*\*\*(\d+\.\d+)%\*\* of the window"),
     ["corridor_saturated"]),
    ("README.md",
     re.compile(r"runs from a \*\*P(\d+)\*\* scarcity spike"),
     ["duration_max"]),
    # widest-swing DICT-wave deltas (cost + offer) and the offer biases
    ("README.md",
     re.compile(r"raises the Luzon daily mean by \*\*\+P(\d+\.\d+)/kWh\*\* on the cost"),
     ["cost_luz_delta"]),
    ("README.md",
     re.compile(r"\*\*\+P(\d+\.\d+)/kWh\*\* replayed on the market's own bids"),
     ["offer_luz_delta"]),
    ("README.md",
     re.compile(r"reaches the Visayas \(\*\*\+P(\d+\.\d+)\*\*\) and Mindanao \(\*\*\+P(\d+\.\d+)\*\*\)"),
     ["offer_vis_delta", "offer_min_delta"]),
    ("studio/README.md",
     re.compile(r"OVER-prices settlement by P(\d+\.\d+)"),
     ["offer_luz_lwap_bias"]),
    ("studio/README.md",
     re.compile(r"keeps a -P(\d+\.\d+)\s*\n?\s*bias"),
     ["offer_vis_mcp_bias"]),
    ("studio/README.md",
     re.compile(r"wave costs \+P(\d+\.\d+)/kWh on the cost stack"),
     ["cost_luz_delta"]),
    ("studio/README.md",
     re.compile(r"\+P(\d+\.\d+)/kWh on the observed bids, with \+P(\d+\.\d+) reaching the Visayas"),
     ["offer_luz_delta", "offer_vis_delta"]),
    ("studio/README.md",
     re.compile(r"\+P(\d+\.\d+) Mindanao where the cost stack"),
     ["offer_min_delta"]),
    ("studio/README.md",
     re.compile(r"travels with the\s*\n?\s*\+P(\d+\.\d+):"),
     ["offer_luz_delta"]),
    ("studio/README.md",
     re.compile(r"rolling series to P(\d+\.\d+) against P12\.413"),
     ["marquee_rolling"]),
    # the same flag is quoted in the top-level README, so guard it there too:
    # an unguarded copy of a nightly number is how the two drift apart
    ("README.md",
     re.compile(r"rolling series to P(\d+\.\d+) against\s*\n?\s*the P12\.413 trigger"),
     ["marquee_rolling"]),
    # drifted 99.2 -> 99.3 unnoticed because nothing guarded it; both copies now do
    ("README.md",
     re.compile(r"single MW value in (\d+\.\d+) percent of windows"),
     ["pinned_share"]),
    ("web/methodology.html",
     re.compile(r"on (\w+) of the six closest days"),
     ["subhourly_neg_days_word"]),
    ("web/methodology.html",
     re.compile(r"modeled marginal fuel on about (\d+) percent of the\s*\n?\s*raise hours"),
     ["coal_marginal_share"]),
    ("web/methodology.html",
     re.compile(r"floor-priced supply \(([\d,]+) MW\)"),
     ["floor_supply_mw"]),
    ("web/methodology.html",
     re.compile(r"nonzero on ([\d.]+) percent of clean-day node-hours"),
     ["cong_clean_share"]),
    ("web/methodology.html",
     re.compile(r"averages ([\d,.]+) MW on Luzon"),
     ["mot_headroom_luz"]),
    ("web/methodology.html",
     re.compile(r"as low as ([\d.]+) MW"),
     ["mot_headroom_vis_min"]),
    ("web/methodology.html",
     re.compile(r"fleet can move ([\d,]+)\s*\n?\s*MW/h on Luzon"),
     ["ramp_luz_fleet"]),
    ("web/methodology.html",
     re.compile(r"is ([\d,]+) MW\s*\n?\s*on Luzon, 308"),
     ["ramp_luz_worst"]),
    ("web/methodology.html",
     re.compile(r"between (\d+\.\d+)\s*\n?\s*and (\d+\.\d+) times faster"),
     ["ramp_headroom_lo", "ramp_headroom_hi"]),
    # --- loss-surface validation numbers (recompute nightly; F4) ---
    ("README.md",
     re.compile(r"Spearman \*\*\+([\d.]+)\*\* over (\d+) nodes \((\d+)\s+"
                r"independent buses, 95% CI \+([\d.]+) to \+([\d.]+)\)"),
     ["loss_luz_spearman", "loss_luz_nodes", "loss_luz_bus",
      "loss_luz_ci_lo", "loss_luz_ci_hi"]),
    ("README.md",
     re.compile(r"Mindanao at \*\*\+([\d.]+)\*\* over (\d+)\s+\((\d+) buses, "
                r"\+([\d.]+) to \+([\d.]+)\)"),
     ["loss_min_spearman", "loss_min_nodes", "loss_min_bus",
      "loss_min_ci_lo", "loss_min_ci_hi"]),
    ("README.md",
     re.compile(r"stable negative rank\s+correlation \(\*\*(-[\d.]+)\*\*"),
     ["loss_vis_spearman"]),
    # --- published-congestion counts over the static DIPCEF sample (F1 guard) ---
    ("web/methodology.html",
     re.compile(r"nonzero on (\d+) of the (\d+) sampled days"),
     ["cong_days_nonzero", "cong_days_sampled"]),
    ("web/methodology.html",
     re.compile(r"up to\s+(\d+) PhP/kWh on 2026-05-26"),
     ["cong_max"]),
    ("web/methodology.html",
     re.compile(r"the (\d+), (\d+), and (\d+) node counts collapse to "
                r"(\d+), (\d+), and\s+(\d+) independent buses"),
     ["loss_luz_nodes", "loss_vis_nodes", "loss_min_nodes",
      "loss_luz_bus", "loss_vis_bus", "loss_min_bus"]),
]


# Marker-delimited blocks regenerated wholesale from the bake (the reserve
# table's 96 cells). The block body between the two markers is replaced with the
# canonical string on --write and compared on --check.
BLOCKS = [
    ("studio/README.md", "<!-- reserve-table:", "<!-- /reserve-table -->",
     "reserve_table"),
    # the six BackcastView tables, hand-typed and drift-prone before this
    ("studio/README.md", "<!-- bc-lwap:", "<!-- /bc-lwap -->", "bc_lwap"),
    ("studio/README.md", "<!-- bc-mcp:", "<!-- /bc-mcp -->", "bc_mcp"),
    ("studio/README.md", "<!-- bc-flows:", "<!-- /bc-flows -->", "bc_flows"),
    ("studio/README.md", "<!-- bc-offer-target:", "<!-- /bc-offer-target -->",
     "bc_offer_target"),
    ("studio/README.md", "<!-- bc-offer-flows:", "<!-- /bc-offer-flows -->",
     "bc_offer_flows"),
    ("studio/README.md", "<!-- bc-rtdhs:", "<!-- /bc-rtdhs -->", "bc_rtdhs"),
]

# Every public prose file is now bake-derived and auto-synced by the nightly
# cron: the scalar registry above plus the reserve-table block below cover all of
# the rolling numbers in each, so none can silently freeze behind the map.
WRITABLE = {"README.md", "studio/README.md", "web/methodology.html"}


def _check_file(path, text, canon, write):
    problems = []
    fixed = 0
    write = write and path in WRITABLE
    for _f, rx, keys in [e for e in REGISTRY if e[0] == path]:
        m = rx.search(text)
        if not m:
            problems.append(f"[MISS] {path}: anchor not found: {rx.pattern!r}")
            continue
        want = [str(canon[k]) for k in keys]
        got = list(m.groups())
        if got == want:
            continue
        if write:
            new = m.group(0)
            for g, w in zip(got, want):
                if g != w:
                    # digit-boundary (not \b): \b fails when the number is
                    # preceded by a word char, e.g. the P in "-P6.91"
                    new = re.sub(rf"(?<![\d.]){re.escape(g)}(?![\d.])",
                                 w, new, count=1)
            text = text[:m.start()] + new + text[m.end():]
            fixed += 1
        else:
            problems.append(
                f"[DRIFT] {path} {keys}: prose has {got}, bake says {want}")
    for _f, start, end, key in [b for b in BLOCKS if b[0] == path]:
        si, ei = text.find(start), text.find(end)
        if si == -1 or ei == -1:
            problems.append(f"[MISS] {path}: block markers not found ({start!r})")
            continue
        body_start = text.find("\n", si) + 1
        want = canon[key] + "\n"
        got = text[body_start:ei]
        if got == want:
            continue
        if write:
            text = text[:body_start] + want + text[ei:]
            fixed += 1
        else:
            problems.append(
                f"[DRIFT] {path} block {key}: table out of sync with the bake")
    return text, problems, fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite the rolling numbers in each file from the bake")
    args = ap.parse_args()

    canon = canonical()
    files = sorted({e[0] for e in REGISTRY} | {b[0] for b in BLOCKS})
    all_problems = []
    total_fixed = 0
    for rel in files:
        path = os.path.join(ROOT, rel)
        with open(path) as fh:
            original = fh.read()
        text, problems, fixed = _check_file(rel, original, canon, args.write)
        all_problems += problems
        total_fixed += fixed
        if args.write and text != original:
            with open(path, "w") as fh:
                fh.write(text)

    if args.write:
        print(f"verify_claims: rewrote {total_fixed} number(s) across "
              f"{len(files)} file(s) from the bake")
        miss = [p for p in all_problems if p.startswith("[MISS]")]
        if miss:
            print("\n".join(miss))
            sys.exit(1)
        return

    if all_problems:
        print("verify_claims: public prose is out of lockstep with the bake\n")
        print("\n".join(all_problems))
        print("\nfix: run `python3 scripts/verify_claims.py --write` "
              "(and `make viz` for the OG card + montage).")
        sys.exit(1)
    n = len(REGISTRY) + len(BLOCKS)
    print(f"verify_claims: all {n} claims across {len(files)} files match the bake "
          f"(window {canon['window_from']} to {canon['window_to']}, "
          f"{canon['days_covered']} days)")


if __name__ == "__main__":
    main()
