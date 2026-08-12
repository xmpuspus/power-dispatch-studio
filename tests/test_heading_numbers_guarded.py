#!/usr/bin/env python3
"""Every number in a section heading must belong to the claims oracle.

Two headings froze while the archive window rolled under them, and both times
the body two paragraphs down carried the right figure from the same build:

- the loss-surface heading held +0.72 / -0.57 against a body reading +0.73 / -0.58
- the Leyte-Cebu heading held 114 of 117 against a body reading 124 of 127

A heading is the most-read line on the page, so a stale one contradicts the
evidence under it in the place a reader trusts most. This walks every heading in
the files the oracle can rewrite and fails on a number no registry entry covers.

Add a registry entry in scripts/verify_claims.py, or list the number below with
the reason it cannot move.
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import verify_claims as v  # noqa: E402

# Numbers that do not come from the data build. Each needs a reason.
FIXED = {
    "366": "days in 2028, a leap year",
    "90": "IEMOP's published window length, a policy not a measurement",
    "5": "the 5-minute dispatch interval, IEMOP's own cadence",
    "42": "studio destinations, pinned by tests/test_readme_views.py against nav.ts",
    "3,000": "a demand figure the reader chooses on the slider",
    "350": "the size of the worked contract book, an input",
    "6": "a round price the sentence calls approximate",
    "1": "ordinal or count in prose, never a measurement",
    "2": "ordinal or count in prose, never a measurement",
    "141": "named units in the fleet, pinned by tests/test_unit_probe.py",
    "2028": "a calendar year the build list names",
    "365": "days the engine solves separately, a model decision, not a measurement",
    "8760": "the hours in a year the engine deliberately does NOT solve as one program",
    "0.02": "the declared browser-to-Python price tolerance, set by the engine",
}

NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def clean(tok):
    """Trailing punctuation rides along with a number at the end of a clause."""
    return tok.rstrip(".,;:")
fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


for path in sorted(v.WRITABLE):
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        continue
    text = open(full, encoding="utf-8").read()
    spans = []
    for _f, rx, _keys in [e for e in v.REGISTRY if e[0] == path]:
        m = rx.search(text)
        if m:
            spans.append((m.start(), m.end()))
    # Markdown headings and HTML h2/h3 both count as headings here.
    heads = [
        (m.start(), m.end(), m.group(1))
        for m in re.finditer(r"^#{2,3} (.+)$", text, re.M)
    ]
    heads += [
        (m.start(), m.end(), re.sub(r"<[^>]+>", "", m.group(1)))
        for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", text, re.S)
    ]
    for pos, endpos, head in heads:
        for num in NUM.findall(head):
            num = clean(num)
            if num.lstrip("+-") in FIXED:
                continue
            # An HTML heading's registry match starts inside the tag, so test
            # whether the match overlaps the heading at all, not whether it
            # contains the tag's first character.
            covered = any(s < endpos and pos < e for s, e in spans)
            check(
                f"{path}: '{num}' in a heading is guarded ({head[:52]})",
                covered,
            )

print()
print(f"heading numbers: {len(fails)} failures" if fails else "\nheading numbers: all green")
sys.exit(1 if fails else 0)
