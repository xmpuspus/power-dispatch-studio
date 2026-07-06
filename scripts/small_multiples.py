#!/usr/bin/env python3
"""Small-multiples, ported from gridbill-us small_multiples.py: the three island
grids side by side, each showing its own price-vs-load shape. Luzon carries the
volume and a long climb; the smaller grids are flatter until they run tight. One row
makes the point that the same load does different things on different islands.

Reads the baked web/data/price_load.json, so it stays in sync with the map. Output
docs/small-multiples.png.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")
OUT = os.path.join(ROOT, "docs", "small-multiples.png")

GRIDS = [("luzon", "Luzon"), ("visayas", "Visayas"), ("mindanao", "Mindanao")]


def main():
    D = json.load(open(os.path.join(WEB, "price_load.json")))
    pmax = max(c["mean_price"] for g, _ in GRIDS for c in D["curve"][g]) * 1.08

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.9), sharey=True)
    for ax, (key, label) in zip(axes, GRIDS):
        curve = D["curve"][key]
        scat = D["scatter"][key]
        x = [c["gen_mw"] for c in curve]
        y = [c["mean_price"] for c in curve]
        col = vz.REGION[key]
        ax.scatter([p[0] for p in scat],
                   [min(max(p[1], -3), pmax) for p in scat],
                   s=4, alpha=0.05, color="#9fb2c4", edgecolors="none",
                   zorder=1, rasterized=True)
        ax.plot(x, y, color=col, lw=2.4, zorder=3)
        ax.set_title(label, fontsize=12, color=col, loc="left")
        ax.set_ylim(-2, pmax)
        ax.set_xlabel("dispatched generation (MW)", fontsize=9.5)
        vz.tufte(ax, grid="y")
        gwlo, gwhi = min(x), max(x)
        mid = (gwlo + gwhi) / 2

        def klab(v):
            return f"{v/1000:.1f}k" if v < 10000 else f"{int(round(v/1000))}k"
        ax.set_xticks([gwlo, mid, gwhi])
        ax.set_xticklabels([klab(gwlo), klab(mid), klab(gwhi)], fontsize=9)
    axes[0].set_ylabel("WESM price  (PhP per kWh)", fontsize=10.5)
    fig.suptitle("The same load does different things on different islands",
                 fontsize=14, color=vz.NAVY, x=0.02, ha="left", y=1.02)
    vz.caption(fig,
               "Each panel is one island grid: the average WESM price at each level "
               "of dispatched generation, over the archive window. Luzon carries the "
               "volume and a long climb; the smaller grids stay flat until they run "
               "tight. Source: IEMOP RTDSUM generation joined to LWAPF price, archived.",
               y=-0.06)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT, f"({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
