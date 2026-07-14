"""power-dispatch: run a WESM dispatch scenario from the command line.

    power-dispatch days                          list the observed days
    power-dispatch run --date 2026-06-15         replay a day, hourly CSV to stdout
    power-dispatch run --scenario s.json -o out.csv
    power-dispatch run --date 2026-06-15 --offer-mode --demand luzon=1500

Scenario JSON: {"date": "YYYY-MM-DD", "opts": {...}} with the override map from
`power_dispatch.OPT_KEYS`. Output is one row per hour with per-grid price,
marginal fuel, demand, shortfall, corridor flows, and storage state.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from . import __version__, list_days, run_scenario

GRIDS = ("luzon", "visayas", "mindanao")


def _hours_to_rows(result: dict) -> list[dict]:
    rows = []
    for h in result["hours"]:
        row = {"hour": h["hour"]}
        for g in GRIDS:
            row[f"{g}_price_php_kwh"] = h["price"][g]
            row[f"{g}_marginal"] = h["marginal"][g]
            row[f"{g}_demand_mw"] = h["demand"][g]
            row[f"{g}_shortfall_mw"] = h["shortfall"][g]
        row["flow_lv_mw"] = h["flow_lv"]
        row["flow_vm_mw"] = h["flow_vm"]
        row["soc_mwh"] = h["soc_mwh"]
        row["charge_mw"] = h["charge_mw"]
        row["discharge_mw"] = h["discharge_mw"]
        rows.append(row)
    return rows


def _write_csv(rows: list[dict], out) -> None:
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)


def _parse_kv(pairs: list[str], cast) -> dict:
    """Parse repeated grid=value flags into {grid: value}."""
    out: dict[str, float] = {}
    for p in pairs:
        k, _, v = p.partition("=")
        out[k.strip()] = cast(v.strip())
    return out


def _build_scenario(args) -> dict:
    if args.scenario:
        with open(args.scenario, encoding="utf-8") as fh:
            scenario = json.load(fh)
        if args.date:
            scenario["date"] = args.date
        return scenario
    if not args.date:
        raise SystemExit("run: pass --scenario FILE or --date YYYY-MM-DD")
    opts: dict = {}
    if args.demand:
        opts["demand_delta"] = _parse_kv(args.demand, float)
    if args.fuel_cost:
        opts["fuel_cost"] = _parse_kv(args.fuel_cost, float)
    if args.hydrology is not None:
        opts["hydrology"] = args.hydrology
    if args.offer_mode:
        opts["offer_mode"] = True
    if args.reserve_deduction:
        opts["reserve_deduction"] = True
    return {"date": args.date, "opts": opts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="power-dispatch",
                                 description="PH WESM dispatch engine")
    ap.add_argument("--version", action="version",
                    version=f"power-dispatch {__version__}")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("days", help="list observed days available for replay")

    r = sub.add_parser("run", help="run a scenario, emit hourly CSV")
    r.add_argument("--scenario", help="scenario JSON file")
    r.add_argument("--date", help="observed day YYYY-MM-DD")
    r.add_argument("--demand", action="append", default=[], metavar="GRID=MW",
                   help="load delta, e.g. luzon=1500 (repeatable)")
    r.add_argument("--fuel-cost", action="append", default=[],
                   metavar="FUEL=PHP", help="marginal-cost override (repeatable)")
    r.add_argument("--hydrology", type=float, help="water multiplier (1.0=observed)")
    r.add_argument("--offer-mode", action="store_true",
                   help="replay the observed offer book, not the cost proxy")
    r.add_argument("--reserve-deduction", action="store_true",
                   help="withhold scheduled reserve from the book")
    r.add_argument("--data-dir", help="override the baked data directory")
    r.add_argument("-o", "--out", help="write CSV here (default stdout)")
    r.add_argument("--json", action="store_true",
                   help="emit the full result as JSON instead of hourly CSV")

    args = ap.parse_args(argv)

    if args.cmd == "days":
        for d in list_days():
            print(d)
        return 0

    if args.cmd == "run":
        scenario = _build_scenario(args)
        result = run_scenario(scenario, data_dir=args.data_dir)
        if args.json:
            text = json.dumps(result, indent=2)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(text)
            else:
                print(text)
            return 0
        rows = _hours_to_rows(result)
        if args.out:
            with open(args.out, "w", newline="", encoding="utf-8") as fh:
                _write_csv(rows, fh)
            s = result["summary"]
            print(f"wrote {len(rows)} hours -> {args.out} "
                  f"(mean Luzon {s['mean_price']['luzon']} PhP/kWh)",
                  file=sys.stderr)
        else:
            _write_csv(rows, sys.stdout)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
