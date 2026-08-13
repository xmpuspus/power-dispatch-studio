#!/usr/bin/env python3
"""Pin the Studio catalog's view table to nav.ts.

The catalog lists every supported Studio view as a `#v=<slug>` deep link. A
hand-maintained table can drift from the app, so this test checks that every
slug that nav.ts
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
check("nav.ts declares 26 destinations", len(dests) == 26)

# The view catalog lives outside the front-page README so it can document every
# route without making the project introduction harder to scan.
CATALOG = os.path.join(ROOT, "docs", "studio-views.md")
with open(CATALOG) as f:
    readme = f.read()

linked = re.findall(r"/studio/#v=([a-z0-9-]+)\)", readme)
declared = [d["slug"] for d in dests]

missing = [s for s in declared if s not in linked]
extra = [s for s in linked if s not in declared]

check(
    f"every declared slug is linked from the view catalog (missing: {missing})",
    not missing,
)
check(f"the catalog links no slug nav.ts does not declare (extra: {extra})", not extra)

# uniqueness is a property of the table, not of the whole file: prose elsewhere
# may link a view a second time in context, and should be free to
table = readme.split("<!-- views table start -->")[1].split("<!-- views table end -->")[
    0
]
in_table = re.findall(r"/studio/#v=([a-z0-9-]+)\)", table)
dupes = sorted({s for s in in_table if in_table.count(s) > 1})
check(f"the table lists each slug once (dupes: {dupes})", not dupes)
check(f"the table lists all 26 ({len(in_table)})", len(in_table) == len(declared))

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

# --- the project front door is a browser how-to, not only a task index -------
FRONT = os.path.join(ROOT, "README.md")
with open(FRONT, encoding="utf-8") as f:
    front = f.read()

how_to_labels = [
    "Use the Studio in five minutes",
    "Replay a recorded market day",
    "Run, save, and compare a scenario",
    "Observed day",
    "Dispatch engine",
    "Evidence and sources",
    "Copy link",
    "Export CSV",
    "Results current",
    "Save run",
    "Saved runs",
    "Export runs",
]
for label in how_to_labels:
    check(f"README how-to names {label!r}", label in front)

front_images = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", front))
front_images |= set(re.findall(r'src="([^"]+)"', front))
front_images = {q for q in front_images if not q.startswith("http")}
expected_images = {
    "docs/hero.png",
    "docs/studio-shell.gif",
    "docs/analyst-walkthrough.gif",
}
check(
    f"README embeds the static overview and two how-to clips ({sorted(front_images)})",
    front_images == expected_images,
)
for clip in ("docs/studio-shell.mp4", "docs/analyst-walkthrough.mp4"):
    check(f"README links {clip}", f"]({clip})" in front)
    check(f"{clip} exists", os.path.isfile(os.path.join(ROOT, clip)))


# --- the stated media weight has to match the files on disk -------------------
# GitHub applies no lazy loading, so the embedded set is what a reader downloads
# on open. Each page states its own weight and it is measured here, never
# trusted. The catalog and the findings split off the README on 2026-08-12, so
# the front door has to stay light on its own.
def weigh(rel):
    text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    emb = set(re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text))
    emb |= set(re.findall(r'src="([^"]+)"', text))
    emb = {q for q in emb if not q.startswith("http")}
    here = os.path.dirname(os.path.join(ROOT, rel))
    # Resolve the way GitHub does, relative to the page. Resolving from the repo
    # root instead hides the break a moved page causes: docs/findings.md linking
    # "docs/x.gif" would point at docs/docs/x.gif on the site and still pass here.
    resolved = {q: os.path.normpath(os.path.join(here, q)) for q in emb}
    missing = sorted(q for q, c in resolved.items() if not os.path.isfile(c))
    check(f"{rel}: every embedded file exists (missing: {missing})", not missing)
    mb = (
        sum(os.path.getsize(c) for c in resolved.values() if os.path.isfile(c))
        / 1048576
    )
    stated = re.search(
        r"downloads (\d+\.\d) MB of media across\s*\n?\s*(\d+) files?", text
    )
    check(f"{rel}: states its own media weight", stated is not None)
    if stated:
        check(
            f"{rel}: stated MB matches disk ({stated.group(1)} vs {mb:.1f})",
            abs(float(stated.group(1)) - mb) < 0.05,
        )
        check(
            f"{rel}: stated file count matches ({stated.group(2)} vs {len(emb)})",
            int(stated.group(2)) == len(emb),
        )
    return mb


front_mb = weigh("README.md")
weigh("docs/studio-views.md")
# The front door is what a stranger loads before deciding anything, so cap it.
check(f"the README stays under 8 MB of media ({front_mb:.1f})", front_mb < 8.0)

print(f"\n{len(fails)} failures" if fails else "\nall green")


def test_readme_views_script():
    assert not fails, "\n".join(fails)


if __name__ == "__main__":
    sys.exit(1 if fails else 0)
