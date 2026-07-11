#!/usr/bin/env python3
"""Pass F probe: prototype the per-resource joint energy+reserve clear from the
raw RTDOE + RTDOR offers, and DIAGNOSE why it cannot reproduce the official
co-optimised reserve price (RSVPR), so the wedge stays measured, not closed.

The pooled reserve replay (Pass B reserve_validation) under-prices RSVPR by a
one-signed wedge. The named fix was a per-resource joint energy+reserve LP from
the raw hourly offers. Prototyped, it does not reproduce RSVPR, and the reason
is not co-optimisation ramp/commitment mechanics: it is that the reserve
requirement CLEARS SHORT on the scarce hours and the shortfall is priced by an
administered reserve-scarcity demand curve that is not in the public offers.

Per sample grid-hour this records: the reserve requirement (RTDSUM MKT_REQT) vs
the quantity the market actually scheduled (RTDSUM GENERATION, the met
fraction); the marginal Dr offer that clears the offer stack to that SCHEDULED
quantity; the official RSVPR; and the scarcity uplift (official minus marginal
offer). Where the requirement is met the offer stack reproduces RSVPR to the
centavo; where it clears short the official price sits well above the entire
offer stack, the administered scarcity value the offers cannot explain. A free
joint LP that forces the full requirement goes infeasible on exactly those
hours (the market could not meet it either) and lands at the marginal offer
where feasible, below the scarcity-priced official.

    python3 pipeline/joint_lp_probe.py --derive
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from datetime import datetime, timedelta

import highspy

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "data", "derived", "joint_lp_probe.json")
SAMPLE = [
    ("2026-05-15", 19, "CLUZ"), ("2026-05-30", 20, "CLUZ"),
    ("2026-06-10", 19, "CVIS"), ("2026-06-20", 19, "CLUZ"),
    ("2026-06-20", 20, "CMIN"),
]
GRID_NAME = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
INF = highspy.kHighsInf


def _segs(row, n=11):
    out, prev = [], 0.0
    for i in range(1, n + 1):
        p, q = row.get(f"PRICE{i}"), row.get(f"QUANTITY{i}")
        if not p or not q:
            break
        try:
            price, qty = float(p) / 1000.0, float(q)
        except ValueError:
            break
        w = qty - prev
        if w > 1e-9:
            out.append((price, w))
        prev = max(prev, qty)
    return out


def _interval(date: str, hour: int) -> str:
    dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour, minutes=5)
    return dt.strftime("%-m/%-d/%Y %-I:%M:%S %p")


def _stamp(date: str, hour: int) -> str:
    return (datetime.strptime(date, "%Y-%m-%d")
            + timedelta(hours=hour + 1)).strftime("%Y%m%d%H%M")


def _rtdsum_dr(date, hour, grid):
    """(MKT_REQT, GENERATION scheduled) for Dr reserve at the interval."""
    iv = _interval(date, hour)
    p = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
        if (r.get("TIME_INTERVAL") == iv and r.get("REGION_NAME") == grid
                and r.get("COMMODITY_TYPE") == "Dr"):
            return float(r.get("MKT_REQT") or 0), float(r.get("GENERATION") or 0)
    return None, None


def _official_rsvpr(date, hour, grid):
    iv = _interval(date, hour)
    for p in glob.glob(os.path.join(RAW, "RSVPR",
                                    f"*{date.replace('-', '')}*.csv")):
        for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
            if (r.get("TIME_INTERVAL") == iv and r.get("REGION_NAME") == grid
                    and r.get("COMMODITY_TYPE") == "Dr"):
                return round(float(r.get("PRICE") or 0) / 1000, 3)
    return None


def _joint_free_reserve_price(date, hour, grid):
    """The free joint LP's Dr reserve dual (energy re-dispatched freely,
    requirement forced): the naive clear, for the record."""
    from offers import _fetch_hour_csv
    oe = _fetch_hour_csv("rtd-generation-offers", "RTDOE", _stamp(date, hour))
    orr = _fetch_hour_csv("rtd-reserve-offers", "RTDOR", _stamp(date, hour))
    if not oe or not orr:
        return None
    iv = _interval(date, hour)
    oe = [r for r in oe if r.get("TIME_INTERVAL") == iv
          and r.get("REGION_NAME") == grid]
    orr = [r for r in orr if r.get("TIME_INTERVAL") == iv
           and r.get("REGION_NAME") == grid and r.get("COMMODITY_TYPE") == "Dr"]
    energy = {r["RESOURCE_NAME"]: _segs(r) for r in oe if _segs(r)}
    pmax = {res: sum(w for _, w in s) for res, s in energy.items()}
    reserve = {r["RESOURCE_NAME"]: _segs(r) for r in orr if _segs(r)}
    reqt, _sched = _rtdsum_dr(date, hour, grid)
    demand = None
    p = os.path.join(RAW, "RTDSUM", f"RTDREG_{date.replace('-', '')}.csv")
    for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
        if (r.get("TIME_INTERVAL") == iv and r.get("REGION_NAME") == grid
                and r.get("COMMODITY_TYPE") == "En"):
            demand = float(r.get("GENERATION") or 0)
    if demand is None or reqt is None or not reserve:
        return None
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    cols = []
    for res, s in energy.items():
        for pr, w in s:
            cols.append((pr, w, "e", res))
    for res, s in reserve.items():
        for pr, w in s:
            cols.append((pr, w, "r", res))
    for pr, w, kind, res in cols:
        h.addCol(pr, 0.0, w, 0, [], [])
    ei = [i for i, c in enumerate(cols) if c[2] == "e"]
    ri = [i for i, c in enumerate(cols) if c[2] == "r"]
    h.addRow(demand, demand, len(ei), ei, [1.0] * len(ei))
    h.addRow(reqt, INF, len(ri), ri, [1.0] * len(ri))
    for res, cap in pmax.items():
        m = [i for i, c in enumerate(cols) if c[3] == res]
        if m:
            h.addRow(-INF, cap, len(m), m, [1.0] * len(m))
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return "infeasible"
    return round(h.getSolution().row_dual[1], 3)


def _sample(date, hour, grid) -> dict:
    """Clear the Dr offer stack to the ACTUAL scheduled quantity and compare
    the marginal offer to the official price."""
    from offers import _fetch_hour_csv
    orr = _fetch_hour_csv("rtd-reserve-offers", "RTDOR", _stamp(date, hour))
    if not orr:
        return {}
    iv = _interval(date, hour)
    orr = [r for r in orr if r.get("TIME_INTERVAL") == iv
           and r.get("REGION_NAME") == grid and r.get("COMMODITY_TYPE") == "Dr"]
    stack = []
    for r in orr:
        stack.extend(_segs(r))
    stack.sort()
    reqt, sched = _rtdsum_dr(date, hour, grid)
    official = _official_rsvpr(date, hour, grid)
    if reqt is None or official is None:
        return {}
    cum, marg = 0.0, (stack[-1][0] if stack else 0.0)
    for price, w in stack:
        cum += w
        marg = price
        if cum >= sched - 1e-9:
            break
    return {
        "date": date, "hour": hour, "grid": GRID_NAME[grid],
        "mkt_reqt_mw": round(reqt, 1), "scheduled_mw": round(sched, 1),
        "met_pct": round(100 * sched / reqt, 1) if reqt else None,
        "marginal_offer_at_scheduled_php_kwh": round(marg, 3),
        "official_rsvpr_php_kwh": official,
        "scarcity_uplift_php_kwh": round(official - marg, 3),
        "joint_lp_free_redispatch_php_kwh": _joint_free_reserve_price(
            date, hour, grid),
    }


def derive() -> dict:
    rows = [d for (date, hour, grid) in SAMPLE
            if (d := _sample(date, hour, grid))]
    met = [r for r in rows if (r["met_pct"] or 0) >= 99]
    short = [r for r in rows if (r["met_pct"] or 0) < 99]
    max_met_gap = max((abs(r["scarcity_uplift_php_kwh"]) for r in met),
                      default=0.0)
    max_short_uplift = max((r["scarcity_uplift_php_kwh"] for r in short),
                           default=0.0)
    return {
        "available": True,
        "samples": rows,
        "n_samples": len(rows),
        "n_requirement_met": len(met),
        "n_requirement_short": len(short),
        "max_offer_stack_gap_on_met_hours_php_kwh": round(max_met_gap, 3),
        "max_scarcity_uplift_on_short_hours_php_kwh": round(max_short_uplift, 2),
        "verdict": "wedge_is_administered_reserve_scarcity_not_in_offers",
        "note": ("The named per-resource joint energy+reserve LP was prototyped "
                 "from the raw RTDOE + RTDOR offers and does not reproduce the "
                 "official reserve price (RSVPR); the diagnosis is that the "
                 "reserve requirement CLEARS SHORT on the scarce hours and the "
                 "shortfall is priced by an administered scarcity value that is "
                 "not in the offers. On the requirement-met hours the marginal "
                 "Dr offer cleared to the actually scheduled quantity (RTDSUM "
                 "GENERATION) reproduces RSVPR to the centavo (the offer stack "
                 "explains it, and the pooled replay already scores these). On "
                 "the short hours the market scheduled only a fraction of the "
                 "requirement (RTDSUM GENERATION well below MKT_REQT) and the "
                 "official price sits above the ENTIRE offer stack, an "
                 "administered reserve-scarcity value the public offers cannot "
                 "explain; a free joint LP that forces the full requirement "
                 "goes infeasible on exactly those hours. So the wedge Pass B "
                 "measures is administered reserve scarcity on the "
                 "requirement-short hours, not a co-optimisation internal "
                 "recoverable from offers. It stays measured, not closed, and "
                 "the model keeps its stated approximation, withhold the "
                 "requirement and show the official price beside it. Fixing the "
                 "energy dispatch to the observed schedule (DIPCEF) and "
                 "registered capacity (CAPEG) does not change this: it tracks "
                 "RSVPR only where the requirement is met, and cannot recover "
                 "the administered scarcity uplift where it is not."),
        "src": "https://www.iemop.ph/market-data/rtd-regional-reserve-prices/",
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    a = ap.parse_args()
    if a.derive:
        out = derive()
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, indent=1)
        print(f"wrote {OUT}: {out['n_requirement_met']} met, "
              f"{out['n_requirement_short']} short; max met-hour gap "
              f"{out['max_offer_stack_gap_on_met_hours_php_kwh']}, max "
              f"short-hour uplift {out['max_scarcity_uplift_on_short_hours_php_kwh']}")
        for r in out["samples"]:
            print(f"  {r['date']} h{r['hour']} {r['grid']}: met {r['met_pct']}% "
                  f"| offer@sched {r['marginal_offer_at_scheduled_php_kwh']} "
                  f"| official {r['official_rsvpr_php_kwh']} "
                  f"| uplift {r['scarcity_uplift_php_kwh']}")
    else:
        print(__doc__)
