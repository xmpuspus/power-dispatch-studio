#!/usr/bin/env python3
"""Animated GIF: the constraint league on the actual grid, kepler.gl style.

The bar chart version ranks named transmission equipment by days at a binding
limit and says nothing about where any of it is. The whole finding is
geographic: one corridor between two islands tops the league, and the rest
clusters on the Luzon backbone. So this draws the same league on the real
network, dark canvas, glowing nodes, and an arc for the corridor.

What is real here and what is not:
  - Every line is OpenStreetMap geometry (ODbL), community-mapped, and is NOT
    NGCP's own network model. Geometry only, no ratings.
  - Every dot is a named OSM substation, resolved through constants_ph
    .STATION_OSM, never a fuzzy name match and never snapped to a near-miss.
  - Dot area is days at a binding limit, a day counted once, which is the
    league's own ranking field. The white core is real-time days, the smaller
    count and the one settlement sees. The card states both, because collapsing
    them into one dot hides the split the README keeps in separate columns.

Reads web/data/congestion.json, grid_lines.geojson and grid_nodes.geojson.
Frames in matplotlib, GIF assembled by ffmpeg. Output docs/constraint-map.gif.

    python3.12 scripts/constraint_map_gif.py
"""

import json
import math
import os
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
from constants_ph import CORRIDOR_ARC, STATION_OSM, STATION_UNPLACED  # noqa: E402

DOCS = os.path.join(ROOT, "docs")
WEB = os.path.join(ROOT, "web", "data")
FRAMES = "/tmp/pds_cmap_frames"
OUT = os.path.join(DOCS, "constraint-map.gif")

# kepler.gl dark: near-black canvas, one cool hue for context, one hot accent
BG = "#080b10"
# the network reads as the country only if it is bright enough to see, so the
# three voltage classes get three weights rather than one dim grey
VOLT = {
    "ac500": ("#4d90c8", 1.15, 0.95),
    "hvdc": ("#4d90c8", 1.05, 0.90),
    "cable": ("#3f7fae", 0.75, 0.85),
    "ac230": ("#2a5c8a", 0.62, 0.85),
    "ac138": ("#1d4062", 0.45, 0.75),
}
VOLT_DEF = ("#17324c", 0.40, 0.65)
COOL = "#4cc9f0"  # ordinary constrained equipment
HOT = "#ff5c39"  # the Leyte-Cebu corridor
TEXT = "#e9edf2"
MUTE = "#8592a3"
CORRIDOR = {"5DAAN_4TAB2", "5DAAN_4TAB1", "LEYTE_TO_CEBU"}
TOP_N = 12
PAD = 0.45  # degrees of margin around the network


def load():
    C = json.load(open(os.path.join(WEB, "congestion.json")))
    lines = json.load(open(os.path.join(WEB, "grid_lines.geojson")))["features"]
    nodes = json.load(open(os.path.join(WEB, "grid_nodes.geojson")))["features"]
    by_name = {}
    for f in nodes:
        n = (f["properties"].get("name") or "").strip()
        if n and n not in by_name:
            by_name[n] = f["geometry"]["coordinates"]
    return C, lines, by_name


