#!/usr/bin/env python3
"""Animated GIF: the same data center, priced against two different grids.

The old version swept one marker along the curve, so the reader met the two
answers seconds apart and had to hold the first in memory. Both states now sit
in one frame, because adjacency is the comparison: the same 300 MW added to a
quiet grid and to a full one, with the price move labelled on each. The sweep
still runs, but it runs between two marks the reader can already see.

Reads web/data/price_load.json. Output docs/price-shape.gif.
"""
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")
DC_MW = 300   # one large campus, the size the announced sites come in


def bump_at(x, y, xc):
    """The price move the same DC_MW causes with the grid at xc."""
    return float(np.interp(xc + DC_MW, x, y)) - float(np.interp(xc, x, y))


def main():
    D = json.load(open(os.path.join(WEB, "price_load.json")))
    curve = D["curve"]["luzon"]
    scat = D["scatter"]["luzon"]
    x = np.array([c["gen_mw"] for c in curve], float)
    y = np.array([c["mean_price"] for c in curve], float)
    sx = np.array([p[0] for p in scat], float)
    sy = np.clip(np.array([p[1] for p in scat], float), -5, 40)

    lo, hi = x.min() + 200, x.max() - DC_MW - 200
    quiet, full = lo, hi
    b_quiet, b_full = bump_at(x, y, quiet), bump_at(x, y, full)
    times = b_full / b_quiet if b_quiet > 0 else 0

    sweep = np.linspace(quiet, full, 30)
    seq = list(sweep) + [full] * 14 + list(sweep[::-1]) + [quiet] * 8

    fdir = cs.frames_dir("shape")
    for fi, xc in enumerate(seq):
        fig, ax = cs.card(figsize=(8.8, 5.1), field="day",
                          rect=(0.075, 0.185, 0.615, 0.585))
        ax.scatter(sx, sy, s=4, alpha=0.05, color=cs.STEEL, edgecolors="none",
                   zorder=1, rasterized=True)
        cs.glow(ax, x, y, cs.STEEL, lw=2.0, zorder=3,
                passes=((6.0, 0.07), (3.0, 0.12)))

        # both answers, always on screen
        for xa, col, lab in ((quiet, cs.STEEL, "grid with room"),
                             (full, cs.CORAL, "grid nearly full")):
            ya, yb = float(np.interp(xa, x, y)), float(np.interp(xa + DC_MW, x, y))
            ax.plot([xa, xa], [ya, yb], color=col, lw=2.4, zorder=6,
                    solid_capstyle="round")
            cs.dot(ax, xa, ya, col, size=34, zorder=6)
            cs.chip(ax, xa, yb + 1.5, f"+P{yb - ya:.2f}/kWh", col, 9.4)
            ax.text(xa, -1.6, lab, fontsize=8.4, color=col, ha="center",
                    va="top", zorder=6)

        # the moving marker, showing that the answer changes continuously
        ym = float(np.interp(xc, x, y))
        cs.dot(ax, xc, ym, cs.WHITE, size=16, zorder=8)

        ax.set_xlim(x.min() - 250, x.max() + 250)
        ax.set_ylim(-3.4, max(y) * 1.16)
        ax.set_xlabel("Luzon generation meeting demand, MW", fontsize=9)
        ax.set_ylabel("WESM price, PhP per kWh", fontsize=9)

        cs.title(fig, f"The same {DC_MW} MW costs {times:.0f} times more when the grid is full",
                 "Every faint dot is one 5-minute interval on the Luzon grid. "
                 "The line is the average price at each load.")
        cs.payoff(fig, 0.745, 0.615, f"{times:.0f}x", "the same load, "
                  "the bigger price move", cs.CORAL, 40)
        fig.text(0.745, 0.475,
                 f"with room  +P{b_quiet:.2f}/kWh\nnearly full  +P{b_full:.2f}/kWh",
                 fontsize=9.0, color=cs.BODY, va="top", zorder=6)
        cs.source(fig,
                  f"A data center draws the same {DC_MW} MW every hour. What it "
                  "does to the price depends on how busy the grid already is.\n"
                  "Source: IEMOP RTDSUM generation joined to LWAPF price, archived.")
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=104, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "price-shape.gif"), fps=14, width=880)


if __name__ == "__main__":
    main()
