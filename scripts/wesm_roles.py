#!/usr/bin/env python3
"""Who runs the Philippine power market. Five bodies split the functions of the
electricity market between them, and WESM runs an energy-only market with no
centralized capacity auction. This figure is why gridbill-ph has no capacity-market
chart: there is no capacity market to chart.

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

# function -> (body, one-line role). Kept short and true; sources in methodology.
ROWS = [
    ("Runs the spot market", "IEMOP", "Independent Electricity Market Operator"),
    ("Operates the grid", "NGCP", "National Grid Corporation of the Philippines"),
    ("Governs the market", "PEMC", "Philippine Electricity Market Corporation"),
    ("Regulates prices and rules", "ERC", "Energy Regulatory Commission"),
    ("Sets energy policy", "DOE", "Department of Energy"),
    ("Capacity market", "none", "energy-only, no capacity auction"),
]


def main():
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    ax.axis("off")
    n = len(ROWS)
    x_fn, x_body, x_role = 0.02, 0.36, 0.52
    y0, dy = 0.82, 0.125

    ax.text(x_fn, 0.95, "Function", fontsize=10.5, fontweight="bold", color=vz.MUTE)
    ax.text(x_body, 0.95, "Body", fontsize=10.5, fontweight="bold", color=vz.NAVY)
    ax.text(x_role, 0.95, "Who they are", fontsize=10.5, fontweight="bold",
            color=vz.MUTE)
    ax.plot([0.0, 1.0], [0.91, 0.91], color=vz.GRID, lw=1)

    for i, (fn, body, role) in enumerate(ROWS):
        y = y0 - i * dy
        last = i == n - 1
        ax.text(x_fn, y, fn, fontsize=10.5, color=vz.NAVY,
                fontweight="bold" if last else "normal", va="center")
        ax.text(x_body, y, body, fontsize=10.5,
                color=vz.CORAL if last else vz.NAVY,
                fontweight="bold", va="center")
        ax.text(x_role, y, role, fontsize=10, color=vz.MUTE, va="center")
        if not last:
            ax.plot([0.0, 1.0], [y - dy / 2, y - dy / 2], color=vz.FILL, lw=0.8)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Five bodies run the Philippine power market",
                 fontsize=14, color=vz.NAVY, loc="left", x=0.02)
    vz.caption(fig,
               "IEMOP runs the spot market, NGCP operates the grid, PEMC governs, ERC "
               "regulates, and DOE sets policy. WESM is energy-only. Generators are "
               "paid for the energy they dispatch, not for standing capacity, so there "
               "is no capacity auction to price or to chart. Sources: IEMOP, NGCP, "
               "PEMC, ERC, DOE.",
               y=0.02)
    fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", OUT, f"({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()
