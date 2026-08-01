#!/usr/bin/env python3
"""Animated GIF: one Luzon day, generation above and price below.

The old version put megawatts on the left axis and pesos on the right. A dual
axis lets whoever picks the scales pick the apparent correlation too, and the
Tufte veto bans it. Two panels stacked on one shared clock carry the same
comparison, and let a reader read each series against its own zero.

The day plays out interval by interval, so the evening ramp arrives rather than
sitting there already finished.

Reads web/data/price_load.json. Output docs/supply-demand-day.gif.
"""
import json
import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")


def hour_of(ti):
    """'6/20/2026 6:35:00 PM' -> fractional hour."""
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


def ground(fig, field="day"):
    lo, hi = cs.FIELDS[field]
    gnd = fig.add_axes([0, 0, 1, 1], zorder=0)
    gnd.imshow(np.linspace(0, 1, 256).reshape(-1, 1),
               cmap=LinearSegmentedColormap.from_list("f", [hi, lo]),
               aspect="auto", extent=(0, 1, 0, 1), interpolation="bicubic")
    gnd.set_xticks([])
    gnd.set_yticks([])
    for s in gnd.spines.values():
        s.set_visible(False)


def main():
    D = json.load(open(os.path.join(WEB, "price_load.json")))["representative_day"]
    rows = D["series"]["luzon"]
    day = datetime.strptime(D["date"], "%Y-%m-%d").strftime("%-d %B %Y")
    hours = np.array([hour_of(r["t"]) for r in rows], float)
    gen = np.array([r["gen_mw"] for r in rows], float)
    pr = np.array([r["price"] for r in rows], float)
    order = np.argsort(hours)
    hours, gen, pr = hours[order], gen[order], pr[order]

    peak_i, trough_i = int(np.argmax(pr)), int(np.argmin(pr))
    swing = pr[peak_i] - pr[trough_i]
    # the load band dips overnight and recovers; it does not climb all day,
    # and the title has to say what the panels show
    dem_pct = 100.0 * (gen.max() - gen.min()) / gen.max()

    fdir = cs.frames_dir("sdd")
    for fi, t in enumerate(cs.reveal(40, 18)):
        n = max(2, int(round(len(rows) * t)))
        cs.apply()
        fig = plt.figure(figsize=(8.8, 5.3), facecolor=cs.BG)
        ground(fig)
        ax1 = fig.add_axes([0.085, 0.470, 0.605, 0.300], facecolor="none", zorder=2)
        ax2 = fig.add_axes([0.085, 0.180, 0.605, 0.230], facecolor="none", zorder=2)
        for a in (ax1, ax2):
            cs.tufte(a)

        ax1.fill_between(hours[:n], 0, gen[:n], color=cs.STEEL, alpha=0.15, zorder=3)
        cs.glow(ax1, hours[:n], gen[:n], cs.STEEL, lw=1.7, zorder=4)
        ax1.set_ylim(0, gen.max() * 1.20)
        ax1.set_xlim(0, 24)
        ax1.set_xticks([])
        ax1.set_ylabel("generation meeting\ndemand, MW", fontsize=8.4)

        cs.glow(ax2, hours[:n], pr[:n], cs.CORAL, lw=1.7, zorder=4)
        ax2.set_ylim(min(0.0, pr.min() * 1.2), pr.max() * 1.30)
        ax2.set_xlim(0, 24)
        ax2.set_xticks([0, 6, 12, 18, 24])
        ax2.set_xticklabels(["12am", "6am", "noon", "6pm", "12am"])
        ax2.set_ylabel("WESM price\nPhP per kWh", fontsize=8.4)

        if n > peak_i:
            cs.dot(ax2, hours[peak_i], pr[peak_i], cs.CORAL, size=28, zorder=7)
            cs.chip(ax2, hours[peak_i], pr[peak_i] * 1.19,
                    f"P{pr[peak_i]:.2f} at the peak", cs.CORAL, 8.6)
        if n > trough_i:
            cs.chip(ax2, hours[trough_i], pr[trough_i] + pr.max() * 0.17,
                    f"P{pr[trough_i]:.2f} overnight", cs.MUTE, 8.4)

        cs.title(fig,
                 f"Demand moves {dem_pct:.0f}% across the day. "
                 f"The price moves P{swing:.0f}.",
                 f"One Luzon day from the archive, {day}, every 5-minute interval.")
        if t > 0.9:
            cs.payoff(fig, 0.735, 0.585, f"P{swing:.2f}",
                      "overnight low to evening peak,\non the same day",
                      cs.CORAL, 31)
        cs.source(fig,
                  "Generation and price share one clock, and each reads against "
                  "its own zero.\nFrom IEMOP RTDSUM generation and LWAPF "
                  "price, archived.")
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=104, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, os.path.join(DOCS, "supply-demand-day.gif"), fps=13, width=880)


if __name__ == "__main__":
    main()
