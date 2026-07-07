#!/usr/bin/env python3
"""QA gate: banned framings, em-dash ban, AI-jargon ban, and overwrought-voice
sweep across every user-visible artifact. A failure here means the map is about
to make a claim that gets fact-checked to death or reads as machine-written.
Run: python3 tests/qa_gate.py
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
# Every user-visible artifact: the map, the baked data the map reads, the README,
# and the docs/ writeups (audit, roadmap, research, LinkedIn draft) whose copy is
# also public and must clear the same banned-framing and voice bars.
TARGETS = (glob.glob(os.path.join(ROOT, "web", "*.html"))
           + glob.glob(os.path.join(ROOT, "web", "data", "*.json"))
           + glob.glob(os.path.join(ROOT, "docs", "*.md"))
           + [os.path.join(ROOT, "README.md")])

fails = []

# Banned framings for THIS project (CLAUDE.md stance). Data-center attribution
# and brownout prophecy are the two ways this map gets torn apart.
BANNED = [
    ("'data centers raised/spiked prices' (current DC load is small; unproven attribution)",
     r"data\s+cent(er|re)s?\s+(have\s+)?(raised|spiked|drove|caused|pushed\s+up|increased)\s+(wesm|spot|power|electricity)?\s*prices"),
    ("'will cause brownouts' (prophecy; use observed curtailment/alerts)",
     r"will\s+cause\s+(brownouts|blackouts|rotating\s+outages)"),
    ("'ghost'/'fraud' style accusation (conservative language only)",
     r"\b(fraudulent|thieves?|plunder(ed|ing)?)\b"),
    ("capacity/wholesale % stated as a bill % (keep wholesale and bill apart)",
     r"bill(s)?\s+(rose|up|jumped|climbed)\s+38\.5\s*%"),
]

# US-market framing must not creep back into user-facing artifacts. This map stands
# on Philippine terms only; a US-ISO name in the copy reads as a ported artifact.
# Word-boundary matched so SPP/MISO/PJM don't fire inside ordinary words.
US_FRAMING = [
    r"\bERCOT\b", r"\bPJM\b", r"\bNYISO\b", r"\bISO-NE\b", r"\bMISO\b",
    r"\bSPP\b", r"\bCAISO\b", r"\bGridStatus\b", r"\bgridstatus\b",
    r"\bgridbill-us\b", r"\bElectricity Maps\b", r"\belectricitymaps\b",
    r"\bEPRI\b", r"\bDCFlex\b", r"\bWattTime\b",
]

AI_JARGON = [
    "delve", "leverage", "utilize", "seamless", "robust", "tapestry", "pivotal",
    "in today's", "it's important to note", "game-changer", "cutting-edge",
    "navigate the complexities", "ever-evolving", "underscore", "showcase",
    "testament", "paramount", "plethora", "myriad", "at the forefront",
    "crucial", "comprehensive",
]

# Domain terms of art that contain an otherwise-banned jargon word. "Pivotal
# supplier" is a published WESM/ERC structural index (the Pivotal Supplier Test,
# alongside HHI and the residual-supply index), not filler; it is scrubbed before
# the jargon scan so the bare-filler ban on "pivotal" still holds elsewhere.
DOMAIN_TERMS = ["pivotal supplier", "pivotal-supplier", "pivotal_supplier"]

OVERWROUGHT = [
    ("dramatic number-verb (skyrocket/plummet/spiral/unleash/shatter)",
     r"\b(skyrocket|plummet|spiral|unleash|shatter)(ed|ing|s)?\b"),
    ("'broke from/away' trend metaphor", r"\bbroke\s+(from|away|out)\b"),
    ("'the pack' metaphor", r"\bthe\s+pack\b"),
    ("'grid on the brink/edge of collapse' (alert language, not doom copy)",
     r"\b(brink|edge)\s+of\s+collapse\b"),
]


def scan(path, text):
    base = os.path.basename(path)
    if "—" in text:
        fails.append(f"{base}: contains em-dash")
    # '1.5 GW' must be labeled as the DICT forecast somewhere NEAR the number
    # (before or after; the regex-lookahead version missed 'DICT: ... 1.5 GW').
    for m in re.finditer(r"1\.5\s*GW", text):
        window = text[max(0, m.start() - 160):m.end() + 160].lower()
        if "dict" not in window and "forecast" not in window:
            fails.append(f"{base}: unlabeled '1.5 GW' (label the DICT forecast)")
    low = text.lower()
    for label, rx in BANNED:
        if re.search(rx, text, re.I):
            fails.append(f"{base}: BANNED framing {label}")
    # The DOE plant list names dozens of solar plants "<NAME> SPP" (solar power
    # plant) and Kalayaan "PSPP" (pumped storage). Scrub SPP only when it follows
    # an ALL-CAPS plant name, so the ban still catches prose about the US ISO.
    us_text = re.sub(r"([A-Z0-9][A-Z0-9'()./-]*\s+)P?SPP\b", r"\1", text)
    for rx in US_FRAMING:
        m = re.search(rx, us_text)
        if m:
            fails.append(f"{base}: US-market framing '{m.group(0)}' "
                         "(map stands on PH terms only)")
    scrubbed = low
    for t in DOMAIN_TERMS:
        scrubbed = scrubbed.replace(t, "")
    for j in AI_JARGON:
        if j in scrubbed:
            fails.append(f"{base}: AI-jargon '{j}'")
    for label, rx in OVERWROUGHT:
        if re.search(rx, text, re.I):
            fails.append(f"{base}: overwrought voice {label}")


def main():
    scanned = 0
    for path in TARGETS:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            scan(path, f.read())
        scanned += 1
    print(f"scanned {scanned} artifacts")
    for f_ in fails:
        print("FAIL " + f_)
    if fails:
        return 1
    print("PASS qa gate clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
