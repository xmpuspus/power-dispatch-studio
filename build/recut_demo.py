"""Re-cut a recorded demo into the smallest GIF that still reads well.

A README on GitHub gets no lazy loading: every embedded image downloads when the
page opens, whether the reader scrolls to it or not. I measured that against the
rendered page, and a closed `<details>` does not defer the fetch either. So the
weight of the embedded set is the cost of opening the front door, and it has to
be spent on purpose.

A screen recording costs about 20 KB per GIF frame at 840 px, because a panning
map changes every pixel and inter-frame compression wins nothing. Duration and
frame rate therefore buy more than any palette flag. gifsicle --lossy moved
these files by under 2 percent, so it is not used.

    python3 build/recut_demo.py docs/hero.gif --src /tmp/map-rec/map-hero.webm
    python3 build/recut_demo.py docs/studio-e2e.gif --trim 6:38 --fps 8

Reads --src if given, else the .mp4 beside the target, else the target itself.
Prints the before and after size so the trade is on the record.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def mb(p: Path) -> float:
    return p.stat().st_size / 1048576 if p.exists() else 0.0


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd[:6])}...\n{r.stderr[-800:]}")


def source_for(out: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    mp4 = out.with_suffix(".mp4")
    if mp4.exists():
        return mp4
    if out.exists():
        return out
    sys.exit(f"no source for {out}")


def recut(out: Path, src: Path, fps: int, width: int, colors: int, trim: str | None) -> None:
    before = mb(out)
    cut: list[str] = []
    if trim:
        start, end = trim.split(":")
        cut = ["-ss", start, "-to", end]
    chain = f"fps={fps},scale={width}:-1:flags=lanczos"
    with tempfile.TemporaryDirectory() as td:
        pal = Path(td) / "pal.png"
        tmp = Path(td) / "out.gif"
        run(["ffmpeg", "-v", "error", "-y", *cut, "-i", str(src),
             "-vf", f"{chain},palettegen=stats_mode=diff:max_colors={colors}", str(pal)])
        run(["ffmpeg", "-v", "error", "-y", *cut, "-i", str(src), "-i", str(pal),
             "-lavfi", f"{chain}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
             str(tmp)])
        if shutil.which("gifsicle"):
            packed = Path(td) / "packed.gif"
            r = subprocess.run(["gifsicle", "-O3", str(tmp), "-o", str(packed)],
                               capture_output=True)
            if r.returncode == 0 and packed.stat().st_size < tmp.stat().st_size:
                packed.replace(tmp)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(tmp, out)
    name = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"{name}: {before:.2f} MB -> {mb(out):.2f} MB "
          f"(fps {fps}, {width} px, {colors} colors)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--src")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--width", type=int, default=840)
    ap.add_argument("--colors", type=int, default=96)
    ap.add_argument("--trim", help="START:END in seconds, passed to ffmpeg -ss/-to")
    a = ap.parse_args()
    out = Path(a.target)
    if not out.is_absolute():
        out = ROOT / out
    recut(out, source_for(out, a.src), a.fps, a.width, a.colors, a.trim)


if __name__ == "__main__":
    main()
