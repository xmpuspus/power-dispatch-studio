#!/usr/bin/env python3
"""The wholesale-to-retail wedge, built on the actual Meralco peso breakdown. A move
in the WESM wholesale price only touches the generation slice of the bill, and only
through a monthly pass-through, so a wholesale swing is never a one-for-one bill swing.

Reads only web/data/market_anchors.json, so the figure follows the bake. Output
docs/bill-wedge.png.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")
DOCS = os.path.join(ROOT, "docs")


def main():
    A = json.load(open(os.path.join(WEB, "market_anchors.json")))
    total = A["meralco_june2026_rate_php_kwh"]        # 14.4833
    gen = A["meralco_june2026_generation_charge"]     # 9.0704
    wesm = A["meralco_june2026_wesm_cost_php_kwh"]     # 7.0281
    other = round(total - gen, 4)                     # transmission, distribution, taxes, etc
    gen_non_wesm = round(gen - wesm, 4)               # IPP + other generation inside the charge

    fig, ax = plt.subplots(figsize=(9.4, 3.6))
    # one horizontal bar, the whole Meralco rate, split into three slices
    segs = [
        ("WESM (spot) cost", wesm, vz.CORAL, True),
        ("rest of\ngeneration", gen_non_wesm, vz.STEEL, False),
        ("transmission, distribution,\ntaxes and the rest", other, vz.FILL, False),
    ]
    left = 0
    for name, val, color, hi in segs:
        share = 100 * val / total
        ax.barh(0, share, left=left, color=color, height=0.5,
                edgecolor="white", linewidth=1.6, zorder=3)
        tc = "white" if hi else vz.NAVY
        if share < 18:
            # narrow slice: label below the bar with a tick so text never clips
            ax.text(left + share / 2, -0.42,
                    f"{name.replace(chr(10), ' ')}\nP{val:.2f} ({share:.0f}%)",
                    ha="center", va="top", fontsize=8, color=vz.NAVY)
            ax.plot([left + share / 2, left + share / 2], [-0.25, -0.34],
                    color=vz.MUTE, lw=0.8)
        else:
            ax.text(left + share / 2, 0,
                    f"{name}\nP{val:.2f}/kWh ({share:.0f}%)", ha="center",
                    va="center", fontsize=9, color=tc,
                    fontweight="bold" if hi else "normal")
        left += share

    wesm_share = 100 * wesm / total
    ax.annotate("a swing in the WESM spot price moves\nONLY this slice, and only next month",
                xy=(wesm_share / 2, 0.26), xytext=(wesm_share / 2 + 6, 0.74),
                ha="center", fontsize=9.5, color=vz.NAVY,
                arrowprops=dict(arrowstyle="->", color=vz.NAVY, lw=1.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(-1.05, 1.05)
    ax.set_yticks([])
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%",
                        f"100% = P{total:.2f}/kWh"], fontsize=9)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(vz.MUTE)
    ax.tick_params(length=0)
    ax.set_title("A swing in the WESM price is only a slice of the Meralco bill",
                 fontsize=13.5, color=vz.NAVY, pad=12, loc="left")
    fig.text(0.5, -0.05,
             f"Meralco June 2026 residential rate, P{total:.2f}/kWh. The generation "
             f"charge (P{gen:.2f}) is the largest part, and WESM (P{wesm:.2f}) sits "
             f"inside it, passed through monthly. A jump in the spot price moves that "
             f"one slice on the next bill, not the whole bill and not the same day. "
             f"Source: Meralco June 2026 advisory.",
             ha="center", fontsize=8.5, color=vz.MUTE, wrap=True)
    fig.tight_layout()
    out = os.path.join(DOCS, "bill-wedge.png")
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
