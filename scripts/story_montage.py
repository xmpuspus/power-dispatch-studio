#!/usr/bin/env python3
"""One attachable view for LinkedIn: tile the figure panels into a single GIF with
plain-English labels, so the whole gridbill-ph story reads in one frame. Ported from
gridbill-us scripts/story_montage.py.

Thesis: the choke points already bind daily and the market prices them; the announced
data-center wave is the size of the margin; and a WESM swing is only a lagged slice of
the Meralco bill. The four panels carry that:
  top-left    constraint league   -> the grid names its own choke point
  top-right   regional price fan   -> one market, three prices, once trading resumes
  bottom-left Sual arithmetic      -> one unit trip takes a fifth of the margin
  bottom-right the bill wedge (static) -> a WESM swing is only a slice, and only later

PIL composites the already-decoded panel frames (allowed); ffmpeg assembles the final
GIF (required, never PIL for GIF assembly). Output docs/story-montage.gif.
"""
import glob
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
SRC = "/tmp/gridbill_montage_src"
FRAMES = "/tmp/gridbill_montage_frames"
OUT = os.path.join(DOCS, "story-montage.gif")

NAVY, MUTE, CORAL = "#12335c", "#5b6b75", "#e2664b"
PANELS = [
    ("constraint-league.gif",
     "1.  The grid names its own choke point. Named 230 kV lines at a limit on most of 90 days."),
    ("price-shape.gif",
     "2.  The price is a shape. The same data center barely moves it with room, jumps it when full."),
    ("sual-margin.gif",
     "3.  One plant trip takes a fifth of the margin with it. Arithmetic, not prophecy."),
    ("bill-wedge.png",
     "And a WESM swing is only a slice of the Meralco bill, and only on the next month's bill."),
]
CELL_W, CELL_H = 820, 470
LABEL_H, BANNER_H, PAD = 42, 104, 12
COLS = 2
OUT_W = COLS * CELL_W + (COLS + 1) * PAD
OUT_H = BANNER_H + 2 * (LABEL_H + CELL_H) + 3 * PAD


def font(sz, bold=False):
    for p in ("/System/Library/Fonts/Helvetica.ttc",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf"):
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
    subprocess.run(["ffmpeg", "-y", "-i", path, os.path.join(d, "f%03d.png")],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return [Image.open(f).convert("RGB")
            for f in sorted(glob.glob(os.path.join(d, "f*.png")))]


def fit(img, w, h):
    im = img.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    cell = Image.new("RGB", (w, h), "white")
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
        canvas = Image.new("RGB", (OUT_W, OUT_H), "white")
        d = ImageDraw.Draw(canvas)
        d.text((PAD + 4, 16),
               "Can the Philippine grid host the data-center wave?",
               font=tf, fill=NAVY)
        d.text((PAD + 4, 60),
               "Built from the market operator's own public files. The choke points "
               "already bind daily; the market prices them.",
               font=sf, fill=MUTE)
        for i, (seq, (_, label)) in enumerate(zip(seqs, PANELS)):
            r, c = divmod(i, COLS)
            x = PAD + c * (CELL_W + PAD)
            y = BANNER_H + r * (LABEL_H + CELL_H + PAD)
            col = CORAL if label[:2] in ("1.", "2.", "3.") else NAVY
            d.text((x + 2, y + 9), label, font=lf, fill=col)
            frame = seq[t % len(seq)]
            canvas.paste(fit(frame, CELL_W, CELL_H), (x, y + LABEL_H))
        canvas.save(os.path.join(FRAMES, f"m{t:03d}.png"))

    pal = "/tmp/gridbill_montage_pal.png"
    vf = "fps=8,scale=1200:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-y", "-i", os.path.join(FRAMES, "m%03d.png"),
                    "-vf", vf + ",palettegen=stats_mode=diff", pal], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-framerate", "8",
                    "-i", os.path.join(FRAMES, "m%03d.png"), "-i", pal,
                    "-lavfi", vf + "[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
                    OUT], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    print("wrote", OUT, f"({os.path.getsize(OUT) // 1024} KB)  {OUT_W}x{OUT_H}")


if __name__ == "__main__":
    main()
