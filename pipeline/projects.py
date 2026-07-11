#!/usr/bin/env python3
"""Bake the LT Plan layer: the DOE's committed and indicative power project
lists, plus the NGCP TDP corridor pipeline, as sourced build candidates.

Generation projects come from the DOE "Private Sector Initiated Power Projects"
lists (committed + indicative, per grid, "As of 31 December 2025" edition,
Internet Archive captures of the DOE's own PDFs; the DOE CMS refuses non-PH
requests). Text extracts live in data/external/doe/ alongside the PDFs, same
pattern as fleet_doe.py.

The parser keeps the aggregate accurate and refuses to guess names:
  - every fuel section prints its own MW subtotal; a section's parsed rows must
    sum EXACTLY to that subtotal or the section is kept aggregate-only
    (subtotal, no timed rows) and flagged;
  - per-grid generation totals must reconcile to the DOE's own LVM summary PDF
    or the bake fails loudly;
  - rows carry (grid, status, fuel, MW, target commercial operation) and NO
    project name: name text wraps unpredictably in the PDF layout and a wrong
    name on a right number is still a defect.

ESS sections are tracked separately, exactly as the DOE's summaries do.

Transmission corridors come from the NGCP TDP 2025-2050 (March 2025 edition,
with the September 2025 revision for MVIP Stage 2). Only corridors whose TDP
figure reads as TRANSFER capacity carry MW; conductor thermal ratings do not.
"""
from __future__ import annotations

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DOE_DIR = os.path.join(HERE, "..", "data", "external", "doe")

AS_OF = "2025-12-31"
CAPTURE = "https://web.archive.org/web/{ts}id_/https://prod-cms.doe.gov.ph/documents/d/guest/{slug}"
FILES = {
    ("committed", "luzon"): ("doe_luzon_committed_2025-12-31.txt",
                             "01-luzon-committed-8-pdf", "20260330220811"),
    ("committed", "visayas"): ("doe_visayas_committed_2025-12-31.txt",
                               "02-visayas-committed-9-pdf", "20260330221412"),
    ("committed", "mindanao"): ("doe_mindanao_committed_2025-12-31.txt",
                                "03-mindanao-committed-9-pdf", "20260330222524"),
    ("indicative", "luzon"): ("doe_luzon_indicative_2025-12-31.txt",
                              "06-luzon-indicative-9-pdf", "20260330222356"),
    ("indicative", "visayas"): ("doe_visayas_indicative_2025-12-31.txt",
                                "07-visayas-indicative-9-pdf", "20260330222820"),
    ("indicative", "mindanao"): ("doe_mindanao_indicative_2025-12-31.txt",
                                 "08-mindanao-indicative-9-pdf", "20260330223944"),
}
SUMMARIES = {
    "committed": ("doe_lvm_committed_summary_2025-12-31.txt",
                  "04-lvm-committed-summary-9-pdf", "20260330215126"),
    "indicative": ("doe_lvm_indicative_summary_2025-12-31.txt",
                   "09-lvm-indicative-summary-8-pdf", "20260330223514"),
}

SECTION_FUEL = {
    "COAL": "coal",
    "OIL-BASED": "oil",
    "OIL BASED": "oil",
    "NATURAL GAS": "natural_gas",
    "GEOTHERMAL": "geothermal",
    "HYDRO": "hydro",
    "HYDROPOWER": "hydro",
    "HYDROELECTRIC": "hydro",
    "BIOMASS": "biomass",
    "SOLAR": "solar",
    "WIND": "wind",
    "ENERGY STORAGE SYSTEM (ESS)": "storage",
}

SECTION_RE = re.compile(r"^([A-Z][A-Z /()&-]*[A-Z)])\s+([\d,]+\.\d{2,3})\s*$")
DATE_TOKEN = (r"(?:TBD|Completed|[A-Z][a-z]{2}-\d{2}|"
              r"[A-Z][a-z]+ \d{4}|Q[1-4]\s?\d{4}|\d{4})")
ROW_RE = re.compile(r"([\d,]+\.\d{2,3})\s+(" + DATE_TOKEN + r")"
                    r"(?:\s+(" + DATE_TOKEN + r"))?(?:\s|$)")
TOTAL_RE = re.compile(r"^TOTAL\b.*?([\d,]+\.\d{2})\s*$")


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _year_of(token: str | None) -> int | None:
    if not token or token in ("TBD", "Completed"):
        return None
    m = re.match(r"^[A-Z][a-z]{2}-(\d{2})$", token)
    if m:
        return 2000 + int(m.group(1))
    m = re.search(r"(\d{4})", token)
    return int(m.group(1)) if m else None


