#!/usr/bin/env python3
"""Build a future year as a data directory the same engine already reads.

The archive holds 118 recorded days of this year. A planner asks about 2028.
Nothing in the engine has to change to answer that: `run_scenario` reads a
directory holding dispatch.json and profiles.json, and `--data-dir` already
points at any directory. So a future year is a data build, not an engine build.

Four sourced inputs, joined here:

  DOE peak-demand path      web/data/demand_path.json   (PDP 2023-2050, Table 28)
  DOE project lists         web/data/projects.json      (committed + indicative)
  NGCP corridor upgrades    web/data/projects.json      (corridors block, TDP)
  recorded hourly shapes    web/data/profiles.json      (118 archived days)

Method, and every step is an assumption this file labels:

  1. Demand. Take the DOE's own growth ratio between the base year and the
     target year, per grid, and multiply every recorded hour by it. The archive
     keeps its own level and shape; the plan supplies only the growth. Scaling
     to the DOE's absolute peak instead would impose a level the recorded days
     never had.
  2. Calendar. One row per date in the target year. Each date borrows the shape
     of an archived day of the same kind, weekday or weekend, cycling in date
     order. That keeps the weekday and weekend shapes apart, which a plain
     round-robin would blur.
  3. Supply. Add project MW whose target year is at or before the target year,
     per grid and per fuel. Committed by default; --indicative adds the rest.
     Solar and storage are tracked apart from the dispatchable stack, exactly
     as the DOE's own summaries do.
  4. Links. Add corridor MW whose target year is at or before the target year.
  5. Retirements. NONE. No public Philippine retirement schedule sits in this
     repository, so this build retires nothing and says so in meta.json. A
     fleet that never retires is optimistic about supply.

The result is a scenario, never a forecast. Every figure it produces carries
that label, the same as every other forward figure in this project.

    python3 pipeline/future_year.py --year 2028
    python3 pipeline/future_year.py --year 2028 --summary --limit 20
    power-dispatch run --data-dir data/derived/future/2028 --date 2028-06-17
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(ROOT, "web", "data")
OUT_ROOT = os.path.join(ROOT, "data", "derived", "future")

GRIDS = ("luzon", "visayas", "mindanao")
# fuels the dispatchable stack carries; solar rides its own installed MW and
# storage is not generation, so both stay out of fuel_avail_mw
STACK_FUELS = ("coal", "natural_gas", "oil", "geothermal", "hydro", "biomass", "wind")


def _load(name):
    with open(os.path.join(WEB, name)) as fh:
        return json.load(fh)


def growth_ratios(demand_path: dict, base_year: int, year: int) -> dict:
    """The DOE's peak-demand growth between two years, per grid."""
    years = demand_path["years"]
    if base_year not in years:
        raise SystemExit(f"base year {base_year} is not in the DOE path")
    if year not in years:
        raise SystemExit(f"target year {year} is not in the DOE path ({years[-1]} max)")
    bi, ti = years.index(base_year), years.index(year)
    out = {}
    for g in GRIDS:
        series = demand_path["per_grid_mw"][g]
        base = float(series[bi])
        if base <= 0:
            raise SystemExit(f"DOE path has no {base_year} peak for {g}")
        out[g] = float(series[ti]) / base
    return out


def added_mw(projects: dict, year: int, indicative: bool) -> tuple[dict, dict, dict]:
    """Project MW at or before the target year: stack fuels, solar, storage."""
    stack = {g: {} for g in GRIDS}
    solar = {g: 0.0 for g in GRIDS}
    storage = {g: 0.0 for g in GRIDS}
    wanted = {"committed", "indicative"} if indicative else {"committed"}
    for r in projects["rows"]:
        if r["status"] not in wanted:
            continue
        ty = r.get("target_year")
        if ty is None or ty > year:
            continue
        g, fuel, mw = r["grid"], r["fuel"], float(r.get("mw") or 0.0)
        if g not in stack or mw <= 0:
            continue
        if fuel == "solar":
            solar[g] += mw
        elif fuel == "storage":
            storage[g] += mw
        elif fuel in STACK_FUELS:
            stack[g][fuel] = stack[g].get(fuel, 0.0) + mw
    return stack, solar, storage


def added_corridor_mw(projects: dict, year: int) -> dict:
    out = {}
    for c in projects.get("corridors") or []:
        ty = c.get("target_year")
        iface = c.get("iface")
        if ty is None or iface is None or ty > year:
            continue
        out[iface] = out.get(iface, 0.0) + float(c.get("adds_mw") or 0.0)
    return out


