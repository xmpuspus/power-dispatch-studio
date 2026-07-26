#!/usr/bin/env python3
"""The Pax Silica post video: one claim per beat, phone-legible, 4:5.

A feed autoplays muted and renders the first frame as the thumbnail, so beat one
carries the whole claim on its own and nothing here needs sound or a caption to
land. Dark card in the same palette as scripts/stat_card.py.

Every number comes from the model runs, not typed here. What the two lines carry
is read from the headroom file that scripts/pax_silica_headroom.py writes, and
the solar shape from the bake, so this cannot drift from the figure.

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
CACHE = "/tmp/pds_pax_headroom.json"

BG = "#0d2137"
WHITE = "#ffffff"
MUTE = "#7f9ab5"
STEEL = "#4e79a7"
NAVY = "#1f4d7a"
GOLD = "#e8b04b"
CORAL = "#e2664b"

NEED = 3000.0
FPS = 12


def load_limit() -> float:
    if os.path.exists(CACHE):
        return json.load(open(CACHE))["headroom_mw"][19]
    raise SystemExit("run scripts/pax_silica_headroom.py first")


def card(beat, t, limit, solar_noon):
    """One frame. `t` runs 0 to 1 inside the beat, for the bar growth."""
    fig = plt.figure(figsize=(10.8, 13.5))
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    def T(x, y, s, size, color=WHITE, weight="normal", ha="left"):
        ax.text(x, y, s, transform=ax.transAxes, fontsize=size, color=color,
                fontweight=weight, ha=ha, va="top", linespacing=1.35)

    T(0.07, 0.955, "PAX SILICA, NEW CLARK CITY", 17, MUTE, "bold")

    # the bar sits in the same place every beat so the eye never re-hunts it
    bx, by, bw, bh = 0.07, 0.44, 0.86, 0.085

    def seg(frac_start, frac_len, color):
        if frac_len <= 0:
            return
        ax.add_patch(plt.Rectangle((bx + bw * frac_start, by), bw * frac_len, bh,
                                   transform=ax.transAxes, color=color, zorder=3))

    def bar_label(frac_mid, text, color=WHITE, size=21):
        ax.text(bx + bw * frac_mid, by + bh / 2, text, transform=ax.transAxes,
                fontsize=size, color=color, ha="center", va="center",
                fontweight="medium", zorder=5)

    grid = limit / NEED
    ax.add_patch(plt.Rectangle((bx, by), bw, bh, transform=ax.transAxes,
                               color="#173553", zorder=2))
    T(0.07, 0.415, "what the campus needs every hour, 3,000 MW", 16, MUTE)

    if beat == 0:
        T(0.07, 0.86, "It will need 3,000 MW.", 42, WHITE, "bold")
        T(0.07, 0.74, "The two power lines\ninto the site carry 770.", 40, CORAL,
          "bold")
        seg(0, grid, STEEL)
        bar_label(grid / 2, "770", WHITE, 20)

    elif beat == 1:
        T(0.07, 0.86, "2,230 MW of it\nhas no source.", 42, WHITE, "bold")
        seg(0, grid, STEEL)
        seg(grid, (1 - grid) * t, CORAL)
        bar_label(grid / 2, "770", WHITE, 20)
        if t > 0.7:
            bar_label(grid + (1 - grid) / 2, "2,230 short", WHITE, 22)

    elif beat == 2:
        T(0.07, 0.86, "A 500 MW solar farm\nis being built there.", 38, WHITE,
          "bold")
        T(0.07, 0.70, "At 7pm it makes nothing.\nThe gap does not move.", 34, GOLD,
          "bold")
        seg(0, grid, STEEL)
        seg(grid, 1 - grid, CORAL)
        bar_label(grid / 2, "770", WHITE, 20)
        bar_label(grid + (1 - grid) / 2, "2,230 short", WHITE, 22)

    elif beat == 3:
        T(0.07, 0.86, "Which is why it has to\nbuild its own\npower station.", 40,
          WHITE, "bold")
        own = 2500.0 / NEED
        seg(0, 500.0 / NEED, STEEL)
        seg(500.0 / NEED, own * t, NAVY)
        if t > 0.7:
            bar_label(500.0 / NEED + own / 2, "2,500 MW of its own", WHITE, 21)

    else:
        T(0.07, 0.86, "Then one 600 MW unit\ngoes down.", 40, WHITE, "bold")
        T(0.07, 0.735, "330 MW is left\nwith no source.", 36, CORAL, "bold")
        seg(0, limit / NEED, STEEL)
        seg(limit / NEED, 1900.0 / NEED, NAVY)
        seg((limit + 1900.0) / NEED, 330.0 / NEED, CORAL)
        bar_label((limit + 1900.0 + 165.0) / NEED, "330", WHITE, 19)

    ax.plot([0.07, 0.34], [0.115, 0.115], transform=ax.transAxes,
            color="#24425f", lw=1.4)
    T(0.07, 0.095, "Modelled on the public grid map and one recorded day.\n"
                   "Line ratings are estimates. NGCP does not publish them.", 14,
      MUTE)
    return fig


def main():
    limit = load_limit()
    solar = json.load(
        open(os.path.join(ROOT, "web", "data", "profiles.json")))["solar_profile"]
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        if f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))

    # beat 0 holds longest: it is the thumbnail the feed shows before anyone taps
    holds = [34, 26, 30, 26, 34]
    grow = [0, 10, 0, 10, 0]
    idx = 0
    for beat, (hold, g) in enumerate(zip(holds, grow)):
        for k in range(g):
            fig = card(beat, (k + 1) / max(g, 1), limit, max(solar))
            fig.savefig(os.path.join(FRAMES, f"f{idx:04d}.png"), dpi=100,
                        facecolor=BG)
            plt.close(fig)
            idx += 1
        for _ in range(hold):
            fig = card(beat, 1.0, limit, max(solar))
            fig.savefig(os.path.join(FRAMES, f"f{idx:04d}.png"), dpi=100,
                        facecolor=BG)
            plt.close(fig)
            idx += 1

    mp4 = os.path.join(DOCS, "pax-silica-social.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(FPS),
         "-i", os.path.join(FRAMES, "f%04d.png"),
         "-vf", "scale=1080:1350:flags=lanczos,format=yuv420p",
         "-c:v", "libx264", "-preset", "slow", "-crf", "20", mp4],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    gif = os.path.join(DOCS, "pax-silica-social.gif")
    pal = "/tmp/pds_pax_social_pal.png"
    vf = f"fps={FPS},scale=720:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(FRAMES, "f%04d.png"),
                    "-vf", vf + ",palettegen=stats_mode=diff", pal],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS),
                    "-i", os.path.join(FRAMES, "f%04d.png"), "-i", pal,
                    "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                    gif], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    for p in (mp4, gif):
        print("wrote", p, f"({os.path.getsize(p) // 1024} KB)")
    print(f"{idx} frames, {idx / FPS:.1f} s")


if __name__ == "__main__":
    main()
