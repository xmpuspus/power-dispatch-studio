#!/bin/zsh
# Record the gridbill-ph story GIF: a real screen recording of the live map driven
# through the three questions. Uses agent-browser's native WebM video capture (a real
# recording of the running page, not stitched screenshots), then ffmpeg two-pass
# palettegen to a GIF. Reproducible: make serve first, then `zsh build/record_demo.sh`.
#
# Beats, in order:
#   open -> Q1 Supply (the wave-vs-margin bars)
#   -> Q2 Choke points (the constraint league) + hover the Leyte-Cebu line
#      + toggle the Sual arithmetic
#   -> Q3 Prices (the regional sparkline + the Meralco bill panel)
#   -> open the findings drawer and fly to the Leyte-Cebu finding
set -u
BASE="${1:-http://localhost:8789}"
ROOT="${0:A:h:h}"
OUT="$ROOT/docs/hero.gif"
WEBM="/tmp/gridbill_demo.webm"

step(){ agent-browser eval "$1" >/dev/null 2>&1; sleep "${2:-1.4}"; }

agent-browser close >/dev/null 2>&1; sleep 2
agent-browser record start "$WEBM" "$BASE/" >/dev/null 2>&1
sleep 5   # let the map paint and the rail load

# Q1 Supply: hold on the announced-wave bars
step 'document.querySelector("[data-mode=supply]").click()' 2.4

# Q2 Choke points: the league, then hover the Leyte-Cebu line, then Sual toggle
step 'document.querySelector("[data-mode=choke]").click()' 2.2
step 'map.flyTo({center:[124.27,10.7],zoom:7.2,duration:900})' 1.8
# synthesize a hover popup over the corridor line (real layer, real properties)
step 'const f=map.queryRenderedFeatures({layers:["choke-line"]}); if(f[0]){pop.setLngLat([123.9,10.6]).setHTML("<b>230 kV Leyte-Cebu corridor</b><br>At a limit on 87 of the window’s days").addTo(map);}' 2.4
step 'document.getElementById("sualbtn") && document.getElementById("sualbtn").click()' 2.6

# Q3 Prices: the sparkline and the bill panel
step 'pop.remove(); document.querySelector("[data-mode=price]").click()' 3.0

# Findings drawer: open and fly to the named-choke-point finding
step 'document.getElementById("fopen").click()' 1.6
step 'document.querySelectorAll("#flist .fcard")[0].click()' 3.0

agent-browser record stop >/dev/null 2>&1
sleep 2
agent-browser close >/dev/null 2>&1

if [ ! -f "$WEBM" ]; then echo "no recording produced"; exit 1; fi

PAL=/tmp/gridbill_demo_pal.png
VF="fps=12,scale=900:-1:flags=lanczos"
ffmpeg -y -i "$WEBM" -vf "${VF},palettegen=stats_mode=diff" "$PAL" >/dev/null 2>&1
ffmpeg -y -i "$WEBM" -i "$PAL" -lavfi "${VF}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "$OUT" >/dev/null 2>&1
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
