#!/usr/bin/env python3
"""Check that public text matches the current data files.

The map reads findings.json/answers.json, which build_data.py recomputes every
data build, so the on-screen numbers are always current. The README, share card
caption, and montage use fixed text. The archive window rolls forward every
night, so counts derived from that window can drift out of date.

This check reads the same generated files the
map reads, derives the canonical value for every rolling number the prose
carries, and either checks the prose against them (--check, run by `make qa` and
CI, fails on drift) or rewrites the prose to match (--write, run by `make data`
so the nightly data preparation keeps the README and share image in step with the map).

Numbers that do not move with the window (the 3,629 MW May margin, the 41
percent, the Meralco split, the 87.8 percent outage backcast) are NOT registered
here: they are pinned by tests/test_data.py and change only when their source
does. This file owns exactly the window-derived counts, including the MOT-raise
and line-limitation instruction totals, which grow with the archive every night.
"""

# ruff: noqa: E501

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


_RES_NAMES = {
    "Fr": "contingency (Fr)",
    "Dr": "dispatchable (Dr)",
    "Ru": "regulation up (Ru)",
    "Rd": "regulation down (Rd)",
}


def _reserve_table_md(rv):
    """Regenerate the studio reserve-validation table from the generated pools."""

    def peso(x):
        return f"-P{abs(x):.2f}" if x < 0 else f"P{x:.2f}"

    rows = [
        "| Pool | Hours | Recorded mean | Modeled mean | Bias | Exact hours "
        "| Scarcity hours | MAE outside scarcity |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for grid in ("luzon", "visayas", "mindanao"):
        for cm in ("Fr", "Dr", "Ru", "Rd"):
            p = rv["pools"][grid][cm]
            rows.append(
                f"| {grid.capitalize()} {_RES_NAMES[cm]} | {p['n_hours']:,} | "
                f"P{p['observed_mean_php_kwh']:.2f} | P{p['modeled_mean_php_kwh']:.2f} | "
                f"{peso(p['bias_php_kwh'])} | {p['exact_hours_pct']:.1f}% | "
                f"{p['n_scarcity_hours']} | P{p['mae_nonscarcity_php_kwh']:.2f} |"
            )
    return "\n".join(rows)


# The studio BackcastView renders these tables from profiles.json with
# Intl.NumberFormat (halfExpand rounding). Python's round() is banker's rounding,
# so use Decimal ROUND_HALF_UP to reproduce the app's cells exactly; the README
# then matches what the live studio shows, not just the raw data build fields.
def _q(v, dp):
    return Decimal(str(v)).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)


def _n(v, dp=0):
    return f"{_q(v, dp):,.{dp}f}"


def _p(v, kwh=False):  # peso mean/MAE, README P-convention
    return f"P{_q(v, 2):.2f}" + ("/kWh" if kwh else "")


def _pb(v):  # signed peso bias, +P / -P
    return ("-" if v < 0 else "+") + f"P{_q(abs(v), 2):.2f}"


def _hit(s):
    v = s.get("high_hour_hit_rate_pct")
    return "n/a (flat model)" if v is None else f"{_n(v, 0)}%"


def _mw(v):
    return f"{_n(v, 0)} MW"


def _bc_grid_table(pg, window_pg=None, coverage=False):
    cols = (
        (
            "| Grid | Coverage | Recorded mean | Modeled mean | MAE | Bias | "
            "Correlation | High-hour hit |"
        )
        if coverage
        else (
            "| Grid | Recorded mean | Modeled mean | MAE | Bias | Correlation "
            "| High-hour hit |"
        )
    )
    dash = "| " + " | ".join(["---"] * (8 if coverage else 7)) + " |"
    rows = [cols, dash]
    for g in ("luzon", "visayas", "mindanao"):
        s = pg[g]
        cov = (
            f" {int(s['n_hours']):,} of {int(window_pg[g]['n_hours']):,} h |"
            if coverage
            else ""
        )
        rows.append(
            f"| {g.capitalize()} |{cov} {_p(s['observed_mean_php_kwh'], True)} | "
            f"{_p(s['modeled_mean_php_kwh'], True)} | {_p(s['mae_php_kwh'])} | "
            f"{_pb(s['bias_php_kwh'])} | {_n(s['correlation'], 2)} | {_hit(s)} |"
        )
    return "\n".join(rows)


def _bc_flows_table(flows, header):
    rows = [
        f"| {header} | Recorded mean | Modeled mean | MAE | Direction agreement |",
        "| --- | --- | --- | --- | --- |",
    ]
    for k in ("lv", "vm"):
        f = flows[k]
        rows.append(
            f"| {f['corridor']} | {_mw(f['observed_mean_mw'])} | "
            f"{_mw(f['modeled_mean_mw'])} | {_mw(f['mae_mw'])} | "
            f"{_n(f['direction_agreement_pct'], 0)}% |"
        )
    return "\n".join(rows)


