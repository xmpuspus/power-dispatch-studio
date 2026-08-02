#!/usr/bin/env python3
"""Create a phone-size Pax Silica summary video.

A feed may autoplay without sound and use the first frame as its thumbnail, so
the first scene states the result without relying on audio or post text.

The displayed values come from the model runs. The feeding-route capacity is
read from the headroom file that scripts/pax_silica_headroom.py
writes, and the station size, the tripped unit and the solar shape from
web/data/perspective.json, so this cannot drift from the page.

Writes docs/pax-silica-social.mp4 and docs/pax-silica-social.gif.
Run scripts/pax_silica_headroom.py first if the cache is cold.
"""

import json
import os
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FRAMES = "/tmp/pds_pax_social"
CACHE = os.path.join(ROOT, "tmp", "pax_silica_headroom.json")

BG = "#0d2137"
WHITE = "#ffffff"
MUTE = "#7f9ab5"
STEEL = "#4e79a7"
NAVY = "#1f4d7a"
GOLD = "#e8b04b"
CORAL = "#e2664b"

NEED = 3000.0
FPS = 12
DATA_PATH = os.path.join(ROOT, "web", "data", "perspective.json")


def load_limit() -> float:
    if os.path.exists(CACHE):
        rows = json.load(open(CACHE))["hours"]
        return rows[19]["headroom_mw"]
    raise SystemExit("run scripts/pax_silica_headroom.py first")


def scenario() -> tuple[float, float, float]:
    """The station size, the unit that goes out and what is left, all from the
    generated data, so the clip and page use the same figures."""
    w = json.load(open(DATA_PATH))["wires"]
    return w["own_station_mw"], w["trip_unit_mw"], float(w["own_gap_mw"])


def card(scene, t, limit, solar_noon):
    """Draw one frame. `t` runs from 0 to 1 while the bar grows."""
    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    def T(x, y, s, size, color=WHITE, weight="normal", ha="left"):
        ax.text(
            x,
            y,
            s,
            transform=ax.transAxes,
            fontsize=size,
            color=color,
            fontweight=weight,
            ha=ha,
            va="top",
            linespacing=1.35,
        )

    T(0.07, 0.955, "PAX SILICA, NEW CLARK CITY", 17, MUTE, "bold")

    # Keep the bar in one position across scenes.
    bx, by, bw, bh = 0.07, 0.44, 0.86, 0.085

    def seg(frac_start, frac_len, color):
        if frac_len <= 0:
            return
        ax.add_patch(
            plt.Rectangle(
                (bx + bw * frac_start, by),
                bw * frac_len,
                bh,
                transform=ax.transAxes,
                color=color,
                zorder=3,
            )
        )

    def bar_label(frac_mid, text, color=WHITE, size=21):
        ax.text(
            bx + bw * frac_mid,
            by + bh / 2,
            text,
            transform=ax.transAxes,
            fontsize=size,
            color=color,
            ha="center",
            va="center",
            fontweight="medium",
            zorder=5,
        )

    grid = limit / NEED
    ax.add_patch(
        plt.Rectangle(
            (bx, by), bw, bh, transform=ax.transAxes, color="#173553", zorder=2
        )
    )
    T(0.07, 0.415, "what Pax Silica needs every hour, 3,000 MW", 16, MUTE)

    if scene == 0:
        T(0.07, 0.86, "Pax Silica will need 3,000 MW.", 42, WHITE, "bold")
        T(
            0.07,
            0.74,
            "One existing route feeds Pax Silica\nand carries about 770 MW.",
            34,
            CORAL,
            "bold",
        )
        seg(0, grid, STEEL)
        bar_label(grid / 2, "770", WHITE, 20)

    elif scene == 1:
        T(
            0.07,
            0.86,
            f"{NEED - limit:,.0f} MW of demand\nremains unmet.",
            42,
            WHITE,
            "bold",
        )
        seg(0, grid, STEEL)
        seg(grid, (1 - grid) * t, CORAL)
        bar_label(grid / 2, "770", WHITE, 20)
        if t > 0.7:
            bar_label(grid + (1 - grid) / 2, f"{NEED - limit:,.0f} short", WHITE, 22)

    elif scene == 2:
        T(
            0.07,
            0.86,
            "A 500 MW solar farm is leased\nnext to Pax Silica.",
            38,
            WHITE,
            "bold",
        )
        T(
            0.07,
            0.70,
            "At 7pm, solar output is zero.\nThe supply gap does not change.",
            34,
            GOLD,
            "bold",
        )
        seg(0, grid, STEEL)
        seg(grid, 1 - grid, CORAL)
        bar_label(grid / 2, "770", WHITE, 20)
        bar_label(grid + (1 - grid) / 2, f"{NEED - limit:,.0f} short", WHITE, 22)

    elif scene == 3:
        st, trip, gap = scenario()
        T(
            0.07,
            0.86,
            "Pax Silica therefore plans\nits own power station\non site.",
            40,
            WHITE,
            "bold",
        )
        own = st / NEED
        seg(0, (NEED - st) / NEED, STEEL)
        seg((NEED - st) / NEED, own * t, NAVY)
        if t > 0.7:
            bar_label(
                (NEED - st) / NEED + own / 2, f"{st:,.0f} MW of its own", WHITE, 21
            )

    else:
        st, trip, gap = scenario()
        left = st - trip
        T(0.07, 0.86, f"Then one {trip:,.0f} MW unit\ngoes down.", 40, WHITE, "bold")
        T(0.07, 0.735, f"{gap:,.0f} MW of demand\nremains unmet.", 36, CORAL, "bold")
        seg(0, limit / NEED, STEEL)
        seg(limit / NEED, left / NEED, NAVY)
        seg((limit + left) / NEED, gap / NEED, CORAL)
        bar_label((limit + left + gap / 2) / NEED, f"{gap:,.0f}", WHITE, 19)

    ax.plot(
        [0.07, 0.34], [0.115, 0.115], transform=ax.transAxes, color="#24425f", lw=1.4
    )
    T(
        0.07,
        0.095,
        "Modelled on the public grid map and one recorded day.\n"
        "Line ratings are class defaults. NGCP does not publish them.\n"
        "3,000 MW is BCDA's full-development figure, 10 to 15 years out.",
        14,
        MUTE,
    )
    return fig


