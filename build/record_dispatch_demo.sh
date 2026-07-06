#!/bin/zsh
# Record a real end-to-end walkthrough of the Simulate (merit-order dispatch) mode.
# Drives the live map with agent-browser and captures Playwright-native WebM, then
# ffmpeg two-pass palette to an optimized GIF. Requires: make serve (:8789) running.
set -u
BASE="${1:-http://localhost:8789}"
OUT=tmp/sim-qa
mkdir -p "$OUT"
WEBM="$OUT/plexos-demo.webm"
GIF="docs/dispatch-demo.gif"

ab(){ agent-browser "$@" >/dev/null 2>&1 }
ev(){ agent-browser eval "$1" >/dev/null 2>&1 }

ab close; sleep 1
# fresh recorded context, navigate to the map
ab record start "$WEBM" "$BASE/"
ab set viewport 1280 800
ab wait 5500                                   # basemap tiles + baked data load

# Beat 1: enter Simulate mode, let the stack settle (Luzon, on the coal margin)
ev 'document.querySelector("[data-mode=simulate]").click()'
ab wait 2200
# inject a smooth slider-ramp helper (real input events, the tool re-clears live)
ev 'window.__anim=(id,to,ms)=>{const el=document.getElementById(id);if(!el)return Promise.resolve();const from=+el.value,t0=performance.now();return new Promise(r=>{function f(t){const k=Math.min(1,(t-t0)/ms);el.value=Math.round(from+(to-from)*k);el.dispatchEvent(new Event("input"));k<1?requestAnimationFrame(f):r();}requestAnimationFrame(f);});}'

# Beat 2: add the data-center wave; the demand line marches into the oil block and
# the clearing price flips from coal (P6) to oil (P12)
ev 'window.__anim("sim-dc",3000,3800)'
ab wait 4100
ab wait 1300                                   # hold on the P6 -> P12 flip

# Beat 3: trip Sual (N-1) on top of the wave; a supply shortfall opens (red)
ev 'const t=document.getElementById("sim-trip");t.value="Sual";t.dispatchEvent(new Event("change"))'
ab wait 2000

# Beat 4: relieve a choke point (extra inter-island import); the shortfall shrinks
ev 'window.__anim("sim-imp",250,2200)'
ab wait 2500
ab wait 1200

# Beat 5: reset and switch to the constrained Visayas grid to show the tighter stack
ev 'window.__anim("sim-dc",0,1000)'
ab wait 1200
ev 'const t=document.getElementById("sim-trip");t.value="";t.dispatchEvent(new Event("change"))'
ev 'document.querySelector(".gsel[data-grid=visayas]").click()'
ab wait 2000
ev 'window.__anim("sim-dc",700,2200)'
ab wait 2500
ab wait 1300

ab record stop
ab close
sleep 1

RAW=$(ls -S "$OUT"/*.webm 2>/dev/null | head -1)
[ -n "$RAW" ] || { echo "no webm captured"; exit 1 }
echo "captured: $RAW ($(du -h "$RAW" | cut -f1))"

# webm -> optimized GIF, two-pass palette, capped width for GitHub camo (<5 MB)
ffmpeg -y -i "$RAW" -vf "fps=10,scale=880:-1:flags=lanczos,palettegen=max_colors=128:stats_mode=diff" "$OUT/pal.png" >/dev/null 2>&1
ffmpeg -y -i "$RAW" -i "$OUT/pal.png" -lavfi "fps=10,scale=880:-1:flags=lanczos [x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" "$OUT/raw.gif" >/dev/null 2>&1
gifsicle -O3 --lossy=90 --colors 128 "$OUT/raw.gif" -o "$GIF"
echo "wrote $GIF ($(du -h "$GIF" | cut -f1))"
