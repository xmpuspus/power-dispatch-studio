#!/usr/bin/env python3
"""Replay one recorded market day and print what set the price each hour.

    pip install power-dispatch-studio
    python3 examples/01_replay_a_day.py

The wheel carries a dated snapshot of the public archive, so this runs with no
network and no account. Nothing here reaches the internet.
"""

import power_dispatch as pd

days = pd.list_days()
print(f"{len(days)} recorded days available, {days[0]} to {days[-1]}")

date = days[-1]
result = pd.run_scenario({"date": date, "opts": {}})

print(f"\n{date}, Luzon, hour by hour")
print(f"{'hour':>4}  {'demand MW':>10}  {'price':>8}  price set by")
for h in result["hours"]:
    print(
        f"{h['hour']:>4}  {h['demand']['luzon']:>10,.0f}"
        f"  {h['price']['luzon']:>8.2f}  {h['marginal']['luzon']}"
    )

s = result["summary"]
print(f"\nMean price PhP/kWh: {s['mean_price']}")
print(f"Peak price PhP/kWh: {s['peak_price']}")
print(f"Unserved energy MWh: {s['unserved_mwh']}")

# Every run carries the hash of the linear program it solved. The browser build
# writes the same text byte for byte, which is how the two engines stay one
# engine rather than two that agree today.
print(f"\nLP text sha256: {result['lp_sha256'][:16]}...")
