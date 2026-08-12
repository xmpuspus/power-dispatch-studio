#!/usr/bin/env python3
"""Animated GIF: the Sual arithmetic, drawn as a quantity you can count.

The margin used to be one bar that got shorter. A bar shrinking says "less". It
does not say how much less, and 3,629 MW is a number nobody feels. So the
margin is a grid of 100 MW blocks instead. The blocks fill in, one Sual unit
takes its blocks away, then the second does, and a reader counts the loss.

This is arithmetic on IEMOP's published May 2026 margin, never a dispatch
simulation, and the card says so.

Reads web/data/market_anchors.json + sual.geojson. Output docs/sual-margin.gif.
"""

import json
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")
BLOCK_MW = 100
COLS = 12


def square(x, y, color, alpha, grow=0.0):
    s = 0.40 + grow
    return FancyBboxPatch(
        (x - s, y - s),
        2 * s,
        2 * s,
        boxstyle="round,pad=0,rounding_size=0.10",
        fc=color,
        ec="none",
        alpha=alpha,
        zorder=4,
    )


def main():
    A = json.load(open(os.path.join(WEB, "market_anchors.json")))
    sual = json.load(open(os.path.join(WEB, "sual.geojson")))["features"][0]
    margin = A["wesm_may2026_margin_mw"]
    unit = sual["properties"]["unit_mw"]

    n_blocks = int(round(margin / BLOCK_MW))
    per_unit = unit / BLOCK_MW
    share = 100.0 * unit / margin
    rows = (n_blocks + COLS - 1) // COLS

    fdir = cs.frames_dir("sual")
    seq = (
        [("fill", t) for t in cs.reveal(18, 8)]
        + [("one", t) for t in cs.reveal(9, 10)]
        + [("two", t) for t in cs.reveal(9, 16)]
    )

    for fi, (stage, t) in enumerate(seq):
        fig, ax = cs.card(
            figsize=(8.6, 4.25), field="dusk", rect=(0.075, 0.315, 0.885, 0.470)
        )
        shown = n_blocks if stage != "fill" else int(round(n_blocks * t))
        gone = 0.0
        if stage == "one":
            gone = per_unit * t
        elif stage == "two":
            gone = per_unit * (1 + t)

        for i in range(shown):
            x, y = i % COLS, -(i // COLS)
            # the loss is taken off the end of the same grid, so it reads as a
            # bite out of one quantity rather than as a second, different bar
            lost = i >= n_blocks - gone
            if lost:
                ax.add_patch(square(x, y, cs.ACCENT, 0.13, grow=0.10))
            ax.add_patch(
                square(x, y, cs.ACCENT if lost else cs.STEEL, 0.96 if lost else 0.80)
            )

        ax.set_xlim(-0.7, COLS - 0.3)
        ax.set_ylim(-rows + 0.35, 0.7)
        ax.set_aspect("equal")
        ax.axis("off")

        left = margin - gone * BLOCK_MW
        cs.title(
            fig,
            f"One Sual unit is {share:.0f}% of the whole system's spare margin",
            # Kept short on purpose. The longer wording ran to the card's last
            # pixel and shipped with its full stop cut off.
            f"Each block is {BLOCK_MW} MW. The {n_blocks} blocks are the "
            f"{margin:,} MW May 2026 margin, to the nearest {BLOCK_MW} MW. "
            f"Sual runs two {unit} MW units.",
        )
        cs.result_label(
            fig,
            0.075,
            0.205,
            f"{left:,.0f}",
            "MW of margin left" if gone else "MW of spare margin",
            cs.ACCENT if gone else cs.STEEL,
            size=37,
        )
        if stage != "fill":
            # Report what is subtracted RIGHT NOW, not what the stage is
            # heading for. The old label said "2 of 2 units trip, -1,294 MW"
            # through the whole second stage while the figure beside it still
            # read a partly-subtracted margin, so the two did not add up.
            removed = gone * BLOCK_MW
            n = 1 if removed <= unit else 2
            word = "unit trips" if n == 1 else "units trip"
            fig.text(
                0.30,
                0.225,
                f"{n} of 2 {word}, -{removed:,.0f} MW",
                fontsize=9.6,
                color=cs.BODY,
                va="top",
                zorder=6,
            )
        cs.source(
            fig,
            y=0.055,
            text="Arithmetic on IEMOP's published May 2026 supply margin, not a "
            "dispatch simulation. The margin itself moves daily.\n"
            "From the IEMOP May 2026 report and Sual Power Station unit ratings.",
        )
        # the payoff only exists on the late frames, so the overflow
        # check has to run on the last one, never on frame 0
        if fi == len(seq) - 1:
            cs.check_fit(fig, dpi=104)
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=104, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "sual-margin.gif"), fps=12, width=880)


if __name__ == "__main__":
    main()
