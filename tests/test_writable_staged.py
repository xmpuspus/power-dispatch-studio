#!/usr/bin/env python3
"""Every file the claims oracle rewrites has to be staged by the nightly job.

`scripts/verify_claims.py --write` runs in the archive workflow and rewrites the
rolling numbers in each WRITABLE file. The commit step then stages a hand-typed
list of paths. A file that the oracle rewrites and that list misses loses its
rewrite, and the next `--check` run turns CI red days later with nothing local to
catch it.

So this compares the two lists. It is three lines of work that prevents a failure
mode with a multi-day delay between cause and symptom.

Plain python, no pytest dependency. Run: python3 tests/test_writable_staged.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import verify_claims as vc  # noqa: E402

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


lines = (
    open(os.path.join(ROOT, ".github", "workflows", "archive.yml")).read().split("\n")
)
staged: set[str] = set()
for i, line in enumerate(lines):
    if "git add " not in line:
        continue
    # keep reading while the shell line continues with a trailing backslash
    parts = [line.split("git add ", 1)[1]]
    while parts[-1].rstrip().endswith("\\"):
        parts[-1] = parts[-1].rstrip()[:-1]
        i += 1
        parts.append(lines[i])
    staged |= set(" ".join(parts).split())
check("the archive workflow stages files after the write", bool(staged))

for path in sorted(vc.WRITABLE):
    check(f"the nightly job stages {path}", path in staged)

# the reverse direction is a warning, not a failure: the job stages generated
# data directories that the oracle never touches, and that is correct
extra = [s for s in staged if s not in vc.WRITABLE and s.endswith((".md", ".html"))]
if extra:
    print(f"note: staged prose the oracle does not rewrite: {', '.join(extra)}")

check("the oracle knows it can write more than one file", len(vc.WRITABLE) >= 2)

print()
print(
    f"writable staging: {len(fails)} failures"
    if fails
    else "writable staging: all green"
)
sys.exit(1 if fails else 0)
