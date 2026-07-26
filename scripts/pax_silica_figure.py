#!/usr/bin/env python3
"""Where Pax Silica's 3,000 megawatts would come from, in the evening peak.

BCDA says the campus at New Clark City will build its own power rather than take
3,000 MW from the grid. This tests that against the network. The question is
about parts of a whole, so the picture is too. Four bars, each the same 3,000 MW
long, cut into where those megawatts come from.

Everything is drawn at 7pm, because that is when demand is highest and when
the solar farm has stopped for the day. A second small panel
shows the solar day so the zero at 7pm is visible rather than asserted.

How much can come over the lines is the only figure here the model works out.
It is the limit on the two Concepcion to Clark 230 kV circuits, worked out for
each hour on the reduced network for one recorded day. Flow rises in step with
the load added, so two runs an hour find the crossing point exactly, and a third
run at that point sits on the rating.

Writes docs/pax-silica-embedded.png. Kept out of `make viz`, since the nightly
rebuild does not need it.
"""
import json
import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vizstyle as vz  # noqa: E402

vz.apply()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
CACHE = "/tmp/pds_pax_headroom.json"
DAY = "2026-06-25"
HOUR = 19
NEED_MW = 3000.0
SOLAR_MW = 500.0

# each row is (label, own round-the-clock plant MW, own solar MW, the stricter
# figure from solving the whole Luzon network rather than these two lines alone)
ROWS = [
    ("All of it from the grid", 0.0, 0.0, 2471.0),
    ("Grid plus the 500 MW solar farm", 0.0, SOLAR_MW, 2471.0),
    ("Its own 2,500 MW station, plus 500 from the grid", 2500.0, SOLAR_MW, 163.0),
    ("Same station, one 600 MW unit down", 1900.0, SOLAR_MW, 661.0),
]

# drawn left to right. The grid segment is anchored at zero on every bar so one
# reference line reads across all four; the personas who misread the earlier
# version all did so because a shared series moved position between panels.
SEGMENTS = [
    ("from the grid, over its two lines", vz.STEEL),
    ("its own power station", vz.NAVY),
    ("its own solar farm", vz.GOLD),
    ("no source for this", vz.CORAL),
]


def headroom() -> dict:
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    sys.path.insert(0, os.path.join(ROOT, "pipeline"))
    from nodal_dcopf import (SITES, _load_day, _plant_load, build_network,
                             hour_injections, map_resources, resolve_site,
                             solve_hour)
    net = build_network()
    day = _load_day(DAY)
    res_bus, _ = map_resources(day, net)
    pax = SITES["pax-silica"]
    site = resolve_site(net, pax["lon"], pax["lat"])
    bus, branches = site["bus"], net["branches"]
    local = [bi for bi, b in enumerate(branches) if b["a"] == bus or b["b"] == bus]
    probe, out = 1000.0, []
    for hr in range(24):
        inj = hour_injections(day, res_bus, net, hr)
        s0 = solve_hour(net, _plant_load(inj, net, bus, 0.0), "replay")
        s1 = solve_hour(net, _plant_load(inj, net, bus, probe), "replay")
        best = None
        for bi in local:
            f0, f1 = s0["flows_mw"][bi], s1["flows_mw"][bi]
            slope = (f1 - f0) / probe
            if abs(slope) < 1e-9:
                continue
            for target in (branches[bi]["rating_mw"], -branches[bi]["rating_mw"]):
                d = (target - f0) / slope
                if d > 0 and (best is None or d < best):
                    best = d
        out.append(round(best, 1))
    res = {"day": DAY, "snap_km": site["snap_km"], "headroom_mw": out}
    json.dump(res, open(CACHE, "w"))
    return res


def split(firm: float, solar_mw: float, solar_now: float, limit: float):
    """The four parts of the 3,000 MW at this hour, in drawing order."""
    own_solar = min(solar_mw * solar_now, NEED_MW)
    own_firm = min(firm, NEED_MW - own_solar)
    residual = NEED_MW - own_firm - own_solar
    over_lines = min(residual, limit)
    missing = residual - over_lines
    return [over_lines, own_firm, own_solar, missing]


