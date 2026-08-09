#!/usr/bin/env python3
"""Replay every bundled day at four load levels and write one CSV.

    python3 examples/03_sweep_the_window.py             # every day, writes sweep.csv
    python3 examples/03_sweep_the_window.py out.csv     # somewhere else
    python3 examples/03_sweep_the_window.py out.csv 5   # the last 5 days only

One row per day per load level. This is the shape an analyst pulls into a
spreadsheet: how the mean and peak price move as new load arrives, measured
across every recorded day rather than one convenient one.

Runtime is about one second per day per level on a laptop.
"""

import csv
import sys

import power_dispatch as pd

LEVELS_MW = [0, 500, 1500, 3000]
OUT = sys.argv[1] if len(sys.argv) > 1 else "sweep.csv"

days = pd.list_days()
if len(sys.argv) > 2:
    days = days[-int(sys.argv[2]) :]
print(f"{len(days)} days x {len(LEVELS_MW)} load levels = {len(days) * len(LEVELS_MW)} runs")

rows = []
for i, date in enumerate(days, 1):
    for mw in LEVELS_MW:
        opts = {"demand_delta": {"luzon": mw}} if mw else {}
        r = pd.run_scenario({"date": date, "opts": opts})
        s = r["summary"]
        rows.append(
            {
                "date": date,
                "added_luzon_mw": mw,
                "mean_price_luzon_php_kwh": s["mean_price"]["luzon"],
                "peak_price_luzon_php_kwh": s["peak_price"]["luzon"],
                "unserved_luzon_mwh": s["unserved_mwh"]["luzon"],
                "leyte_rent_m_php": s["leyte_rent_m_php"],
            }
        )
    print(f"  {i}/{len(days)} {date}", end="\r", flush=True)

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print(f"\nwrote {len(rows)} rows to {OUT}")

base = [r for r in rows if r["added_luzon_mw"] == 0]
top = [r for r in rows if r["added_luzon_mw"] == LEVELS_MW[-1]]
mb = sum(r["mean_price_luzon_php_kwh"] for r in base) / len(base)
mt = sum(r["mean_price_luzon_php_kwh"] for r in top) / len(top)
tight = sum(1 for r in top if r["unserved_luzon_mwh"] > 0)
print(f"Window mean Luzon price PhP/kWh: {mb:.3f} at +0 MW, {mt:.3f} at +{LEVELS_MW[-1]} MW")
print(f"{tight} of {len(top)} days leave load unserved at +{LEVELS_MW[-1]} MW")
