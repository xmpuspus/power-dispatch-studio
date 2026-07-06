#!/usr/bin/env python3
"""Bake the contract-cover / bill-impact layer.

The map's third question is "what does a WESM move do to the Meralco bill?" A naive
reading passes a WESM price move straight through: a P5/kWh spike reads as a P5/kWh
bill increase. That is wrong. WESM prices only the RESIDUAL slice of a distribution
utility's supply; the rest is under bilateral Power Supply Agreements (PSAs) and IPP
contracts whose prices do not move with the spot market. In June 2026 Meralco sourced
just 10% of its energy from WESM (69% PSAs, 21% First Gas / Prime CoreGen), so a WESM
move passes through to the generation charge only in proportion to that 10%.

This bakes the sourced supply mix and bill anchors so the studio can reframe any WESM
move as its actual bill impact (contract-buffered), not the full-spot illusion.

NOT a forecast: the mix and the bill components are the utility's own published
figures for a specific month.

Sources:
  Meralco June 2026 supply mix (WESM 10%, PSA 69%, First Gas/Prime CoreGen 21%):
    https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-june-2026
    https://www.pna.gov.ph/articles/1277062
  June 2026 rate and generation charge (P14.4833 total, P9.0704 generation, WESM
  cost P7.0281 within it):
    https://www.bworldonline.com/top-stories/2026/06/12/756242/meralco-rates-climb-p0-15-kwh-in-june/
"""
from __future__ import annotations

# Meralco June 2026 energy supply mix, share of total energy requirement (%).
# Sourced to the Meralco June 2026 advisory (via PNA); WESM is the spot-exposed slice.
SUPPLY_MIX_PCT = {
    "psa": 69,
    "ipp_first_gas_prime_coregen": 21,
    "wesm": 10,
}
MIX_PERIOD = "2026-06"
SRC_MIX = "https://company.meralco.com.ph/news-and-advisories/higher-residential-rates-june-2026"

# June 2026 bill anchors (BusinessWorld, 12 Jun 2026). All PhP/kWh.
TOTAL_RATE = 14.4833
GENERATION_CHARGE = 9.0704
WESM_COST_IN_GEN = 7.0281
SRC_BILL = "https://www.bworldonline.com/top-stories/2026/06/12/756242/meralco-rates-climb-p0-15-kwh-in-june/"

# Meralco quotes rate impact for a typical residential household at 200 kWh/month.
HOUSEHOLD_KWH_MONTH = 200


def build_bill() -> dict:
    wesm_share = SUPPLY_MIX_PCT["wesm"] / 100.0
    return {
        "available": True,
        "period": MIX_PERIOD,
        "supply_mix_pct": SUPPLY_MIX_PCT,
        "wesm_share_pct": SUPPLY_MIX_PCT["wesm"],
        "src_mix": SRC_MIX,
        "total_rate_php_kwh": TOTAL_RATE,
        "generation_charge_php_kwh": GENERATION_CHARGE,
        "wesm_cost_in_gen_charge_php_kwh": WESM_COST_IN_GEN,
        "src_bill": SRC_BILL,
        "household_kwh_month": HOUSEHOLD_KWH_MONTH,
        # a WESM move of DP PhP/kWh raises the generation charge by wesm_share * DP,
        # not DP; the pass-through factor is baked so the client does not hardcode it.
        "pass_through_factor": round(wesm_share, 3),
        "note": "WESM prices only the residual slice of a utility's supply. In June "
                "2026 Meralco drew 10% of its energy from WESM, 69% from bilateral "
                "PSAs, and 21% from First Gas / Prime CoreGen. A WESM price move "
                "passes through to the generation charge in proportion to that 10% "
                "residual, so the bill is far less exposed to a spot spike than the "
                "headline WESM number suggests. Contract prices do not move with the "
                "spot market. This is the utility's own published mix for one month, "
                "not a forecast; the residual share varies month to month.",
        "gwap_lwap_note": "The WESM figure a bill passes through is a load-weighted "
                          "average price (LWAP): the price actually paid for energy "
                          "drawn, weighted by withdrawal. It differs from a "
                          "generator-weighted average price (GWAP), which weights by "
                          "injection. The two diverge when the cheap and dear hours "
                          "carry different load, so a plant's revenue and a consumer's "
                          "cost are not the same average.",
        "disclaimer": "Statistical indicators derived from public data. Patterns may "
                      "have legitimate explanations.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_bill(), indent=1))
