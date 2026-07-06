#!/usr/bin/env python3
"""Who-does-what in the Philippine power market, ported in spirit from gridbill-us
wesm_us_roles.py. One US ISO or RTO bundles market operation, grid operation, and a
capacity market under one roof; the Philippine setup splits those across four bodies,
and WESM runs an energy-only market with no centralized capacity auction. This figure
is why gridbill-ph has no capacity-market chart: there is no capacity market to chart.

Static explainer, no archive data. Output docs/wesm-roles.png.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "wesm-roles.png")

# function -> (US, PH body). Kept short and true; sources in methodology.
ROWS = [
    ("Runs the spot market", "the ISO / RTO", "IEMOP (market operator)"),
    ("Operates the grid", "the ISO / RTO", "NGCP (system operator)"),
    ("Governs the market", "the ISO board", "PEMC (governance)"),
    ("Regulates prices and rules", "FERC", "ERC (regulator)"),
    ("Sets energy policy", "DOE / states", "DOE (policy)"),
    ("Capacity market", "yes (PJM, ISO-NE, NYISO)", "none, energy-only market"),
]


def main():
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    ax.axis("off")
    n = len(ROWS)
    x_fn, x_us, x_ph = 0.02, 0.40, 0.70
    y0, dy = 0.82, 0.125

    ax.text(x_fn, 0.95, "Function", fontsize=10.5, fontweight="bold", color=vz.MUTE)
    ax.text(x_us, 0.95, "One US ISO / RTO", fontsize=10.5, fontweight="bold",
            color=vz.MUTE)
    ax.text(x_ph, 0.95, "Philippines (split four ways)", fontsize=10.5,
            fontweight="bold", color=vz.NAVY)
    ax.plot([0.0, 1.0], [0.91, 0.91], color=vz.GRID, lw=1)

    for i, (fn, us, ph) in enumerate(ROWS):
        y = y0 - i * dy
        last = i == n - 1
        ax.text(x_fn, y, fn, fontsize=10.5, color=vz.NAVY,
                fontweight="bold" if last else "normal", va="center")
        ax.text(x_us, y, us, fontsize=10, color=vz.MUTE, va="center")
        ax.text(x_ph, y, ph, fontsize=10,
                color=vz.CORAL if last else vz.NAVY,
                fontweight="bold" if last else "normal", va="center")
        if not last:
            ax.plot([0.0, 1.0], [y - dy / 2, y - dy / 2], color=vz.FILL, lw=0.8)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("One roof in a US market; four bodies in the Philippines",
                 fontsize=14, color=vz.NAVY, loc="left", x=0.02)
    vz.caption(fig,
               "The Philippine market splits functions a US ISO bundles, and WESM is "
               "energy-only. Generators are paid for the energy they dispatch, not for "
               "standing capacity, so there is no capacity auction to price or to "
               "chart. Sources: IEMOP, NGCP, PEMC, ERC, DOE.",
               y=0.02)
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT, f"({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
