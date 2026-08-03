#!/usr/bin/env python3
"""Animated GIF: one market on paper, three prices once trading resumed.

The three island grids share one frame, because the comparison is the whole
finding. While the market ran on administered prices the lines sit on top of
each other, within P0.015. The suspension band ends and they fan apart. The
card labels the widest daily gap and keeps the two regimes
labelled so the suspension never reads as a market outcome.

Reads web/data/prices.json. Output docs/price-spread.gif.
"""

import json
import os
import sys
from datetime import date

import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")


def pretty(iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return date(y, m, d).strftime("%b %-d")


def main():
    P = json.load(open(os.path.join(WEB, "prices.json")))
    dates = P["dates"]
    series = {g: P["series"][g] for g in ("luzon", "visayas", "mindanao")}
    resumed = P.get("resumed", "2026-05-01")
    reg = P["regimes"]
    widest = P["max_spread"]
    n = len(dates)
    cut = next((i for i, d in enumerate(dates) if d >= resumed), 0)
    ymax = max(v for g in series.values() for v in g if v is not None) * 1.14

    fdir = cs.frames_dir("spread")
    seq = cs.reveal(38, 16)

    for fi, t in enumerate(seq):
        fig, ax = cs.card(
            figsize=(8.8, 5.0), field="dusk", rect=(0.075, 0.195, 0.885, 0.575)
        )
        upto = max(2, int(round(n * t)))

        band = min(upto, cut)
        if band > 1:
            ax.axvspan(0, band - 1, color="#18212e", alpha=0.9, zorder=0)
            if t > 0.20:
                ax.text(
                    (band - 1) / 2,
                    ymax * 0.96,
                    "WESM suspended",
                    ha="center",
                    fontsize=8.8,
                    color=cs.MUTE,
                    zorder=6,
                )
                ax.text(
                    (band - 1) / 2,
                    ymax * 0.895,
                    f"administered, the three within "
                    f"P{reg['administered']['max_spread']}",
                    ha="center",
                    fontsize=7.8,
                    color=cs.MUTE,
                    zorder=6,
                )
        if upto > cut:
            ax.axvline(cut, color=cs.FAINT, lw=1.0, ls=(0, (4, 3)), zorder=1)
            ax.text(
                cut + 1.5,
                ymax * 0.96,
                f"market resumes {pretty(resumed)}",
                fontsize=8.8,
                color=cs.BODY,
                zorder=6,
            )

        # Direct labels ride at each line's last value, so two grids that end
        # close together printed one name over the other. Push them apart by a
        # minimum gap first, keeping their order.
        ends = sorted(
            ((series[g][:upto][-1], g) for g in ("luzon", "visayas", "mindanao")),
        )
        gap = ymax * 0.055
        placed = {}
        prev = None
        for val, g in ends:
            yy = val if prev is None else max(val, prev + gap)
            placed[g] = yy
            prev = yy
        for g in ("luzon", "visayas", "mindanao"):
            ys = [v for v in series[g][:upto]]
            xs = list(range(len(ys)))
            cs.glow(ax, xs, ys, cs.REGION[g], lw=1.6, zorder=4)
            cs.dot(ax, xs[-1], ys[-1], cs.REGION[g], size=22, zorder=7)
            if t > 0.45:
                ax.text(
                    xs[-1] + 1.4,
                    placed[g],
                    g.capitalize(),
                    fontsize=9,
                    color=cs.REGION[g],
                    va="center",
                    zorder=8,
                )

        ax.set_xlim(0, n + 11)
        ax.set_ylim(0, ymax)
        ax.set_xticks([])
        ax.set_ylabel("daily average price, PhP per kWh", fontsize=9)

        cs.title(
            fig,
            "One wholesale market produced three different island-grid prices",
            f"Daily load-weighted average price per island grid, "
            f"{pretty(dates[0])} to {pretty(dates[-1])}.",
        )
        if t > 0.9:
            # the lower left is empty: the three grids ran together and cheap
            # while the market was suspended
            cs.payoff(
                ax,
                0.015,
                0.60,
                f"P{widest['php']:.2f}",
                f"widest gap in one day, {pretty(widest['date'])}\n"
                f"{reg['market']['days_spread_gt5']} of "
                f"{reg['market']['days']} days split\nby more than P5",
                cs.ACCENT,
                26,
                va="top",
            )
        cs.source(
            fig,
            "Each line is one island grid's daily average of IEMOP's "
            "load-weighted 5-minute prices.\nLimited transfer capacity lets "
            "regional prices separate when local supply and demand differ. "
            "From IEMOP LWAPF, archived.",
        )
        if fi == 0:
            cs.check_fit(fig)
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=104, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "price-spread.gif"), fps=12, width=880)


if __name__ == "__main__":
    main()
