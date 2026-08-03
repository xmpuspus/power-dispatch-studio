#!/usr/bin/env python3
"""Animated GIF: the same load, priced by three different islands.

Three panels on one shared price axis, so the comparison is adjacency rather
than memory. Each grid's curve draws in together with the others, and the card
carries the result a reader would otherwise have to work out: how much more the
steepest island charges at its own busiest hour than the flattest one.

Reads web/data/price_load.json. Output docs/small-multiples.gif.
"""

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")
GRIDS = [("luzon", "Luzon"), ("visayas", "Visayas"), ("mindanao", "Mindanao")]


def klab(v):
    return f"{v / 1000:.1f}k" if v < 10000 else f"{round(v / 1000):.0f}k"


def main():
    D = json.load(open(os.path.join(WEB, "price_load.json")))
    pmax = max(c["mean_price"] for g, _ in GRIDS for c in D["curve"][g]) * 1.14
    tops = {g: max(c["mean_price"] for c in D["curve"][g]) for g, _ in GRIDS}
    steep = max(tops, key=tops.get)
    flat = min(tops, key=tops.get)

    fdir = cs.frames_dir("smult")
    FRAMES = cs.reveal(30, 16)
    for fi, t in enumerate(FRAMES):
        cs.apply()
        fig = plt.figure(figsize=(10.6, 5.0), facecolor=cs.BG)
        lo, hi = cs.FIELDS["dusk"]
        gnd = fig.add_axes([0, 0, 1, 1], zorder=0)
        gnd.imshow(
            np.linspace(0, 1, 256).reshape(-1, 1),
            cmap=LinearSegmentedColormap.from_list("f", [hi, lo]),
            aspect="auto",
            extent=(0, 1, 0, 1),
            interpolation="bicubic",
        )
        gnd.set_xticks([])
        gnd.set_yticks([])
        for s in gnd.spines.values():
            s.set_visible(False)

        axes = []
        for i, (key, label) in enumerate(GRIDS):
            # panels widened from 0.205 to 0.262: the old three ended at 0.756
            # and the last quarter of the card carried one line of text
            ax = fig.add_axes(
                [0.068 + i * 0.302, 0.235, 0.262, 0.495], facecolor="none", zorder=2
            )
            axes.append(ax)
            cs.tufte(ax)
            curve = D["curve"][key]
            x = np.array([c["gen_mw"] for c in curve], float)
            y = np.array([c["mean_price"] for c in curve], float)
            scat = D["scatter"][key]
            n = max(2, int(round(len(x) * t)))
            col = cs.REGION[key]

            # the dots the caption promises, at a size and an alpha that show
            cs.evidence(
                ax,
                [p[0] for p in scat],
                [min(max(p[1], -3), pmax) for p in scat],
                col,
            )
            cs.glow(
                ax,
                x[:n],
                y[:n],
                col,
                lw=1.9,
                zorder=3,
                passes=((5.5, 0.08), (2.8, 0.13)),
            )
            cs.dot(ax, x[n - 1], y[n - 1], col, size=20, zorder=6)
            ax.text(
                0.0,
                1.06,
                label,
                transform=ax.transAxes,
                fontsize=11.5,
                color=cs.text_of(col),
                ha="left",
                va="bottom",
                zorder=6,
            )
            ax.set_ylim(-2, pmax)
            ax.set_xlim(x.min() - 200, x.max() + 200)
            ax.set_xticks([x.min(), (x.min() + x.max()) / 2, x.max()])
            ax.set_xticklabels(
                [klab(x.min()), klab((x.min() + x.max()) / 2), klab(x.max())],
                fontsize=8.2,
            )
            if i == 0:
                ax.set_ylabel("WESM price, PhP per kWh", fontsize=9)
            else:
                ax.set_yticklabels([])
            if i == 1:
                ax.set_xlabel("dispatched generation, MW", fontsize=9)

        cs.title(
            fig,
            f"At their busiest sampled loads, {steep.capitalize()} reaches "
            f"P{tops[steep]:.0f}/kWh; {flat.capitalize()} reaches P{tops[flat]:.0f}",
            "Average WESM price at each level of dispatched generation, "
            "over the archive window. One shared price axis.",
        )
        if t > 0.9:
            cs.payoff(
                axes[-1],
                0.03,
                0.95,
                f"P{tops[steep]:.0f}",
                f"{steep.capitalize()} at its busiest,\n"
                f"against P{tops[flat]:.0f} on {flat.capitalize()}",
                cs.REGION[steep],
                28,
                va="top",
            )
        cs.source(
            fig,
            "Each faint dot is one 5-minute interval. All three panels use "
            "the same price scale, so their levels compare directly. Each panel covers its own grid's load range, so the slopes do not.\n"
            "From IEMOP RTDSUM generation joined "
            "to LWAPF price, archived.",
        )
        # the payoff only exists on the late frames, so the overflow
        # check has to run on the last one, never on frame 0
        if fi == len(FRAMES) - 1:
            cs.check_fit(fig)
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=100, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "small-multiples.gif"), fps=12, width=940)


if __name__ == "__main__":
    main()
