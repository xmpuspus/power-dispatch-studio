#!/usr/bin/env python3
"""Who runs the Philippine power market, as a dark card. Six bodies split the functions of the
electricity market between them, and WESM runs an energy-only market with no
centralized capacity auction. This figure is why Power Dispatch Studio has no capacity-market
chart: there is no capacity market to chart.

Static explainer, no archive data. Output docs/wesm-roles.png.
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

cs.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "wesm-roles.png")

# function -> (body, one-line role). Kept short and true; sources in methodology.
ROWS = [
    ("Runs the spot market", "IEMOP", "Independent Electricity Market Operator"),
    ("Operates the grid", "NGCP", "National Grid Corporation of the Philippines"),
    ("Governs the market", "PEMC", "Philippine Electricity Market Corporation"),
    ("Regulates prices and rules", "ERC", "Energy Regulatory Commission"),
    ("Sets energy policy", "DOE", "Department of Energy"),
    ("Owns the transmission assets", "TransCo", "National Transmission Corporation"),
    ("Capacity market", "none", "energy-only, no capacity auction"),
]


def main():
    fig, ax = cs.card(
        figsize=(9.6, 5.0), field="dusk", rect=(0.055, 0.135, 0.90, 0.635)
    )
    ax.axis("off")
    ax.grid(False)
    n = len(ROWS)
    x_fn, x_body, x_role = 0.015, 0.35, 0.50
    y0, dy = 0.90, 0.145

    ax.text(x_fn, 1.01, "Function", fontsize=9.6, color=cs.MUTE)
    ax.text(x_body, 1.01, "Body", fontsize=9.6, color=cs.MUTE)
    ax.text(x_role, 1.01, "Who they are", fontsize=9.6, color=cs.MUTE)
    ax.plot([0.0, 1.0], [0.975, 0.975], color=cs.FAINT, lw=1.0)

    for i, (fn, body, role) in enumerate(ROWS):
        y = y0 - i * dy
        last = i == n - 1
        col = cs.CORAL if last else cs.STEEL
        # the last row is the finding, not another body: there is no capacity
        # market to chart, so it gets the accent and a rule of its own
        if last:
            ax.plot([0.0, 1.0], [y + dy / 2, y + dy / 2], color=cs.FAINT, lw=1.0)
        ax.text(
            x_fn, y, fn, fontsize=10.4, color=cs.TEXT if last else cs.BODY, va="center"
        )
        ax.text(
            x_body, y, body, fontsize=10.8, color=col, va="center", fontweight="bold"
        )
        ax.text(x_role, y, role, fontsize=9.8, color=cs.MUTE, va="center")

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.02, 1.06)
    cs.title(
        fig,
        "Six bodies run the market, and none of them runs a capacity auction",
        "WESM is energy-only, which is why this project has no capacity-market chart.",
    )
    cs.source(
        fig,
        "Generators are paid for the energy they dispatch and for the "
        "reserve they hold. No forward capacity auction exists to price "
        "or to chart.\nFrom IEMOP, NGCP, PEMC, ERC and DOE.",
    )
    cs.check_fit(fig, dpi=140)
    cs.save_png(fig, OUT, dpi=140)


if __name__ == "__main__":
    main()
