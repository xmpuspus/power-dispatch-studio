#!/usr/bin/env python3
"""Per-resource daily energy from DIPCEF, derived and committed compactly.

DIPCEF (nodal LMP results, final) carries SCHED_MW per resource per 5-minute
interval, one zip per hour. That is the archive's only per-resource dispatch
record, but a full day is ~2.5 MB zipped and the public window would be
~200 MB: too heavy to commit as raw files. So this module fetches a day's 24
hourly zips into a temp dir, aggregates each resource's daily energy, checks
the sum against the RTDSUM regional totals (the reconciliation gate), writes
one compact JSON per day under data/derived/dipcef_daily/, and discards the
zips. The derived dailies ARE the durable record (the raw window rolls);
they carry everything needed to re-split fuels later without refetching.

Derivation is exact by construction: MWh = SCHED_MW * 5/60 summed over the
day's 288 intervals; on the committed sample day the three regional totals
reconcile to RTDSUM within 0.25 percent (Mindanao, the worst).

Run: python3 pipeline/fuelmix.py --derive           # top up missing days
     python3 pipeline/fuelmix.py --derive --limit 5 # bounded run
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import tempfile
import time
import zipfile
from collections import defaultdict

from archive_iemop import fetch, list_files, page_config

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
DERIVED = os.path.join(HERE, "..", "data", "derived", "dipcef_daily")
SLUG = "dipc-energy-results-final"
REGION = {"LUZON": "luzon", "VISAYAS": "visayas", "MINDANAO": "mindanao"}
GRIDS = ("luzon", "visayas", "mindanao")


def rtdsum_gen_mwh(date: str) -> dict | None:
    """RTDSUM daily generation MWh per grid, for the reconciliation gate."""
    path = os.path.join(RAW, "RTDSUM", f"RTDREG_{date}.csv")
    if not os.path.isfile(path):
        return None
    out = {g: 0.0 for g in GRIDS}
    m = {"CLUZ": "luzon", "CVIS": "visayas", "CMIN": "mindanao"}
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            if (r.get("COMMODITY_TYPE") or "").strip() != "En":
                continue
            g = m.get((r.get("REGION_NAME") or "").strip())
            if g:
                out[g] += float(r.get("GENERATION") or 0) * 5 / 60
    return {g: round(v, 1) for g, v in out.items()}


def derive_day(date: str, hour_files: list[tuple[str, str]]) -> dict:
    """Fetch one day's hourly zips to temp, aggregate, and reconcile."""
    energy: dict[str, float] = defaultdict(float)
    region_of: dict[str, str] = {}
    n_rows = 0
    with tempfile.TemporaryDirectory() as tmp:
        for b64, name in hour_files:
            dest = os.path.join(tmp, name)
            ok = fetch(SLUG, b64, dest)
            time.sleep(0.5)
            if not ok:
                # transient mid-window failures are common; one paused retry
                # before declaring the day failed
                time.sleep(45)
                ok = fetch(SLUG, b64, dest)
                time.sleep(0.5)
            if not ok:
                raise RuntimeError(f"fetch failed: {name}")
            with zipfile.ZipFile(dest) as z:
                for member in z.namelist():
                    with z.open(member) as fh:
                        rd = csv.DictReader(
                            io.TextIOWrapper(fh, "utf-8", errors="replace"))
                        for r in rd:
                            res = (r.get("RESOURCE_NAME") or "").strip()
                            if not res:
                                continue
                            mw = float(r.get("SCHED_MW") or 0)
                            if mw <= 0:
                                continue
                            energy[res] += mw * 5 / 60
                            g = REGION.get((r.get("REGION_NAME") or "").strip())
                            if g:
                                region_of[res] = g
                            n_rows += 1
    per_grid = {g: 0.0 for g in GRIDS}
    for res, e in energy.items():
        g = region_of.get(res)
        if g:
            per_grid[g] += e
    rtd = rtdsum_gen_mwh(date)
    if rtd is None:
        # without the same-day RTDSUM the reconciliation gate cannot run;
        # refuse now and the next run derives the day once RTDSUM lands
        raise RuntimeError(f"{date}: no RTDSUM day yet for the gate")
    recon = None
    if rtd:
        recon = {g: {"dipcef_mwh": round(per_grid[g], 1),
                     "rtdsum_mwh": rtd[g],
                     "gap_pct": (round(100 * abs(per_grid[g] - rtd[g])
                                       / rtd[g], 2) if rtd[g] else None)}
                 for g in GRIDS}
        for g in GRIDS:
            gap = recon[g]["gap_pct"]
            if gap is not None and gap > 2.0:
                raise RuntimeError(
                    f"{date} {g}: DIPCEF/RTDSUM gap {gap}% exceeds the gate")
    return {
        "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
        "n_hour_files": len(hour_files),
        "n_rows": n_rows,
        "resources": {res: {"grid": region_of.get(res),
                            "mwh": round(e, 2)}
                      for res, e in sorted(energy.items())},
        "per_grid_total_mwh": {g: round(per_grid[g], 1) for g in GRIDS},
        "reconciliation": recon,
        "note": ("Per-resource daily energy from DIPCEF SCHED_MW (5-minute "
                 "schedules, final run), derived at archive time because the "
                 "raw hourly zips are too heavy to commit; the regional "
                 "totals must reconcile to RTDSUM within 2 percent or the "
                 "day is refused."),
    }


