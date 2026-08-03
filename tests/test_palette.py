#!/usr/bin/env python3
"""Check the fuel palette against the data-viz gates, and against itself.

Two failures this catches, both of which shipped before:

1. A fuel borrows another series' token. `wind` used to read `--series-flow`,
   which `hydro` already read, so the merit stack drew one block where the
   data had two. Five pairs collided that way. Here every fuel must own a
   declared token and no two may resolve to one hex.
2. A hue moves and stops being separable. The stack draws a fixed fuel order
   and each island grid carries a different subset, so the pairs that can ever
   touch are the union over the three grids. Every such pair must clear the
   colour-vision floor and the normal-vision floor.

The colour maths is the same OKLab and Machado-Oliveira-Fernandes transform the
data-viz skill's validator uses, vendored here so `make qa` needs no skill path.

Plain python, no pytest dependency. Run: python3 tests/test_palette.py
"""

import math
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
TOKENS = os.path.join(ROOT, "studio", "src", "styles", "tokens.css")
MAP = os.path.join(ROOT, "web", "index.html")

# thresholds, from the data-viz skill (references/color-formula.md)
BAND = {"light": (0.43, 0.77), "dark": (0.48, 0.67)}
CHROMA_FLOOR = 0.10
CVD_TARGET = 8.0
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0
SURFACE = {"light": "#ffffff", "dark": "#111a2b"}

# the stack draws this order, cheapest first (studio/src/studio/charts.tsx
# AREA_ORDER); `gas` is the token name for natural_gas
ORDER = [
    "solar",
    "wind",
    "hydro",
    "geothermal",
    "gas",
    "biomass",
    "coal",
    "storage",
    "oil",
]
# what each island grid carries, from web/data/dispatch.json fuel_avail_mw
PRESENT = {
    "luzon": set(ORDER),
    "visayas": set(ORDER) - {"gas"},
    "mindanao": set(ORDER) - {"gas", "wind"},
}
# declared but never side by side in a stack: a scenario addition, a flow, and
# one reserved status colour
EXTRA = ["firm", "import", "shortage"]

MACHADO = {
    "protan": [
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998],
    ],
    "deutan": [
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881],
    ],
}

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not cond:
        fails.append(name)


def hex2srgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))


def s2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lin(h):
    return tuple(s2lin(c) for c in hex2srgb(h))


