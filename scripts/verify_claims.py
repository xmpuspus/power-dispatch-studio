#!/usr/bin/env python3
"""Keep the hand-written public prose in lockstep with the bake.

The map reads findings.json/answers.json, which build_data.py recomputes every
bake, so the on-screen numbers are always current. The README, the OG card
caption, and the montage are hand-typed and freeze at whatever bake last touched
them; the archive window rolls a day forward every night, so every window-derived
count in that prose silently drifts. A journalist who checks the README against
the live map finds them disagreeing.

This is the oracle that closes that gap. It reads the same baked artifacts the
map reads, derives the canonical value for every rolling number the prose
carries, and either checks the prose against them (--check, run by `make qa` and
CI, fails on drift) or rewrites the prose to match (--write, run by `make data`
so the nightly rebake keeps README + OG in lockstep with the map).

Numbers that do not move with the window (89,322 MOT rows, the 3,629 MW May
margin, the 41 percent, the Meralco split, the 87.8 percent outage backcast) are
NOT registered here: they are pinned by tests/test_data.py and change only when
their source does. This file owns exactly the window-derived counts.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web", "data")


def _load(name):
    with open(os.path.join(WEB, name)) as fh:
        return json.load(fh)


_RES_NAMES = {"Fr": "contingency (Fr)", "Dr": "dispatchable (Dr)",
              "Ru": "regulation up (Ru)", "Rd": "regulation down (Rd)"}


def _reserve_table_md(rv):
    """Regenerate the studio reserve-validation table from the baked pools."""
    def peso(x):
        return f"-P{abs(x):.2f}" if x < 0 else f"P{x:.2f}"
    rows = ["| Pool | Hours | Observed mean | Modeled mean | Bias | Exact hours "
            "| Scarcity hours | MAE outside scarcity |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for grid in ("luzon", "visayas", "mindanao"):
        for cm in ("Fr", "Dr", "Ru", "Rd"):
            p = rv["pools"][grid][cm]
            rows.append(
                f"| {grid.capitalize()} {_RES_NAMES[cm]} | {p['n_hours']:,} | "
                f"P{p['observed_mean_php_kwh']:.2f} | P{p['modeled_mean_php_kwh']:.2f} | "
                f"{peso(p['bias_php_kwh'])} | {p['exact_hours_pct']:.1f}% | "
                f"{p['n_scarcity_hours']} | P{p['mae_nonscarcity_php_kwh']:.2f} |")
    return "\n".join(rows)


def canonical():
    """Every rolling count the public prose carries, straight from the bake."""
    cg = _load("congestion.json")
    mo = _load("market_ops.json")
    fnd = {f["id"]: f for f in _load("findings.json")["findings"]}

    league = cg["league"]

    def _corridor(sub, field):
        # the day-ahead / real-time day counts for a named corridor element
        rows = [r for r in league if sub in (r.get("equipment") or "")]
        return max((r.get(field, 0) for r in rows), default=0)

    def _leyte_cebu(field):
        rows = [r for r in league if r.get("equipment") == "LEYTE_TO_CEBU"]
        return max((r.get(field, 0) for r in rows), default=0)

    sodir = mo["so_instructions"]["sodir"]
    rv = mo["reserve_validation"]
    profiles = _load("profiles.json")

    # reserve-shortfall days are baked into the findings blurb; read the number
    # build_data.py already computed rather than recomputing the series here.
    thin = fnd["thin-normal"]["stat"]
    m = re.search(r"below the stated requirement on (\d+) of (\d+)", thin)
    luzon_short, _thin_days = (int(m.group(1)), int(m.group(2))) if m else (0, 0)

    # curtailment grid-days and MWh come from the same findings card the map shows
    blurb = fnd["thin-normal"]["blurb"]
    mc = re.search(r"curtailed on (\d+) grid-days? in this window \(([\d,]+\.\d+) MWh\)",
                   blurb)
    curtail_days, curtail_mwh = (int(mc.group(1)), mc.group(2)) if mc else (0, "0")

    return {
        "days_covered": cg["days_covered"],
        "distinct_equipment": cg["distinct_equipment"],
        "leyte_cebu_dap_days": _leyte_cebu("dap_days"),
        "top_corridor_dap_days": _corridor("5DAAN_4TAB2", "dap_days"),
        "top_corridor_rtd_days": _corridor("5DAAN_4TAB2", "rtd_days"),
        "luzon_reserve_short_days": luzon_short,
        "curtail_grid_days": curtail_days,
        "curtail_mwh": curtail_mwh,
        "sodir_days": sodir["n_days"],
        "reserve_days": rv["days"],
        "reserve_above_pct": f'{rv["hours_model_above_pct"]:.1f}',
        "scored_hours": f"{sum(c['n_hours'] for g in rv['pools'].values() for c in g.values()):,}",
        "reserve_table": _reserve_table_md(rv),
        "profiles_days": len(profiles["days"]),
        "window_from": cg["window"]["from"],
        "window_to": cg["window"]["to"],
    }


# Each registry entry: a unique anchor regex over the README with ONE capture
# group holding the number, and the canonical key it must equal. The anchor
# carries enough surrounding words to match exactly one place.
# Each entry: (file, anchor regex with ONE capture group per key, keys). The
# anchor carries enough surrounding words to match exactly one place. --write
# rewrites the captured number(s) in place; --check fails on any mismatch. The
# studio reserve TABLE's 96 cells are handled as a regenerated BLOCK below, not
# as scalars here.
REGISTRY = [
    # --- README.md (the LinkedIn-facing surface; --write auto-syncs it nightly)
    ("README.md",
     re.compile(r"day-ahead runs on \*\*(\d+) of the window's (\d+) days\*\*"),
     ["leyte_cebu_dap_days", "days_covered"]),
    ("README.md",
     re.compile(r"binding limit in the hourly day-ahead runs on \*\*(\d+) of (\d+)"),
     ["top_corridor_dap_days", "days_covered"]),
    ("README.md",
     re.compile(r"the run settlement\s*\n?\s*actually sees, on \*\*(\d+) days\*\*"),
     ["top_corridor_rtd_days"]),
    ("README.md",
     re.compile(r"Across the (\d+)-day window, \*\*(\d+) distinct pieces of equipment\*\*"),
     ["days_covered", "distinct_equipment"]),
    ("README.md",
     re.compile(r"below the stated requirement on (\d+) of the window's (\d+) days\*\*"),
     ["luzon_reserve_short_days", "days_covered"]),
    ("README.md",
     re.compile(r"dispatch schedules on \*\*(\d+) grid-days \(([\d,]+\.\d) MWh\)\*\*"),
     ["curtail_grid_days", "curtail_mwh"]),
    ("README.md",
     re.compile(r"Across the (\d+)\s*\n?\s*daily logs the System Operator"),
     ["sodir_days"]),
    # --- studio/README.md scalars (reserve replay + data table)
    ("studio/README.md",
     re.compile(r"at the same interval: (\d+) days, twelve"),
     ["reserve_days"]),
    ("studio/README.md",
     re.compile(r"noise-level \((\d+\.\d) percent of the ~([\d,]+) scored"),
     ["reserve_above_pct", "scored_hours"]),
    ("studio/README.md",
     re.compile(r"Hourly demand and observed prices \((\d+) observed days\)"),
     ["profiles_days"]),
    # --- web/methodology.html scalars
    ("web/methodology.html",
     re.compile(r"same interval, (\d+) days by 12 grid-commodity pools"),
     ["reserve_days"]),
    ("web/methodology.html",
     re.compile(r"noise-level \((\d+\.\d) percent of scored hours"),
     ["reserve_above_pct"]),
]


# Marker-delimited blocks regenerated wholesale from the bake (the reserve
# table's 96 cells). The block body between the two markers is replaced with the
# canonical string on --write and compared on --check.
BLOCKS = [
    ("studio/README.md", "<!-- reserve-table:", "<!-- /reserve-table -->",
     "reserve_table"),
]

# Every public prose file is now bake-derived and auto-synced by the nightly
# cron: the scalar registry above plus the reserve-table block below cover all of
# the rolling numbers in each, so none can silently freeze behind the map.
WRITABLE = {"README.md", "studio/README.md", "web/methodology.html"}


def _check_file(path, text, canon, write):
    problems = []
    fixed = 0
    write = write and path in WRITABLE
    for _f, rx, keys in [e for e in REGISTRY if e[0] == path]:
        m = rx.search(text)
        if not m:
            problems.append(f"[MISS] {path}: anchor not found: {rx.pattern!r}")
            continue
        want = [str(canon[k]) for k in keys]
        got = list(m.groups())
        if got == want:
            continue
        if write:
            new = m.group(0)
            for g, w in zip(got, want):
                if g != w:
                    new = re.sub(rf"\b{re.escape(g)}\b", w, new, count=1)
            text = text[:m.start()] + new + text[m.end():]
            fixed += 1
        else:
            problems.append(
                f"[DRIFT] {path} {keys}: prose has {got}, bake says {want}")
    for _f, start, end, key in [b for b in BLOCKS if b[0] == path]:
        si, ei = text.find(start), text.find(end)
        if si == -1 or ei == -1:
            problems.append(f"[MISS] {path}: block markers not found ({start!r})")
            continue
        body_start = text.find("\n", si) + 1
        want = canon[key] + "\n"
        got = text[body_start:ei]
        if got == want:
            continue
        if write:
            text = text[:body_start] + want + text[ei:]
            fixed += 1
        else:
            problems.append(
                f"[DRIFT] {path} block {key}: table out of sync with the bake")
    return text, problems, fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="rewrite the rolling numbers in each file from the bake")
    args = ap.parse_args()

    canon = canonical()
    files = sorted({e[0] for e in REGISTRY} | {b[0] for b in BLOCKS})
    all_problems = []
    total_fixed = 0
    for rel in files:
        path = os.path.join(ROOT, rel)
        with open(path) as fh:
            original = fh.read()
        text, problems, fixed = _check_file(rel, original, canon, args.write)
        all_problems += problems
        total_fixed += fixed
        if args.write and text != original:
            with open(path, "w") as fh:
                fh.write(text)

    if args.write:
        print(f"verify_claims: rewrote {total_fixed} number(s) across "
              f"{len(files)} file(s) from the bake")
        miss = [p for p in all_problems if p.startswith("[MISS]")]
        if miss:
            print("\n".join(miss))
            sys.exit(1)
        return

    if all_problems:
        print("verify_claims: public prose is out of lockstep with the bake\n")
        print("\n".join(all_problems))
        print("\nfix: run `python3 scripts/verify_claims.py --write` "
              "(and `make viz` for the OG card + montage).")
        sys.exit(1)
    n = len(REGISTRY) + len(BLOCKS)
    print(f"verify_claims: all {n} claims across {len(files)} files match the bake "
          f"(window {canon['window_from']} to {canon['window_to']}, "
          f"{canon['days_covered']} days)")


if __name__ == "__main__":
    main()