def main():
    hd = headroom()
    limit = hd["headroom_mw"][HOUR]
    solar = json.load(
        open(os.path.join(ROOT, "web", "data", "profiles.json")))["solar_profile"]

    fig = plt.figure(figsize=(12.2, 7.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[3.05, 1.0], hspace=0.62)
    ax = fig.add_subplot(gs[0])
    sx = fig.add_subplot(gs[1])

    y = np.arange(len(ROWS))[::-1]
    for i, (label, firm, sol_mw, _strict) in enumerate(ROWS):
        parts = split(firm, sol_mw, solar[HOUR], limit)
        left = 0.0
        for (seg_label, color), value in zip(SEGMENTS, parts):
            if value <= 0:
                continue
            ax.barh(y[i], value, left=left, height=0.52, color=color, lw=0,
                    zorder=3)
            if value > 300:
                ax.text(left + value / 2, y[i], f"{round(value, -1):,.0f}",
                        color=vz.NAVY if color == vz.GOLD else "white",
                        fontsize=11, ha="center", va="center", zorder=5,
                        fontweight="medium")
            left += value
        ax.text(-90, y[i], label, ha="right", va="center", fontsize=11.5,
                color=vz.NAVY)
        # the fuller check, drawn under each bar so row three cannot read as
        # solved when the wider network says it is 160 MW short
        ax.barh(y[i] - 0.40, _strict, left=NEED_MW - _strict, height=0.10,
                color=vz.CORAL, alpha=0.55, lw=0, zorder=3)
        ax.text(NEED_MW - _strict - 40, y[i] - 0.40,
                f"{round(_strict, -1):,.0f} short",
                ha="right", va="center", fontsize=9.5, color=vz.CORAL, zorder=5)

    # the limit, printed and drawn, because the earlier version made readers
    # subtract two numbers to recover the one figure the whole thing turns on
    ax.axvline(limit, color=vz.MUTE, lw=1.4, ls=(0, (4, 3)), zorder=4)
    ax.annotate(f"the two lines carry {round(limit, -1):,.0f} MW",
                xy=(limit + 55, y[0] + 0.60), color=vz.MUTE, fontsize=11,
                ha="left", va="center", zorder=6)
    ax.annotate("one of the two is the only way in, and losing it leaves nothing",
                xy=(limit + 55, y[0] + 0.36), color=vz.CORAL, fontsize=10,
                ha="left", va="center", zorder=6)


    ax.set_xlim(0, NEED_MW * 1.02)
    ax.set_ylim(-0.75, len(ROWS) - 0.15)
    ax.set_xticks([0, 1000, 2000, 3000])
    ax.set_xticklabels(["0", "1,000", "2,000", "3,000 MW"])
    ax.set_yticks([])
    ax.set_title(
        "Pax Silica needs 3,000 MW. The two power lines into the site carry "
        "about 770.",
        fontsize=15, color=vz.NAVY, loc="left", pad=72)
    ax.annotate(
        "A data centre and factory campus proposed at New Clark City, Tarlac.\n"
        "3,000 MW of power is about a fifth of the Luzon grid at its peak.\n"
        "Shown at 7pm, when demand is highest and solar has stopped.",
        xy=(0, 1.028), xycoords="axes fraction", fontsize=11, color=vz.MUTE,
        va="bottom", linespacing=1.55)
    vz.tufte(ax, grid="x")
    for side in ("left",):
        ax.spines[side].set_visible(False)

    # one legend row under the bars. Four stacked segments need a key; the
    # numbers inside the bars are the direct labels doing the reading work.
    shown = [(t, c) for t, c in SEGMENTS if c != vz.GOLD]
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, lw=0) for _, c in shown]
    handles.append(plt.Rectangle((0, 0), 1, 1, color=vz.CORAL, alpha=0.55, lw=0))
    labels = [t for t, _ in shown] + ["short, checked against the whole grid"]
    ax.legend(handles, labels, loc="upper center",
              bbox_to_anchor=(0.5, -0.07), ncol=4, frameon=False,
              handlelength=1.1, handleheight=1.0, columnspacing=1.3,
              fontsize=10, labelcolor=vz.NAVY)

    # why the solar column is empty at 7pm
    hours = np.arange(24)
    out = np.array([SOLAR_MW * s for s in solar])
    sx.fill_between(hours, 0, out, color=vz.GOLD, alpha=0.9, lw=0, zorder=3)
    sx.axvline(HOUR, color=vz.CORAL, lw=1.6, zorder=4)
    sx.annotate("by 7pm, none left", xy=(HOUR - 0.4, 300), color=vz.CORAL,
                fontsize=10.5, ha="right", zorder=5)
    sx.set_xlim(-0.5, 23.5)
    sx.set_ylim(0, 460)
    sx.set_xticks([0, 6, 12, 18])
    sx.set_xticklabels(["midnight", "6am", "noon", "6pm"])
    sx.set_yticks([0, 400])
    sx.set_yticklabels(["0", "400 MW"])
    sx.set_title("The solar farm makes nothing in the evening, when demand is highest",
                 fontsize=12, color=vz.NAVY, loc="left")
    vz.tufte(sx, grid="y")

    vz.caption(
        fig,
        "The 3,000 MW is BCDA's figure for full development, held flat. The solar "
        "is the 500 MW ACWA project on a cloudless day. NGCP does not publish "
        "what the two Concepcion to Clark lines are rated to carry, so the model "
        "uses the standard rating for 230 kV. What was worked out for every hour "
        "of one real day, 25 June 2026, is how much more the site could draw "
        "before reaching that rating, given the power already flowing on those "
        "lines. Every number moves if the real rating differs, so treat them all "
        "as approximate. The thin bars ask the same question of the whole Luzon "
        "grid, which finds more bottlenecks past these two lines, so the real "
        "shortfall is bigger in every row including the third. The two circuits "
        "are two segments of one route rather than two separate ways in. In this "
        "map one of them is the site's only connection to the rest of the grid, "
        "and losing that one takes it to zero. Whether the real grid has a second "
        "route is not something a public map can answer, and no line outage is "
        "modelled here. The 2,500 MW station is a size chosen for this "
        "comparison, not an announced project. In the third row the site needs "
        "only 500 MW from the grid, so that is all it takes. In the fourth it "
        "needs 1,100 and takes everything the lines allow. BCDA is the government "
        "agency developing the site. NGCP runs the transmission grid. ACWA is the "
        "solar developer.",
        y=0.015)
    fig.subplots_adjust(left=0.26, right=0.975, top=0.79, bottom=0.15)
    png = os.path.join(DOCS, "pax-silica-embedded.png")
    fig.savefig(png, dpi=110, facecolor="white")
    plt.close(fig)
    print("wrote", png, f"({os.path.getsize(png) // 1024} KB)")


if __name__ == "__main__":
    main()
