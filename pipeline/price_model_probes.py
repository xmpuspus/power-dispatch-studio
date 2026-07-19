#!/usr/bin/env python3
"""Price-model levers, measured on the backcast before any adoption.

The cost-mode backcast prices every hour off a handful of flat per-fuel
blocks, so its correlation with the observed tape is structurally low; the
offer replay (0.73-0.88) shows the missing information is the bidding
behavior in the books. This probe measures the levers that could close part
of that gap while keeping the project's stance: inputs come from sourced
constants or the operator's own files, never from the price tape.

Variants, all scored on the same full-coverage market days:

  base       the shipped cost-mode engine, unchanged (control)
  reserve    base plus reserve withholding at the DAY's scheduled MW
             (RTDSUM MKT_REQT, non-Rd), the existing engine hook that the
             shipped backcast leaves off
  stylized   a TYPICAL offer book instead of the cost proxy: for each grid
             and hour-of-day, the median of the observed cumulative offer
             curves across the OTHER days (leave-one-out, so a day is never
             priced by a curve that saw its own book). Estimated from bids,
             which are inputs, not outcomes; the price tape stays the exam.
  styl_res   stylized plus the same whole-book reserve withholding the
             offer replay offers (a stated approximation: the book cannot
             say which MW are reserve-capable)
  offer      the true same-day offer replay, recomputed with this probe's
             extended scorer as the ceiling reference

Two levers from the same program are consolidated or blocked, stated here
rather than silently dropped:
  - a monthly fuel-price index for coal/gas has no sourced in-repo series
    (the ERC administered P6.00 IS the sourced constant); the observed
    offer books already embed each day's fuel-cost level, so that lever
    rides the stylized book instead of a hand-built index.
  - an observed UNPLANNED daily-unavailability layer has no derived series
    yet (PASA carries scheduled outages, the NSO stream carries HVDC
    blocks and alert prose, not per-day unavailable MW); building that
    parser is the named unblock, and the dated 935 MW July 1 case in
    dispatch.json remains its one-day proof.

The engine is NOT changed. Whatever wins here is adopted separately, the
same worsens-becomes-finding / improves-becomes-adoption pattern as
uc_probe and vre_probe.

    python3 pipeline/price_model_probes.py --derive   # measure, write JSON
    python3 pipeline/price_model_probes.py            # print the table
"""

from __future__ import annotations

import argparse
import glob
import json
import os

from chrono import GRID_KEYS, _corr, _pctl_low, _score_pairs, round1, round3
from lp_dispatch import OFFER_CAP, _highs_solve, run_chronology_lp
from lp_model import G_SHORT, build_day_lp

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "derived", "price_model_probes.json")
OFFER_DIR = os.path.join(HERE, "..", "data", "derived", "offer_daily")

# evening-peak scoring window (hours 17..21): the block the cost model is
# known to under-price and the levers here aim at
PEAK_HOURS = (17, 18, 19, 20, 21)
# the stylized curve is sampled on a fixed MW grid; 100 MW resolves the
# Luzon book to ~160 steps, well under the replay's own 48x24x3 block count
MW_STEP = 100.0
# a MW point enters the stylized curve only while at least half the other
# days' books reach it, so the typical book ends where typical books end
MIN_COVER_FRAC = 0.5


def _smape(pts: list[tuple[float, float]]) -> float | None:
    """Symmetric MAPE in percent, the metric PyPSA-Eur reports (20.76%
    Europe-wide), so the fundamentals engines here can sit beside a
    published par. Pairs where both sides are ~0 carry no information and
    are skipped."""
    terms = [
        2 * abs(m - o) / (abs(m) + abs(o)) for m, o in pts if abs(m) + abs(o) > 1e-9
    ]
    if not terms:
        return None
    return round(100 * sum(terms) / len(terms), 2)


