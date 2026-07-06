#!/usr/bin/env python3
"""Animated GIF: one real Luzon day, dispatched generation meeting demand through 24 hours, with the WESM price tracking
it. Deep supply keeps the price low most of the day; it climbs into the evening peak
and spikes when the grid runs tight.

Reads the baked web/data/price_load.json representative day, so the figure follows
the bake. Output docs/supply-demand-day.gif.
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
FRAMES = "/tmp/gridbill_sd_frames"
DATA = os.path.join(ROOT, "web", "data", "price_load.json")


def hour_of(ti):
    # "6/20/2026 6:35:00 PM" -> fractional hour
    try:
        t = ti.split(" ", 1)[1]
        hm, _, ap = t.rpartition(" ")
        h, m, _s = hm.split(":")
        h, m = int(h) % 12, int(m)
        if ap.upper() == "PM":
            h += 12
        return h + m / 60
    except Exception:
        return 0.0


def main():
    D = json.load(open(DATA))
    rep = D["representative_day"]
    day = rep["date"]
    lz = rep["series"]["luzon"]
    hrs = [hour_of(p["t"]) for p in lz]
    gen = [p["gen_mw"] for p in lz]
    price = [p["price"] for p in lz]

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    gmax = max(gen)
    reveal = list(range(6, len(lz) + 1, 6))
    if reveal[-1] != len(lz):
        reveal.append(len(lz))
    frames = reveal + [len(lz)] * 10

    for fi, upto in enumerate(frames):
        fig, ax = plt.subplots(figsize=(8.8, 5.0))
        ax2 = ax.twinx()
        # demand met by dispatched generation, as a filled area (the supply soaking
        # up the demand); price as the line on the right axis
        ax.fill_between(hrs[:upto], gen[:upto], color="#dbe4ec", zorder=1)
        ax.plot(hrs[:upto], gen[:upto], color=vz.STEEL, lw=1.8, zorder=2)
        ax2.plot(hrs[:upto], price[:upto], color=vz.CORAL, lw=2.2, zorder=3)
        if upto:
            ax.scatter([hrs[upto - 1]], [gen[upto - 1]], s=26, color=vz.STEEL, zorder=4)
            ax2.scatter([hrs[upto - 1]], [price[upto - 1]], s=26, color=vz.CORAL, zorder=4)

        ax.set_xlim(0, 24)
        ax.set_ylim(0, gmax * 1.12)
        ax2.set_ylim(-3, max(20, max(price) + 3))
        ax.set_xticks([0, 6, 12, 18, 24])
        ax.set_xticklabels(["12am", "6am", "noon", "6pm", "12am"])
        ax.set_xlabel(f"hour of the day, Luzon, {day}", fontsize=10.5)
        ax.set_ylabel("dispatched generation meeting demand  (MW)",
                      fontsize=10.5, color=vz.STEEL)
        ax2.set_ylabel("WESM price  (PhP per kWh)", fontsize=10.5, color=vz.CORAL)
        ax.tick_params(axis="y", colors=vz.STEEL)
        ax2.tick_params(axis="y", colors=vz.CORAL)
        ax.set_title("Deep supply keeps the price low, until the evening peak",
                     fontsize=13.5, color=vz.NAVY, loc="left")
        vz.tufte(ax, grid="y")
        ax2.spines["top"].set_visible(False)
        vz.caption(fig,
                   "One Luzon day from the archive. The band is generation meeting "
                   "demand through the day. The coral line is the price. The price "
                   "stays low while there is room and climbs into the evening peak. "
                   "Source: IEMOP RTDSUM generation and LWAPF price, archived.",
                   y=-0.05)
        fig.tight_layout()
        fig.savefig(os.path.join(FRAMES, f"f{fi:03d}.png"), dpi=110,
                    bbox_inches="tight", facecolor="white")
        plt.close(fig)

    out = os.path.join(DOCS, "supply-demand-day.gif")
    pal = "/tmp/gridbill_sd_pal.png"
    vf = "fps=11,scale=880:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(FRAMES, "f%03d.png"),
                    "-vf", vf + ",palettegen=stats_mode=diff", pal], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-framerate", "11",
                    "-i", os.path.join(FRAMES, "f%03d.png"), "-i", pal,
                    "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                    out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote", out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
