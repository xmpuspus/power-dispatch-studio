#!/usr/bin/env python3
"""Parse the DOE List of Existing Power Plants (grid-connected) into fleet.json.

Source documents are the DOE's own per-grid PDFs. doe.gov.ph and
legacy.doe.gov.ph refuse non-PH requests (403), so the files in
data/external/doe/ are the Internet Archive's captures of the same DOE URLs;
each edition's original URL, capture URL, and as-of date ship in the artifact.
Text is extracted with pdftotext -layout (committed alongside the PDFs).

The parser is defensive the same way the archiver is: every fuel section in the
PDF prints its own installed/dependable subtotal, and build_fleet() refuses to
emit a grid whose parsed rows do not reconcile to those subtotals. No silent
partial fleets.
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOE_DIR = os.path.join(HERE, "..", "data", "external", "doe")

EDITIONS = {
    "luzon": {
        "file": "doe_luzon_2025-04-30.txt",
        "as_of": "2025-04-30",
        "original_url": "https://legacy.doe.gov.ph/sites/default/files/pdf/"
                        "electric_power/01_Luzon%20Grid_2.pdf",
        "src": "https://web.archive.org/web/20251104021000/https://legacy.doe."
               "gov.ph/sites/default/files/pdf/electric_power/01_Luzon%20Grid_2.pdf",
    },
    "visayas": {
        "file": "doe_visayas_2025-03-31.txt",
        "as_of": "2025-03-31",
        "original_url": "https://legacy.doe.gov.ph/sites/default/files/pdf/"
                        "electric_power/02_%20Visayas%20Grid.pdf",
        "src": "https://web.archive.org/web/20250515115334/https://legacy.doe."
               "gov.ph/sites/default/files/pdf/electric_power/02_%20Visayas%20Grid.pdf",
    },
    "mindanao": {
        "file": "doe_mindanao_2025-04-30.txt",
        "as_of": "2025-04-30",
        "original_url": "https://legacy.doe.gov.ph/sites/default/files/pdf/"
                        "electric_power/03_Mindanao%20Grid_2.pdf",
        "src": "https://web.archive.org/web/20250712234701/https://legacy.doe."
               "gov.ph/sites/default/files/pdf/electric_power/03_Mindanao%20Grid_2.pdf",
    },
}

SECTION_FUEL = {
    "COAL": "coal",
    "OIL-BASED": "oil",
    "OIL BASED": "oil",
    "NATURAL GAS": "natural_gas",
    "NATURALGAS": "natural_gas",
    "BIOMASS": "biomass",
    "GEOTHERMAL": "geothermal",
    "SOLAR": "solar",
    "HYDROELECTRIC": "hydro",
    "WIND": "wind",
    "ENERGY STORAGE SYSTEM (ESS)": "storage",
}

# a fuel-section header line: NAME  <installed subtotal>  <dependable subtotal>
SECTION_RE = re.compile(
    r"^\s*([A-Z][A-Z ()\-/]*[A-Z)])\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$")
TOTAL_RE = re.compile(r"^TOTAL\s+(LUZON|VISAYAS|MINDANAO)\s+([\d,]+\.\d+)")
CONN_RE = re.compile(r"\b(Grid|Embedded)\b")
NUM_RE = re.compile(r"[\d,]+\.\d+|\b\d{1,3}\b")
# values are RIGHT-aligned: a token belongs to the column whose header's right
# edge (+3 slack) is nearest its own end, within this reach (columns sit ~14
# chars apart in every edition, so 7 cannot cross-claim)
COL_REACH = 7


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_grid(grid: str) -> dict:
    """Column-window state machine over the pdftotext -layout text.

    The PDF wraps long rows: a plant's installed/dependable values can sit on
    the physical line above or below its name line, and header column offsets
    differ page to page. So we track the current header's INSTALLED /
    DEPENDABLE / UNITS x-positions, tag every numeric token on every line with
    the column it sits under, and let each record claim its own line's tokens
    first, then the nearest unclaimed tokens between its neighbours.
    """
    meta = EDITIONS[grid]
    path = os.path.join(DOE_DIR, meta["file"])
    if not os.path.exists(path):
        return {"available": False,
                "note": f"{meta['file']} absent; run the DOE fetch first"}
    with open(path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    cols: dict[str, int] = {}
    section: str | None = None
    subtotals: dict[str, dict] = {}
    grand_total = None
    # per section: records [{line, name, conn}], tokens {col: [(line, value)]}
    records: list[dict] = []
    tokens: dict[int, dict[str, float]] = {}

    def col_of(end: int) -> str | None:
        best, dist = None, COL_REACH + 1
        for key, edge in cols.items():
            d = abs(end - (edge + 3))
            if d < dist:
                best, dist = key, d
        return best

    for idx, line in enumerate(lines):
        if "INSTALLED" in line and "DEPENDABLE" in line:
            cols = {"installed": line.index("INSTALLED") + len("INSTALLED"),
                    "dependable": line.index("DEPENDABLE") + len("DEPENDABLE")}
            if "UNITS" in line:
                cols["units"] = line.index("UNITS") + len("UNITS")
            continue
        mt = TOTAL_RE.match(line.strip())
        if mt:
            grand_total = _num(mt.group(2))
            section = None
            continue
        ms = SECTION_RE.match(line.rstrip())
        if ms and ms.group(1).strip() in SECTION_FUEL:
            section = SECTION_FUEL[ms.group(1).strip()]
            subtotals[section] = {"installed": _num(ms.group(2)),
                                  "dependable": _num(ms.group(3))}
            continue
        if not section or section == "storage" or not cols:
            continue
        # numeric tokens under the tracked columns
        line_tokens: dict[str, float] = {}
        for m in NUM_RE.finditer(line):
            c = col_of(m.end())
            if c and c not in line_tokens:
                line_tokens[c] = _num(m.group(0))
        if line_tokens:
            tokens[idx] = line_tokens
        # a record line: non-blank name cell plus a connection-type token
        name_cell = re.split(r"\s{2,}", line.strip())[0].strip()
        mc = CONN_RE.search(line)
        if mc and line[:1].strip() and name_cell not in SECTION_FUEL:
            records.append({"line": idx, "name": name_cell,
                            "conn": mc.group(1).lower(), "fuel": section})
        elif (line[:1].strip() and name_cell not in SECTION_FUEL
              and ("installed" in line_tokens or "dependable" in line_tokens)):
            # wrapped record: the name line carries the numbers, the connection
            # sits alone on the next line or two, and a trailing short line may
            # finish the name (ARAYAT ... PHASE 2, CENTRAL MALL ... PROJECT)
            for j in range(idx + 1, min(idx + 3, len(lines))):
                nxt = lines[j]
                mnc = CONN_RE.search(nxt)
                if mnc and not nxt[:1].strip():
                    name = name_cell
                    for k in range(j + 1, min(j + 3, len(lines))):
                        frag = lines[k]
                        frag_cell = re.split(r"\s{2,}", frag.strip())[0].strip()
                        if (frag[:1].strip() and frag_cell
                                and not CONN_RE.search(frag)
                                and not any(col_of(m.end()) for m in
                                            NUM_RE.finditer(frag))):
                            name = f"{name} {frag_cell}"
                        break
                    records.append({"line": idx, "name": name,
                                    "conn": mnc.group(1).lower(),
                                    "fuel": section})
                    break

    # each record claims its own line's tokens, then the nearest unclaimed
    # tokens strictly between its neighbouring records
    claimed: set[tuple[int, str]] = set()
    plants: list[dict] = []
    for k, rec in enumerate(records):
        li = rec["line"]
        lo = records[k - 1]["line"] if k > 0 else li - 4
        hi = records[k + 1]["line"] if k + 1 < len(records) else li + 4
        got: dict[str, float] = {}
        for c in ("installed", "dependable", "units"):
            if c in tokens.get(li, {}):
                got[c] = tokens[li][c]
                claimed.add((li, c))
        for c in ("installed", "dependable", "units"):
            if c in got:
                continue
            best = None
            for j in range(lo + 1, hi):
                if j == li or (j, c) in claimed:
                    continue
                if c in tokens.get(j, {}):
                    if best is None or abs(j - li) < abs(best - li):
                        best = j
            if best is not None:
                got[c] = tokens[best][c]
                claimed.add((best, c))
        if "installed" not in got:
            continue  # reconciliation below decides if this miss matters
        plants.append({
            "name": rec["name"],
            "grid": grid,
            "fuel": rec["fuel"],
            "connection": rec["conn"],
            "installed_mw": got["installed"],
            "dependable_mw": got.get("dependable", 0.0),
            "units": int(got.get("units", 1)),
        })

    # reconcile parsed rows against the PDF's own per-section subtotals; a
    # section that does not reconcile fails the whole grid loudly
    recon = {}
    ok = True
    for fuel, sub in subtotals.items():
        if fuel == "storage":
            continue
        got = round(sum(p["installed_mw"] for p in plants
                        if p["fuel"] == fuel), 1)
        want = sub["installed"]
        tol = max(1.0, want * 0.005)
        match = abs(got - want) <= tol
        ok = ok and match
        recon[fuel] = {"subtotal_mw": want, "parsed_mw": got, "ok": match}
    non_storage = round(sum(s["installed"] for f, s in subtotals.items()
                            if f != "storage"), 1)
    return {
        "available": ok,
        "as_of": meta["as_of"],
        "src": meta["src"],
        "original_url": meta["original_url"],
        "plants": plants,
        "reconciliation": recon,
        "sections_total_mw": non_storage,
        "doe_total_mw": grand_total,
    }


def build_fleet() -> dict:
    grids = {g: parse_grid(g) for g in EDITIONS}
    bad = [g for g, v in grids.items() if not v.get("available")]
    if bad:
        raise SystemExit(f"DOE fleet parse failed reconciliation: {bad}; "
                         f"details: "
                         f"{ {g: grids[g].get('reconciliation') for g in bad} }")
    plants = [p for g in grids.values() for p in g["plants"]]
    return {
        "available": True,
        "note": "DOE List of Existing Power Plants (grid-connected), parsed "
                "per unit from the DOE's own per-grid PDFs (Internet Archive "
                "captures of legacy.doe.gov.ph, which refuses non-PH "
                "requests). Every fuel section reconciles to the PDF's own "
                "subtotal before this file is written. Dependable capacity is "
                "the DOE's figure, not a model derate. ESS rows are carried "
                "by the storage layer, not here.",
        "editions": {g: {k: grids[g][k] for k in
                         ("as_of", "src", "original_url", "sections_total_mw",
                          "doe_total_mw", "reconciliation")}
                     for g in grids},
        "n_plants": len(plants),
        "plants": plants,
    }