def calendar_days(year: int, archive: list[dict]) -> list[tuple[str, dict]]:
    """One row per date in the year, each borrowing a recorded day of the same
    kind. Weekday dates draw from recorded weekdays, weekend from weekends, and
    each pool cycles in date order so the mapping is deterministic."""
    pools = {False: [], True: []}
    for d in archive:
        wd = dt.date.fromisoformat(d["date"]).weekday()
        pools[wd >= 5].append(d)
    if not pools[False] or not pools[True]:
        # a window with only one kind of day: fall back to the whole archive
        pools = {False: archive, True: archive}
    seen = {False: 0, True: 0}
    out = []
    day = dt.date(year, 1, 1)
    while day.year == year:
        weekend = day.weekday() >= 5
        pool = pools[weekend]
        src = pool[seen[weekend] % len(pool)]
        seen[weekend] += 1
        out.append((day.isoformat(), src))
        day += dt.timedelta(days=1)
    return out


def build(year: int, base_year: int, indicative: bool) -> dict:
    dispatch = _load("dispatch.json")
    profiles = _load("profiles.json")
    demand_path = _load("demand_path.json")
    projects = _load("projects.json")

    ratios = growth_ratios(demand_path, base_year, year)
    stack_add, solar_add, storage_add = added_mw(projects, year, indicative)
    corr_add = added_corridor_mw(projects, year)

    # --- supply -------------------------------------------------------------
    hydro_scale = {}
    for g in GRIDS:
        mo = dispatch["merit_order"][g]
        fa = dict(mo["fuel_avail_mw"])
        base_hydro = fa.get("hydro") or 0.0
        for fuel, mw in stack_add[g].items():
            fa[fuel] = round(fa.get(fuel, 0.0) + mw, 1)
        mo["fuel_avail_mw"] = fa
        mo["solar_installed_mw"] = round(mo["solar_installed_mw"] + solar_add[g], 1)
        new_hydro = fa.get("hydro") or 0.0
        hydro_scale[g] = (new_hydro / base_hydro) if base_hydro > 0 else 1.0

    for c in dispatch["coupling"]["corridors"]:
        add = corr_add.get(c["id"], 0.0)
        if add:
            c["limit_mw"] = round(c["limit_mw"] + add, 1)

    # --- demand -------------------------------------------------------------
    days = []
    for date, src in calendar_days(year, profiles["days"]):
        row = {
            "date": date,
            "source_day": src["date"],
            "demand": {
                g: [round(v * ratios[g], 1) for v in src["demand"][g]] for g in GRIDS
            },
        }
        for key in ("reserve_req_mw", "corridor_caps", "out_dev_mw"):
            if src.get(key):
                row[key] = src[key]
        hb = src.get("hydro_budget_mwh")
        if hb:
            row["hydro_budget_mwh"] = {
                g: (None if hb.get(g) is None else round(hb[g] * hydro_scale[g], 1))
                for g in GRIDS
            }
        days.append(row)

    profiles["days"] = days
    profiles["default_day"] = f"{year}-06-17"
    profiles.pop("backcast", None)
    profiles.pop("offer_backcast", None)
    profiles.pop("chrono_golden", None)

    meta = {
        "kind": "future-year scenario",
        "year": year,
        "base_year": base_year,
        "built_from": {
            "archive_window": [
                profiles.get("resumed") or "",
                _load("meta.json").get("built_utc", ""),
            ],
            "recorded_days_used": len(_load("profiles.json")["days"]),
        },
        "demand": {
            "method": "DOE peak growth ratio applied to every recorded hour",
            "ratio_per_grid": {g: round(ratios[g], 4) for g in GRIDS},
            "owner": demand_path.get("owner"),
            "plan": demand_path.get("plan"),
            "src": demand_path.get("src"),
        },
        "supply": {
            "method": "DOE project list, target year at or before this year",
            "status_included": ["committed"] + (["indicative"] if indicative else []),
            "as_of": projects.get("as_of"),
            "added_stack_mw": {
                g: {k: round(v, 1) for k, v in stack_add[g].items()} for g in GRIDS
            },
            "added_solar_mw": {g: round(solar_add[g], 1) for g in GRIDS},
            "storage_projects_mw": {g: round(storage_add[g], 1) for g in GRIDS},
            "storage_note": (
                "Storage projects are reported and never added to the stack. "
                "Storage is a scenario lever, not generation."
            ),
            "retirements": "none applied; no public retirement schedule is archived here",
        },
        "links": {"added_mw": corr_add, "src": projects.get("src_tdp")},
        "calendar": {
            "days": len(days),
            "method": "each date borrows a recorded day of the same kind, weekday or weekend",
        },
        "label": (
            "This is a scenario built from published plans, and it is not a "
            "forecast. Each day solves on its own, so storage resets at midnight "
            "and the hydro budget caps one day at a time."
        ),
        "disclaimer": (
            "Statistical indicators derived from public data. Patterns may have "
            "legitimate explanations."
        ),
    }
    return {"dispatch": dispatch, "profiles": profiles, "meta": meta}