def _bc_offer_target(ob):
    rows = [
        "| Grid | Target | MAE | Bias | Correlation | High-hour hit |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for tgt, key in (("LWAP", "per_grid"), ("MCP", "per_grid_mcp")):
        for g in ("luzon", "visayas", "mindanao"):
            s = ob[key][g]
            rows.append(
                f"| {g.capitalize()} | {tgt} | {_p(s['mae_php_kwh'])} | "
                f"{_pb(s['bias_php_kwh'])} | {_n(s['correlation'], 2)} | "
                f"{_hit(s)} |"
            )
    return "\n".join(rows)


def _bc_offer_html(ob):
    """The same offer-replay scores as HTML rows, for web/for-analysts.html.

    That page answers "how close does it get" for a reader arriving from a
    licensed tool, so its numbers have to roll with the window like the
    README's do rather than freeze on the day someone typed them."""
    rows = []
    for tgt, key in (("LWAP", "per_grid"), ("MCP", "per_grid_mcp")):
        for g in ("luzon", "visayas", "mindanao"):
            s = ob[key][g]
            rows.append(
                f"      <tr><td>{g.capitalize()}</td><td>{tgt}</td>"
                f"<td>{_n(s['correlation'], 2)}</td>"
                f"<td>{_p(s['mae_php_kwh'])}</td>"
                f"<td>{_pb(s['bias_php_kwh'])}</td>"
                f"<td>{_hit(s)}</td></tr>"
            )
    return "\n".join(rows)


def _bc_rtdhs(bc, ob):
    rows = [
        "| Link (vs operator record) | Recorded mean | Modeled mean | MAE "
        "| Direction | Recorded limit share | Modeled at-cap share |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for mode, src in (
        ("cost mode", bc["flows_rtdhs"]),
        ("offer mode", ob["flows_rtdhs"]),
    ):
        for k in ("lv", "vm"):
            f = src[k]
            rows.append(
                f"| {f['corridor']}, {mode} | {_mw(f['observed_mean_mw'])} | "
                f"{_mw(f['modeled_mean_mw'])} | {_mw(f['mae_mw'])} | "
                f"{_n(f['direction_agreement_pct'], 0)}% | "
                f"{_n(f['observed_binding_share_pct'], 0)}% | "
                f"{_n(f['modeled_at_cap_share_pct'], 0)}% |"
            )
    return "\n".join(rows)


def _ci(w, i):
    """CI bound i for a loss-surface grid, falling back to the point estimate if
    the Fisher CI is unavailable (guards a None subscript on a degenerate grid)."""
    ci = w.get("spearman_ci95")
    return ci[i] if ci else w["spearman"]


def canonical():
    """Every rolling count the public prose carries, straight from the data build."""
    cg = _load("congestion.json")
    mo = _load("market_ops.json")
    fnd = {f["id"]: f for f in _load("findings.json")["findings"]}
    # the solved future year (`make future`). It rebuilds on demand rather than
    # nightly, so its numbers still have to stay in lockstep with the prose.
    fy = _load("future_year.json")
    fy_on = bool(fy.get("available"))
    # the named-unit dispatch probe (`python3 pipeline/unit_probe.py --derive`)
    up = _load("unit_probe.json")
    up_on = bool(up.get("generated_by"))
    # the worked contract position (`python3 pipeline/position_probe.py --derive`)
    pp = _load("position_probe.json")
    pp_on = bool(pp.get("generated_by"))

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
        # Daily-mean change from the DICT demand case, read from the saved cases.
        return (
            _cg[wave_lbl]["expect"]["summary"]["mean_price"][g]
            - _cg[base_lbl]["expect"]["summary"]["mean_price"][g]
        )

    _DEMAND_C, _BASE_C = "DICT 1.5 GW flat load on Luzon", "base day, no storage"
    _DEMAND_O, _BASE_O = (
        "DICT 1.5 GW on the observed offer book",
        "observed offer book, unchanged scenario",
    )

    # reserve-shortfall days are generated into the findings blurb; read the number
    # build_data.py already computed rather than recomputing the series here.
    thin = fnd["thin-normal"]["stat"]
    m = re.search(r"below the stated requirement on (\d+) of (\d+)", thin)
    luzon_short, _thin_days = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    # curtailment grid-days and MWh come from the same findings card the map shows
    blurb = fnd["thin-normal"]["blurb"]
    mc = re.search(
        r"curtailed on (\d+) grid-days? in this window \(([\d,]+\.\d+) MWh\)", blurb
    )
    curtail_days, curtail_mwh = (int(mc.group(1)), mc.group(2)) if mc else (0, "0")

    mru = mo["so_instructions"]["mru_contrast"]
    out = {
        "days_covered": cg["days_covered"],
        "distinct_equipment": cg["distinct_equipment"],
        "constraint_records": cg["constraint_records"],
        "mru_grid_hours": _n(mru["mru_grid_hours"], 0),
        "mru_gh_peak_median": _n(mru["mru_gh_peak_median_mw"], 0),
        "mru_median": _n(mru["mru_median_mw"], 1),
        "mru_n_weeks": _n(mru["mru_n_weeks"], 0),
        "motrd_n_weeks": _n(mo["so_instructions"]["motrd"]["n_weeks"], 0),
        "motrd_empty_weeks": _n(mo["so_instructions"]["motrd"]["n_empty_weeks"], 0),
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
            / sodir["n_limitation_remarks"]
            * 100,
            0,
        ),
        "motrd_rows": _n(mo["so_instructions"]["motrd"]["n_rows"], 0),
        "motrd_median": _n(mo["so_instructions"]["motrd"]["median_mw"], 0),
        # methodology.html rounds the count to thousands ("97 thousand")
        "motrd_thousands": _n(
            round(mo["so_instructions"]["motrd"]["n_rows"] / 1000), 0
        ),
        # Repeated outage calculations for the base and DICT demand cases.
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
        "offer_corr_lo": _n(
            min(
                v["correlation"]
                for d in ("per_grid", "per_grid_mcp")
                for v in ob[d].values()
            ),
            2,
        ),
        "offer_corr_hi": _n(
            max(
                v["correlation"]
                for d in ("per_grid", "per_grid_mcp")
                for v in ob[d].values()
            ),
            2,
        ),
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
        # Reliability change from storage under the DICT demand case.
        "buyback_lolp_wo": _n(
            disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["without"][
                "lolp_pct"
            ],
            2,
        ),
        "buyback_lolp_w": _n(
            disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["with_storage"][
                "lolp_pct"
            ],
            2,
        ),
        "buyback_eue_wo": _n(
            disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["without"][
                "eue_mwh_evening_window"
            ],
            0,
        ),
        "buyback_eue_w": _n(
            disp["storage"]["reliability_buyback"]["luzon_dict_2028"]["with_storage"][
                "eue_mwh_evening_window"
            ],
            0,
        ),
        # added Visayas load that binds the Leyte-Luzon corridor (dc_binding_threshold)
        "dc_knee": _n(
            disp["coupling"]["dc_binding_threshold"][
                "added_visayas_load_to_bind_leyte_mw"
            ],
            0,
        ),
        # The coupling decomposition, which the README quoted in four places and
        # nothing guarded. The nightly data preparation moved both: the outage scenario
        # read 87.8 against a data build of 0.879, and the cost-only share read
        # "about 1%" against a data build of 0.005, which is half that.
        "coupling_outage_pct": _n(
            disp["coupling"]["outage_scenario"]["explained_fraction"] * 100, 1
        ),
        "coupling_cost_pct": _n(
            disp["coupling"]["spread_decomposition"]["visayas_vs_luzon"][
                "explained_fraction"
            ]
            * 100,
            1,
        ),
        "vis_luz_spread": _n(
            disp["coupling"]["spread_decomposition"]["visayas_vs_luzon"][
                "observed_php_kwh"
            ],
            2,
        ),
        # the regime split, quoted across a whole README section and guarded
        # nowhere until now: both regime spreads, the three market-window means,
        # and the count of days past P5
        "admin_max_spread": _n(
            _load("prices.json")["regimes"]["administered"]["max_spread"], 3
        ),
        "mkt_max_spread": _n(_load("prices.json")["max_spread"]["php"], 2),
        "mkt_days_gt5": _load("prices.json")["regimes"]["market"]["days_spread_gt5"],
        "mkt_luz": _n(_load("prices.json")["regimes"]["market"]["means"]["luzon"], 2),
        "mkt_vis": _n(_load("prices.json")["regimes"]["market"]["means"]["visayas"], 2),
        "mkt_min": _n(
            _load("prices.json")["regimes"]["market"]["means"]["mindanao"], 2
        ),
        # backcast narrative scalars quoted in studio/README prose next to the tables
        "vis_lwap_hit": _n(bc["per_grid"]["visayas"]["high_hour_hit_rate_pct"], 0),
        "vis_mcp_hit": _n(bc["per_grid_mcp"]["visayas"]["high_hour_hit_rate_pct"], 0),
        "luz_lwap_corr": _n(bc["per_grid"]["luzon"]["correlation"], 2),
        "offer_vismin_mae": _n(ob["flows"]["vm"]["mae_mw"], 0),
        # Visayas evening-peak gap (evening hours, moves with hour grouping)
        "evening_residual_vis": _n(cal["visayas"]["evening_peak_residual_php_kwh"], 2),
        # marginal-block shares + corridor availability + price-duration spike
        "coal_margin_luz": _n(
            next(
                b["share_pct"]
                for b in disp["marginal_frequency"]["luzon"]["by_block"]
                if b["block"].startswith("coal (marginal)")
            ),
            0,
        ),
        "mindanao_overnight": _n(
            next(
                b["share_pct"]
                for b in disp["marginal_frequency"]["mindanao"]["by_block"]
                if "committed" in b["block"]
            ),
            1,
        ),
        "corridor_blocked": _n(
            disp["coupling"]["observed_corridor_caps"]["leyte_luzon_hvdc"][
                "capped_share_pct"
            ],
            1,
        ),
        "corridor_saturated": _n(
            disp["coupling"]["outage_scenario"]["leyte_luzon_saturated_pct"], 1
        ),
        "duration_max": _n(
            max(x["price"] for x in disp["price_duration"]["luzon"]["observed"]), 0
        ),
        # Offer-book biases and the largest DICT demand-case changes.
        "offer_luz_lwap_bias": _n(ob["per_grid"]["luzon"]["bias_php_kwh"], 2),
        "offer_vis_mcp_bias": _n(abs(ob["per_grid_mcp"]["visayas"]["bias_php_kwh"]), 2),
        "cost_luz_delta": _n(_delta(_DEMAND_C, _BASE_C, "luzon"), 2),
        "offer_luz_delta": _n(_delta(_DEMAND_O, _BASE_O, "luzon"), 2),
        "offer_vis_delta": _n(_delta(_DEMAND_O, _BASE_O, "visayas"), 2),
        "offer_min_delta": _n(_delta(_DEMAND_O, _BASE_O, "mindanao"), 2),
        "reference_rolling": _n(
            mo["gwap_trigger"]["reference_case"]["scenario_max_rolling_72h"][
                "rolling_php_kwh"
            ],
            2,
        ),
        "pinned_share": _n(mo["security_limits"]["pinned_share_pct"], 1),
        # The boundaries prose carries market_ops-derived scalars that nothing
        # guarded, and every one of them had drifted before the later source check:
        # "five of the six" days (data build said four), "about 90 percent" coal
        # marginal share (95.2), 9,833 MW floor supply (9,834). Guard them.
        # the ramp measurement: the fleet figures are registration data but
        # the worst observed demand rise grows with the archive, so the
        # ratios move nightly and the prose must move with them
        "ramp_luz_worst": f"{mo['ramp_probe']['worst_observed_demand_rise_mw_per_hour']['luzon']:,.0f}",
        # the adequacy block the prose flags as "the checkable one". Kept on a
        # consistent clock: firm evening capacity vs the evening peak, plus the
        # solar-observed tightest interval. All rolling with the archive.
        "adq_gross_peak": f"{disp['adequacy']['luzon']['gross_peak_mw']:,.0f}",
        "adq_eve_peak": f"{disp['adequacy']['luzon']['evening_peak_demand_mw']:,.0f}",
        "adq_firm_avail": f"{disp['adequacy']['luzon']['avail_at_peak_mw']:,.0f}",
        "adq_margin": _n(disp["adequacy"]["luzon"]["reserve_margin_pct"], 1),
        "adq_dc_margin": _n(
            disp["adequacy"]["dict_2028"]["reserve_margin_with_dc_pct"], 1
        ),
        "adq_tight_dc_margin": _n(
            disp["adequacy"]["dict_2028"]["tight_reserve_margin_with_dc_pct"], 1
        ),
        # the inter-island flow-direction agreement range; drifted 88->87
        # unguarded (the offer replay's per-corridor direction hit rate)
        "flowdir_lo": f"{min(profiles['offer_backcast']['flows'][c]['direction_agreement_pct'] for c in ('lv', 'vm')):.0f}",
        "flowdir_hi": f"{max(profiles['offer_backcast']['flows'][c]['direction_agreement_pct'] for c in ('lv', 'vm')):.0f}",
        "ramp_strict_luz": _n(
            mo["ramp_probe"]["strict_headroom_online_slowest_band"]["luzon"], 1
        ),
        "ramp_strict_vis": _n(
            mo["ramp_probe"]["strict_headroom_online_slowest_band"]["visayas"], 1
        ),
        "ramp_strict_min": _n(
            mo["ramp_probe"]["strict_headroom_online_slowest_band"]["mindanao"], 1
        ),
        # "about one percent of clean-day node-hours" rides on six public
        # surfaces and was hand-written; it is 1.18% and now computed
        "mot_headroom_luz": _n(
            mo["mot_dispatch_cut"]["per_grid"]["luzon"]["headroom_mw"]["mean"], 0
        ),
        # the MOT headroom means + Luzon stack share, and the residual-probe
        # scalars, all rolling with the window and until now hand-typed
        "mot_headroom_vis": _n(
            mo["mot_dispatch_cut"]["per_grid"]["visayas"]["headroom_mw"]["mean"], 0
        ),
        "mot_headroom_min": _n(
            mo["mot_dispatch_cut"]["per_grid"]["mindanao"]["headroom_mw"]["mean"], 0
        ),
        "mot_headroom_share_luz": _n(
            mo["mot_dispatch_cut"]["per_grid"]["luzon"]["headroom_share_pct"], 1
        ),
        "resid_import": _n(
            mo["mot_dispatch_cut"]["luzon_residual_probe"]["import_mw_mean"], 0
        ),
        "resid_gap": _n(
            mo["mot_dispatch_cut"]["luzon_residual_probe"]["gap_mw_mean"], 0
        ),
        "resid_balance": _n(
            mo["mot_dispatch_cut"]["luzon_residual_probe"]["balance_residual_mw_mean"],
            0,
        ),
        # the MOT-raise share of dispatched generation, per-grid range (generated in
        # admin_dispatch.mw_weighted_fraction_of_dispatch), lo to hi across grids
        "raise_share_lo": _n(
            min(
                v["mw_weighted_pct"]
                for v in mo["admin_dispatch"][
                    "mw_weighted_fraction_of_dispatch"
                ].values()
                if isinstance(v, dict) and v.get("mw_weighted_pct") is not None
            ),
            0,
        ),
        "raise_share_hi": _n(
            max(
                v["mw_weighted_pct"]
                for v in mo["admin_dispatch"][
                    "mw_weighted_fraction_of_dispatch"
                ].values()
                if isinstance(v, dict) and v.get("mw_weighted_pct") is not None
            ),
            0,
        ),
        "cong_clean_share": _n(
            _load("nodal_obs.json")["congestion"]["clean_day_nonzero_share_pct"], 2
        ),
        "subhourly_neg_days": mo["subhourly_probe"]["n_days_with_observed_negatives"],
        "subhourly_neg_days_word": (
            "one two three four five six seven eight".split()[
                mo["subhourly_probe"]["n_days_with_observed_negatives"] - 1
            ]
        ),
        "coal_marginal_share": _n(mo["admin_dispatch"]["coal_marginal_share_pct"], 0),
        "floor_supply_mw": f"{mo['subhourly_probe']['deep_negative_structural']['aggregate_floor_supply_mw']:,}",
        "sneg_load": f"{mo['subhourly_probe']['deep_negative_structural']['physical_native_load_mw']:,}",
        # the crossing-days floor-supply-vs-load margin range, which rolls with
        # the window (was hand-typed and drifted from 0.66-2.53 to a stale 0.54-2.3)
        "sneg_range_lo": f"{min(r['floor_supply_vs_load_margin_pct'] for r in mo['subhourly_probe']['crossing_days']):.2f}",
        "sneg_range_hi": f"{max(r['floor_supply_vs_load_margin_pct'] for r in mo['subhourly_probe']['crossing_days']):.2f}",
        "reserve_days": rv["days"],
        "reserve_above_pct": f"{rv['hours_model_above_pct']:.1f}",
        "scored_hours": f"{sum(c['n_hours'] for g in rv['pools'].values() for c in g.values()):,}",
        "reserve_table": _reserve_table_md(rv),
        "bc_lwap": _bc_grid_table(bc["per_grid"]),
        "bc_mcp": _bc_grid_table(bc["per_grid_mcp"], bc["per_grid"], coverage=True),
        "bc_flows": _bc_flows_table(bc["flows"], "Link"),
        "bc_offer_target": _bc_offer_target(ob),
        "bc_offer_html": _bc_offer_html(ob),
        # --- the worked contract position
        "pp_book_mw": str(int(pp["book_mw"])) if pp_on else "",
        "pp_cover": f"{pp['covered_share_pct']:.0f}" if pp_on else "",
        "pp_base_spot": f"{pp['base_mean_spot_php_kwh']:.2f}" if pp_on else "",
        "pp_scen_spot": f"{pp['scenario_mean_spot_php_kwh']:.2f}" if pp_on else "",
        "pp_pos": f"{pp['position_change_php']:,.0f}" if pp_on else "",
        "pp_open": f"{pp['open_cost_change_php']:,.0f}" if pp_on else "",
        "pp_net": f"{pp['net_change_php']:,.0f}" if pp_on else "",
        # --- the named-unit dispatch probe
        "up_units": (
            str(sum(up["n_units_dispatched"].values())) if up_on else ""
        ),
        "up_daily_gap": f"{up['generation_gap']['daily_mwh']:.1f}" if up_on else "",
        "up_hourly_gap": (
            f"{up['generation_gap']['hourly_mw']:,.0f}" if up_on else ""
        ),
        "up_days": str(up["generation_gap_days"]) if up_on else "",
        "up_min_mcp_block": (
            f"{up['delta']['mcp']['mindanao']['block_corr']:.3f}" if up_on else ""
        ),
        "up_min_mcp_unit": (
            f"{up['delta']['mcp']['mindanao']['unit_corr']:.3f}" if up_on else ""
        ),
        "up_price_gap": (
            f"{up['generation_gap']['hourly_price_php_kwh']:.3f}" if up_on else ""
        ),
        # --- the solved future year
        "fy_year": str(fy["year"]) if fy_on else "",
        "fy_days": str(fy["days_solved"]) if fy_on else "",
        "fy_luz_peak": f"{fy['peak_demand_mw']['luzon']:,.0f}" if fy_on else "",
        "fy_luz_growth": (
            f"{(fy['meta']['demand']['ratio_per_grid']['luzon'] - 1) * 100:.1f}"
            if fy_on
            else ""
        ),
        "fy_luz_mean": f"{fy['mean_price_php_kwh']['luzon']:.2f}" if fy_on else "",
        "fy_luz_eve": f"{fy['evening_price_php_kwh']['luzon']:.2f}" if fy_on else "",
        "fy_luz_short": str(fy["days_with_unserved_load"]["luzon"]) if fy_on else "",
        "fy_luz_solar": (
            f"{fy['meta']['supply']['added_solar_mw']['luzon']:,.0f}" if fy_on else ""
        ),
        "fy_luz_firm": (
            f"{sum(fy['meta']['supply']['added_stack_mw']['luzon'].values()):,.0f}"
            if fy_on
            else ""
        ),
        "bc_offer_flows": _bc_flows_table(ob["flows"], "Link (offer mode)"),
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
    # GitHub builds a heading anchor by dropping the decimal point, so
    # "P15.72" in a heading becomes "...-p1572" in the contents link that
    # points at it. Both forms carry the same number and both go stale when
    # the data build moves, so both are guarded. Without the slug form the contents
    # link breaks on the first night the window grows.
    for k in (
        "admin_max_spread",
        "mkt_max_spread",
        "offer_corr_lo",
        "offer_corr_hi",
        "coupling_cost_pct",
        "coupling_outage_pct",
        "loss_luz_spearman",
        "loss_min_spearman",
    ):
        out[f"{k}_slug"] = str(out[k]).replace(".", "").replace("-", "")
    return out


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
    (
        "README.md",
        re.compile(r"day-ahead runs on \*\*(\d+) of the window's (\d+) days\*\*"),
        ["leyte_cebu_dap_days", "days_covered"],
    ),
    (
        "README.md",
        re.compile(r"binding limit in the hourly day-ahead runs on \*\*(\d+) of (\d+)"),
        ["top_corridor_dap_days", "days_covered"],
    ),
    (
        "README.md",
        re.compile(r"the run settlement\s*\n?\s*actually sees, on \*\*(\d+) days\*\*"),
        ["top_corridor_rtd_days"],
    ),
    (
        "README.md",
        re.compile(
            r"Across the (\d+)-day window, \*\*(\d+) distinct pieces of equipment\*\*"
            r" hit a limit at least\s+once, in \*\*(\d+) monitored constraints\*\*"
        ),
        ["days_covered", "distinct_equipment", "constraint_records"],
    ),
    (
        "README.md",
        re.compile(r"below the stated need\s+on (\d+) of the window's (\d+) days\*\*"),
        ["luzon_reserve_short_days", "days_covered"],
    ),
    (
        "README.md",
        re.compile(r"curtailed\s+load on \*\*(\d+) grid-days \(([\d,]+\.\d) MWh\)\*\*"),
        ["curtail_grid_days", "curtail_mwh"],
    ),
    (
        "README.md",
        re.compile(r"Across (\d+)\s+daily logs, its instructions"),
        ["sodir_days"],
    ),
    (
        "README.md",
        re.compile(
            r"citing a line limitation \*\*([\d,]+) times, and ([\d,]+) of those name the"
        ),
        ["limitation_remarks", "leyte_cebu_remarks"],
    ),
    (
        "README.md",
        re.compile(
            r"This link appears in (\d+) percent of\s*\n?\s*every line-limitation"
        ),
        ["limitation_pct"],
    ),
    (
        "README.md",
        re.compile(
            r"\*\*([\d,]+) MOT-raise instructions\*\* across the window at a \*\*(\d+)\s*\n?\s*MW\*\* median"
        ),
        ["motrd_rows", "motrd_median"],
    ),
    # --- the contents list. Its link text AND the #fragment it points at both
    # carry the heading's numbers, so both go stale the night the window grows,
    # and a stale fragment scrolls nowhere. The cron runs --write, so guarding
    # them here is what keeps the contents working without a human in the loop.
    (
        "README.md",
        re.compile(
            r"- \[Luzon reserves fell short on (\d+) of the window's (\d+) days\]"
            r"\(#luzon-reserves-fell-short-on-(\d+)-of-the-windows-(\d+)-days\)"
        ),
        [
            "luzon_reserve_short_days",
            "days_covered",
            "luzon_reserve_short_days",
            "days_covered",
        ],
    ),
    (
        "README.md",
        re.compile(
            r"- \[The three grids priced within P(0\.\d+) while suspended, then "
            r"split to P(\d+\.\d+)\]\(#the-three-grids-priced-within-p(\d+)-while-"
            r"suspended-then-split-to-p(\d+)\)"
        ),
        [
            "admin_max_spread",
            "mkt_max_spread",
            "admin_max_spread_slug",
            "mkt_max_spread_slug",
        ],
    ),
    (
        "README.md",
        re.compile(
            r"- \[Offer-book replay correlations range from "
            r"(0\.\d+) to (0\.\d+)\]\(#offer-book-replay-correlations-range-"
            r"from-(\d+)-to-(\d+)\)"
        ),
        ["offer_corr_lo", "offer_corr_hi", "offer_corr_lo_slug", "offer_corr_hi_slug"],
    ),
    # --- README headings. A number in a heading is the most-read number in the
    # file and drifts like any other, so each one is anchored on its own. The
    # anchors start at "## " so they can never match the body sentence below.
    (
        "README.md",
        re.compile(r"## Luzon reserves fell short on (\d+) of the window's (\d+) days"),
        ["luzon_reserve_short_days", "days_covered"],
    ),
    (
        "README.md",
        re.compile(
            r"## Offer-book replay correlations range from "
            r"(0\.\d+) to (0\.\d+)"
        ),
        ["offer_corr_lo", "offer_corr_hi"],
    ),
    (
        "README.md",
        re.compile(
            r"## The three grids priced within P(0\.\d+) while suspended, "
            r"then split to P(\d+\.\d+)"
        ),
        ["admin_max_spread", "mkt_max_spread"],
    ),
    # --- the regime-split body, which quoted six numbers and guarded none
    (
        "README.md",
        re.compile(r"priced within \*\*P(0\.\d+)/kWh\*\* of each other"),
        ["admin_max_spread"],
    ),
    (
        "README.md",
        re.compile(
            r"the average was \*\*Luzon P(\d+\.\d+), Visayas P(\d+\.\d+), Mindanao\s*\n?\s*"
            r"P(\d+\.\d+) per kWh\*\*, with \*\*(\d+) days spreading beyond P5/kWh\*\* "
            r"and a widest daily spread\s*\n?\s*of \*\*P(\d+\.\d+)/kWh"
        ),
        ["mkt_luz", "mkt_vis", "mkt_min", "mkt_days_gt5", "mkt_max_spread"],
    ),
    (
        "README.md",
        re.compile(
            r"### The base model explains (\d+\.\d)% of the Visayas-Luzon price "
            r"difference\. The recorded outage explains (\d+\.\d)%"
        ),
        ["coupling_cost_pct", "coupling_outage_pct"],
    ),
    # --- the coupling decomposition in the body, quoted in four places and
    # guarded in none until now; both had drifted from nightly data preparation
    (
        "README.md",
        re.compile(
            r"explains only \*\*(\d+\.\d)%\*\* of the recorded "
            r"\*\*P(\d+\.\d+)/kWh\*\*\s+Visayas-Luzon difference"
        ),
        ["coupling_cost_pct", "vis_luz_spread"],
    ),
    (
        "README.md",
        re.compile(r"the coupled model now reproduces \*\*(\d+\.\d)%\*\* of"),
        ["coupling_outage_pct"],
    ),
    (
        "README.md",
        re.compile(r"outage historical replay explains (\d+\.\d)% of the price"),
        ["coupling_outage_pct"],
    ),
    (
        "README.md",
        re.compile(
            r"reproduces \*\*(\d+\.\d) percent\*\* of the recorded\s+"
            r"island price gap"
        ),
        ["coupling_outage_pct"],
    ),
    (
        "studio/README.md",
        re.compile(r"reproduces (\d+\.\d)% of the recorded Visayas-over-Luzon spread"),
        ["coupling_outage_pct"],
    ),
    (
        "studio/README.md",
        re.compile(r"the 275 MW threshold, and the (\d+\.\d+) percent"),
        ["coupling_outage_pct"],
    ),
    # --- studio/README.md scalars (reserve replay + data table)
    (
        "studio/README.md",
        re.compile(r"comparison uses (\d+) days and twelve"),
        ["reserve_days"],
    ),
    (
        "studio/README.md",
        re.compile(r"higher in\s+(\d+\.\d)\s+percent of about ([\d,]+) scored hours"),
        ["reserve_above_pct", "scored_hours"],
    ),
    (
        "studio/README.md",
        re.compile(r"Hourly demand and recorded prices \((\d+) days\)"),
        ["profiles_days"],
    ),
    # the two backcast correlations quoted in the narrative prose (they must
    # agree with the tables above them, which drifted apart before this)
    (
        "studio/README.md",
        re.compile(r"settlement-price series a (0\.\d+) correlation"),
        ["vis_lwap_corr"],
    ),
    (
        "studio/README.md",
        re.compile(r"Correlation dropped from 0\.\d+ to (0\.\d+) and the hit rate"),
        ["vis_mcp_corr"],
    ),
    # README outage calculations for the base and DICT demand cases.
    (
        "README.md",
        re.compile(r"loses load in only \*\*(0\.\d+)%\*\* of tight evenings"),
        ["rel_base_lolp"],
    ),
    (
        "README.md",
        re.compile(r"worst draw sheds\s+\*\*([\d,]+) MW\*\*"),
        ["rel_base_worst"],
    ),
    (
        "README.md",
        re.compile(r"climbs more than tenfold to \*\*(\d\.\d+)%\*\*"),
        ["rel_dict_lolp"],
    ),
    (
        "README.md",
        re.compile(r"1-in-100 draw sheds\s*\n?\s*\*\*([\d,]+) MW\*\*"),
        ["rel_dict_p99"],
    ),
    (
        "README.md",
        re.compile(r"evening-peak window is\s*\n?\s*\*\*([\d,]+) MWh\*\*"),
        ["rel_dict_eue"],
    ),
    # --- README layered-calibration correlations + MAE + means
    (
        "README.md",
        re.compile(
            r"correlation of \*\*(0\.\d+)\*\* with an MAE\s*\n?\s*of \*\*P(\d+\.\d+)\*\*"
        ),
        ["cal_vis_corr", "cal_vis_mae"],
    ),
    (
        "README.md",
        re.compile(r"Luzon is \*\*(0\.\d+)\*\* with an MAE of \*\*P(\d+\.\d+)\*\*"),
        ["cal_luz_corr", "cal_luz_mae"],
    ),
    (
        "README.md",
        re.compile(r"undefined correlation to \*\*(0\.\d+)\*\*\.\s+After the layer"),
        ["cal_min_corr"],
    ),
    (
        "README.md",
        re.compile(
            r"Luzon averages a modeled \*\*P(\d+\.\d+)/kWh\*\* against a "
            r"recorded \*\*P(\d+\.\d+)/kWh\*\*"
        ),
        ["cal_luz_modeled", "cal_luz_observed"],
    ),
    # --- README offer-book backcast Mindanao MCP correlation (two mentions)
    (
        "README.md",
        re.compile(r"Mindanao clearing-price correlation \*\*(0\.\d+)\*\*"),
        ["offer_min_mcp_corr"],
    ),
    (
        "README.md",
        re.compile(r"correlation ranges from \*\*(0\.\d+) to (0\.\d+)\*\*"),
        ["offer_corr_lo", "offer_corr_hi"],
    ),
    (
        "README.md",
        re.compile(
            r"collapsing from\s*\n?\s*\*\*-P(\d+\.\d+)\*\* to \*\*-P(\d+\.\d+)/kWh\*\*"
        ),
        ["cost_vis_bias", "offer_vis_bias"],
    ),
    # --- studio/README.md carries the same bias + Mindanao-correlation prose
    (
        "studio/README.md",
        re.compile(r"settlement bias falls from -P(\d+\.\d+) to -P(\d+\.\d+)"),
        ["cost_vis_bias", "offer_vis_bias"],
    ),
    (
        "studio/README.md",
        re.compile(r"clearing-price\s*\n?\s*correlation reaches (0\.\d+)"),
        ["offer_min_mcp_corr"],
    ),
    # storage buyback (README) + the corridor knee (README + studio)
    (
        "README.md",
        re.compile(
            r"loss-of-load probability with the added demand falls from "
            r"\*\*(\d+\.\d+)%\*\* to \*\*(\d+\.\d+)%\*\*"
        ),
        ["buyback_lolp_wo", "buyback_lolp_w"],
    ),
    (
        "README.md",
        re.compile(r"unserved energy from \*\*([\d,]+) MWh\*\* to \*\*(\d+) MWh\*\*"),
        ["buyback_eue_wo", "buyback_eue_w"],
    ),
    (
        "README.md",
        re.compile(r"just \*\*(\d+) MW\*\* of added Visayas load fills the"),
        ["dc_knee"],
    ),
    ("studio/README.md", re.compile(r"puts the threshold at (\d+) MW"), ["dc_knee"]),
    ("studio/README.md", re.compile(r"the (\d+) MW threshold, and the"), ["dc_knee"]),
    # studio narrative scalars that must agree with the regenerated backcast tables
    (
        "studio/README.md",
        re.compile(r"(\d+) percent high-hour hit rate"),
        ["vis_lwap_hit"],
    ),
    (
        "studio/README.md",
        re.compile(r"hit rate from 93 to (\d+) percent"),
        ["vis_mcp_hit"],
    ),
    (
        "studio/README.md",
        re.compile(r"(\d+) MW mean absolute error against a 375 MW mean"),
        ["offer_vismin_mae"],
    ),
    (
        "studio/README.md",
        re.compile(r"Luzon reaches (0\.\d+) correlation"),
        ["luz_lwap_corr"],
    ),
    # README coupling/marginal narrative scalars
    (
        "README.md",
        re.compile(r"evening gap runs \*\*P(\d+\.\d+)/kWh\*\* above the cost stack"),
        ["evening_residual_vis"],
    ),
    (
        "README.md",
        re.compile(r"coal is on the margin \*\*(\d+)%\*\* of"),
        ["coal_margin_luz"],
    ),
    (
        "README.md",
        re.compile(r"\*\*(\d+\.\d+)%\*\* of Mindanao"),
        ["mindanao_overnight"],
    ),
    (
        "README.md",
        re.compile(
            r"blocked the Leyte-Luzon link for \*\*(\d+\.\d+)%\*\* of market-window"
        ),
        ["corridor_blocked"],
    ),
    (
        "README.md",
        re.compile(r"link saturates in \*\*(\d+\.\d+)%\*\* of intervals"),
        ["corridor_saturated"],
    ),
    (
        "README.md",
        re.compile(r"runs from a \*\*P(\d+)\*\* scarcity spike"),
        ["duration_max"],
    ),
    # Largest DICT demand-case changes and offer biases.
    (
        "README.md",
        re.compile(
            r"raises the Luzon daily mean by \*\*\+P(\d+\.\d+)/kWh\*\* on the cost"
        ),
        ["cost_luz_delta"],
    ),
    (
        "README.md",
        re.compile(r"\*\*\+P(\d+\.\d+)/kWh\*\* replayed on the market's own bids"),
        ["offer_luz_delta"],
    ),
    (
        "README.md",
        re.compile(
            r"reaches the Visayas \(\*\*\+P(\d+\.\d+)\*\*\) and Mindanao \(\*\*\+P(\d+\.\d+)\*\*\)"
        ),
        ["offer_vis_delta", "offer_min_delta"],
    ),
    (
        "studio/README.md",
        re.compile(r"overprices\s+settlement by P(\d+\.\d+)"),
        ["offer_luz_lwap_bias"],
    ),
    (
        "studio/README.md",
        re.compile(r"keeps a -P(\d+\.\d+)\s*\n?\s*bias"),
        ["offer_vis_mcp_bias"],
    ),
    (
        "studio/README.md",
        re.compile(r"cost calculation adds P(\d+\.\d+)/kWh"),
        ["cost_luz_delta"],
    ),
    (
        "studio/README.md",
        re.compile(
            r"recorded\s+offers add P(\d+\.\d+)/kWh\. The increase reaches P(\d+\.\d+) in the Visayas"
        ),
        ["offer_luz_delta", "offer_vis_delta"],
    ),
    (
        "studio/README.md",
        re.compile(r"and P(\d+\.\d+) in\s+Mindanao, where the cost calculation"),
        ["offer_min_delta"],
    ),
    (
        "studio/README.md",
        re.compile(r"raises the series to P(\d+\.\d+)/kWh, below"),
        ["reference_rolling"],
    ),
    # the same flag is quoted in the top-level README, so guard it there too:
    # an unguarded copy of a nightly number is how the two drift apart
    (
        "README.md",
        re.compile(r"rolling series to P(\d+\.\d+)\s+against the P12\.413 trigger"),
        ["reference_rolling"],
    ),
    # drifted 99.2 -> 99.3 unnoticed because nothing guarded it; both copies now do
    (
        "README.md",
        re.compile(r"one MW value in\s+(\d+\.\d+) percent of windows"),
        ["pinned_share"],
    ),
    (
        "README.md",
        re.compile(r"nonzero on ([\d.]+) percent of clean-day node-hours"),
        ["cong_clean_share"],
    ),
    (
        "README.md",
        re.compile(r"recorded direction \*\*(\d+) to (\d+) percent\*\* of the time"),
        ["flowdir_lo", "flowdir_hi"],
    ),
    (
        "README.md",
        re.compile(
            r"gross\s+peak\s+of\s+\*\*([\d,]+)\s+MW\*\*\s+is\s+a\s+mid-afternoon"
        ),
        ["adq_gross_peak"],
    ),
    (
        "README.md",
        re.compile(
            r"firm\s+evening\s+peak,\s+when\s+solar\s+is\s+gone,\s+is\s+\*\*([\d,]+)\s+MW\*\*"
        ),
        ["adq_eve_peak"],
    ),
    (
        "README.md",
        re.compile(
            r"stack\s+of\s+\*\*([\d,]+)\s+MW\*\*\s+that\s+is\s+an\s+\*\*([\d.]+)%\*\*\s+reserve"
        ),
        ["adq_firm_avail", "adq_margin"],
    ),
    (
        "README.md",
        re.compile(r"the\s+firm\s+margin\s+falls\s+to\s+\*\*([\d.]+)%\*\*"),
        ["adq_dc_margin"],
    ),
    (
        "README.md",
        re.compile(r"still\s+holds\s+\*\*([\d.]+)%\*\*\s+with\s+the\s+DICT\s+forecast"),
        ["adq_tight_dc_margin"],
    ),
    # --- loss-surface validation numbers (recompute nightly; F4) ---
    (
        "README.md",
        re.compile(
            r"Spearman \*\*\+([\d.]+)\*\* over (\d+) nodes \((\d+)\s+"
            r"distinct buses, 95% confidence interval \+([\d.]+) to \+([\d.]+)\)"
        ),
        [
            "loss_luz_spearman",
            "loss_luz_nodes",
            "loss_luz_bus",
            "loss_luz_ci_lo",
            "loss_luz_ci_hi",
        ],
    ),
    (
        "README.md",
        re.compile(
            r"Mindanao at \*\*\+([\d.]+)\*\* over (\d+)\s+\((\d+) buses, "
            r"\+([\d.]+) to \+([\d.]+)\)"
        ),
        [
            "loss_min_spearman",
            "loss_min_nodes",
            "loss_min_bus",
            "loss_min_ci_lo",
            "loss_min_ci_hi",
        ],
    ),
    (
        "README.md",
        re.compile(r"stable negative rank\s+correlation \(\*\*(-[\d.]+)\*\*"),
        ["loss_vis_spearman"],
    ),
    # --- the worked contract position
    (
        "README.md",
        re.compile(r"gains a (\d+) MW contract book more than it costs"),
        ["pp_book_mw"],
    ),
    (
        "README.md",
        re.compile(r"which leaves the book \*\*(\d+) percent\*\*"),
        ["pp_cover"],
    ),
    (
        "README.md",
        re.compile(r"spot rises from\s*\n?\s*P([\d.]+)/kWh to P([\d.]+)/kWh"),
        ["pp_base_spot", "pp_scen_spot"],
    ),
    (
        "README.md",
        re.compile(r"\| The contracts gain \| \*\*\+P([\d,]+)\*\* \|"),
        ["pp_pos"],
    ),
    (
        "README.md",
        re.compile(r"\| The uncontracted load costs more \| \*\*\+P([\d,]+)\*\* \|"),
        ["pp_open"],
    ),
    (
        "README.md",
        re.compile(r"\| Net \| \*\*\+P([\d,]+)\*\* \|"),
        ["pp_net"],
    ),
    # --- the named-unit dispatch probe
    (
        "README.md",
        re.compile(r"## Naming all (\d+) units changes no daily energy"),
        ["up_units"],
    ),
    (
        "README.md",
        re.compile(r"own variable, \*\*(\d+) units\*\* across the"),
        ["up_units"],
    ),
    (
        "README.md",
        re.compile(r"fuel on every grid, to \*\*([\d.]+) MWh\*\*"),
        ["up_daily_gap"],
    ),
    (
        "README.md",
        re.compile(r"price differs by more than\s*\n?\s*\*\*P([\d.]+)/kWh\*\*"),
        ["up_price_gap"],
    ),
    (
        "README.md",
        re.compile(r"move, by up to\s*\n?\s*\*\*([\d,]+) MW\*\*"),
        ["up_hourly_gap"],
    ),
    (
        "README.md",
        re.compile(
            r"Mindanao market clearing price correlation goes from\s*\n?\s*"
            r"([\d.]+) to ([\d.]+)\."
        ),
        ["up_min_mcp_block", "up_min_mcp_unit"],
    ),
    (
        "web/methodology.html",
        re.compile(
            r"Mindanao market clearing price correlation goes\s*\n?\s*from "
            r"([\d.]+) to ([\d.]+),"
        ),
        ["up_min_mcp_block", "up_min_mcp_unit"],
    ),
    # --- the solved future year (`make future`)
    (
        "README.md",
        re.compile(r"\| Peak demand \| \*\*([\d,]+) MW\*\*"),
        ["fy_luz_peak"],
    ),
    (
        "README.md",
        re.compile(r"grown \*\*([\d.]+) percent\*\* by the DOE path"),
        ["fy_luz_growth"],
    ),
    (
        "README.md",
        re.compile(r"\| Dispatchable capacity added \| \*\*([\d,]+) MW\*\*"),
        ["fy_luz_firm"],
    ),
    (
        "README.md",
        re.compile(r"\| Solar added \| \*\*([\d,]+) MW\*\*"),
        ["fy_luz_solar"],
    ),
    (
        "README.md",
        re.compile(r"\| Mean price across the year \| \*\*P([\d.]+)/kWh\*\*"),
        ["fy_luz_mean"],
    ),
    (
        "README.md",
        re.compile(r"\| Mean price 6pm to 9pm \| \*\*P([\d.]+)/kWh\*\*"),
        ["fy_luz_eve"],
    ),
    (
        "README.md",
        re.compile(r"\| Days that leave load unserved \| \*\*(\d+) of (\d+)\*\*"),
        ["fy_luz_short", "fy_days"],
    ),
]


