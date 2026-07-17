#!/usr/bin/env bash
# Convert the per-view recordings (scripts/record-views.py) to optimized GIFs.
# Two-pass ffmpeg palette then gifsicle, the same recipe as the workflow demos.
# Reproducible: record first, then `bash scripts/convert-views.sh`.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=/tmp/studio-viewrec
OUT=docs
VIEWS="backcast explain week forward multiyear ensembles expansion capture portfolio crossrun rtdoe5 nodal vintage"

for k in $VIEWS; do
  [ -f "$SRC/$k.webm" ] || { echo "missing $SRC/$k.webm (run record-views.py $k)"; continue; }
  ffmpeg -y -ss 2 -i "$SRC/$k.webm" \
    -vf "fps=9,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/vpal.png >/dev/null 2>&1
  ffmpeg -y -ss 2 -i "$SRC/$k.webm" -i /tmp/vpal.png \
    -lavfi "fps=9,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
    /tmp/vraw.gif >/dev/null 2>&1
  gifsicle -O3 --lossy=60 /tmp/vraw.gif -o "$OUT/view-$k.gif"
  printf "%-24s %s\n" "$OUT/view-$k.gif" "$(du -h "$OUT/view-$k.gif" | cut -f1)"
done