def derive(limit: int | None = None) -> int:
    os.makedirs(DERIVED, exist_ok=True)
    post_id, _ = page_config(SLUG)
    listing = list_files(SLUG, post_id)
    by_day: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for b64, name in listing:
        m = re.search(r"DIPCEF_(\d{8})(\d{4})", name)
        if m:
            by_day[m.group(1)].append((b64, name))
    done = 0
    fetch_fail_streak = 0
    days = sorted(by_day)
    print(f"listing: {len(listing)} files across {len(days)} days "
          f"({days[0]}..{days[-1]})" if days else "empty listing", flush=True)
    # administered-period days (pre-resumption) consistently fail the
    # reconciliation gate by 3-5 percent, so skip them before fetching:
    # the studio's market replay does not use them and the fetches are paid
    # for nothing. The divergence itself is noted in the methodology.
    from constants_ph import MARKET_ANCHORS
    resumed = MARKET_ANCHORS.get("wesm_resumed", "2026-05-01").replace("-", "")
    for date in days:
        if date < resumed:
            continue
        hours = sorted(by_day[date], key=lambda t: t[1])
        if len(hours) < 24:
            continue  # incomplete day (the newest day publishes hourly)
        out = os.path.join(DERIVED, f"DIPCEFD_{date}.json")
        if os.path.isfile(out):
            continue
        try:
            day = derive_day(date, hours[:24])
        except RuntimeError as e:
            print(f"SKIP {date}: {e}", flush=True)
            if "fetch failed" in str(e):
                # courtesy: IEMOP firewalls repeated HTTP errors; back off
                # hard rather than hammering through a bad patch
                fetch_fail_streak += 1
                if fetch_fail_streak >= 3:
                    print("aborting: 3 consecutive fetch-failure days",
                          flush=True)
                    break
                time.sleep(90)
            continue
        fetch_fail_streak = 0
        with open(out, "w") as f:
            json.dump(day, f, indent=1)
        done += 1
        print(f"derived {date}: {day['per_grid_total_mwh']}", flush=True)
        if limit and done >= limit:
            break
    return done


if __name__ == "__main__":
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if "--derive" in sys.argv:
        n = derive(limit)
        print(f"derived {n} day(s)")
    else:
        print(__doc__)


# ---- hydro classification + daily budgets -----------------------------------------
# Grid-connected WESM hydro resources, classified per code CORE (the segment
# between the two-digit area prefix and the unit suffix). Auto-matched against
# the DOE fleet's hydro plants (same grid required), plus explicit aliases for
# the abbreviations a substring match cannot see. Pumped storage and batteries
# are EXCLUDED (the storage layer owns them). Embedded hydro never appears in
# WESM nodal data, which matches the model's grid-connected scope.

HYDRO_ALIAS = {
    "SROQUE": ("SAN ROQUE", "luzon"),
    "PNTBNG": ("PANTABANGAN", "luzon"),
    "PULA4": ("PULANGI 4", "mindanao"),
    "CALIRY": ("CALIRAYA", "luzon"),
    "LKMAINIT": ("LAKE MAINIT", "mindanao"),
    "ASIGA": ("ASIGA", "mindanao"),  # VILLASIGA is the visayas plant
    "VILLA": ("VILLASIGA HEPP", "visayas"),
}
# hydro by public record but not in the 2025 DOE fleet editions (new plants;
# the DOE committed list carries their commissioning)
HYDRO_EXTRA = {"PULANAI": "mindanao"}
# pumped storage (Kalayaan) and grid batteries stay in the storage layer
EXCLUDE_CORES = {"KAL"}
HINTS = ("HYDRO", "HEP", "AGUS", "PULA", "MAINIT", "SIBUL", "LIANG",
         "SROQ", "MAGAT", "BINGA", "AMBUK", "BAKUN", "PNTB", "CASEC",
         "MASIW", "TIMBA", "VILLA", "ASIGA", "BOT", "CALIR", "ANGAT")


