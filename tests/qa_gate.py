#!/usr/bin/env python3
"""Check visible text for banned claims, em dashes, AI jargon, and overwriting.

A failure means the map is about to make an unsupported claim or sound
machine-written.
Run: python3 tests/qa_gate.py
"""

import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
# Every user-visible file: the map, the generated data the map reads, the README,
# and the docs/ writeups (audit, roadmap, research, LinkedIn draft) whose copy is
# also public and must clear the same banned-framing and voice bars.
TARGETS = (
    glob.glob(os.path.join(ROOT, "web", "*.html"))
    + glob.glob(os.path.join(ROOT, "web", "data", "*.json"))
    + glob.glob(os.path.join(ROOT, "docs", "*.md"))
    # the studio's in-app React copy is user-visible too; scan it, but
    # skip *.test.* (test fixtures carry deliberate tells like em-dashes)
    + [
        p
        for p in glob.glob(
            os.path.join(ROOT, "studio", "src", "**", "*.tsx"), recursive=True
        )
        + glob.glob(os.path.join(ROOT, "studio", "src", "**", "*.ts"), recursive=True)
        if ".test." not in os.path.basename(p)
    ]
    + [
        os.path.join(ROOT, "README.md"),
        os.path.join(ROOT, "studio", "README.md"),
        # CLAUDE.md ships in the public clone, and it is the file that named the
        # vendor in the sentence banning the vendor. Scan it like any other.
        os.path.join(ROOT, "CLAUDE.md"),
    ]
)

fails = []

# Banned claims for this project. Data-center attribution
# and brownout prophecy are the two ways this map gets torn apart.
BANNED = [
    (
        (
            "'data centers raised/spiked prices' "
            "(current DC load is small; unproven attribution)"
        ),
        r"data\s+cent(er|re)s?\s+(have\s+)?(raised|spiked|drove|caused|pushed\s+up|increased)\s+(wesm|spot|power|electricity)?\s*prices",
    ),
    (
        "'will cause brownouts' (prophecy; use observed curtailment/alerts)",
        r"will\s+cause\s+(brownouts|blackouts|rotating\s+outages)",
    ),
    (
        "'ghost'/'fraud' style accusation (conservative language only)",
        r"\b(fraudulent|thieves?|plunder(ed|ing)?)\b",
    ),
    (
        "capacity/wholesale % stated as a bill % (keep wholesale and bill apart)",
        r"bill(s)?\s+(rose|up|jumped|climbed|soared|spiked|surged|increased|went\s+up)"
        r"\s*(by\s+)?38\.5\s*(%|percent|per\s*cent|pct)",
    ),
]

# US-market framing must not creep back into user-facing files. This map stands
# on Philippine terms only; a US-ISO name in the copy reads as borrowed US-market text.
# Word-boundary matched so SPP/MISO/PJM don't fire inside ordinary words.
# The licensed suite and its vendor. The project stands on its own backcast
# number, so no public file names either. Nothing enforced this until
# 2026-08-11, and the rule's own sentence in CLAUDE.md was the first breach.
# data/external/doe/ is out of scope here: it is a quoted source document.
VENDOR = [
    r"\bPLEXOS\b",
    r"\bEnergy\s+Exemplar\b",
]

# One check step in either gate list: a test file, or the claims oracle.
GATE_STEP_RX = re.compile(r"(tests/[a-z0-9_]+\.py|scripts/verify_claims\.py)")

US_FRAMING = [
    r"\bERCOT\b",
    r"\bPJM\b",
    r"\bNYISO\b",
    r"\bISO-NE\b",
    r"\bMISO\b",
    r"\bSPP\b",
    r"\bCAISO\b",
    r"\bGridStatus\b",
    r"\bgridstatus\b",
    r"\bgridbill-us\b",
    r"\bElectricity Maps\b",
    r"\belectricitymaps\b",
    r"\bEPRI\b",
    r"\bDCFlex\b",
    r"\bWattTime\b",
]

AI_JARGON = [
    "delve",
    "leverage",
    "utilize",
    "seamless",
    "robust",
    "tapestry",
    "pivotal",
    "in today's",
    "it's important to note",
    "game-changer",
    "cutting-edge",
    "navigate the complexities",
    "ever-evolving",
    "underscore",
    "showcase",
    "testament",
    "paramount",
    "plethora",
    "myriad",
    "at the forefront",
    "crucial",
    "comprehensive",
]

# Domain terms of art that contain an otherwise-banned jargon word. "Pivotal
# supplier" is a published WESM/ERC structural index (the Pivotal Supplier Test,
# alongside HHI and the residual-supply index), not filler; it is scrubbed before
# the jargon scan so the bare-filler ban on "pivotal" still holds elsewhere.
DOMAIN_TERMS = ["pivotal supplier", "pivotal-supplier", "pivotal_supplier"]

OVERWROUGHT = [
    (
        "dramatic number-verb (skyrocket/plummet/spiral/unleash/shatter)",
        r"\b(skyrocket|plummet|spiral|unleash|shatter)(ed|ing|s)?\b",
    ),
    ("'broke from/away' trend metaphor", r"\bbroke\s+(from|away|out)\b"),
    ("'the pack' metaphor", r"\bthe\s+pack\b"),
    (
        "'grid on the brink/edge of collapse' (alert language, not doom copy)",
        r"\b(brink|edge)\s+of\s+collapse\b",
    ),
]

