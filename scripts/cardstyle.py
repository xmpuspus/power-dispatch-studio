#!/usr/bin/env python3
"""The dark card the README's charts share, on top of vizstyle's Tufte rules.

vizstyle keeps the ink discipline: no chartjunk, direct labels, a sourced
caption, the navy/steel/coral family. This adds the layer that makes a chart
worth screenshotting, and it is the same treatment the constraint map got.

The chart rules are:

  - One card, one charcoal ground with a single meaning-bearing gradient.
    Charcoal, never pure black. The gradient decorates the ground; flat colour
    still encodes every value.
  - One ink and one accent per card, three hues at most. The accent is the
    subject, and everything that is context stays muted.
  - The title states the finding in everyday words. The subtitle carries the
    measure, the unit and the date.
  - The main result sits large in the accent, parked in empty space, away
    from the series.
  - Direct labels beside marks, no legend unless a label cannot fit.
  - Sources and assumptions are printed on the card.

Animation draws the series from left to right so changes remain easy to follow.

    import cardstyle as cs
    fig, ax = cs.card(figsize=(8.6, 5.0), field="dusk")
    cs.title(fig, "The claim", "the measure, the unit, the date")
    cs.result_label(ax, 0.72, 0.30, "18%", "of the margin")
    cs.source(fig, "Source: IEMOP RTDSUM, archived.")
    cs.save_gif(frames_dir, out_path, fps=12, width=880)
"""

import os
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

# --- the dark set -------------------------------------------------------------
BG = "#0d1117"  # charcoal ground, never pure black
PANEL = "#121821"  # a panel sitting on the ground
TEXT = "#e9edf2"  # headline and value ink
BODY = "#c3ccd8"  # sentence ink
MUTE = "#8592a3"  # axis labels, captions, context
FAINT = "#28313f"  # gridlines, rules, the quietest geometry

STEEL = "#4cc9f0"  # the primary series, legible on charcoal
CORAL = "#ff5c39"  # the subject, the thing to look at
GREEN = "#3ddc97"  # the third grid, or a relieved state
GOLD = "#f0b429"  # a fourth series, used sparingly
WHITE = "#ffffff"

# the three grids, matching the map and every other figure in the repo
REGION = {"luzon": STEEL, "visayas": CORAL, "mindanao": GREEN}

# One gradient per card, chosen for the subject rather than for variety:
# a day runs night to day, a bottleneck goes aubergine, money stays cool.
FIELDS = {
    "dusk": ("#0d1117", "#141d2b"),
    "night": ("#0a0d12", "#101826"),
    "choke": ("#0d0f17", "#1a1226"),
    "money": ("#0c1016", "#101b24"),
    "day": ("#0b1018", "#17202e"),
}


def apply():
    matplotlib.rcParams.update(
        {
            "text.parse_math": False,  # a literal P, never LaTeX math mode
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10,
            "figure.facecolor": BG,
            "axes.facecolor": "none",
            "axes.edgecolor": FAINT,
            "axes.labelcolor": MUTE,
            "text.color": TEXT,
            "xtick.color": MUTE,
            "ytick.color": MUTE,
            "xtick.labelcolor": MUTE,
            "ytick.labelcolor": MUTE,
            "axes.grid": False,
            "savefig.facecolor": BG,
        }
    )


def card(figsize=(8.6, 5.0), field="dusk", rect=(0.075, 0.175, 0.90, 0.60)):
    """A figure carrying one gradient ground, and one axes to draw on.

    `rect` is explicit because the title, main result, and source line are
    placed in figure coordinates. A shorter card needs a shorter plot, or the
    source runs off the bottom edge.
    """
    apply()
    fig = plt.figure(figsize=figsize, facecolor=BG)
    lo, hi = FIELDS.get(field, FIELDS["dusk"])
    gnd = fig.add_axes([0, 0, 1, 1], zorder=0)
    gnd.imshow(
        np.linspace(0, 1, 256).reshape(-1, 1),
        cmap=matplotlib.colors.LinearSegmentedColormap.from_list("f", [hi, lo]),
        aspect="auto",
        extent=(0, 1, 0, 1),
        interpolation="bicubic",
    )
    gnd.set_xticks([])
    gnd.set_yticks([])
    for s in gnd.spines.values():
        s.set_visible(False)
    ax = fig.add_axes(list(rect), facecolor="none", zorder=2)
    tufte(ax)
    return fig, ax