def _parse_detail(status: str, grid: str) -> dict:
    fname, slug, ts = FILES[(status, grid)]
    path = os.path.join(DOE_DIR, fname)
    sections: list[dict] = []
    cur: dict | None = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = SECTION_RE.match(line)
            if m and m.group(1).strip() in SECTION_FUEL:
                cur = {"header": m.group(1).strip(),
                       "fuel": SECTION_FUEL[m.group(1).strip()],
                       "subtotal_mw": _num(m.group(2)), "rows": []}
                sections.append(cur)
                continue
            if cur is None:
                continue
            for rm in ROW_RE.finditer(line):
                mw = _num(rm.group(1))
                # target commercial operation is the SECOND date column; rows
                # missing one column carry only the operation date
                op = rm.group(3) or rm.group(2)
                cur["rows"].append({"mw": mw, "target": op,
                                    "target_year": _year_of(op)})
    out_sections = []
    rows = []
    for s in sections:
        got = round(sum(r["mw"] for r in s["rows"]), 3)
        reconciled = abs(got - s["subtotal_mw"]) < 0.01
        out_sections.append({"grid": grid, "status": status, "fuel": s["fuel"],
                             "subtotal_mw": s["subtotal_mw"],
                             "n_rows": len(s["rows"]) if reconciled else 0,
                             "rows_reconciled": reconciled})
        if reconciled:
            for r in s["rows"]:
                rows.append({"grid": grid, "status": status, "fuel": s["fuel"],
                             **r})
    gen_total = round(sum(s["subtotal_mw"] for s in sections
                          if SECTION_FUEL[s["header"]] != "storage"), 2)
    ess_total = round(sum(s["subtotal_mw"] for s in sections
                          if SECTION_FUEL[s["header"]] == "storage"), 2)
    return {"sections": out_sections, "rows": rows,
            "gen_total_mw": gen_total, "ess_total_mw": ess_total,
            "src": CAPTURE.format(ts=ts, slug=slug),
            "original_url": f"https://prod-cms.doe.gov.ph/documents/d/guest/{slug}"}


def _summary_totals(status: str) -> list[float]:
    fname, _, _ = SUMMARIES[status]
    totals = []
    with open(os.path.join(DOE_DIR, fname), encoding="utf-8",
              errors="replace") as f:
        for line in f:
            m = TOTAL_RE.match(line.strip())
            if m:
                totals.append(_num(m.group(1)))
    return totals


# NGCP TDP 2025-2050 corridor pipeline. `adds_mw` only where the TDP figure
# reads as transfer capacity; conductor thermal ratings stay descriptive.
# `iface` names the studio interface a corridor upgrade applies to, when the
# model's two-corridor topology can carry it at all.
SRC_TDP_MAR = ("https://www.ngcp.ph/Attachment-Uploads/"
               "TDP%202025-2050%20REPORT-2025-03-11-10-38-56.pdf")
SRC_TDP_SEP = ("https://www.ngcp.ph/Attachment-Uploads/"
               "TDP%202025-2050%20REPORT-2025-09-25-09-29-14.pdf")
TDP_CORRIDORS = [
    {"name": "Luzon-Visayas HVDC bipolar upgrade", "iface": "leyte_luzon_hvdc",
     "adds_mw": 440, "target": "Stage 1 Mar 2028, Stage 2 Dec 2030",
     "target_year": 2028, "cost_mphp": 22463,
     "detail": "Upgrades the existing 350 kV Leyte-Luzon link to bipolar "
               "MMC-VSC operation, adding 440 MW of Luzon-Visayas transfer. "
               "Awaiting ERC approval; the date assumes the regulator's final "
               "determination lands on NGCP's planning schedule.",
     "src": SRC_TDP_MAR},
    {"name": "MVIP Stage 2", "iface": "mvip_hvdc",
     "adds_mw": 450, "target": "2025-2030 window, no month stated",
     "target_year": 2030, "cost_mphp": None,
     "detail": "Raises the Mindanao-Visayas link from 450 MW to its 900 MW "
               "design transfer capacity. Itemized in the September 2025 TDP "
               "revision.",
     "src": SRC_TDP_SEP},
    {"name": "Batangas-Mindoro interconnection (BMIBP) Stage 1", "iface": None,
     "adds_mw": None, "target": "TDP says Sep 2027; Mar 2026 press says Jan "
                                "2028 for the subsea segment",
     "target_year": 2028, "cost_mphp": 90656,
     "detail": "Luzon to Mindoro, 28.5 km submarine cable (2x600 MW cable "
               "rating, initially energized 230 kV). ERC approved the P90.66B "
               "project in late 2025. Mindoro is outside this model's "
               "three-grid topology, so it displays here and applies nowhere.",
     "src": "https://www.bworldonline.com/corporate/2026/03/18/737000/"},
    {"name": "Cebu-Leyte 230 kV lines 3 and 4", "iface": None,
     "adds_mw": None, "target": "Stage 1 Dec 2028, Stage 2 Dec 2031",
     "target_year": 2028, "cost_mphp": None,
     "detail": "Parallels the existing Cebu-Leyte corridor (the Visayas leg "
               "of the Luzon-Visayas path). The TDP states no MW transfer "
               "figure, so no number is imputed.",
     "src": SRC_TDP_MAR},
    {"name": "Northern Luzon 500 kV extension", "iface": None,
     "adds_mw": None, "target": "Bolo-Balaoan Oct 2030; Balaoan-Laoag Aug 2031",
     "target_year": 2030, "cost_mphp": 40195,
     "detail": "219 km of 500 kV lines toward the Ilocos wind belt, "
               "ERC-approved. Intra-Luzon: outside the model's two-corridor "
               "topology. The 2x4,234 MW figure in the TDP is a conductor "
               "thermal rating, not a transfer limit.",
     "src": SRC_TDP_MAR},
    {"name": "Bataan-Cavite 500 kV line", "iface": None,
     "adds_mw": None, "target": "feasibility to be assessed; windowed 2031-2040",
     "target_year": None, "cost_mphp": None,
     "detail": "Would close the western Manila Bay loop. Still planning-stage "
               "as of 2026; no capacity stated.",
     "src": SRC_TDP_MAR},
]