AI_TELLS = [
    ("persona-door heading", r"\bpick the door that fits you\b"),
    ("staged receipts contrast", r"\breceipts,\s*not estimates\b"),
    (
        "choose-us instruction",
        r"\bpoint the engine at your own system, not at ours\b",
    ),
    (
        "competitor recommendation",
        r"\bfor everything else on the list, pick them\b",
    ),
    ("reader payment metaphor", r"\bvisitor pays for them\b"),
    (
        "paper-practice contrast",
        r"\bone market on paper, three prices in practice\b",
    ),
    ("story framing", r"\bthe same story with unit names\b"),
    ("normal-state slogan", r"\bthin is the normal state\b"),
    ("margin metaphor", r"\btakes? \d+% of the margin with it\b"),
]


def scan(path, text):
    base = os.path.basename(path)
    if "—" in text:
        fails.append(f"{base}: contains em-dash")
    # '1.5 GW' must be labeled as the DICT forecast somewhere NEAR the number
    # (before or after; the regex-lookahead version missed 'DICT: ... 1.5 GW').
    for m in re.finditer(r"1\.5\s*GW", text):
        window = text[max(0, m.start() - 160) : m.end() + 160].lower()
        if "dict" not in window and "forecast" not in window:
            fails.append(f"{base}: unlabeled '1.5 GW' (label the DICT forecast)")
    low = text.lower()
    for label, rx in BANNED:
        if re.search(rx, text, re.I):
            fails.append(f"{base}: BANNED framing {label}")
    # 'congestion premium'/'congestion cost' is a banned affirmative WESM framing
    # (the published LMP_CONGESTION column is not a per-node premium); allowed
    # only in the negated or debunking form ("not a congestion premium", the
    # "= 0" chart that "would mislead"). Require a marker in the local window.
    for m in re.finditer(r"congestion\s+(premium|cost)", text, re.I):
        ctx = text[max(0, m.start() - 55) : m.end() + 20].lower()
        # a quoted mention ("congestion premium") is a term being debunked, not
        # an assertion; otherwise require a negation/debunk marker in the window
        quoted = bool(re.search(r"[\"']\s*$", text[max(0, m.start() - 2) : m.start()]))
        if not quoted and not re.search(
            r"\bnot\b|\bnever\b|n't|\bno\b|rather than|=\s*0|mislead", ctx
        ):
            fails.append(
                f"{base}: BANNED affirmative 'congestion "
                f"{m.group(1).lower()}' (only the negated form is allowed)"
            )
    # The DOE plant list names dozens of solar plants "<NAME> SPP" (solar power
    # plant) and Kalayaan "PSPP" (pumped storage). Scrub SPP only when it follows
    # an ALL-CAPS plant name, so the ban still catches prose about the US ISO.
    us_text = re.sub(r"([A-Z0-9][A-Z0-9'()./-]*\s+)P?SPP\b", r"\1", text)
    for rx in US_FRAMING:
        m = re.search(rx, us_text)
        if m:
            fails.append(
                f"{base}: US-market framing '{m.group(0)}' "
                "(map stands on PH terms only)"
            )
    for rx in VENDOR:
        m = re.search(rx, text, re.I)
        if m:
            fails.append(
                f"{base}: names the licensed vendor '{m.group(0)}' "
                "(lead with the backcast number instead)"
            )
    scrubbed = low
    for t in DOMAIN_TERMS:
        scrubbed = scrubbed.replace(t, "")
    for j in AI_JARGON:
        if j in scrubbed:
            fails.append(f"{base}: AI-jargon '{j}'")
    for label, rx in OVERWROUGHT:
        if re.search(rx, text, re.I):
            fails.append(f"{base}: overwrought voice {label}")
    for label, rx in AI_TELLS:
        if re.search(rx, text, re.I):
            fails.append(f"{base}: AI-tell '{label}'")


def check_both_gate_lists():
    """Every workflow that writes to main runs the whole gate, not a copy of it.

    The Makefile qa target is the one list. A workflow satisfies this by calling
    `make qa`. A workflow that instead spells the checks out by hand has to spell
    out all of them, because a hand-kept second copy is what broke twice:

    - ci.yml missed nodal_scenario, sites, perspective, contrast and palette, so
      the WCAG contrast gate never ran on a push.
    - archive.yml ran 4 of 18 and then pushed to main. A push made with the
      workflow token starts no other workflow, so nothing else checked it.

    Both were found on 2026-08-11 and both now call `make qa`.
    """
    mk_path = os.path.join(ROOT, "Makefile")
    qa_body = re.search(
        r"^qa:\n((?:\t.*\n)+)", open(mk_path, encoding="utf-8").read(), re.M
    )
    if not qa_body:
        fails.append("Makefile: no qa target found")
        return
    in_make = set(GATE_STEP_RX.findall(qa_body.group(1)))
    for wf in ("ci.yml", "archive.yml"):
        path = os.path.join(ROOT, ".github/workflows", wf)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        if re.search(r"^\s*run:\s*make qa\s*$", text, re.M):
            continue
        for missing in sorted(in_make - set(GATE_STEP_RX.findall(text))):
            fails.append(
                f"{wf}: {missing} runs in make qa but not here (or call `make qa`)"
            )


def main():
    scanned = 0
    for path in TARGETS:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            scan(path, f.read())
        scanned += 1
    check_both_gate_lists()
    print(f"scanned {scanned} files")
    for f_ in fails:
        print("FAIL " + f_)
    if fails:
        return 1
    print("PASS qa gate clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
