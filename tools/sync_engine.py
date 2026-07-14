#!/usr/bin/env python3
"""Generate src/power_dispatch/engine/ from the pipeline engine core.

The pipeline is a flat collection of scripts that run with `python3
pipeline/x.py` and no install step. The pip package (roadmap item 16) needs
the same engine as a proper importable module. Rather than duplicate the code
by hand, this tool copies the five engine-core modules and rewrites their
intra-engine imports to package-relative, so pipeline/ stays the single source
of truth and tests/test_engine_sync.py fails the moment the two drift.

    python3 tools/sync_engine.py            # regenerate the vendored engine
    python3 tools/sync_engine.py --check    # verify committed files are current
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "pipeline")
DST = os.path.join(ROOT, "src", "power_dispatch", "engine")

# The engine-core closure for run_chronology_lp. Verified self-contained:
# none of these import any pipeline module outside this set (see the import
# graph in tools/sync_engine.py's companion test).
MODULES = ["lp_model", "fleet_ph", "constants_ph", "chrono", "lp_dispatch"]

_PEERS = "|".join(MODULES)
_IMPORT_RE = re.compile(rf"^(\s*)from ({_PEERS}) import", re.MULTILINE)

_BANNER = ("# GENERATED from pipeline/{mod}.py by tools/sync_engine.py -- do "
           "not edit.\n# Edit the pipeline source and re-run the sync; "
           "tests/test_engine_sync.py enforces identity.\n")


def rewrite(mod: str, text: str) -> str:
    """Rewrite intra-engine absolute imports to package-relative and prepend
    the generation banner."""
    body = _IMPORT_RE.sub(r"\1from .\2 import", text)
    return _BANNER.format(mod=mod) + body


def sync(check: bool) -> int:
    os.makedirs(DST, exist_ok=True)
    drift = []
    for mod in MODULES:
        src_path = os.path.join(SRC, f"{mod}.py")
        with open(src_path, encoding="utf-8") as fh:
            want = rewrite(mod, fh.read())
        dst_path = os.path.join(DST, f"{mod}.py")
        have = None
        if os.path.isfile(dst_path):
            with open(dst_path, encoding="utf-8") as fh:
                have = fh.read()
        if have == want:
            continue
        if check:
            drift.append(mod)
        else:
            with open(dst_path, "w", encoding="utf-8") as fh:
                fh.write(want)
            print(f"[sync] wrote engine/{mod}.py")
    if check and drift:
        print(f"[DRIFT] out of date: {', '.join(drift)} -- run "
              f"tools/sync_engine.py", file=sys.stderr)
        return 1
    if not check:
        print(f"synced {len(MODULES)} engine modules -> {DST}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify committed files match the source, exit 1 on drift")
    args = ap.parse_args()
    return sync(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
