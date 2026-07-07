#!/usr/bin/env python3
"""Animated GIF: the constraint league fills in bar by bar, named equipment ranked
by how many of the window's days it sat at a binding limit. The lesson is that the
grid names its own choke point, and one corridor tops the list.

Reads only web/data/congestion.json. Frames in matplotlib, GIF assembled by ffmpeg.
Output docs/constraint-league.gif.
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
FRAMES = "/tmp/pds_league_frames"
DATA = os.path.join(ROOT, "web", "data", "congestion.json")

# The Leyte-Cebu corridor lines: highlight in coral, everything else steel.
CORRIDOR = {"5DAAN_4TAB2", "5DAAN_4TAB1", "LEYTE_TO_CEBU"}


def main():
    C = json.load(open(DATA))
    days_covered = C["days_covered"]
    league = C["league"][:12]
    labels = [f'{e["equipment"]}  ({e["station"]})' for e in league]
    vals = [e["days"] for e in league]
    cols = [vz.CORAL if e["equipment"] in CORRIDOR else vz.STEEL for e in league]
    y = list(range(len(league)))[::-1]

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    steps = 26
    grow = [min(1.0, (s + 1) / steps) for s in range(steps)]
    frames = grow + [1.0] * 12

    for fi, g in enumerate(frames):
        fig, ax = plt.subplots(figsize=(8.8, 5.2))
        widths = [v * g for v in vals]
        ax.barh(y, widths, color=cols, height=0.72, zorder=3)
        for yi, e, w in zip(y, league, widths):
            if g > 0.55:
                ax.text(w + 0.6, yi, f'{int(round(w))}', va="center",
                        fontsize=9, color=vz.NAVY,
                        fontweight="bold" if e["equipment"] in CORRIDOR else "normal")
        ax.axvline(days_covered, color=vz.MUTE, lw=1.0, ls=(0, (3, 3)), zorder=2)
        ax.text(days_covered, len(league) - 0.3, f" all {days_covered} days",
                fontsize=8.5, color=vz.MUTE, va="top")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlim(0, days_covered + 8)
        ax.set_xlabel("days at a binding limit in the archive window", fontsize=10.5)
        ax.set_title("The grid names its own choke point",
                     fontsize=14, color=vz.NAVY, loc="left")
        vz.tufte(ax, grid="x")
        vz.caption(fig,
                   "Each bar is a named piece of transmission equipment from IEMOP's "
                   "congestions-manifesting files, ranked by days at a limit (a day "
                   "counts once). Coral is the Leyte-Cebu corridor. "
                   "Source: IEMOP RTDCV and DAPCV, archived.", y=-0.03)
        fig.tight_layout()
        fig.savefig(os.path.join(FRAMES, f"f{fi:03d}.png"), dpi=110,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

    out = os.path.join(DOCS, "constraint-league.gif")
    pal = "/tmp/pds_league_pal.png"
    vf = "fps=12,scale=880:-1:flags=lanczos"
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
