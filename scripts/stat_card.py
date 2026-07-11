#!/usr/bin/env python3
"""The LinkedIn hero card: one claim, one number, one source, phone-legible.

On LinkedIn a shared video autoplays muted and the feed renders its actual first
frame, so a blank or busy frame is a scroll-past. This builds a dark, high-contrast
4:5 card (docs/linkedin-card.png) carrying the single number the post rides on, the
announced data-center wave as a share of the whole system's spare margin, with both
figures labeled by owner and source. Numbers come from the bake (market_anchors,
demand_anchors), not typed, so the card cannot drift from the map.

The two figures are on the same footing the map uses: a labeled DICT forecast and
the IEMOP May supply-margin figure. The share is arithmetic on those two.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")
DOCS = os.path.join(ROOT, "docs")

BG = "#0d2137"       # deep navy, the app's ink pushed to a background
WHITE = "#f4f7fa"
MUTE = "#9db0c4"
CORAL = vz.CORAL     # the announced wave, the thing to look at
GREEN = "#4ec27f"    # the spare margin (supply), lifted for dark-bg contrast


def main():
    ma = json.load(open(os.path.join(WEB, "market_anchors.json")))
    da = json.load(open(os.path.join(WEB, "demand_anchors.json")))
    margin = ma["wesm_may2026_margin_mw"]
    dict_row = next(d for d in da if d["owner"] == "DICT" and d.get("mw"))
    wave = dict_row["mw"]
    pct = round(wave / margin * 100)

    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def T(x, y, s, size, color=WHITE, weight="normal", ha="left", family="sans-serif"):
        ax.text(x, y, s, transform=ax.transAxes, fontsize=size, color=color,
                fontweight=weight, ha=ha, va="center", family=family)

    T(0.07, 0.945, "POWER DISPATCH STUDIO", 15, MUTE, "bold")
    T(0.93, 0.945, "the Philippine grid, from the operator's own files", 12.5,
      MUTE, ha="right")

    # the number
    T(0.07, 0.78, f"{pct}%", 132, CORAL, "bold")
    T(0.075, 0.63,
      "of the grid's entire spare margin is the size", 27, WHITE, "bold")
    T(0.075, 0.585,
      "of the announced data-center wave.", 27, WHITE, "bold")

    # the two figures as a comparison bar
    y_wave, y_marg, h = 0.485, 0.375, 0.045
    full = 0.60  # axes-fraction width the larger (margin) bar fills
    x0 = 0.075
    ax.add_patch(plt.Rectangle((x0, y_wave - h / 2), full * wave / margin, h,
                               transform=ax.transAxes, color=CORAL, zorder=2))
    ax.add_patch(plt.Rectangle((x0, y_marg - h / 2), full, h,
                               transform=ax.transAxes, color=GREEN, zorder=2))
    T(x0, y_wave + 0.048, "ANNOUNCED WAVE", 13, MUTE, "bold")
    T(x0 + full * wave / margin + 0.02, y_wave, f"{wave:,} MW", 22, WHITE, "bold")
    T(x0, y_marg + 0.048, "SYSTEM SPARE MARGIN", 13, MUTE, "bold")
    T(x0 + full + 0.02, y_marg, f"{margin:,} MW", 22, WHITE, "bold")
    T(x0, 0.305,
      "1,500 MW: DICT forecast, by 2028.   3,629 MW: IEMOP, May 2026.",
      13, MUTE)

    # the guardrail, the line that makes it unimpeachable
    T(0.075, 0.235,
      "Today's data centers are small and did not cause the", 16, MUTE)
    T(0.075, 0.198,
      "recent red alerts. The question is the announced wave", 16, MUTE)
    T(0.075, 0.161,
      "landing on a grid whose margin is already this thin.", 16, MUTE)

    ax.plot([0.075, 0.925], [0.105, 0.105], transform=ax.transAxes,
            color="#24425f", lw=1.2)
    T(0.075, 0.072, "power-dispatch-studio.vercel.app", 18, WHITE, "bold")
    T(0.075, 0.037,
      "Free. Runs in your browser. Every number links to its source.", 13.5, MUTE)

    out = os.path.join(DOCS, "linkedin-card.png")
    fig.savefig(out, dpi=100, facecolor=BG)
    plt.close(fig)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)  "
          f"{pct}% = {wave} / {margin}")
    _wide(margin, wave, pct)


def _wide(margin, wave, pct):
    """A 1440x900 landscape cut of the same card, used as the opening title frame
    of the studio-e2e video so its first (autoplay) frame carries the claim."""
    fig = plt.figure(figsize=(14.4, 9.0))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def T(x, y, s, size, color=WHITE, weight="normal", ha="left"):
        ax.text(x, y, s, transform=ax.transAxes, fontsize=size, color=color,
                fontweight=weight, ha=ha, va="center")

    T(0.05, 0.92, "POWER DISPATCH STUDIO", 15, MUTE, "bold")
    # left column: the number, the guardrail, the CTA
    T(0.05, 0.63, f"{pct}%", 150, CORAL, "bold")
    T(0.05, 0.40, "Today's data centers are small and did", 15.5, MUTE)
    T(0.05, 0.355, "not cause the recent red alerts. The", 15.5, MUTE)
    T(0.05, 0.31, "question is the announced wave landing", 15.5, MUTE)
    T(0.05, 0.265, "on a grid whose margin is already thin.", 15.5, MUTE)
    ax.plot([0.05, 0.42], [0.17, 0.17], transform=ax.transAxes, color="#24425f", lw=1.2)
    T(0.05, 0.125, "power-dispatch-studio.vercel.app", 18, WHITE, "bold")
    T(0.05, 0.08, "Free. Runs in your browser.", 13.5, MUTE)
    # right column: the headline and the two figures
    rx = 0.50
    T(rx, 0.85, "of the grid's entire spare margin", 25, WHITE, "bold")
    T(rx, 0.795, "is the size of the announced", 25, WHITE, "bold")
    T(rx, 0.74, "data-center wave.", 25, WHITE, "bold")
    y_wave, y_marg, h = 0.55, 0.42, 0.05
    full = 0.30  # leaves room for the "3,629 MW" label before the frame edge
    ax.add_patch(plt.Rectangle((rx, y_wave - h / 2), full * wave / margin, h,
                               transform=ax.transAxes, color=CORAL, zorder=2))
    ax.add_patch(plt.Rectangle((rx, y_marg - h / 2), full, h,
                               transform=ax.transAxes, color=GREEN, zorder=2))
    T(rx, y_wave + 0.055, "ANNOUNCED WAVE", 13, MUTE, "bold")
    T(rx + full * wave / margin + 0.015, y_wave, f"{wave:,} MW", 21, WHITE, "bold")
    T(rx, y_marg + 0.055, "SYSTEM SPARE MARGIN", 13, MUTE, "bold")
    T(rx + full + 0.015, y_marg, f"{margin:,} MW", 21, WHITE, "bold")
    T(rx, 0.30, "1,500 MW: DICT forecast, by 2028.", 13, MUTE)
    T(rx, 0.26, "3,629 MW: IEMOP system supply margin, May 2026.", 13, MUTE)

    out = os.path.join(DOCS, "linkedin-card-wide.png")
    fig.savefig(out, dpi=100, facecolor=BG)
    plt.close(fig)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)  1440x900")


if __name__ == "__main__":
    main()