def score_days(day_pairs: dict[str, list[tuple[float, float]]]) -> dict | None:
    """The shipped scorer plus the shape metrics the levers aim at:
    pooled-hour metrics from _score_pairs, SMAPE, evening-peak MAE, and the
    median WITHIN-day correlation (pooled correlation rewards cross-day
    level luck; a flat model can move it without ever tracking an evening
    ramp)."""
    pooled = [p for pts in day_pairs.values() for p in pts]
    base = _score_pairs(pooled)
    if not base:
        return None
    day_corrs = []
    peak_pts = []
    for pts in day_pairs.values():
        if len(pts) == 24:
            c = _corr([m for m, _ in pts], [o for _, o in pts])
            if c is not None:
                day_corrs.append(c)
            peak_pts.extend(pts[h] for h in PEAK_HOURS)
    base["smape_pct"] = _smape(pooled)
    base["peak_mae_php_kwh"] = (
        round(sum(abs(m - o) for m, o in peak_pts) / len(peak_pts), 3)
        if peak_pts
        else None
    )
    base["within_day_corr_median"] = (
        _pctl_low(sorted(day_corrs), 0.5) if day_corrs else None
    )
    base["n_days_ranked"] = len(day_corrs)
    return base


def _replay_days(profiles: dict) -> list[dict]:
    """Market days with full 24-hour LWAP on all grids, the same gate the
    shipped backcast applies."""
    out = []
    for day in profiles["days"]:
        if not day["market"]:
            continue
        lw = day.get("lwap") or {}
        if all(
            len(lw.get(g) or []) == 24 and all(v is not None for v in lw[g])
            for g in GRID_KEYS
        ):
            out.append(day)
    return out


def _collect(day: dict, prices_by_hour, pairs, pairs_mcp) -> None:
    lw = day["lwap"]
    mc = day.get("mcp") or {}
    for g in GRID_KEYS:
        pl = pairs.setdefault(g, {}).setdefault(day["date"], [])
        for h in range(24):
            pl.append((prices_by_hour[h][g], lw[g][h]))
        mcg = mc.get(g) or []
        ml = pairs_mcp.setdefault(g, {}).setdefault(day["date"], [])
        for h in range(24):
            if h < len(mcg) and mcg[h] is not None:
                ml.append((prices_by_hour[h][g], mcg[h]))


def _lever_backcast(dispatch: dict, profiles: dict, opts: dict) -> dict:
    """Run the shipped LP engine over the window with the given opts and
    score with the extended scorer. Also counts hydro-marginal hours (the
    water dual pricing the day's budget), the diagnostic for how much work
    the existing opportunity-cost channel already does."""
    pairs: dict = {}
    pairs_mcp: dict = {}
    hydro_marg_hours = {g: 0 for g in GRID_KEYS}
    n_hours = 0
    for day in _replay_days(profiles):
        res = run_chronology_lp(dispatch, profiles, day["date"], dict(opts))
        prices = [res["hours"][h]["price"] for h in range(24)]
        _collect(day, prices, pairs, pairs_mcp)
        n_hours += 24
        for h in range(24):
            for g in GRID_KEYS:
                if res["hours"][h]["marginal"][g] == "hydro":
                    hydro_marg_hours[g] += 1
    return {
        "lwap": {g: score_days(pairs[g]) for g in GRID_KEYS},
        "mcp": {g: score_days(pairs_mcp[g]) for g in GRID_KEYS},
        "hydro_marginal_hours": hydro_marg_hours,
        "n_hours_per_grid": n_hours,
    }


# ---- stylized book: leave-one-out median of the observed offer curves --------


def _offer_files() -> dict[str, str]:
    return {
        os.path.basename(p)[7:15]: p
        for p in glob.glob(os.path.join(OFFER_DIR, "OFFERD_*.json"))
    }


def _curve_at(blocks: list[list[float]], m: float) -> float | None:
    """Price of the m-th MW on one cumulative offer curve, None past its top."""
    cum = 0.0
    for price, mw in blocks:
        cum += mw
        if cum >= m:
            return price
    return None