def gc_km(a, b):
    """Great-circle km between two lon/lat points."""
    R = 6371.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dl, dp = math.radians(b[0] - a[0]), p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def bezier(a, b, bulge=0.22, n=48):
    """A kepler-style arc: quadratic bezier bulging left of the a->b vector."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    cx, cy = mx - dy * bulge, my + dx * bulge
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append(
            (
                u * u * a[0] + 2 * u * t * cx + t * t * b[0],
                u * u * a[1] + 2 * u * t * cy + t * t * b[1],
            )
        )
    return pts


def main():
    C, lines, by_name = load()
    days_covered = C["days_covered"]

    # one row per station, carrying its worst equipment on that station
    seen, ranked = set(), []
    for r in C["league"]:
        st = r["station"]
        if st in seen or st not in STATION_OSM:
            continue
        osm = STATION_OSM[st]
        if osm not in by_name:
            continue
        seen.add(st)
        ranked.append(
            {**r, "osm": osm, "xy": by_name[osm], "hot": r["equipment"] in CORRIDOR}
        )
    # rank on the league's own field: days at a limit, a day counted once.
    # dap_days is 0 for equipment that only ever bound in real time, which
    # printed a bare "0" beside an empty bar.
    ranked = ranked[:TOP_N]
    placed = len(ranked)
    top = max(r["days"] for r in ranked)

    arc = None
    if all(s in STATION_OSM and STATION_OSM[s] in by_name for s in CORRIDOR_ARC):
        arc = bezier(
            by_name[STATION_OSM[CORRIDOR_ARC[0]]], by_name[STATION_OSM[CORRIDOR_ARC[1]]]
        )

    # fit the frame to the network instead of guessing a bounding box; a
    # hardcoded one spent half the canvas on empty sea
    xs, ys = [], []
    for f in lines:
        g = f["geometry"]
        for s in [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]:
            for p in s:
                xs.append(p[0])
                ys.append(p[1])
    x0, x1 = min(xs) - PAD, max(xs) + PAD
    y0, y1 = min(ys) - PAD, max(ys) + PAD
    lat0 = (y0 + y1) / 2

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))

    # one frame per node lighting up, then the arc, then a hold
    n_frames = placed + 16

    for fi in range(n_frames):
        fig = plt.figure(figsize=(8.6, 5.9), facecolor=BG)
        gs = fig.add_gridspec(
            1,
            2,
            width_ratios=[0.70, 1.0],
            wspace=0.03,
            left=0.012,
            right=0.988,
            top=0.855,
            bottom=0.115,
        )
        ax = fig.add_subplot(gs[0, 0], facecolor=BG)
        bx = fig.add_subplot(gs[0, 1], facecolor=BG)

        # --- the network, as context -----------------------------------------
        for f in lines:
            g = f["geometry"]
            segs = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            col, lw, al = VOLT.get(f["properties"].get("kind"), VOLT_DEF)
            for s in segs:
                sx = [p[0] for p in s]
                sy = [p[1] for p in s]
                if lw > 1.0:  # a soft glow under the backbone
                    ax.plot(
                        sx,
                        sy,
                        color=col,
                        lw=lw * 3.2,
                        alpha=0.10,
                        zorder=1,
                        solid_capstyle="round",
                    )
                ax.plot(
                    sx, sy, color=col, lw=lw, alpha=al, zorder=2, solid_capstyle="round"
                )

        # --- the corridor arc, drawn once the two end stations are lit --------
        lit = min(fi + 1, placed)
        ends_lit = sum(1 for r in ranked[:lit] if r["station"] in CORRIDOR_ARC)
        if arc and ends_lit == 2:
            grow = min(1.0, (fi - placed + 6) / 6) if fi >= placed - 6 else 0.35
            k = max(2, int(len(arc) * min(1.0, max(0.35, grow))))
            pth = MPath(arc[:k])
            for w, a in ((7.0, 0.10), (4.0, 0.18), (1.9, 0.95)):
                ax.add_patch(
                    PathPatch(
                        pth,
                        fill=False,
                        edgecolor=HOT,
                        lw=w,
                        alpha=a,
                        zorder=4,
                        capstyle="round",
                    )
                )

        # --- the constrained stations, lighting up in rank order --------------
        for i, r in enumerate(ranked):
            if i >= lit:
                break
            x, y = r["xy"]
            col = HOT if r["hot"] else COOL
            base = 26 + 300 * (r["days"] / top)
            pop = 1.0 if i < lit - 1 else 0.45 + 0.55 * ((fi % n_frames) >= i)
            for m, a in ((6.0, 0.045), (3.4, 0.085), (1.9, 0.16)):
                ax.scatter(
                    [x],
                    [y],
                    s=base * m * pop,
                    color=col,
                    alpha=a,
                    linewidths=0,
                    zorder=5,
                )
            ax.scatter(
                [x], [y], s=base * pop, color=col, alpha=0.92, linewidths=0, zorder=6
            )
            # the real-time core: the smaller count, the one settlement sees
            rt = base * (r["rtd_days"] / max(1, r["days"]))
            ax.scatter(
                [x],
                [y],
                s=max(4.0, rt),
                color="#ffffff",
                alpha=0.85,
                linewidths=0,
                zorder=7,
            )

        ax.set_aspect(1.0 / math.cos(math.radians(lat0)))
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.axis("off")

        # --- the corridor, zoomed ---------------------------------------------
        # Tabango to Daanbantayan is about 30 km, so at national scale the arc
        # disappears inside its own glow. The inset is the only place the
        # corridor reads as a corridor rather than as one coral dot.
        if arc and ends_lit == 2:
            a, b = arc[0], arc[-1]
            cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            h = 0.42
            ix = ax.inset_axes([0.015, 0.035, 0.54, 0.32], facecolor="#0c1119")
            for f in lines:
                g = f["geometry"]
                for s in (
                    [g["coordinates"]]
                    if g["type"] == "LineString"
                    else g["coordinates"]
                ):
                    col, lw, al = VOLT.get(f["properties"].get("kind"), VOLT_DEF)
                    ix.plot(
                        [p[0] for p in s],
                        [p[1] for p in s],
                        color=col,
                        lw=lw * 1.5,
                        alpha=al,
                        zorder=2,
                    )
            k = max(2, int(len(arc) * min(1.0, max(0.25, grow))))
            pth = MPath(arc[:k])
            for w, al in ((9.0, 0.10), (5.0, 0.20), (2.4, 0.95)):
                ix.add_patch(
                    PathPatch(
                        pth,
                        fill=False,
                        edgecolor=HOT,
                        lw=w,
                        alpha=al,
                        zorder=4,
                        capstyle="round",
                    )
                )
            # one label above and one below, each anchored so it grows inward:
            # at 31 km apart centred labels collide, and the western one ran
            # off the inset frame
            for pt, lbl, dy, va, ha, dx in (
                (a, "Tabango (Leyte)", 0.055, "bottom", "right", -0.02),
                (b, "Daanbantayan (Cebu)", -0.055, "top", "left", 0.02),
            ):
                for m, al in ((5.0, 0.10), (2.6, 0.20)):
                    ix.scatter(
                        [pt[0]],
                        [pt[1]],
                        s=70 * m,
                        color=HOT,
                        alpha=al,
                        linewidths=0,
                        zorder=5,
                    )
                ix.scatter([pt[0]], [pt[1]], s=52, color=HOT, zorder=6, linewidths=0)
                ix.text(
                    pt[0] + dx,
                    pt[1] + dy,
                    lbl,
                    fontsize=6.2,
                    color=TEXT,
                    ha=ha,
                    va=va,
                    zorder=7,
                )
            ix.set_xlim(cx - h, cx + h)
            ix.set_ylim(cy - h * 0.62, cy + h * 0.62)
            ix.set_aspect(1.0 / math.cos(math.radians(cy)))
            ix.set_xticks([])
            ix.set_yticks([])
            for sp in ix.spines.values():
                sp.set_color("#26344a")
                sp.set_linewidth(0.8)
            ix.text(
                0.03,
                0.94,
                f"the corridor, {gc_km(a, b):.0f} km across",
                transform=ix.transAxes,
                fontsize=6.6,
                color=MUTE,
                va="top",
            )

        # Equipment ranking.
        bx.set_xlim(0, 1)
        bx.set_ylim(-0.6, TOP_N - 0.4)
        bx.invert_yaxis()
        bx.axis("off")
        for i, r in enumerate(ranked):
            on = i < lit
            col = HOT if r["hot"] else COOL
            w = 0.40 * (r["days"] / top)
            bx.barh(
                i,
                w if on else 0,
                left=0.44,
                height=0.52,
                color=col,
                alpha=0.92 if on else 0.0,
                zorder=3,
            )
            bx.text(
                0.42,
                i,
                f"{r['equipment']}",
                va="center",
                ha="right",
                fontsize=8.4,
                color=TEXT if on else "#39424f",
                family="monospace",
                zorder=4,
            )
            if on:
                bx.text(
                    0.44 + w + 0.012,
                    i,
                    f"{r['days']}",
                    va="center",
                    fontsize=8.2,
                    color=col,
                    zorder=4,
                )
        bx.text(
            0.44,
            -0.62,
            "days at a binding limit",
            fontsize=7.6,
            color=MUTE,
            va="bottom",
        )

        # Titles and sources.
        fig.text(
            0.012,
            0.972,
            f"Leyte-Cebu reached a binding limit on {ranked[0]['days']} of "
            f"{days_covered} days",
            fontsize=14.6,
            color=TEXT,
            weight="bold",
            va="top",
        )
        fig.text(
            0.012,
            0.918,
            f"{placed} named substations sat at a binding limit across the "
            f"{days_covered}-day archive. The corridor on top joins Leyte to Cebu.",
            fontsize=9.2,
            color=MUTE,
            va="top",
        )
        fig.text(
            0.012,
            0.082,
            "Dot area is days at a binding limit, a day counted once. The white core is "
            "real-time days, the count settlement sees. Coral is the Leyte-Cebu corridor,",
            fontsize=7.6,
            color=MUTE,
            va="top",
        )
        fig.text(
            0.012,
            0.050,
            "drawn as an arc from Tabango (Leyte) to Daanbantayan (Cebu). Lines "
            "and substations are OpenStreetMap (ODbL), community-mapped, and are",
            fontsize=7.6,
            color=MUTE,
            va="top",
        )
        fig.text(
            0.012,
            0.018,
            "not NGCP's network model. Counts from IEMOP RTDCV and DAPCV, archived. "
            f"{len(STATION_UNPLACED)} league codes carry no OSM substation and are left off.",
            fontsize=7.6,
            color=MUTE,
            va="top",
        )

        fig.savefig(os.path.join(FRAMES, f"f{fi:03d}.png"), dpi=104, facecolor=BG)
        plt.close(fig)

    pal = "/tmp/pds_cmap_pal.png"
    vf = "fps=12,scale=900:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            os.path.join(FRAMES, "f%03d.png"),
            "-vf",
            vf + ",palettegen=stats_mode=diff:max_colors=128",
            pal,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            "12",
            "-i",
            os.path.join(FRAMES, "f%03d.png"),
            "-i",
            pal,
            "-lavfi",
            vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4",
            OUT,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["gifsicle", "-O3", OUT, "-o", OUT], capture_output=True)
    print(
        f"wrote {OUT} ({os.path.getsize(OUT) // 1024} KB), {placed} stations placed, "
        f"{len(STATION_UNPLACED)} left off"
    )


if __name__ == "__main__":
    main()