# Marker-delimited blocks regenerated wholesale from the data build (the reserve
# table's 96 cells). The block body between the two markers is replaced with the
# canonical string on --write and compared on --check.
BLOCKS = [
    (
        "studio/README.md",
        "<!-- reserve-table.",
        "<!-- /reserve-table -->",
        "reserve_table",
    ),
    # the six BackcastView tables, hand-typed and drift-prone before this
    ("studio/README.md", "<!-- bc-lwap.", "<!-- /bc-lwap -->", "bc_lwap"),
    ("studio/README.md", "<!-- bc-mcp.", "<!-- /bc-mcp -->", "bc_mcp"),
    ("studio/README.md", "<!-- bc-flows.", "<!-- /bc-flows -->", "bc_flows"),
    (
        "studio/README.md",
        "<!-- bc-offer-target.",
        "<!-- /bc-offer-target -->",
        "bc_offer_target",
    ),
    (
        "studio/README.md",
        "<!-- bc-offer-flows.",
        "<!-- /bc-offer-flows -->",
        "bc_offer_flows",
    ),
    ("studio/README.md", "<!-- bc-rtdhs.", "<!-- /bc-rtdhs -->", "bc_rtdhs"),
    # the arriving analyst's "how close does it get" table
    (
        "web/for-analysts.html",
        "<!-- bc-offer-html.",
        "<!-- /bc-offer-html -->",
        "bc_offer_html",
    ),
]

