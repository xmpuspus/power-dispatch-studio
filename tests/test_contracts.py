#!/usr/bin/env python3
"""Settling a contract book is arithmetic, so every sign and unit gets pinned.

The dispatch model answers half of "what does this scenario do to my position".
The other half is a book the caller brings, and the failure modes are all
arithmetic: a sign that runs the wrong way, a MW read as a MWh, an hour list
that silently covers the whole day.

The cases below check each of those against numbers worked by hand, then run one
real scenario end to end: two Sual units out, a two-contract book, a 400 MW load.

Plain python + highspy, no pytest dependency. Run: python3 tests/test_contracts.py
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

import power_dispatch as pdx  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def flat(price: float, hours: int = 24) -> dict:
    """A solved day at one price on every grid, so the arithmetic is visible."""
    return {
        "summary": {"date": "2030-01-01"},
        "hours": [
            {"hour": h, "price": {g: price for g in ("luzon", "visayas", "mindanao")}}
            for h in range(hours)
        ],
    }


# --- units and signs ---------------------------------------------------------
book = [{"grid": "luzon", "mw": 100, "strike_php_kwh": 5.0, "side": "buy"}]

# 100 MW for 24 h at P1.00/kWh above strike: 100 * 1000 kWh/h * 24 h * P1.00
s = pdx.settle(flat(6.0), book)
check(
    "one peso above strike on 100 MW for a day is P2.4M", s["position_php"] == 2_400_000
)
check("the mwh column counts MW times hours", s["contracts"][0]["mwh"] == 2400)
check(
    "the mean spot reads back",
    math.isclose(s["contracts"][0]["mean_spot_php_kwh"], 6.0),
)

s = pdx.settle(flat(4.0), book)
check(
    "one peso below strike is the same size, the other way",
    s["position_php"] == -2_400_000,
)

sell = [{"grid": "luzon", "mw": 100, "strike_php_kwh": 5.0, "side": "sell"}]
check(
    "a sell contract runs opposite a buy at the same price",
    pdx.settle(flat(6.0), sell)["position_php"] == -2_400_000,
)

# --- hour coverage -----------------------------------------------------------
peak = [{"grid": "luzon", "mw": 100, "strike_php_kwh": 5.0, "hours": [18, 19, 20, 21]}]
s = pdx.settle(flat(6.0), peak)
check("a four-hour block settles four hours", s["contracts"][0]["hours_covered"] == 4)
check("a four-hour block is one sixth of a day", s["position_php"] == 400_000)

# --- the open position -------------------------------------------------------
s = pdx.settle(flat(6.0), book, load_mw={"luzon": 400})
check("300 MW of 400 stays open", s["open"][0]["open_mwh"] == 300 * 24)
check("cover reads as a share", math.isclose(s["open"][0]["covered_share_pct"], 25.0))
check("the open position costs spot", s["open_cost_php"] == 300 * 1000 * 24 * 6.0)
check(
    "a sell contract never covers a load",
    pdx.settle(flat(6.0), sell, load_mw={"luzon": 100})["open"][0]["open_mwh"] == 2400,
)

# --- a book that cannot settle says why --------------------------------------
bad = [
    {"grid": "lozon", "mw": 100, "strike_php_kwh": 5.0},
    {"grid": "luzon", "mw": -50, "strike_php_kwh": 5.0},
    {"grid": "luzon", "mw": 100, "strike_php_kwh": "six"},
    {"grid": "luzon", "mw": 100, "strike_php_kwh": 5.0, "side": "hedge"},
    {"grid": "luzon", "mw": 100, "strike_php_kwh": 5.0, "hours": [25]},
]
msgs = pdx.validate_book(bad)
joined = " | ".join(msgs)
check("a misspelled grid is named", "contract[0].grid" in joined)
check("a negative volume points at side", "side to pick direction" in joined)
check("a text strike is caught", "contract[2].strike_php_kwh" in joined)
check("an unknown side is caught", "buy or sell" in joined)
check("an hour past 23 is caught", "0 to 23" in joined)
check("settle refuses a broken book", True)
try:
    pdx.settle(flat(6.0), bad)
    check("settle raised on a broken book", False)
except ValueError as exc:
    check("settle raised on a broken book", "contract[0].grid" in str(exc))

# --- one real scenario, end to end -------------------------------------------
day = pdx.list_days()[-1]
real_book = [
    {"name": "PSA with the DU", "grid": "luzon", "mw": 250, "strike_php_kwh": 6.4},
    {
        "name": "Evening peak block",
        "grid": "luzon",
        "mw": 100,
        "strike_php_kwh": 9.0,
        "hours": [18, 19, 20, 21],
    },
]
base = pdx.run_scenario({"date": day, "opts": {}})
# both 647 MW Sual units out
trip = pdx.run_scenario(
    {"date": day, "opts": {"fuel_avail_delta": {"luzon": {"coal": -1294}}}}
)
cmp = pdx.compare_position(base, trip, real_book, load_mw={"luzon": 400})

check("the comparison names both contracts", len(cmp["contracts"]) == 2)
check(
    "the trip raises the mean Luzon spot",
    cmp["contracts"][0]["scenario_mean_spot"] > cmp["contracts"][0]["base_mean_spot"],
)
check(
    "a buy contract gains when spot rises",
    cmp["contracts"][0]["change_php"] > 0,
)
check(
    "the open position costs more when spot rises",
    cmp["open_cost_change_php"] > 0,
)
check(
    "the net change is the contract gain less the open cost",
    abs(
        cmp["net_change_php"]
        - (cmp["position_change_php"] - cmp["open_cost_change_php"])
    )
    < 0.01,
)
check("the settlement states what it leaves out", "no tax" in cmp["note"])
check(
    "a scenario with no price move leaves the position where it was",
    pdx.compare_position(base, base, real_book)["position_change_php"] == 0,
)

# --- the browser has to reach the same pesos ---------------------------------
# Both suites settle the SAME golden price series, the one chrono_golden pins for
# "both Sual units out all day", with the same book. So a settlement that drifts
# on one side fails on that side, and the two cannot quietly disagree.
import json  # noqa: E402

profiles = json.load(open(os.path.join(ROOT, "web", "data", "profiles.json")))
golden = next(
    c
    for c in profiles["chrono_golden"]["cases"]
    if c["label"] == "both Sual units out all day"
)
gold_hours = {
    "summary": {"date": golden["input"]["date"]},
    "hours": [
        {
            "hour": h,
            "price": {
                g: golden["expect"]["price"][g][h]
                for g in ("luzon", "visayas", "mindanao")
            },
        }
        for h in range(24)
    ],
}
gold = pdx.settle(gold_hours, real_book, {"luzon": 400})

# These two used to be hand-written pesos, 600,500 and 19,800,300. The golden
# case takes its hydro budget from the rolling archive window, so a fixed
# historical day re-solves every night: on 2026-08-10 the window grew from 77
# days to 83, hydro set the Luzon price in 6 hours where coal had, and the mean
# went from P6.50 to P8.753. The pinned pesos moved 25x and main went red.
#
# So derive the expectation from the same prices instead, by hand, the long way.
# Recording settle()'s own output and comparing would prove nothing, because
# settle() has one implementation and both sides would be it. This arithmetic
# is independent of it: one MW held for one hour is one MWh, and a price in
# PhP/kWh is a thousand pesos per MWh.
MWH_PESOS = 1000.0
OWN_LOAD_MW = 400.0
luz = golden["expect"]["price"]["luzon"]
want_position = 0.0
covered_mw = [0.0] * 24
for c in real_book:
    cover = c.get("hours") or list(range(24))
    want_position += sum(luz[h] - c["strike_php_kwh"] for h in cover) * c["mw"] * MWH_PESOS
    for h in cover:
        covered_mw[h] += float(c["mw"])
# The open position is the load the book does not cover, hour by hour, never
# the whole 400 MW: 250 MW runs all day and 100 MW more covers hours 18 to 21.
want_open = sum(
    max(0.0, OWN_LOAD_MW - covered_mw[h]) * MWH_PESOS * luz[h] for h in range(24)
)

check(
    "the golden Sual day settles to the position its own prices imply",
    abs(gold["position_php"] - round(want_position, 2)) < 0.01,
)
check(
    "and its open position to the cost those prices imply",
    abs(gold["open_cost_php"] - round(want_open, 2)) < 0.01,
)
# A price move has to reach the position, or the check above passes on zeros.
check(
    "the golden day is not a flat no-op",
    abs(gold["position_php"]) > 1.0 and gold["open_cost_php"] > 1.0,
)

print()
print(f"contracts: {len(fails)} failures" if fails else "contracts: all green")
sys.exit(1 if fails else 0)
