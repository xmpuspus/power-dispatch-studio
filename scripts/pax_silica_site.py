#!/usr/bin/env python3
"""Print the announced load sites the nodal model can place on the network."""

import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"
    ),
)

from nodal_dcopf import SITES  # noqa: E402

for key, s in sorted(SITES.items()):
    print(f"{key}")
    print(f"  {s['label']}")
    print(f"  at {s['lat']}, {s['lon']}  ({s['precision']})")
    lo, hi = s["mw_range"]
    print(f"  announced load {lo:,.0f} to {hi:,.0f} MW")