# Every public prose file now uses generated data and is updated by the nightly
# cron: the scalar registry above plus the reserve-table block below cover all of
# the rolling numbers in each, so none can silently freeze behind the map.
WRITABLE = {
    "README.md",
    "studio/README.md",
    "web/for-analysts.html",
    "web/methodology.html",
}


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
                    # preceded by a word char, e.g. the P in "-P6.91".
                    # The trailing guard must let a full stop through: a
                    # registered number that ENDS a sentence is followed by
                    # ".", and blocking on any "." made --write report a
                    # rewrite it never performed. Only a digit, or a period
                    # with a digit behind it, means the number continues.
                    new = re.sub(
                        rf"(?<![\d.]){re.escape(g)}(?!\d|\.\d)", w, new, count=1
                    )
            text = text[: m.start()] + new + text[m.end() :]
            fixed += 1
        else:
            problems.append(
                f"[DRIFT] {path} {keys}: prose has {got}, data build says {want}"
            )
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
                f"[DRIFT] {path} block {key}: table out of sync with the data build"
            )
    return text, problems, fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--write",
        action="store_true",
        help="rewrite the rolling numbers in each file from the data build",
    )
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
        print(
            f"verify_claims: rewrote {total_fixed} number(s) across "
            f"{len(files)} file(s) from the data build"
        )
        miss = [p for p in all_problems if p.startswith("[MISS]")]
        if miss:
            print("\n".join(miss))
            sys.exit(1)
        return

    if all_problems:
        print("verify_claims: public prose is out of lockstep with the data build\n")
        print("\n".join(all_problems))
        print(
            "\nfix: run `python3 scripts/verify_claims.py --write` "
            "(and `make viz` for the OG card + montage)."
        )
        sys.exit(1)
    n = len(REGISTRY) + len(BLOCKS)
    print(
        f"verify_claims: all {n} claims across {len(files)} files match the data build "
        f"(window {canon['window_from']} to {canon['window_to']}, "
        f"{canon['days_covered']} days)"
    )


if __name__ == "__main__":
    main()
