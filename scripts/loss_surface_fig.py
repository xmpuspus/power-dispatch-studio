#!/usr/bin/env python3
"""Animated GIF: does network physics track the market's own per-node prices?

Three panels in one frame, one per island grid, each plotting the model's
marginal loss-factor deviation against the market's observed deviation from its
regional price. The points arrive together, so the shape of each cloud lands at
the same moment, and the verdict sits on the panel: two grids validate, and the
third is shown failing rather than dropped.

Values read from data/derived/loss_surface.json, which is recalculated nightly.

    python3 scripts/loss_surface_fig.py     # -> docs/loss-surface.gif
"""

import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardstyle as cs  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOSS = os.path.join(HERE, "..", "data", "derived", "loss_surface.json")
OUT = os.path.abspath(os.path.join(HERE, "..", "docs", "loss-surface.gif"))
GRIDS = ("luzon", "visayas", "mindanao")


def main():
    with open(LOSS) as f:
        d = json.load(f)
    if not d.get("available"):
        raise SystemExit("loss_surface.json not available; run the pipeline")

    fdir = cs.frames_dir("loss")
    for fi, t in enumerate(cs.reveal(24, 16)):
        cs.apply()
        fig = plt.figure(figsize=(10.6, 5.0), facecolor=cs.BG)
        glo, ghi = cs.FIELDS["night"]
        gnd = fig.add_axes([0, 0, 1, 1], zorder=0)
        gnd.imshow(
            np.linspace(0, 1, 256).reshape(-1, 1),
            cmap=LinearSegmentedColormap.from_list("f", [ghi, glo]),
            aspect="auto",
            extent=(0, 1, 0, 1),
            interpolation="bicubic",
        )
        gnd.set_xticks([])
        gnd.set_yticks([])
        for sp in gnd.spines.values():
            sp.set_visible(False)

        axes = []
        for i, g in enumerate(GRIDS):
            ax = fig.add_axes(
                [0.068 + i * 0.302, 0.235, 0.258, 0.470], facecolor="none", zorder=2
            )
            axes.append(ax)
            cs.tufte(ax, ygrid=False)
            ax.grid(color=cs.FAINT, lw=0.6, alpha=0.7, zorder=0)
            ax.set_axisbelow(True)
            w = d["window"].get(g) or {}
            pts = d["scatter"].get(g, [])
            ok = g in d["validated_grids"]
            col = cs.REGION[g]
            n = max(1, int(round(len(pts) * t)))
            if pts:
                ax.scatter(
                    [p[0] for p in pts[:n]],
                    [p[1] for p in pts[:n]],
                    s=11,
                    alpha=0.50,
                    color=col,
                    edgecolors="none",
                    zorder=3,
                )
                if w.get("affine_slope") is not None and t > 0.55:
                    xa = np.array(
                        [min(p[0] for p in pts), max(p[0] for p in pts)], float
                    )
                    ax.plot(
                        xa,
                        w["affine_slope"] * xa + w["affine_intercept_php_kwh"],
                        color=cs.WHITE,
                        lw=1.3,
                        alpha=0.7,
                        zorder=5,
                    )
            ax.axhline(0, color=cs.FAINT, lw=0.8, zorder=1)
            ax.axvline(0, color=cs.FAINT, lw=0.8, zorder=1)
            ax.text(
                0.0,
                1.20,
                g.capitalize(),
                transform=ax.transAxes,
                fontsize=11.5,
                color=col,
                ha="left",
                va="bottom",
                zorder=6,
            )
            ax.text(
                0.0,
                1.055,
                f"Spearman {w.get('spearman', 0):+.2f}   "
                f"{'validated' if ok else 'fails'}",
                transform=ax.transAxes,
                fontsize=8.6,
                color=cs.GREEN if ok else cs.CORAL,
                ha="left",
                va="bottom",
                zorder=6,
            )
            ax.tick_params(labelsize=8.0)
            if i == 0:
                ax.set_ylabel(
                    "recorded difference from the\nregional price, PhP/kWh",
                    fontsize=8.2,
                )
            if i == 1:
                ax.set_xlabel("modeled marginal-loss price difference", fontsize=8.6)

        n_ok = len(d["validated_grids"])
        cs.title(
            fig,
            f"Transmission-loss estimates match market rankings on {n_ok} of 3 "
            "grids, and fail on the third",
            f"One dot per node, {d['n_nodes_compared']} in all, across "
            f"{d['clean_days']} clean market days. Recomputed nightly.",
        )
        if t > 0.9:
            vis = d["window"]["visayas"]["spearman"]
            cs.payoff(
                axes[1],
                0.985,
                0.97,
                f"{vis:+.2f}",
                "Visayas ranks the wrong way,\nand the sign is not diagnosed",
                cs.ACCENT,
                26,
                ha="right",
                va="top",
            )
        cs.source(
            fig,
            "Marginal loss factors come from the OpenStreetMap-geometry "
            "backbone. Each grid is compared against WESM's published "
            "nodal deviations.\nFrom data/derived/loss_surface.json, "
            "recomputed nightly.",
        )
        fig.savefig(os.path.join(fdir, f"f{fi:03d}.png"), dpi=100, facecolor=cs.BG)
        plt.close(fig)

    cs.save_gif(fdir, OUT, fps=12, width=940)


if __name__ == "__main__":
    main()
