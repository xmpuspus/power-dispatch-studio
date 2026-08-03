#!/usr/bin/env python3
"""Animated GIF: what a WESM swing actually moves on a Meralco bill.

One bar, the whole June 2026 residential rate, split three ways on one frame so
the comparison needs no memory. The slices arrive in turn and the spot slice
keeps pulsing, because that slice is the only part a spot price moves, and only
on the next month's bill.

The arithmetic that matters here: the WESM price applies to the WESM share of
energy, so what reaches the blended generation charge is share times price,
about P0.70/kWh. Stacking the P7.03 price itself against the P14.48 rate
overstates the bill's spot exposure roughly tenfold.

Reads web/data/market_anchors.json. Output docs/bill-wedge.gif.
"""

import json
import math
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")


def main():
    A = json.load(open(os.path.join(WEB, "market_anchors.json")))
    total = A["meralco_june2026_rate_php_kwh"]
    gen = A["meralco_june2026_generation_charge"]
    price = A["meralco_june2026_wesm_price_php_kwh"]
    espc = A["meralco_june2026_wesm_share_pct"] / 100.0
    wesm = round(espc * price, 4)
    other = round(total - gen, 4)
    contracted = round(gen - wesm, 4)

    segs = [
        ("WESM spot", wesm, cs.CORAL),
        ("contracted generation, PSA and IPP", contracted, cs.STEEL),
        ("transmission, distribution, taxes", other, "#33445c"),
    ]
    wesm_pct = 100 * wesm / total

    fdir = cs.frames_dir("wedge")
    # each slice slides in, then the spot slice pulses so the eye returns to it
    seq = [("grow", t) for t in cs.reveal(20, 6)] + [
        ("pulse", i / 24) for i in range(24)
    ]

    for fi, (stage, t) in enumerate(seq):
        fig, ax = cs.card(
            figsize=(9.0, 4.5), field="money", rect=(0.075, 0.255, 0.885, 0.395)
        )
        shown_total = total * (t if stage == "grow" else 1.0)
        left = 0.0
        for name, val, col in segs:
            w = max(0.0, min(val, shown_total - left))
            if w <= 0:
                break
            pct = 100 * val / total
            alpha = 1.0
            if stage == "pulse" and col == cs.CORAL:
                alpha = 0.74 + 0.26 * (0.5 + 0.5 * math.cos(2 * math.pi * t))
            ax.add_patch(
                FancyBboxPatch(
                    (left, -0.50),
                    w,
                    1.00,
                    boxstyle="round,pad=0,rounding_size=0.06",
                    fc=col,
                    ec="none",
                    alpha=alpha,
                    zorder=4,
                )
            )
            if w > val * 0.92 and w > total * 0.09:
                ax.text(
                    left + w / 2,
                    0,
                    f"{name}\nP{val:.2f}  {pct:.0f}%",
                    ha="center",
                    va="center",
                    fontsize=9.0,
                    color=cs.TEXT if col != "#33445c" else cs.BODY,
                    zorder=6,
                )
            left += w

        if stage == "pulse":
            ax.annotate(
                "a spot swing moves this slice alone,\nand only on next month's bill",
                xy=(wesm / 2, 0.52),
                xytext=(total * 0.055, 1.10),
                fontsize=9.2,
                color=cs.CORAL,
                ha="left",
                zorder=8,
                arrowprops=dict(arrowstyle="->", color=cs.CORAL, lw=1.2),
            )

        ax.set_xlim(-0.15, total + 0.15)
        ax.set_ylim(-1.30, 1.30)
        ax.set_yticks([])
        # The scale sits above the bar. Below it, the tick label ran straight
        # through the payoff caption, and a bar this wide needs no axis line.
        ax.set_xticks([])
        ax.text(0, 0.62, "P0", fontsize=8.6, color=cs.MUTE, ha="left", va="bottom")
        ax.text(
            total,
            0.62,
            f"P{total:.2f} per kWh",
            fontsize=8.6,
            color=cs.MUTE,
            ha="right",
            va="bottom",
        )
        ax.grid(False)
        # no baseline: this bar floats in the card, so the axis rule was just a
        # hairline drawn through the payoff caption
        ax.spines["bottom"].set_visible(False)

        cs.title(
            fig,
            f"A WESM swing moves {wesm_pct:.0f}% of a Meralco bill, "
            "and only next month",
            f"The June 2026 residential rate, P{total:.2f}/kWh, split three ways.",
        )
        cs.payoff(
            ax,
            0.0,
            0.27,
            f"P{wesm:.2f}",
            f"of the P{total:.2f} rate rides on the spot market",
            cs.ACCENT,
            34,
            va="top",
        )
        cs.source(
            fig,
            f"Meralco bought {espc * 100:.0f}% of its energy on WESM at "
            f"P{price:.2f}/kWh, so P{wesm:.2f}/kWh of the P{gen:.2f} "
            "generation charge is spot.\nThe other "
            f"{100 - espc * 100:.0f}% sits under contracts whose prices do "
            "not move with the spot market. From the Meralco June 2026 advisory.",
        )
        if fi == 0:
            cs.check_fit(fig)
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=104, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "bill-wedge.gif"), fps=12, width=900)


if __name__ == "__main__":
    main()
