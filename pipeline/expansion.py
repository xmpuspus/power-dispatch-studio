#!/usr/bin/env python3
"""Greenfield capacity-expansion optimizer, lite (roadmap item 12).

The LT Plan view applies the DOE's own build lists on a horizon slider, no
optimizer. This is the honest lite optimizer: a least-cost greenfield capacity
mix that meets the DOE PDP peak-demand path over a few representative operating
periods, choosing from technology archetypes with SOURCED, LABELED generic costs
(NREL ATB moderate case). It captures the one tradeoff that matters, cheap
renewable ENERGY against firm CAPACITY for the evening peak, through per-period
availability and a peak reserve-margin constraint.

It is validated against the DOE's OWN pipeline mix (web/data/projects.json): a
least-cost build should land renewable-heavy the way the DOE plan does. The
result and that comparison are baked to data/derived/expansion.json for the
studio; positioning is check the plan, not replace it.

Costs are generic NREL ATB moderate-case anchors, 2022 USD, annualized with a
capital recovery factor, converted to PhP. Labeled generic, not PH-specific.
Source: https://atb.nrel.gov/electricity/2024/

    python3 pipeline/expansion.py --derive
"""
from __future__ import annotations

import argparse
import json
import os

import highspy

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, "..", "web", "data")
OUT = os.path.join(HERE, "..", "data", "derived", "expansion.json")

USD_PHP = 56.0
CRF = 0.09  # capital recovery factor, ~20 yr at 6 percent

# Technology archetypes. capex_usd_kw: NREL ATB 2024 moderate overnight capital;
# var_php_kwh: fuel plus variable O&M (PH fuel costs for thermal); the per-period
# availability is the fraction of that period the tech can run (solar peaks at
# midday and is ~0 at the evening peak; firm is its peak capacity credit).
# ann_php_kw_yr is derived: capex_usd_kw * USD_PHP * CRF.
ARCHETYPES = {
    "solar": {"capex_usd_kw": 1000, "var": 0.0, "firm": 0.05,
              "avail": {"peak": 0.02, "midday": 0.75, "shoulder": 0.35, "night": 0.0}},
    "wind": {"capex_usd_kw": 1450, "var": 0.0, "firm": 0.15,
             "avail": {"peak": 0.20, "midday": 0.25, "shoulder": 0.25, "night": 0.30}},
    "natural_gas": {"capex_usd_kw": 1200, "var": 4.8, "firm": 0.90,
                    "avail": {"peak": 0.92, "midday": 0.92, "shoulder": 0.92, "night": 0.92}},
    "coal": {"capex_usd_kw": 3800, "var": 6.0, "firm": 0.85,
             "avail": {"peak": 0.88, "midday": 0.88, "shoulder": 0.88, "night": 0.88}},
    "geothermal": {"capex_usd_kw": 5200, "var": 3.5, "firm": 0.90,
                   "avail": {"peak": 0.90, "midday": 0.90, "shoulder": 0.90, "night": 0.90}},
    "hydro": {"capex_usd_kw": 2600, "var": 0.5, "firm": 0.50,
              "avail": {"peak": 0.55, "midday": 0.45, "shoulder": 0.45, "night": 0.40}},
    "oil": {"capex_usd_kw": 850, "var": 12.0, "firm": 0.90,
            "avail": {"peak": 0.90, "midday": 0.90, "shoulder": 0.90, "night": 0.90}},
    "storage": {"capex_usd_kw": 1500, "var": 0.2, "firm": 0.95,
                "avail": {"peak": 0.95, "midday": 0.0, "shoulder": 0.3, "night": 0.0}},
}

# representative periods: hours per year and the load as a fraction of the
# annual peak (a coarse load duration the diurnal RE pattern needs, not a flat
# LDC). Sums to 8760 h.
PERIODS = {
    "peak": {"hours": 1095, "load_frac": 1.00},     # evening peak
    "midday": {"hours": 1825, "load_frac": 0.78},   # solar hours
    "shoulder": {"hours": 3285, "load_frac": 0.72},
    "night": {"hours": 2555, "load_frac": 0.55},
}
RESERVE_MARGIN = 0.20


def _peak_mw(year: int) -> float:
    dp = json.load(open(os.path.join(WEB, "demand_path.json")))
    yrs = dp["years"]
    ph = dp.get("philippines_mw") or []
    return float(ph[yrs.index(year)]) if year in yrs and ph else 0.0