def tufte(ax, ygrid=True):
    """Strip the box, keep at most a faint horizontal grid."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(FAINT)
    ax.spines["bottom"].set_linewidth(0.9)
    ax.tick_params(length=0, labelsize=8.6)
    if ygrid:
        ax.grid(axis="y", color=FAINT, lw=0.7, alpha=0.85, zorder=0)
        ax.set_axisbelow(True)


def title(fig, claim, sub=None, pop=None):
    """The finding, in everyday words. One word or number may get the accent."""
    fig.text(
        0.075,
        0.945,
        claim,
        fontsize=16.5,
        color=TEXT,
        weight="bold",
        va="top",
        zorder=5,
    )
    if pop:
        fig.text(
            0.075,
            0.945,
            claim.split(pop)[0],
            fontsize=16.5,
            color="none",
            va="top",
            zorder=5,
        )
    if sub:
        fig.text(0.075, 0.868, sub, fontsize=9.4, color=MUTE, va="top", zorder=5)


def result_label(fig, x, y, big, small=None, color=CORAL, size=34):
    """The number the reader carries away, parked in empty space."""
    fig.text(
        x,
        y,
        big,
        fontsize=size,
        color=color,
        weight="bold",
        va="center",
        ha="left",
        zorder=6,
    )
    if small:
        fig.text(
            x,
            y - 0.062,
            small,
            fontsize=9.2,
            color=MUTE,
            va="center",
            ha="left",
            zorder=6,
        )


def source(fig, text, y=0.045):
    """Typeset the sources into the card: it travels without the README."""
    fig.text(0.075, y, text, fontsize=7.6, color=MUTE, va="top", zorder=5)


def chip(ax, x, y, s, color=TEXT, size=9.0, ha="center", va="center", pad=0.28):
    """A value label over a busy field, on its own dark chip so it stays read."""
    ax.text(
        x,
        y,
        s,
        fontsize=size,
        color=color,
        ha=ha,
        va=va,
        zorder=9,
        bbox=dict(boxstyle=f"round,pad={pad}", fc=BG, ec="none", alpha=0.78),
    )


def glow(ax, xs, ys, color, lw=2.0, zorder=5, passes=((5.2, 0.09), (2.6, 0.16))):
    """A line with a soft halo, the one move that makes a dark card feel lit."""
    for m, a in passes:
        ax.plot(
            xs,
            ys,
            color=color,
            lw=lw * m,
            alpha=a,
            zorder=zorder,
            solid_capstyle="round",
        )
    ax.plot(xs, ys, color=color, lw=lw, zorder=zorder + 1, solid_capstyle="round")


def dot(ax, x, y, color, size=70, zorder=7):
    for m, a in ((6.0, 0.06), (3.2, 0.12), (1.8, 0.20)):
        ax.scatter(
            [x], [y], s=size * m, color=color, alpha=a, linewidths=0, zorder=zorder
        )
    ax.scatter([x], [y], s=size, color=color, linewidths=0, zorder=zorder + 1)


def rounded(fig, ax, color=PANEL, alpha=0.55):
    """A rounded panel behind an axes, the corpus's card-within-a-card."""
    b = ax.get_position()
    fig.patches.append(
        FancyBboxPatch(
            (b.x0 - 0.012, b.y0 - 0.03),
            b.width + 0.024,
            b.height + 0.06,
            boxstyle="round,pad=0,rounding_size=0.02",
            transform=fig.transFigure,
            fc=color,
            ec="none",
            alpha=alpha,
            zorder=1,
        )
    )


def ease(t):
    """Ease-out cubic. A reveal should decelerate, never run at one speed."""
    return 1 - (1 - t) ** 3


def reveal(n_grow, n_hold=10):
    """The growth fractions for an animated reveal, then a hold on the result."""
    return [ease((i + 1) / n_grow) for i in range(n_grow)] + [1.0] * n_hold


def frames_dir(name):
    d = f"/tmp/pds_{name}_frames"
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    return d


def save_gif(fdir, out, fps=12, width=880, colors=128):
    """Assemble with the palette recipe the rest of the repo uses."""
    pal = f"{fdir}/pal.png"
    vf = f"fps={fps},scale={width}:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            f"{fdir}/f%03d.png",
            "-vf",
            f"{vf},palettegen=stats_mode=diff:max_colors={colors}",
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
            str(fps),
            "-i",
            f"{fdir}/f%03d.png",
            "-i",
            pal,
            "-lavfi",
            f"{vf}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4",
            out,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["gifsicle", "-O3", out, "-o", out], capture_output=True)
    print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")


def save_png(fig, out, dpi=110):
    fig.savefig(out, dpi=dpi, facecolor=BG)
    plt.close(fig)
    print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")
