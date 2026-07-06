#!/usr/bin/env python3
"""Shared Tufte + MBB visual style for every gridbill-ph chart.

Tufte: maximize data-ink, drop chartjunk (no top/right spines, faint y-grid only, no
heavy borders), direct labels over legends, standalone with a sourced caption.
MBB palette: navy / steel blue / coral, one muted grey for context, on white.

Usage in a chart script:
    import vizstyle as vz
    vz.apply()                       # sets rcParams (fonts, colors, sizes)
    fig, ax = plt.subplots(...)
    ...
    vz.tufte(ax)                     # strip spines, faint y-grid
Regional series: vz.REGION colors (luzon steel, visayas coral, mindanao green).
"""
import matplotlib

matplotlib.use("Agg")
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

# --- MBB palette --------------------------------------------------------------
NAVY = "#12335c"      # ink, primary series, titles
STEEL = "#4e79a7"     # secondary data series
CORAL = "#e2664b"     # accent / highlight (the thing to look at)
GOLD = "#e8b04b"      # third series when needed (sparingly)
GREEN = "#1a7f48"     # operational / supply (matches the map's --op)
MUTE = "#7d8896"      # axis labels, captions, context geometry
GRID = "#e6eaee"      # faint gridlines
FILL = "#eef1f4"      # bands, missing-data fills
INK = NAVY            # alias used across scripts

# the three grids, consistent across every figure and the map itself
REGION = {"luzon": STEEL, "visayas": CORAL, "mindanao": GREEN}

# single-hue sequential ramps (Tufte: one hue, light to dark, no rainbow)
SEQ_BLUE = LinearSegmentedColormap.from_list(
    "seq_blue", ["#eef3f8", "#bcd0e4", "#7ea6cc", "#4e79a7", "#1f3f66"])
SEQ_CORAL = LinearSegmentedColormap.from_list(
    "seq_coral", ["#fbeee7", "#f4c9b0", "#e89a72", "#e2664b", "#9c3d28"])


def apply():
    """Set global rcParams once per process. Call before creating figures."""
    matplotlib.rcParams.update({
        "text.parse_math": False,          # render literal P (no LaTeX math mode)
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 10,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": MUTE,
        "axes.linewidth": 0.8,
        "axes.titlecolor": NAVY,
        "axes.labelcolor": NAVY,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTE,
        "ytick.color": MUTE,
        "xtick.labelcolor": NAVY,
        "ytick.labelcolor": NAVY,
        "legend.frameon": False,
        "savefig.facecolor": "white",
    })


def tufte(ax, grid="y"):
    """Strip top/right spines, mute the rest, faint gridline on one axis only."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTE)
        ax.spines[side].set_linewidth(0.8)
    if grid in ("y", "both"):
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    if grid in ("x", "both"):
        ax.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def caption(fig, text, y=-0.02, size=8):
    """Standalone sourced caption in the muted grey, centered under the figure."""
    fig.text(0.5, y, text, ha="center", fontsize=size, color=MUTE, wrap=True)