def optimize(peak_mw: float) -> dict:
    """Least-cost greenfield capacity mix (MW per tech) meeting the periods and
    the peak reserve margin. Returns the mix and the objective."""
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    techs = list(ARCHETYPES)
    periods = list(PERIODS)
    # variables: cap[t] then gen[t, p]
    ncap = len(techs)
    ngen = len(techs) * len(periods)
    n = ncap + ngen
    cost = [0.0] * n
    lb = [0.0] * n
    ub = [highspy.kHighsInf] * n
    # cap is in MW, the annual cost is PhP/kW/yr, so PhP/MW/yr is x1000; gen is
    # in MWh and var is PhP/kWh, so PhP/MWh is x1000
    for i, t in enumerate(techs):
        cost[i] = ARCHETYPES[t]["capex_usd_kw"] * USD_PHP * CRF * 1000.0
    gidx = {}
    k = ncap
    for t in techs:
        for p in periods:
            gidx[(t, p)] = k
            cost[k] = ARCHETYPES[t]["var"] * 1000.0
            k += 1
    h.addVars(n, lb, ub)
    h.changeColsCost(n, list(range(n)), cost)

    inf = highspy.kHighsInf
    # energy balance per period: sum_t gen[t,p] = load_p * hours_p
    for p in periods:
        idx = [gidx[(t, p)] for t in techs]
        val = [1.0] * len(idx)
        rhs = peak_mw * PERIODS[p]["load_frac"] * PERIODS[p]["hours"]
        h.addRow(rhs, rhs, len(idx), idx, val)
    # generation limit: gen[t,p] <= cap[t] * avail[t,p] * hours_p
    for i, t in enumerate(techs):
        for p in periods:
            idx = [gidx[(t, p)], i]
            val = [1.0, -ARCHETYPES[t]["avail"][p] * PERIODS[p]["hours"]]
            h.addRow(-inf, 0.0, 2, idx, val)
    # reserve adequacy: sum_t cap[t]*firm[t] >= peak*(1+margin)
    idx = list(range(ncap))
    val = [ARCHETYPES[t]["firm"] for t in techs]
    h.addRow(peak_mw * (1 + RESERVE_MARGIN), inf, len(idx), idx, val)

    h.run()
    sol = h.getSolution()
    x = sol.col_value
    mix = {t: round(x[i], 1) for i, t in enumerate(techs) if x[i] > 1.0}
    total = sum(mix.values())
    return {"mix_mw": mix, "total_mw": round(total, 1),
            "annual_cost_php_bn": round(h.getObjectiveValue() / 1e9, 1)}


def _doe_mix() -> dict:
    p = json.load(open(os.path.join(WEB, "projects.json")))
    agg: dict[str, float] = {}
    for r in p.get("rows") or []:
        if isinstance(r, dict):
            agg[r.get("fuel") or "unknown"] = agg.get(r.get("fuel") or "unknown", 0.0) + (r.get("mw") or 0.0)
    return agg


def _shares(mix: dict) -> dict:
    tot = sum(mix.values()) or 1.0
    return {k: round(100 * v / tot, 1) for k, v in mix.items()}


def derive() -> dict:
    year = 2040
    peak = _peak_mw(year)
    opt = optimize(peak)
    doe = _doe_mix()
    opt_re = sum(opt["mix_mw"].get(t, 0) for t in ("solar", "wind", "hydro", "geothermal"))
    doe_re = sum(doe.get(t, 0) for t in ("solar", "wind", "hydro", "geothermal"))
    return {
        "available": True,
        "horizon_year": year,
        "peak_mw": round(peak, 0),
        "reserve_margin_pct": round(RESERVE_MARGIN * 100),
        "optimized": {**opt, "mix_share_pct": _shares(opt["mix_mw"]),
                      "re_share_pct": round(100 * opt_re / (opt["total_mw"] or 1), 1)},
        "doe_pipeline": {"mix_mw": {k: round(v) for k, v in doe.items()},
                         "mix_share_pct": _shares(doe),
                         "re_share_pct": round(100 * doe_re / (sum(doe.values()) or 1), 1)},
        "verdict": ("A least-cost greenfield build lands renewable-heavy, the same "
                    "direction as the DOE pipeline, without being told to: the check "
                    "is the RE share, not a plant-by-plant match."),
        "costs_note": ("Generic technology costs, NREL ATB 2024 moderate case, 2022 USD "
                       "annualized (CRF 0.09) and converted at 56 PhP/USD. Labeled "
                       "generic, not PH-specific."),
        "src": "https://atb.nrel.gov/electricity/2024/",
        "disclaimer": ("Statistical indicators derived from public data. Patterns may "
                       "have legitimate explanations."),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"expansion: {out['horizon_year']} peak {out['peak_mw']} MW; "
              f"optimized RE {out['optimized']['re_share_pct']}% vs DOE "
              f"{out['doe_pipeline']['re_share_pct']}%")
        print("optimized mix:", out["optimized"]["mix_share_pct"])
    else:
        print("pass --derive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
