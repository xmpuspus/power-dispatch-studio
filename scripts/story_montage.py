#!/usr/bin/env python3
"""Tile four market charts into one GIF.

The panels compare grid-link limits, the effect of added demand, Sual's share of
spare capacity, and the share of a Meralco bill exposed to WESM prices:
  top-left    Leyte-Cebu reaches its limit most often
  top-right   added demand raises prices more when the grid is nearly full
  bottom-left one Sual unit removes 18 percent of spare capacity
  bottom-right WESM supplied 10 percent of Meralco's June 2026 energy

PIL composites the already-decoded panel frames (allowed); ffmpeg assembles the final
GIF (required, never PIL for GIF assembly). Output docs/story-montage.gif.
"""

import glob
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SRC = "/tmp/pds_montage_src"
FRAMES = "/tmp/pds_montage_frames"
OUT = os.path.join(DOCS, "story-montage.gif")

# the montage now tiles the dark cards, so its own chrome goes dark too
BG = "#0d1117"
NAVY, MUTE, CORAL = "#e9edf2", "#8592a3", "#ff5c39"
PANELS = [
    (
        "constraint-map.gif",
        "1.  Leyte-Cebu reaches a binding limit most often in the archive.",
    ),
    (
        "price-shape.gif",
        "2.  The same 300 MW causes a larger price increase when Luzon is nearly full.",
    ),
    (
        "sual-margin.gif",
        "3.  One Sual unit removes 18% of the whole system's spare margin.",
    ),
    (
        "bill-wedge.gif",
        "4.  WESM supplied 10% of Meralco's energy in June 2026.",
    ),
]
CELL_W, CELL_H = 820, 470
LABEL_H, BANNER_H, PAD = 42, 104, 12
COLS = 2
OUT_W = COLS * CELL_W + (COLS + 1) * PAD
OUT_H = BANNER_H + 2 * (LABEL_H + CELL_H) + 3 * PAD


def font(sz, bold=False):
    for p in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def load_frames(name):
    d = os.path.join(SRC, name.replace(".", "_"))
    os.makedirs(d, exist_ok=True)
    for f in glob.glob(os.path.join(d, "*.png")):
        os.remove(f)
    path = os.path.join(DOCS, name)
    if name.endswith(".png"):
        return [Image.open(path).convert("RGB")]
    subprocess.run(
        ["ffmpeg", "-y", "-i", path, os.path.join(d, "f%03d.png")],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return [
        Image.open(f).convert("RGB")
        for f in sorted(glob.glob(os.path.join(d, "f*.png")))
    ]


def fit(img, w, h):
    im = img.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    cell = Image.new("RGB", (w, h), BG)
    cell.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return cell


def main():
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(FRAMES, exist_ok=True)
    for f in glob.glob(os.path.join(FRAMES, "*.png")):
        os.remove(f)
    seqs = [load_frames(n) for n, _ in PANELS]
    n_out = 48
    tf, sf, lf = font(31, True), font(19), font(18, True)

    for t in range(n_out):
        canvas = Image.new("RGB", (OUT_W, OUT_H), BG)
        d = ImageDraw.Draw(canvas)
        d.text(
            (PAD + 4, 16),
            "Test how much data-center demand the Philippine grid can carry",
            font=tf,
            fill=NAVY,
        )
        d.text(
            (PAD + 4, 60),
            "The market operator's public files name equipment at its limit and "
            "show how the three island grids price scarce capacity.",
            font=sf,
            fill=MUTE,
        )
        for i, (seq, (_, label)) in enumerate(zip(seqs, PANELS)):
            r, c = divmod(i, COLS)
            x = PAD + c * (CELL_W + PAD)
            y = BANNER_H + r * (LABEL_H + CELL_H + PAD)
            col = CORAL if label[:2] in ("1.", "2.", "3.") else NAVY
            d.text((x + 2, y + 9), label, font=lf, fill=col)
            frame = seq[t % len(seq)]
            canvas.paste(fit(frame, CELL_W, CELL_H), (x, y + LABEL_H))
        canvas.save(os.path.join(FRAMES, f"m{t:03d}.png"))

    pal = "/tmp/pds_montage_pal.png"
    vf = "fps=8,scale=1200:-1:flags=lanczos"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            os.path.join(FRAMES, "m%03d.png"),
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
            "8",
            "-i",
            os.path.join(FRAMES, "m%03d.png"),
            "-i",
            pal,
            "-lavfi",
            vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            OUT,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print("wrote", OUT, f"({os.path.getsize(OUT) // 1024} KB)  {OUT_W}x{OUT_H}")


if __name__ == "__main__":
    main()
