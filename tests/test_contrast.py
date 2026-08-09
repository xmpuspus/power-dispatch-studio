#!/usr/bin/env python3
"""Check that every text-on-surface token pair clears WCAG AA.

The studio ships two themes and the map ships one. A token pair that reads
in light can fall under 4.5:1 in dark, and no screenshot review catches a
4.3 reliably. This reads the hex values out of the stylesheets and computes
the ratio, so a regression fails a command instead of an opinion.

Plain python, no pytest dependency. Run: python3 tests/test_contrast.py
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
TOKENS = os.path.join(ROOT, "studio", "src", "styles", "tokens.css")
MAP = os.path.join(ROOT, "web", "index.html")

# text token, background token, minimum ratio, what it is
# 4.5 is AA for body text. 3.0 is AA for large text (18px+ or 14px bold) and
# for the boundary of a control, per WCAG 1.4.11 non-text contrast.
STUDIO_PAIRS = [
    ("--text", "--bg", 4.5, "body text on the app background"),
    ("--text", "--surface", 4.5, "body text on a card"),
    ("--text", "--surface-2", 4.5, "body text on a sunken panel"),
    ("--text", "--surface-3", 4.5, "body text on a raised panel"),
    ("--text-muted", "--bg", 4.5, "secondary text on the app background"),
    ("--text-muted", "--surface", 4.5, "secondary text on a card"),
    ("--text-muted", "--surface-2", 4.5, "secondary text on a sunken panel"),
    ("--text-faint", "--surface", 4.5, "faint text on a card"),
    ("--text-faint", "--bg", 4.5, "faint text on the app background"),
    ("--primary", "--surface", 4.5, "link and accent text on a card"),
    ("--primary", "--bg", 4.5, "link and accent text on the background"),
    ("--primary", "--surface-2", 4.5, "the run dock's take-away action"),
    ("--text-muted", "--surface-3", 4.5, "secondary text on a raised panel"),
    ("--on-primary", "--primary", 4.5, "primary button label"),
    ("--accent", "--surface", 4.5, "highlight figure on a card"),
    ("--accent", "--bg", 4.5, "highlight figure on the background"),
    ("--destructive", "--surface", 4.5, "shortfall figure on a card"),
    ("--positive", "--surface", 4.5, "headroom figure on a card"),
    ("--border", "--surface", 1.3, "card edge against the card"),
    ("--border-strong", "--surface", 3.0, "control edge against a card"),
    ("--border-strong", "--surface-2", 3.0, "control edge against a sunken panel"),
    ("--border-strong", "--surface-3", 2.9, "control edge against a raised panel"),
    ("--chrome-text", "--chrome", 4.5, "top-bar label"),
    ("--chrome-muted", "--chrome", 4.5, "top-bar secondary label"),
    ("--chrome-accent", "--chrome", 4.5, "top-bar link"),
    ("--chrome-warn", "--chrome-2", 4.5, "top-bar warning"),
    ("--chrome-ok", "--chrome-2", 4.5, "top-bar confirmation"),
]

MAP_PAIRS = [
    ("--ink", "--bg", 4.5, "map body text on the page background"),
    ("--ink", "--paper", 4.5, "map body text on a panel"),
    ("--muted", "--paper", 4.5, "map secondary text on a panel"),
    ("--muted", "--bg", 4.5, "map secondary text on the page background"),
    # the panel hairline separates a panel from whatever the map draws behind
    # it, which is not a token pair, so no floor here would mean anything
]

# The methods page and the Pax Silica page carry the same theme key, so they
# get the same floor. Pax Silica keeps every figure on a light plate, so its
# plate tokens are checked against the plate and not against the page.
METHODOLOGY_PAIRS = [
    ("--ink", "--bg", 4.5, "heading on the page background"),
    ("--ink", "--card", 4.5, "heading on a card"),
    ("--muted", "--card", 4.5, "secondary text on a card"),
    ("--muted", "--bg", 4.5, "secondary text on the page background"),
    ("--link", "--bg", 4.5, "link on the page background"),
    ("--link", "--card", 4.5, "link on a card"),
    ("--ink", "--code-bg", 4.5, "inline code"),
]
PAX_PAIRS = [
    ("--ink", "--bg", 4.5, "heading on the page background"),
    ("--body", "--bg", 4.5, "body text on the page background"),
    ("--muted", "--bg", 4.5, "secondary text on the page background"),
]
PAX_PLATE_PAIRS = [
    ("--plateink", "--plate", 4.5, "figure title on its light plate"),
    ("--platetext", "--plate", 4.5, "figure body text on its light plate"),
    ("--platemute", "--plate", 4.5, "figure caption on its light plate"),
    ("--blue", "--plate", 4.5, "figure link on its light plate"),
    ("--red", "--plate", 4.5, "the figure accent mark on its light plate"),
]

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


def srgb(c):
    c = c / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexval):
    h = hexval.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b)


def ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    lo, hi = min(a, b), max(a, b)
    return (hi + 0.05) / (lo + 0.05)


def block_vars(text, start_pat):
    """Pull `--name: #hex;` pairs out of the first rule matching start_pat.

    Stops at the first closing brace, so it reads a rule written on one line as
    happily as one closing in the first column.
    """
    m = re.search(start_pat + r"\s*\{([^}]*)\}", text, re.S)
    if not m:
        return {}
    return {
        k: v
        for k, v in re.findall(
            r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", m.group(1)
        )
    }


def run(label, tokens, pairs):
    for fg, bg, floor, what in pairs:
        if fg not in tokens or bg not in tokens:
            check(f"{label}: {fg} on {bg} is declared", False, f"({what})")
            continue
        r = ratio(tokens[fg], tokens[bg])
        check(
            f"{label}: {fg} on {bg} clears {floor}:1",
            r >= floor,
            f"{r:.2f}:1  ({what})",
        )


css = open(TOKENS).read()
light = block_vars(css, r":root")
dark = dict(light)
dark.update(block_vars(css, r":root\[data-theme='dark'\]"))
run("studio light", light, STUDIO_PAIRS)
run("studio dark", dark, STUDIO_PAIRS)

html = open(MAP).read()
map_light = block_vars(html, r":root")
run("map", map_light, MAP_PAIRS)
# the map switches on the data-theme attribute, not a media query, so it can
# honour the pds.theme pin the studio writes
map_dark = block_vars(html, r":root\[data-theme='dark'\]")
check("map declares a dark theme", bool(map_dark))
check(
    "map reads the studio's pds.theme key",
    "pds.theme" in html and "data-theme" in html,
)

# every public page follows the same key, so a pin made on one holds on all
for fname, light_pairs, dark_extra in [
    ("methodology.html", METHODOLOGY_PAIRS, None),
    ("pax-silica.html", PAX_PAIRS, PAX_PLATE_PAIRS),
]:
    page = open(os.path.join(ROOT, "web", fname)).read()
    label = fname.replace(".html", "")
    check(f"{label} reads the pds.theme key", "pds.theme" in page)
    lt = block_vars(page, r":root")
    dk = dict(lt)
    dk.update(block_vars(page, r":root\[data-theme='dark'\]"))
    check(f"{label} declares a dark theme", dk != lt)
    run(f"{label} light", lt, light_pairs)
    run(f"{label} dark", dk, light_pairs)
    if dark_extra:
        # the plate keeps its light values in both themes, so one run covers both
        run(f"{label} plate", lt, dark_extra)
if map_dark:
    merged = dict(map_light)
    merged.update(map_dark)
    run("map dark", merged, MAP_PAIRS)

# Every fuel the charts can draw must resolve to a declared token. A shortage
# block once pointed at an undeclared --negative and painted near-black, which
# is the one state a reader most needs to see. Hue collisions between fuels are
# a separate, larger job: six adjacent pairs in the stack fail CVD separation
# and they need a validated re-step of the whole fuel ramp, not a token rename.
data_ts = open(os.path.join(ROOT, "studio", "src", "lib", "data.ts")).read()
fuel_map = dict(re.findall(r"^\s*(\w+): 'var\((--[a-z0-9-]+)\)',", data_ts, re.M))
check("every fuel color maps to a token", len(fuel_map) >= 12, f"{len(fuel_map)} fuels")
for mode, tokens in (("light", light), ("dark", dark)):
    for fuel, tok in sorted(fuel_map.items()):
        check(f"fuel {mode}: {fuel} -> {tok} is declared", tok in tokens)

print("\n" + ("contrast: all pairs clear AA" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
