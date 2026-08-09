#!/usr/bin/env python3
"""Pin the README's studio-view table to nav.ts.

The README lists all 40 studio views as `#v=<slug>` deep links instead of
embedding 40 clips, because GitHub applies no lazy loading and 40 clips would
cost about 200 MB on open. A hand-maintained list of 40 rows is the most
drift-prone thing in the file, so it is checked here: every slug that nav.ts
declares appears exactly once in the README, with the label nav.ts gives it,
and the README invents no slug that nav.ts does not have.

Plain python, no pytest dependency. Run: python3 tests/test_readme_views.py
Regenerate the table body: python3 build/gen_view_table.py --write
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "build"))

from gen_view_table import destinations, render  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


dests = destinations()
check("nav.ts declares 40 destinations", len(dests) == 40)

with open(os.path.join(ROOT, "README.md")) as f:
    readme = f.read()

linked = re.findall(r"/studio/#v=([a-z0-9-]+)\)", readme)
declared = [d["slug"] for d in dests]

missing = [s for s in declared if s not in linked]
extra = [s for s in linked if s not in declared]

check(
    f"every declared slug is linked from the README (missing: {missing})", not missing
)
check(f"the README links no slug nav.ts does not declare (extra: {extra})", not extra)

# uniqueness is a property of the table, not of the whole file: prose elsewhere
# may link a view a second time in context, and should be free to
table = readme.split("<!-- views table start -->")[1].split("<!-- views table end -->")[
    0
]
in_table = re.findall(r"/studio/#v=([a-z0-9-]+)\)", table)
dupes = sorted({s for s in in_table if in_table.count(s) > 1})
check(f"the table lists each slug once (dupes: {dupes})", not dupes)
check(f"the table lists all 40 ({len(in_table)})", len(in_table) == len(declared))

# the label and the one-line hint are nav.ts's own words; a rewrite in the
# README would silently disagree with what the app shows in its palette
for d in dests:
    row = re.search(
        r"^\|[^|]*\| \["
        + re.escape(d["label"])
        + r"\]\([^)]*#v="
        + re.escape(d["slug"])
        + r"\) \| ([^|]+?) \|$",
        readme,
        re.M,
    )
    if not row:
        fails.append(f"README row missing or relabelled for {d['slug']}")
        print(f"FAIL README row missing or relabelled for {d['slug']}")
    elif row.group(1).strip() != d["hint"]:
        fails.append(f"README hint drifted for {d['slug']}")
        print(
            f"FAIL README hint drifted for {d['slug']}: "
            f"{row.group(1).strip()!r} != {d['hint']!r}"
        )

# the whole rendered block must appear verbatim, so a row cannot be reordered
# out of its question group
check(
    "the rendered table block appears verbatim in the README", render(dests) in readme
)

# --- every in-page link in the contents has to reach a real heading -----------
# GitHub builds the anchor by lowercasing the heading, dropping everything that
# is not a letter, digit, space or hyphen, then turning spaces into hyphens. A
# heading reword that misses its contents entry gives a link that silently
# scrolls nowhere.


def slugify(heading):
    s = heading.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s", "-", s.strip())


anchors = {slugify(m.group(1)) for m in re.finditer(r"^#{1,6} (.+)$", readme, re.M)}
wanted = re.findall(r"\]\(#([a-z0-9-]+)\)", readme)
dead = sorted({a for a in wanted if a not in anchors})
check(f"every in-page contents link reaches a heading (dead: {dead})", not dead)

# --- the stated media weight has to match the files on disk -------------------
# GitHub applies no lazy loading, so the embedded set is what a reader downloads
# on open. The README states that number, so it is measured here rather than
# trusted.
embedded = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme))
embedded |= set(re.findall(r'src="([^"]+)"', readme))
embedded = {p for p in embedded if not p.startswith("http")}
gone = sorted(p for p in embedded if not os.path.isfile(os.path.join(ROOT, p)))
check(f"every embedded file exists (missing: {gone})", not gone)

total_mb = (
    sum(
        os.path.getsize(os.path.join(ROOT, p))
        for p in embedded
        if os.path.isfile(os.path.join(ROOT, p))
    )
    / 1048576
)
stated = re.search(
    r"downloads (\d+\.\d) MB of media across\s*\n?\s*(\d+) files", readme
)
check("the README states its own media weight", stated is not None)
if stated:
    check(
        f"stated MB matches the files on disk ({stated.group(1)} vs {total_mb:.1f})",
        abs(float(stated.group(1)) - total_mb) < 0.05,
    )
    check(
        f"stated file count matches ({stated.group(2)} vs {len(embedded)})",
        int(stated.group(2)) == len(embedded),
    )

print(f"\n{len(fails)} failures" if fails else "\nall green")
sys.exit(1 if fails else 0)
