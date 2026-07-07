#!/usr/bin/env python3
"""Animated GIF: the three island grids priced as one under administered pricing,
then fanned apart the moment WESM trading resumed. The one-line lesson is that the
inter-island links are the geography, and the market prices that geography daily.

Reads only the baked web/data/prices.json, so the figure follows the bake. Renders
frames with matplotlib, assembles with ffmpeg (palette two-pass, never PIL for the
GIF). Output docs/price-spread.gif.
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
FRAMES = "/tmp/pds_spread_frames"
DATA = os.path.join(ROOT, "web", "data", "prices.json")


def main():
    P = json.load(open(DATA))
    dates = P["dates"]
    resumed = P.get("resumed", "2026-05-01")
    series = {g: P["series"][g] for g in ("luzon", "visayas", "mindanao")}
    resume_i = next((i for i, d in enumerate(dates) if d >= resumed), 0)

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    n = len(dates)
    ymax = max(v for g in series.values() for v in g if v is not None) * 1.08
    reveal = list(range(4, n + 1, 2))
    if reveal[-1] != n:
        reveal.append(n)
    hold = [n] * 10

    for fi, upto in enumerate(reveal + hold):
        fig, ax = plt.subplots(figsize=(8.6, 4.8))
        ax.axvspan(0, resume_i, color=vz.FILL, zorder=0)
        for g, col in vz.REGION.items():
            xs = [i for i in range(upto) if series[g][i] is not None]
            ys = [series[g][i] for i in xs]
            if xs:
                ax.plot(xs, ys, color=col, lw=2.0, zorder=3)
                ax.scatter([xs[-1]], [ys[-1]], s=26, color=col, zorder=4)
                ax.text(xs[-1] + 0.6, ys[-1], g.title(), color=col, fontsize=10,
                        va="center", fontweight="bold")
        ax.axvline(resume_i, color=vz.MUTE, lw=1.0, ls=(0, (4, 3)), zorder=2)
        ax.text(resume_i - 1.5, ymax * 0.96, "WESM suspended\n(administered prices)",
                ha="right", va="top", fontsize=8.5, color=vz.MUTE)
        ax.text(resume_i + 1.5, ymax * 0.96, "market resumes 2026-05-01",
                ha="left", va="top", fontsize=8.5, color=vz.NAVY)
        ax.set_xlim(0, n + 9)
        ax.set_ylim(0, ymax)
        ax.set_ylabel("daily average price  (PhP per kWh)", fontsize=10.5)
        ax.set_xlabel("archive days, 2026-04-07 to 2026-06-25", fontsize=10.5)
        ax.set_xticks([])
        ax.set_title("One market on paper, three prices in practice",
                     fontsize=14, color=vz.NAVY, loc="left")
        vz.tufte(ax, grid="y")
        vz.caption(fig,
                   "Each line is one island grid's daily average of IEMOP's "
                   "load-weighted five-minute prices. Under administered pricing the "
                   "grids move together. Once the market reopens the links between "
                   "them separate the prices. Source: IEMOP LWAPF, archived.",
                   y=-0.04)
        fig.tight_layout()
        fig.savefig(os.path.join(FRAMES, f"f{fi:03d}.png"), dpi=110,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

    out = os.path.join(DOCS, "price-spread.gif")
    pal = "/tmp/pds_spread_pal.png"
    vf = "fps=10,scale=860:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(FRAMES, "f%03d.png"),
                    "-vf", vf + ",palettegen=stats_mode=diff", pal], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-framerate", "10",
                    "-i", os.path.join(FRAMES, "f%03d.png"), "-i", pal,
                    "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                    out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