def main():
    limit = load_limit()
    solar = json.load(open(os.path.join(ROOT, "web", "data", "profiles.json")))[
        "solar_profile"
    ]
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        if f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))

    # Hold the first scene longest because it may be used as the thumbnail.
    holds = [34, 26, 30, 26, 34]
    grow = [0, 10, 0, 10, 0]
    idx = 0
    for scene, (hold, g) in enumerate(zip(holds, grow)):
        for k in range(g):
            fig = card(scene, (k + 1) / max(g, 1), limit, max(solar))
            fig.savefig(os.path.join(FRAMES, f"f{idx:04d}.png"), dpi=100, facecolor=BG)
            plt.close(fig)
            idx += 1
        for _ in range(hold):
            fig = card(scene, 1.0, limit, max(solar))
            fig.savefig(os.path.join(FRAMES, f"f{idx:04d}.png"), dpi=100, facecolor=BG)
            plt.close(fig)
            idx += 1

    mp4 = os.path.join(DOCS, "pax-silica-social.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            os.path.join(FRAMES, "f%04d.png"),
            "-vf",
            "scale=1080:1350:flags=lanczos,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "20",
            mp4,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    gif = os.path.join(DOCS, "pax-silica-social.gif")
    pal = "/tmp/pds_pax_social_pal.png"
    vf = f"fps={FPS},scale=720:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            os.path.join(FRAMES, "f%04d.png"),
            "-vf",
            vf + ",palettegen=stats_mode=diff",
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
            str(FPS),
            "-i",
            os.path.join(FRAMES, "f%04d.png"),
            "-i",
            pal,
            "-lavfi",
            vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            gif,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for p in (mp4, gif):
        print("wrote", p, f"({os.path.getsize(p) // 1024} KB)")
    print(f"{idx} frames, {idx / FPS:.1f} s")


if __name__ == "__main__":
    main()