def build_stylized_curves(days_books: dict[str, dict]) -> dict:
    """For each grid and hour-of-day: sample every day's cumulative offer
    curve on the MW grid, then hold the per-day price columns so the
    leave-one-out median is a sorted-list-minus-one away. Returns
    {grid: {hour: {"mw": [...], "by_day": {date: [prices...]}}}}."""
    out: dict = {}
    for g in GRID_KEYS:
        out[g] = {}
        for h in range(24):
            tops = []
            for book in days_books.values():
                blocks = book["hours"][g][h] or []
                tops.append(sum(mw for _, mw in blocks))
            if not tops:
                continue
            tops.sort()
            # the typical book ends where at least half the books still
            # have MW on offer
            top = (
                tops[max(0, int(len(tops) * (1 - MIN_COVER_FRAC)) - 1)]
                if len(tops) > 1
                else tops[0]
            )
            mws = [m for m in _mw_grid(top)]
            by_day = {}
            for date, book in days_books.items():
                blocks = book["hours"][g][h] or []
                by_day[date] = [_curve_at(blocks, m) for m in mws]
            out[g][h] = {"mw": mws, "by_day": by_day}
    return out


def _mw_grid(top: float):
    m = MW_STEP
    while m <= top:
        yield m
        m += MW_STEP