def write(year: int, built: dict) -> str:
    out = os.path.join(OUT_ROOT, str(year))
    os.makedirs(out, exist_ok=True)
    for name in ("dispatch", "profiles", "meta"):
        with open(os.path.join(out, f"{name}.json"), "w") as fh:
            json.dump(built[name], fh, separators=(",", ":"))
    return out


def summarize(year: int, data_dir: str, limit: int | None) -> dict:
    """Solve the year and reduce it to the numbers a reader can hold."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import power_dispatch as pdx

    dates = pdx.list_days(data_dir)
    if limit:
        step = max(1, len(dates) // limit)
        dates = dates[::step][:limit]
    rows = []
    for i, date in enumerate(dates, 1):
        r = pdx.run_scenario({"date": date, "opts": {}}, data_dir=data_dir)
        s = r["summary"]
        # solar is near zero at the evening peak, so an annual mean flatters a
        # year whose new capacity is mostly solar. The evening hours are where
        # firm capacity actually has to show up.
        evening = [h for h in r["hours"] if 18 <= h["hour"] <= 21]
        rows.append(
            {
                "date": date,
                "mean_price": {g: s["mean_price"][g] for g in GRIDS},
                "peak_price": {g: s["peak_price"][g] for g in GRIDS},
                "evening_price": {
                    g: round(sum(h["price"][g] for h in evening) / len(evening), 3)
                    for g in GRIDS
                },
                "unserved_mwh": {g: s["unserved_mwh"][g] for g in GRIDS},
                "peak_demand_mw": {
                    g: max(h["demand"][g] for h in r["hours"]) for g in GRIDS
                },
            }
        )
        if i % 30 == 0 or i == len(dates):
            print(f"  solved {i}/{len(dates)} {date}", end="\r", flush=True)
    print()

    def _mean(key, g):
        return round(sum(x[key][g] for x in rows) / len(rows), 3)

    short_days = {
        g: sum(1 for x in rows if x["unserved_mwh"][g] > 0) for g in GRIDS
    }
    return {
        "year": year,
        "days_solved": len(rows),
        "days_in_year": len(pdx.list_days(data_dir)),
        "mean_price_php_kwh": {g: _mean("mean_price", g) for g in GRIDS},
        "evening_price_php_kwh": {g: _mean("evening_price", g) for g in GRIDS},
        "peak_price_php_kwh": {
            g: round(max(x["peak_price"][g] for x in rows), 3) for g in GRIDS
        },
        "peak_demand_mw": {
            g: round(max(x["peak_demand_mw"][g] for x in rows), 1) for g in GRIDS
        },
        "unserved_mwh": {
            g: round(sum(x["unserved_mwh"][g] for x in rows), 1) for g in GRIDS
        },
        "days_with_unserved_load": short_days,
        "series": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True, help="target year, e.g. 2028")
    ap.add_argument(
        "--base-year",
        type=int,
        default=2026,
        help="the year the archived days belong to (default 2026)",
    )
    ap.add_argument(
        "--indicative",
        action="store_true",
        help="add indicative projects as well as committed ones",
    )
    ap.add_argument(
        "--summary",
        action="store_true",
        help="solve the year and write the studio summary into web/data/",
    )
    ap.add_argument(
        "--limit", type=int, help="solve this many evenly spaced days, for a quick check"
    )
    args = ap.parse_args()

    built = build(args.year, args.base_year, args.indicative)
    out = write(args.year, built)
    m = built["meta"]
    print(f"wrote {out}")
    print(f"  {m['calendar']['days']} days, demand ratio {m['demand']['ratio_per_grid']}")
    print(f"  added stack MW {m['supply']['added_stack_mw']}")
    print(f"  added solar MW {m['supply']['added_solar_mw']}")
    print(f"  added link MW {m['links']['added_mw']}")

    if args.summary:
        s = summarize(args.year, out, args.limit)
        s["meta"] = m
        s["available"] = True
        # the committed derivation, exactly like the other derive-on-demand
        # probes. build_data.py copies it into web/data on every data build, so
        # `make clean` cannot silently drop it.
        path = os.path.join(ROOT, "data", "derived", "future_year.json")
        with open(path, "w") as fh:
            json.dump(s, fh, separators=(",", ":"))
        print(f"wrote {path}")
        print(f"  mean price {s['mean_price_php_kwh']}")
        print(f"  days with unserved load {s['days_with_unserved_load']}")


if __name__ == "__main__":
    main()
