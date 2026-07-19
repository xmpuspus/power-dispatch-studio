#!/usr/bin/env python3
"""The loss-surface validation figure: can network physics predict the
market's own per-node price deviations?

One small-multiple panel per grid: modeled loss-factor deviation (x)
against the observed deviation from the regional price (y), one dot per
placed node, the fitted affine convention as a line, and the Spearman
rank correlation plus post-fit error stated on the panel. Validated
grids carry a green rule, failing grids a red one, so the verdict reads
off the figure. Every number is read from data/derived/loss_surface.json,
which recomputes nightly.

    python3 scripts/loss_surface_fig.py     # -> docs/loss-surface.png
"""

import json
import os

import matplotlib.pyplot as plt

import vizstyle as vz

HERE = os.path.dirname(os.path.abspath(__file__))
LOSS = os.path.join(HERE, "..", "data", "derived", "loss_surface.json")
OUT = os.path.join(HERE, "..", "docs", "loss-surface.png")

GOOD = "#1a7f48"
CRIT = "#b3261e"
GRIDS = ("luzon", "visayas", "mindanao")


def main() -> None:
    with open(LOSS) as f:
        d = json.load(f)
    if not d.get("available"):
        raise SystemExit("loss_surface.json not available; run the pipeline")
    vz.apply()
    fig, axes = plt.subplots(1, 3, figsize=(12.4, 5.0))
    for ax, g in zip(axes, GRIDS):
        w = d["window"].get(g)
        pts = d["scatter"].get(g, [])
        color = vz.REGION[g]
        validated = g in d["validated_grids"]
        edge = GOOD if validated else CRIT
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.scatter(xs, ys, s=14, c=color, alpha=0.45, linewidths=0, zorder=3)
            # the fitted affine convention (reported, not hidden)
            a = w["affine_slope"]
            b = w["affine_intercept_php_kwh"]
            lo, hi = min(xs), max(xs)
            ax.plot([lo, hi], [a * lo + b, a * hi + b], color=vz.NAVY, lw=1.6, zorder=4)
        vz.tufte(ax, grid="both")
        ax.axhline(0, color=vz.MUTE, lw=0.6, zorder=1)
        ax.axvline(0, color=vz.MUTE, lw=0.6, zorder=1)
        rho = w["spearman"] if w else None
        mae = w["mae_after_affine_php_kwh"] if w else None
        n = w["n_nodes"] if w else 0
        verdict = "validated" if validated else "fails · not diagnosed"
        ax.set_title(g.capitalize(), color=edge, fontsize=13, fontweight="bold", pad=10)
        ax.text(
            0.03,
            0.97,
            f"Spearman {rho:+.2f}\nerror {mae:.2f} P/kWh\n{n} nodes  ·  {verdict}",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=9.5,
            color=vz.NAVY,
            bbox=dict(
                boxstyle="round,pad=0.4", fc="white", ec=edge, lw=1.1, alpha=0.92
            ),
        )
        ax.set_xlabel(
            "modeled loss-factor deviation (P/kWh)", color=vz.MUTE, fontsize=9
        )
    axes[0].set_ylabel(
        "observed deviation from regional price (P/kWh)", color=vz.NAVY, fontsize=9.5
    )
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.text(
        0.5,
        0.965,
        "Does network physics track the market's own per-node prices?",
        ha="center",
        color=vz.NAVY,
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.915,
        f"Marginal loss factors from the OpenStreetMap grid vs WESM's "
        f"published nodal deviations, {d['clean_days']} clean market "
        f"days. Recomputed nightly (data/derived/loss_surface.json).",
        ha="center",
        color=vz.MUTE,
        fontsize=9.5,
    )
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    kb = os.path.getsize(OUT) // 1024
    print(
        f"wrote {OUT} ({kb} KB)  validated={d['validated_grids']} "
        f"failing={d['failing_grids']}"
    )


if __name__ == "__main__":
    main()