def relative_luminance(h):
    r, g, b = lin(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def lin2oklab(r, g, b):
    # long, mid, short cone response; the names are the standard's
    lo = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    mi = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    sh = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    lo, mi, sh = lo ** (1 / 3), mi ** (1 / 3), sh ** (1 / 3)
    return (
        0.2104542553 * lo + 0.7936177850 * mi - 0.0040720468 * sh,
        1.9779984951 * lo - 2.4285922050 * mi + 0.4505937099 * sh,
        0.0259040371 * lo + 0.7827717662 * mi - 0.8086757660 * sh,
    )


def oklch(h):
    L, a, b = lin2oklab(*lin(h))
    return L, math.hypot(a, b)


def simulate(h, kind):
    r, g, b = lin(h)
    M = MACHADO[kind]
    return tuple(
        max(0.0, min(1.0, M[i][0] * r + M[i][1] * g + M[i][2] * b)) for i in range(3)
    )


def deltaE(h1, h2, kind=None):
    a = lin2oklab(*(simulate(h1, kind) if kind else lin(h1)))
    b = lin2oklab(*(simulate(h2, kind) if kind else lin(h2)))
    return 100 * math.dist(a, b)


def read_tokens(path, dark_selector):
    """Return {'light': {...}, 'dark': {...}} of every --fuel-* declaration."""
    with open(path) as f:
        css = f.read()
    cut = css.index(dark_selector)
    out = {}
    for mode, chunk in (("light", css[:cut]), ("dark", css[cut:])):
        out[mode] = {
            m.group(1): m.group(2).lower()
            for m in re.finditer(r"--fuel-([a-z-]+)\s*:\s*(#[0-9a-fA-F]{3,6})", chunk)
        }
    return out


def pairs_union():
    seen = set()
    for members in PRESENT.values():
        drawn = [f for f in ORDER if f in members]
        for a, b in zip(drawn, drawn[1:]):
            seen.add((a, b))
    return sorted(seen)


studio = read_tokens(TOKENS, ":root[data-theme='dark']")
mapdoc = read_tokens(MAP, ":root[data-theme='dark']")

# the map spells natural gas out; the studio calls the token --fuel-gas
for mode in ("light", "dark"):
    if "natural-gas" in mapdoc[mode]:
        mapdoc[mode]["gas"] = mapdoc[mode].pop("natural-gas")

want = ORDER + EXTRA
for mode in ("light", "dark"):
    missing = [f for f in want if f not in studio[mode]]
    check(f"the studio declares every fuel in {mode} (missing: {missing})", not missing)
    missing = [f for f in want if f not in mapdoc[mode]]
    check(f"the map declares every fuel in {mode} (missing: {missing})", not missing)
    drift = sorted(
        f
        for f in want
        if f in studio[mode]
        and f in mapdoc[mode]
        and studio[mode][f] != mapdoc[mode][f]
    )
    check(
        f"the map and the studio agree on every fuel in {mode} (drift: {drift})",
        not drift,
    )

# No two fuels may resolve to one hex. This is the collision the redraw fixed:
# a shared token drew two stack blocks as one.
for mode in ("light", "dark"):
    seen = {}
    dupes = []
    for f in want:
        hx = studio[mode].get(f)
        if hx is None:
            continue
        if hx in seen:
            dupes.append(f"{seen[hx]}={f} ({hx})")
        seen[hx] = f
    check(f"no two fuels share a hex in {mode} (collisions: {dupes})", not dupes)

# The gates, on the pairs that share an edge in a real stack.
PAIRS = pairs_union()
for mode in ("light", "dark"):
    lo, hi = BAND[mode]
    surface = SURFACE[mode]
    bad_band, bad_chroma, bad_contrast = [], [], []
    for f in ORDER:
        hx = studio[mode].get(f)
        if hx is None:
            continue
        L, C = oklch(hx)
        if not (lo <= L <= hi):
            bad_band.append(f"{f} L{L:.3f}")
        if C < CHROMA_FLOOR:
            bad_chroma.append(f"{f} C{C:.3f}")
        if contrast(hx, surface) < CONTRAST_MIN:
            bad_contrast.append(f"{f} {contrast(hx, surface):.2f}:1")
    check(f"{mode}: every fuel sits in the lightness band ({bad_band})", not bad_band)
    check(f"{mode}: every fuel clears the chroma floor ({bad_chroma})", not bad_chroma)
    check(
        f"{mode}: every fuel clears 3:1 on the panel it is drawn on ({bad_contrast})",
        not bad_contrast,
    )

    worst_cvd = worst_norm = None
    where_cvd = where_norm = ""
    for a, b in PAIRS:
        ha, hb = studio[mode].get(a), studio[mode].get(b)
        if not ha or not hb:
            continue
        cvd = min(deltaE(ha, hb, "protan"), deltaE(ha, hb, "deutan"))
        nrm = deltaE(ha, hb)
        if worst_cvd is None or cvd < worst_cvd:
            worst_cvd, where_cvd = cvd, f"{a} vs {b}"
        if worst_norm is None or nrm < worst_norm:
            worst_norm, where_norm = nrm, f"{a} vs {b}"
    check(
        f"{mode}: every touching pair clears colour-vision {CVD_TARGET}",
        worst_cvd is not None and worst_cvd >= CVD_TARGET,
        f"worst {worst_cvd:.1f} at {where_cvd}, {len(PAIRS)} pairs",
    )
    check(
        f"{mode}: every touching pair clears the normal-vision floor {NORMAL_FLOOR}",
        worst_norm is not None and worst_norm >= NORMAL_FLOOR,
        f"worst {worst_norm:.1f} at {where_norm}",
    )

print()
print(f"{len(fails)} failed" if fails else "palette checks pass")
sys.exit(1 if fails else 0)
