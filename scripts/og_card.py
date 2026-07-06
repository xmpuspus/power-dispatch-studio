#!/usr/bin/env python3
"""Build the social share card (web/og.png, 1200x630) and a higher-res still
(docs/hero.png) from the baked data, so the preview image follows the bake. The
card carries the title, the three-question frame, and the regional price fan as the
hero visual with the suspension window shaded.

Reads web/data/prices.json + congestion.json + market_anchors.json.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")
DOCS = os.path.join(ROOT, "docs")


def render(path, w_in, h_in, dpi):
    P = json.load(open(os.path.join(WEB, "prices.json")))
    C = json.load(open(os.path.join(WEB, "congestion.json")))
    dates = P["dates"]
    resume_i = next((i for i, d in enumerate(dates)
                     if d >= P.get("resumed", "2026-05-01")), 0)

    fig = plt.figure(figsize=(w_in, h_in))
    gs = GridSpec(2, 1, height_ratios=[1.0, 1.5], hspace=0.28,
                  left=0.055, right=0.965, top=0.9, bottom=0.11)

    axt = fig.add_subplot(gs[0])
    axt.axis("off")
    axt.text(0, 0.72, "gridbill-ph", fontsize=30, fontweight="bold",
             color=vz.NAVY, transform=axt.transAxes)
    axt.text(0, 0.30,
             "Can the Philippine grid host the announced data-center wave?",
             fontsize=15.5, color=vz.NAVY, transform=axt.transAxes)
    axt.text(0, -0.04,
             "Supply, choke points, and prices, from the market operator's own "
             "public files.", fontsize=11.5, color=vz.MUTE, transform=axt.transAxes)

    ax = fig.add_subplot(gs[1])
    ax.axvspan(0, resume_i, color=vz.FILL, zorder=0)
    for g, col in vz.REGION.items():
        ys = P["series"][g]
        xs = [i for i, v in enumerate(ys) if v is not None]
        ax.plot(xs, [ys[i] for i in xs], color=col, lw=2.0, zorder=3)
        last = xs[-1]
        ax.text(last + 0.8, ys[last], g.title(), color=col, fontsize=10.5,
                va="center", fontweight="bold")
    ax.axvline(resume_i, color=vz.MUTE, lw=1.0, ls=(0, (4, 3)), zorder=2)
    ax.text(resume_i - 1.5, ax.get_ylim()[1] * 0.96, "WESM suspended",
            ha="right", va="top", fontsize=9, color=vz.MUTE)
    ax.text(resume_i + 1.5, ax.get_ylim()[1] * 0.96, "market resumes",
            ha="left", va="top", fontsize=9, color=vz.NAVY)
    ax.set_xlim(0, len(dates) + 12)
    ax.set_ylabel("PhP / kWh", fontsize=10)
    ax.set_xticks([])
    ax.set_title(f'{C["distinct_equipment"]} named lines hit a limit in 90 days, '
                 "and the market prices the geography daily",
                 fontsize=12, color=vz.NAVY, loc="left")
    vz.tufte(ax, grid="y")

    fig.text(0.055, 0.035,
             "Daily average of load-weighted five-minute prices per island grid. "
             "Source: IEMOP, archived. github.com/xmpuspus/gridbill-ph",
             fontsize=8.5, color=vz.MUTE)
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    print("wrote", path, f"({os.path.getsize(path) // 1024} KB)")


def main():
    # og.png at 1200x630 (dpi 100 on 12x6.3), hero.png at 2x for the README
    render(os.path.join(ROOT, "web", "og.png"), 12.0, 6.30, 100)
    render(os.path.join(DOCS, "hero.png"), 12.0, 6.30, 180)


if __name__ == "__main__":
    main()