def build_projects() -> dict:
    if not all(os.path.exists(os.path.join(DOE_DIR, f[0]))
               for f in FILES.values()):
        return {"available": False,
                "note": "DOE project-list extracts absent from "
                        "data/external/doe/; LT Plan layer unavailable."}
    grids = ("luzon", "visayas", "mindanao")
    sections: list[dict] = []
    rows: list[dict] = []
    editions: dict[str, dict] = {"committed": {}, "indicative": {}}
    totals: dict[str, dict] = {"committed": {}, "indicative": {}}
    for status in ("committed", "indicative"):
        summary = _summary_totals(status)
        if len(summary) < 3:
            raise SystemExit(f"projects: {status} summary parse found "
                             f"{len(summary)} TOTAL rows, expected 3+")
        for i, grid in enumerate(grids):
            parsed = _parse_detail(status, grid)
            if abs(parsed["gen_total_mw"] - summary[i]) > 0.02:
                raise SystemExit(
                    f"projects: {status} {grid} sections sum to "
                    f"{parsed['gen_total_mw']} MW but the DOE summary says "
                    f"{summary[i]} MW; refusing to bake a drifted list")
            sections.extend(parsed["sections"])
            rows.extend(parsed["rows"])
            editions[status][grid] = {"src": parsed["src"],
                                      "original_url": parsed["original_url"]}
            totals[status][grid] = {"gen_mw": parsed["gen_total_mw"],
                                    "ess_mw": parsed["ess_total_mw"]}
        totals[status]["lvm_gen_mw"] = round(
            sum(totals[status][g]["gen_mw"] for g in grids), 2)

    unreconciled = [s for s in sections if not s["rows_reconciled"]]
    return {
        "available": True,
        "as_of": AS_OF,
        "editions": editions,
        "totals": totals,
        "sections": sections,
        "rows": rows,
        "n_rows": len(rows),
        "n_sections_aggregate_only": len(unreconciled),
        "corridors": TDP_CORRIDORS,
        "src_tdp": SRC_TDP_MAR,
        "note": (
            "The DOE's own committed and indicative private-sector power "
            "project lists (As of 31 December 2025), parsed with the same "
            "reconciliation gate as the existing-plants fleet: every fuel "
            "section must sum to the DOE's printed subtotal, and every grid "
            "to the DOE's own LVM summary. Committed means permitted and "
            "financed on the DOE's tracking; indicative is earlier-stage and "
            "far larger. Target dates are the proponents' declarations, not "
            "forecasts by this site. Rows carry no project names: names wrap "
            "unpredictably in the PDF layout and a wrong name on a right "
            "number would be worse than no name."),
        "ess_note": ("Energy storage projects are tracked separately from "
                     "generation, exactly as the DOE's summaries do; the LT "
                     "Plan apply step adds only generation MW."),
        "disclaimer": ("Statistical indicators derived from public data. "
                       "Patterns may have legitimate explanations."),
    }


if __name__ == "__main__":
    import json
    out = build_projects()
    slim = {k: (f"{len(v)} rows" if k == "rows" else v)
            for k, v in out.items() if k != "sections"}
    print(json.dumps(slim, indent=1, default=str)[:4000])