def _core(res: str) -> str:
    m = re.match(r"^\d{2}([A-Z0-9-]+?)(?:_[A-Z0-9]+)?$", res)
    return m.group(1) if m else res


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def classify_hydro(fleet: dict) -> dict:
    """core -> fleet plant (or 'extra') for hydro; built once per bake."""
    by_norm = {}
    for p in fleet.get("plants", []):
        if p["fuel"] == "hydro":
            by_norm[_norm(p["name"])] = p

    def fleet_match(core: str, grid: str | None):
        cn = _norm(core)
        if len(cn) < 4:
            return None
        for hn, p in by_norm.items():
            if (cn in hn or hn in cn) and (grid is None or p["grid"] == grid):
                return p
        return None

    return {"by_norm": by_norm, "fleet_match": fleet_match}


def build_hydro_budgets(fleet: dict,
                        merit_hydro_mw: dict | None = None) -> dict:
    """Per-day per-grid hydro MWh from the derived DIPCEF dailies, with the
    classification stated: matched fleet-hydro cores + explicit aliases +
    known new plants; pumped storage and batteries excluded; anything that
    hints hydro but stays unclassified is listed, not silently counted."""
    cls = classify_hydro(fleet)
    files = sorted(
        os.path.join(DERIVED, n) for n in os.listdir(DERIVED)
        if n.endswith(".json")) if os.path.isdir(DERIVED) else []
    budgets: dict[str, dict] = {}
    matched_cores: dict[str, str] = {}
    suspects: dict[str, float] = defaultdict(float)
    excluded_mwh = 0.0
    for path in files:
        day = json.load(open(path))
        per_grid = {g: 0.0 for g in GRIDS}
        for res, meta in day["resources"].items():
            g = meta.get("grid")
            core = _core(res)
            if res.endswith("_BAT") or core in EXCLUDE_CORES:
                excluded_mwh += meta["mwh"]
                continue
            plant = None
            if core in HYDRO_ALIAS:
                name, want_grid = HYDRO_ALIAS[core]
                if g == want_grid:
                    plant = name
            elif core in HYDRO_EXTRA:
                if g == HYDRO_EXTRA[core]:
                    plant = f"{core} (not in the 2025 fleet edition)"
            else:
                p = cls["fleet_match"](core, g)
                if p:
                    plant = p["name"]
            if plant:
                matched_cores[core] = plant
                if g in per_grid:
                    per_grid[g] += meta["mwh"]
            elif any(h in core for h in HINTS):
                suspects[core] += meta["mwh"]
        budgets[day["date"]] = {g: round(per_grid[g], 1) for g in GRIDS}
    # consistency read, reported not tuned: a grid whose observed budget
    # exceeds what its modeled capacity could produce in 24 hours has its
    # hydro availability calibrated LOW; the constraint is then slack there
    over = {}
    for g in GRIDS:
        cap = (merit_hydro_mw or {}).get(g) or 0.0
        if cap <= 0:
            continue
        worst = max((b.get(g) or 0.0) for b in budgets.values()) if budgets \
            else 0.0
        if worst > cap * 24:
            over[g] = {"modeled_hydro_mw": cap,
                       "max_observed_budget_mwh": round(worst, 1)}
    return {
        "days": budgets,
        "n_days": len(budgets),
        "budget_exceeds_modeled_capacity": over or None,
        "matched_cores": dict(sorted(matched_cores.items())),
        "suspects_mwh": {k: round(v, 1)
                         for k, v in sorted(suspects.items(),
                                            key=lambda kv: -kv[1])},
        "excluded_note": ("Kalayaan pumped storage and grid batteries are "
                          "excluded from the hydro budget (the storage layer "
                          "owns them); "
                          f"{round(excluded_mwh):,} MWh excluded across the "
                          "derived days."),
        "note": ("Observed daily hydro energy per grid, derived from DIPCEF "
                 "per-resource schedules (data/derived/dipcef_daily/). "
                 "Coverage is grid-connected WESM hydro; embedded hydro "
                 "never appears in the nodal schedules, matching the "
                 "model's grid-connected scope. A resource that hints hydro "
                 "but stays unclassified is listed in suspects_mwh and NOT "
                 "counted, so the budget is a verified floor."),
    }
