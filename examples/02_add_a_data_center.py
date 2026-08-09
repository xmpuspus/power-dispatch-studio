#!/usr/bin/env python3
"""Put a 1,500 MW data center on Luzon and read the price back.

    python3 examples/02_add_a_data_center.py

The load is flat, 24 hours a day, which is how a data center draws. The same
scenario runs in the browser at
https://power-dispatch-studio.vercel.app/studio/#v=quick-scenario
"""

import power_dispatch as pd

DATE = pd.list_days()[-1]
ADD_MW = 1500

base = pd.run_scenario({"date": DATE, "opts": {}})
withdc = pd.run_scenario(
    {"date": DATE, "opts": {"demand_delta": {"luzon": ADD_MW}}},
)

print(f"{DATE}: Luzon with {ADD_MW:,} MW of flat new load\n")
print(f"{'hour':>4}  {'base':>7}  {'with load':>10}  {'change':>8}  now set by")
for b, w in zip(base["hours"], withdc["hours"]):
    d = w["price"]["luzon"] - b["price"]["luzon"]
    print(
        f"{b['hour']:>4}  {b['price']['luzon']:>7.2f}  {w['price']['luzon']:>10.2f}"
        f"  {d:>+8.2f}  {w['marginal']['luzon']}"
    )

mb = base["summary"]["mean_price"]["luzon"]
mw = withdc["summary"]["mean_price"]["luzon"]
print(f"\nMean Luzon price PhP/kWh: {mb:.3f} -> {mw:.3f}  ({mw - mb:+.3f})")

short = sum(h["shortfall"]["luzon"] for h in withdc["hours"])
if short > 0:
    print(f"The added load leaves {short:,.0f} MWh unserved on this day.")
else:
    print("Supply covers the added load on this day, at a price.")

# The price barely moves while capacity is spare and climbs steeply once the
# grid fills, so read one day as one day. Sweep the whole window with
# examples/03_sweep_the_window.py before drawing a curve.
