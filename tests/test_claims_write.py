#!/usr/bin/env python3
"""`verify_claims --write` has to actually rewrite what it says it rewrote.

The rewrite guards a number with a digit boundary, so replacing 0.24 never
corrupts 0.241. The first version of that guard also blocked a full stop, which
meant a registered number at the END of a sentence could never be rewritten:
--write counted it as fixed, wrote nothing, and the next --check failed with no
sign of why. The nightly cron would have gone red on its own schedule.

These cases pin the boundary in both directions on the real function.

Plain python, no pytest dependency. Run: python3 tests/test_claims_write.py
"""

import os
import re
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


def rewrite(text, rx, keys, canon):
    """Run one registry entry through the writer, as _check_file does."""
    saved = vc.REGISTRY[:]
    saved_w = set(vc.WRITABLE)
    try:
        vc.REGISTRY[:] = [("t.md", rx, keys)]
        vc.WRITABLE.add("t.md")
        out, problems, fixed = vc._check_file("t.md", text, canon, True)
        return out, problems, fixed
    finally:
        vc.REGISTRY[:] = saved
        vc.WRITABLE.clear()
        vc.WRITABLE.update(saved_w)


CANON = {"a": "0.243", "b": "1,311,900", "c": "5.77"}

cases = [
    (
        "a number that ends a sentence",
        "the correlation goes from 0.133 to 0.241.",
        re.compile(r"to ([\d.]+)\."),
        ["a"],
        "the correlation goes from 0.133 to 0.243.",
    ),
    (
        "a number mid-sentence",
        "the net is P954,000 for the day",
        re.compile(r"net is P([\d,]+) for"),
        ["b"],
        "the net is P1,311,900 for the day",
    ),
    (
        "a number followed by a unit",
        "spot rises to P5.22/kWh here",
        re.compile(r"rises to P([\d.]+)/kWh"),
        ["c"],
        "spot rises to P5.77/kWh here",
    ),
    (
        "a number at the very end of the file",
        "the correlation is 0.241",
        re.compile(r"correlation is ([\d.]+)"),
        ["a"],
        "the correlation is 0.243",
    ),
]

for name, text, rx, keys, want in cases:
    out, problems, fixed = rewrite(text, rx, keys, CANON)
    check(f"{name} rewrites", out == want)
    check(f"{name} counts one fix", fixed == 1)
    check(f"{name} reports no problem", problems == [])

# the guard still has to protect a longer number that starts with the old one
out, _p, _f = rewrite(
    "the value 0.241 sits beside 0.2415",
    re.compile(r"value ([\d.]+) sits"),
    ["a"],
    CANON,
)
check("a longer number beside it survives", out == "the value 0.243 sits beside 0.2415")

# and a rewrite that changes nothing must not claim a fix
out, _p, fixed = rewrite(
    "the correlation is 0.243",
    re.compile(r"correlation is ([\d.]+)"),
    ["a"],
    CANON,
)
check("an already-correct number counts no fix", fixed == 0)

print()
print(f"claims write: {len(fails)} failures" if fails else "claims write: all green")
sys.exit(1 if fails else 0)
