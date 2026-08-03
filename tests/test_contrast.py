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
    ("--line", "--paper", 1.3, "map panel edge"),
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
    """Pull `--name: #hex;` pairs out of the first rule matching start_pat."""
    m = re.search(start_pat + r"\s*\{(.*?)\n\}", text, re.S)
    if not m:
        return {}
    return {
        k: v for k, v in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", m.group(1))
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
if map_dark:
    merged = dict(map_light)
    merged.update(map_dark)
    run("map dark", merged, MAP_PAIRS)

print("\n" + ("contrast: all pairs clear AA" if not fails else f"{len(fails)} FAILED"))
sys.exit(1 if fails else 0)
