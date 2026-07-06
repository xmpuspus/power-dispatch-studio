#!/usr/bin/env python3
"""Animated GIF: the Sual arithmetic. The May 2026 system margin is one bar; one
647 MW Sual unit is subtracted, then the second, showing why a single trip of the
grid's largest units moves the whole system. Arithmetic on the published margin,
never a dispatch simulation.

Reads only web/data/market_anchors.json + sual.geojson. Output docs/sual-margin.gif.
"""
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FRAMES = "/tmp/gridbill_sual_frames"
WEB = os.path.join(ROOT, "web", "data")


def main():
    A = json.load(open(os.path.join(WEB, "market_anchors.json")))
    sual = json.load(open(os.path.join(WEB, "sual.geojson")))["features"][0]["properties"]
    margin = A["wesm_may2026_margin_mw"]
    unit = sual["unit_mw"]

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    # three states: full margin, minus one unit, minus two units. Ease between.
    stops = [margin, margin - unit, margin - 2 * unit]
    labels = ["May 2026 system margin",
              "after one Sual unit trips (-647 MW)",
              "after both units trip (-1,294 MW)"]
    seq = []
    for k in range(len(stops) - 1):
        a, b = stops[k], stops[k + 1]
        for s in range(22):
            t = s / 21
            seq.append((a + (b - a) * t, k, k + 1, t))
        seq += [(b, k + 1, k + 1, 1.0)] * 12
    seq = [(stops[0], 0, 0, 1.0)] * 12 + seq

    for fi, (val, li, lj, t) in enumerate(seq):
        fig, ax = plt.subplots(figsize=(8.4, 4.8))
        # ghost of the full margin
        ax.bar([0], [margin], width=0.5, color=vz.FILL, zorder=1)
        col = vz.CORAL if val < margin - unit + 1 else (
            vz.GOLD if val < margin - 1 else vz.GREEN)
        ax.bar([0], [val], width=0.5, color=col, zorder=3)
        ax.text(0, val + 55, f"{int(round(val)):,} MW", ha="center",
                fontsize=15, fontweight="bold", color=vz.NAVY)
        ax.text(0, margin + 55, f"full margin {margin:,} MW", ha="center",
                fontsize=9, color=vz.MUTE)
        lab = labels[lj] if t > 0.5 else labels[li]
        ax.text(0, -230, lab, ha="center", fontsize=11, color=col, fontweight="bold")
        ax.text(0.62, margin * 0.5,
                f"one unit = {round(100 * unit / margin)}%\nof the margin",
                fontsize=10, color=vz.MUTE, va="center")
        ax.set_xlim(-0.7, 1.1)
        ax.set_ylim(-320, margin * 1.16)
        ax.set_xticks([])
        ax.set_ylabel("megawatts of system supply margin", fontsize=10.5)
        ax.set_title("One plant trip takes a fifth of the margin with it",
                     fontsize=14, color=vz.NAVY, loc="left")
        vz.tufte(ax, grid="y")
        vz.caption(fig,
                   "Sual's two 647 MW units are the largest single contingencies on "
                   "the Luzon grid. This subtracts a unit from IEMOP's published May "
                   "2026 margin as arithmetic, not a dispatch simulation. The margin "
                   "itself moves daily. Source: IEMOP May 2026 report.", y=-0.03)
        fig.tight_layout()
        fig.savefig(os.path.join(FRAMES, f"f{fi:03d}.png"), dpi=110,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

    out = os.path.join(DOCS, "sual-margin.gif")
    pal = "/tmp/gridbill_sual_pal.png"
    vf = "fps=12,scale=840:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(FRAMES, "f%03d.png"),
                    "-vf", vf + ",palettegen=stats_mode=diff", pal], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-framerate", "12",
                    "-i", os.path.join(FRAMES, "f%03d.png"), "-i", pal,
                    "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                    out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