def _loo_median_blocks(curve: dict, leave_out: str) -> list[dict]:
    """Median price at each MW point across every day but leave_out, folded
    back into {fuel, cost, mw} step blocks (merging equal-price steps)."""
    mws = curve["mw"]
    med = []
    for i in range(len(mws)):
        vals = sorted(
            v[i]
            for d, v in curve["by_day"].items()
            if d != leave_out and v[i] is not None
        )
        if len(vals) < max(2, int(len(curve["by_day"]) * MIN_COVER_FRAC)):
            break
        med.append(
            vals[(len(vals) - 1) // 2]
            if len(vals) % 2
            else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
        )
    blocks: list[dict] = []
    for i, price in enumerate(med):
        width = MW_STEP if i else mws[0]
        p = round3(price)
        if blocks and abs(blocks[-1]["cost"] - p) < 1e-9:
            blocks[-1]["mw"] = round1(blocks[-1]["mw"] + width)
        else:
            blocks.append({"fuel": "offer", "cost": p, "mw": round1(width)})
    return blocks


def _stylized_backcast(profiles: dict, with_reserve: bool) -> dict:
    files = _offer_files()
    days = _replay_days(profiles)
    books = {}
    for day in days:
        stamp = day["date"].replace("-", "")
        if stamp in files:
            with open(files[stamp]) as fh:
                books[day["date"]] = json.load(fh)
    curves = build_stylized_curves(books)
    pairs: dict = {}
    pairs_mcp: dict = {}
    days_used = []
    for day in days:
        stacks = {g: [] for g in GRID_KEYS}
        demand = {g: [] for g in GRID_KEYS}
        ok = True
        for h in range(24):
            for g in GRID_KEYS:
                curve = curves[g].get(h)
                blocks = _loo_median_blocks(curve, day["date"]) if curve else []
                if not blocks:
                    ok = False
                stacks[g].append(blocks)
                demand[g].append(day["demand"][g][h])
        if not ok:
            continue
        caps: dict = {"leyte": 250.0, "mvip": 450.0}
        for key in ("leyte", "mvip"):
            frac = (day.get("corridor_caps") or {}).get(key)
            if frac:
                caps[key] = [round1(caps[key] * frac[h]) for h in range(24)]
        reserve = None
        if with_reserve:
            day_req = day.get("reserve_req_mw") or {}
            mean_req = profiles.get("reserve_req_mean_mw") or {}
            reserve = {
                g: round1(
                    sum(
                        v
                        for k, v in (day_req.get(g) or mean_req.get(g) or {}).items()
                        if k != "Rd"
                    )
                )
                for g in GRID_KEYS
            }
        dearest = max(b["cost"] for g in GRID_KEYS for hb in stacks[g] for b in hb)
        text = build_day_lp(
            stacks, demand, caps, 0.02, [], reserve, max(OFFER_CAP, dearest + 0.001)
        )
        sol = _highs_solve(text)
        duals = sol["duals"]
        prices = [
            {g: round3(duals.get(f"bal_{G_SHORT[g]}_{h}", 0.0)) for g in GRID_KEYS}
            for h in range(24)
        ]
        _collect(day, prices, pairs, pairs_mcp)
        days_used.append(day["date"])
    return {
        "days": len(days_used),
        "lwap": {g: score_days(pairs.get(g) or {}) for g in GRID_KEYS},
        "mcp": {g: score_days(pairs_mcp.get(g) or {}) for g in GRID_KEYS},
    }


def _offer_replay_backcast(profiles: dict) -> dict:
    """The true same-day replay, rescored with the extended metrics so the
    ceiling sits in the same table."""
    files = _offer_files()
    pairs: dict = {}
    pairs_mcp: dict = {}
    days_used = []
    for day in _replay_days(profiles):
        stamp = day["date"].replace("-", "")
        path = files.get(stamp)
        if not path:
            continue
        with open(path) as fh:
            book = json.load(fh)
        stacks = {g: [] for g in GRID_KEYS}
        demand = {g: [] for g in GRID_KEYS}
        ok = True
        for h in range(24):
            for g in GRID_KEYS:
                blocks = [
                    {"fuel": "offer", "cost": p, "mw": mw}
                    for p, mw in (book["hours"][g][h] or [])
                ]
                if not blocks:
                    ok = False
                stacks[g].append(sorted(blocks, key=lambda b: b["cost"]))
                demand[g].append(day["demand"][g][h])
        if not ok:
            continue
        caps: dict = {"leyte": 250.0, "mvip": 450.0}
        for key in ("leyte", "mvip"):
            frac = (day.get("corridor_caps") or {}).get(key)
            if frac:
                caps[key] = [round1(caps[key] * frac[h]) for h in range(24)]
        dearest = max(b["cost"] for g in GRID_KEYS for hb in stacks[g] for b in hb)
        text = build_day_lp(
            stacks, demand, caps, 0.02, [], None, max(OFFER_CAP, dearest + 0.001)
        )
        sol = _highs_solve(text)
        duals = sol["duals"]
        prices = [
            {g: round3(duals.get(f"bal_{G_SHORT[g]}_{h}", 0.0)) for g in GRID_KEYS}
            for h in range(24)
        ]
        _collect(day, prices, pairs, pairs_mcp)
        days_used.append(day["date"])
    return {
        "days": len(days_used),
        "lwap": {g: score_days(pairs.get(g) or {}) for g in GRID_KEYS},
        "mcp": {g: score_days(pairs_mcp.get(g) or {}) for g in GRID_KEYS},
    }


def derive(dispatch: dict, profiles: dict) -> dict:
    variants = {
        "base": _lever_backcast(dispatch, profiles, {}),
        "reserve": _lever_backcast(dispatch, profiles, {"reserve_deduction": True}),
        "stylized": _stylized_backcast(profiles, with_reserve=False),
        "styl_res": _stylized_backcast(profiles, with_reserve=True),
        "offer": _offer_replay_backcast(profiles),
    }

    def cell(v, tgt, g, key):
        s = (v.get(tgt) or {}).get(g)
        return s.get(key) if s else None

    deltas = {}
    for name in ("reserve", "stylized", "styl_res"):
        deltas[name] = {}
        for tgt in ("lwap", "mcp"):
            deltas[name][tgt] = {}
            for g in GRID_KEYS:
                b = cell(variants["base"], tgt, g, "correlation")
                v = cell(variants[name], tgt, g, "correlation")
                deltas[name][tgt][g] = (
                    round3(v - b) if b is not None and v is not None else None
                )
    # adoption tests mirror uc_probe: a lever must beat base on the Luzon
    # LWAP correlation, and a stylized engine must also close at least half
    # the base-to-replay correlation gap to earn a third-engine slot
    lz = lambda n: deltas[n]["lwap"]["luzon"]  # noqa: E731
    b_corr = cell(variants["base"], "lwap", "luzon", "correlation")
    o_corr = cell(variants["offer"], "lwap", "luzon", "correlation")
    s_corr = cell(variants["stylized"], "lwap", "luzon", "correlation")
    gap_closed = (
        round3((s_corr - b_corr) / (o_corr - b_corr))
        if None not in (b_corr, o_corr, s_corr) and abs(o_corr - b_corr) > 1e-9
        else None
    )
    return {
        "generated_by": "pipeline/price_model_probes.py",
        "peak_hours": list(PEAK_HOURS),
        "mw_step": MW_STEP,
        "stylized_note": (
            "Stylized book: per grid and hour-of-day, the leave-one-out "
            "median of the observed cumulative offer curves (RTDOE + "
            "self-scheduled) across the window's other days, sampled every "
            f"{int(MW_STEP)} MW while at least half the books reach the "
            "point. Estimated from bids (inputs), scored on prices "
            "(outcomes); a day is never priced by a curve that saw its own "
            "book."
        ),
        "consolidated_levers": {
            "fuel_price_index": (
                "no sourced in-repo monthly coal/gas series; the observed "
                "books already carry each day's fuel-cost level, so the "
                "lever rides the stylized book instead of a hand-built "
                "index"
            ),
            "observed_unavailability": (
                "blocked on a derived per-day unplanned-unavailable-MW "
                "series (PASA is scheduled-only; the NSO stream carries "
                "HVDC blocks and alert prose, not MW); the dated 935 MW "
                "July 1 case remains the one-day proof and the parser is "
                "the named unblock"
            ),
        },
        "variants": variants,
        "corr_delta_vs_base": deltas,
        "stylized_gap_closed_frac": gap_closed,
        "verdicts": {
            "reserve": ("adopt" if (lz("reserve") or 0) > 0 else "finding"),
            "stylized": (
                "adopt as third engine"
                if ((lz("stylized") or 0) > 0 and (gap_closed or 0) >= 0.5)
                else "finding"
            ),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derive", action="store_true")
    args = ap.parse_args()
    web = os.path.join(HERE, "..", "web", "data")
    dispatch = json.load(open(os.path.join(web, "dispatch.json")))
    profiles = json.load(open(os.path.join(web, "profiles.json")))
    out = derive(dispatch, profiles)
    if args.derive:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump(out, f, indent=2)
        print(f"wrote {OUT}")
    print("\ncorrelation vs LWAP (pooled | within-day median), by variant:")
    hdr = (
        f"{'variant/grid':22s}{'pooled':>8s}{'in-day':>8s}{'SMAPE%':>8s}"
        f"{'pkMAE':>8s}{'MAE':>8s}"
    )
    print(hdr)
    for name, v in out["variants"].items():
        for g in GRID_KEYS:
            s = (v.get("lwap") or {}).get(g)
            if not s:
                continue
            wd = s.get("within_day_corr_median")
            print(
                f"{name + '/' + g:22s}"
                f"{s.get('correlation'):>8.3f}"
                f"{(wd if wd is not None else float('nan')):>8.3f}"
                f"{(s.get('smape_pct') or float('nan')):>8.2f}"
                f"{(s.get('peak_mae_php_kwh') or float('nan')):>8.2f}"
                f"{s.get('mae_php_kwh'):>8.2f}"
            )
    print(
        "\nhydro-marginal hours (base, of",
        out["variants"]["base"]["n_hours_per_grid"],
        "per grid):",
        out["variants"]["base"]["hydro_marginal_hours"],
    )
    print("stylized gap closed (Luzon LWAP corr):", out["stylized_gap_closed_frac"])
    print("verdicts:", out["verdicts"])


if __name__ == "__main__":
    main()
