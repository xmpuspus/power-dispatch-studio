#!/usr/bin/env python3
"""Animated GIF: the price is a shape, not a number. A data center plugs in the same power every hour, but the effect on the WESM
price depends on how busy the grid already is. Nearly nothing when there is room, a
jump when the grid is full.

Reads the baked web/data/price_load.json (Luzon generation joined to price, from the
archive), so the figure follows the bake. Output docs/price-shape.gif.
"""
import json
import os
import subprocess
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402
vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FRAMES = "/tmp/pds_shape_frames"
DATA = os.path.join(ROOT, "web", "data", "price_load.json")

DC_MW = 300   # one large campus, e.g. the announced Narra Technology Park (3 x 100 MW)


def main():
    D = json.load(open(DATA))
    curve = D["curve"]["luzon"]
    scat = D["scatter"]["luzon"]
    x = np.array([c["gen_mw"] for c in curve], float)
    y = np.array([c["mean_price"] for c in curve], float)
    sx = np.array([p[0] for p in scat], float)
    sy = np.clip(np.array([p[1] for p in scat], float), -5, 40)

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    lo, hi = x.min() + 200, x.max() - DC_MW - 200
    sweep = np.linspace(lo, hi, 34)
    positions = np.concatenate([sweep, sweep[::-1]])   # ping-pong for a smooth loop

    for i, xc in enumerate(positions):
        y0 = float(np.interp(xc, x, y))
        y1 = float(np.interp(xc + DC_MW, x, y))
        bump = y1 - y0
        tight = xc > (lo + 0.6 * (hi - lo))
        col = vz.CORAL if tight else vz.STEEL
        verdict = ("price jumps" if bump > 1.2 else
                   "price nudges up" if bump > 0.35 else "price barely moves")

        fig, ax = plt.subplots(figsize=(8.6, 5.0))
        ax.scatter(sx, sy, s=4, alpha=0.06, color="#9fb2c4",
                   edgecolors="none", zorder=1, rasterized=True)
        ax.plot(x, y, color=vz.NAVY, lw=2.6, zorder=3)
        ax.scatter([xc], [y0], s=110, color=col, zorder=5)
        ax.annotate("", xy=(xc + DC_MW, y1), xytext=(xc, y0),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=2.4), zorder=4)
        ax.text(xc, y0 - 1.7, "the grid right now", ha="center", fontsize=9.5,
                color=vz.NAVY)
        ax.text(xc + DC_MW * 0.5, (y0 + y1) / 2 + 0.6,
                f"+ one {DC_MW} MW data center", fontsize=9.5, color=col)
        ax.text(0.5, 0.94, f"{verdict}, about +P{bump:.2f}/kWh",
                transform=ax.transAxes, ha="center", fontsize=15,
                fontweight="bold", color=col)

        ax.set_xlim(x.min() - 300, x.max() + 300)
        ax.set_ylim(-2, max(16, y.max() + 2))
        ax.set_xlabel("how busy the Luzon grid is  (dispatched generation, MW, busier to the right)",
                      fontsize=10.5)
        ax.set_ylabel("WESM price  (PhP per kWh)", fontsize=10.5)
        ax.set_title("Same data center. The price effect depends on how busy the grid is.",
                     fontsize=13.5, color=vz.NAVY, loc="left")
        vz.tufte(ax, grid="y")
        vz.caption(fig,
                   "Each faint dot is one five-minute interval on the Luzon grid. The "
                   "line is the average price at each load. A data center adds the "
                   "same megawatts every hour, but when the grid has room the price "
                   f"hardly notices and when it is full the same {DC_MW} MW shoves it "
                   "up. Source: IEMOP RTDSUM generation joined to LWAPF price, archived.",
                   y=-0.05)
        fig.tight_layout()
        fig.savefig(os.path.join(FRAMES, f"f{i:03d}.png"), dpi=110,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

    out = os.path.join(DOCS, "price-shape.gif")
    pal = "/tmp/pds_shape_pal.png"
    vf = "fps=12,scale=860:-1:flags=lanczos"
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
