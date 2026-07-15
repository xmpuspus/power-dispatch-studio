# power-dispatch-studio (formerly gridbill-ph) - working notes

PH civic map: can the Philippine grid host the announced data-center wave, where do
choke points force siting, and what does that do to WESM and retail prices. Sibling
of gridbill-us and sinkmap-ph; mirror their layout and conventions. Born 2026-07-05
from the ultrawork data-source pass (verdict GO; evidence ~/Desktop/wesm-probe-20260705/,
memo ~/Desktop/next-build-20260705.md Part 3).

## The three questions (the story rail IS these, in order)

1. Supply: if PH builds more data centers, is there headroom? (margins vs announced MW)
2. Infra: where would they have to sit? (choke points, Sual-trip fragility, alerts)
3. Prices: what does that do to WESM and the Meralco bill? (congestion receipts, pass-through)

## Stance (locked, non-negotiable)

- NEVER claim "data centers raised WESM prices." Current PH DC load (~200 MW per DICT,
  contested up to 630 MW) is small against a ~15 GW Luzon peak. The defensible frame:
  the choke points already bind daily and the market prices them (receipts); here is
  where the announced wave (DICT 1.5 GW by 2028, Meralco 1,000 MW for 10 DCs) lands.
- Forecasts are LABELED forecasts with owner + date (DICT, DOE, DCPH). Contested
  current-capacity figures are shown as a range with both sources, or dropped.
- Sual is arithmetic, not prophecy: unit trip sizes (2x647 MW) subtracted from
  observed margins on observed days, plus documented alert episodes. Never "will
  cause brownouts."
- Every number traces to a primary source (IEMOP file, NGCP TDP, IEMOP monthly
  report, Meralco advisory, PCIJ). Compute before narrating. Schematic map lines
  are labeled schematic. City-precision DC pins are labeled city-precision.
- Neutral economic framing. No takedown of a named company. Data centers are also
  investment; the map shows who pays for what, not villains.
- Plain English, short sentences, no em-dashes, no AI-jargon (tests/qa_gate.py enforces).

## Data architecture

- `pipeline/archive_iemop.py` - the compounding asset. IEMOP's public window is a
  rolling ~90 days per dataset (min_date in each page's config). We archive daily
  CSVs into `data/raw/<KEY>/` and COMMIT them; the git history becomes the public
  archive nobody else keeps. Datasets: RTDCV + DAPCV (congestions manifesting, named
  equipment per 5-min interval), RTDSUM (rtd regional summaries), LWAPF (load
  weighted average prices final), HVDCRTD (hvdc limits imposed in rtd), OUTRTD
  (outage schedules used in rtd), DIPCEF (nodal LMP with LMP_CONGESTION component,
  sample days only, zips).
- Access mechanic (verified 2026-07-05): each iemop.ph/market-data/<slug>/ page
  carries post_id + min_date in a `var php = {...}` blob; POST wp-admin/admin-ajax.php
  action=display_filtered_market_data_files&post_id=N returns the FULL b64 file list
  (client-side pagination); GET <page>?md_file=<b64 server path> serves the file.
  No login, no geo-block from US IPs. Constructed URLs reach ~2026-03-01 (200,
  header-only when no congestion), 404 by 2024. Courtesy: sequential fetches,
  0.25 s sleep, abort a dataset after 5 consecutive errors (IEMOP firewalls
  50 HTTP errors / 2 h).
- `pipeline/build_data.py` bakes `web/data/*.json` from the archive + verified
  constants (each constant carries its primary-source URL in a comment). The
  frontend reads only baked artifacts.

## Layout

- `pipeline/archive_iemop.py` - archiver (curl subprocess, stdlib only; macOS
  python3 + requests has SSL issues, so shell out to curl).
- `pipeline/build_data.py` - bake web/data/ from data/raw/ + constants.
- `web/index.html` - single-file MapLibre, no-key Carto basemap, story rail with
  the three questions, choke-point arcs, DC sites layer, price/margin panels.
  window.__diag exposed for e2e.
- `web/methodology.html` - every number, every source, every caveat.
- `tests/test_data.py` - plain-python PASS/FAIL pins on baked artifacts.
- `tests/qa_gate.py` - banned framings + em-dash + AI-jargon + overwrought voice.
- `tests/e2e.sh` - zsh behavioral checks against the running map.
- `.github/workflows/archive.yml` - daily cron: --daily fetch + commit.

## Commands

```bash
make backfill   # one-time: pull the full public window into data/raw/
make archive    # daily incremental (what the cron runs)
make data       # bake web/data/ from the archive
make serve      # Range-capable dev server :8788
make qa         # data integrity pins + banned-framing gate
make e2e        # behavioral suite (make serve & first)
```

## Verified anchors (primary sources; full list in web/methodology.html)

- IEMOP Dec 2025 monthly report: Leyte-Luzon HVDC at its 250 MW Luzon-to-Visayas
  limit or offline 69% of the billing period; 230 kV Leyte-Cebu congestion.
- IEMOP May 2026 report (via powerphilippines): system avg P7.79/kWh (+38.5% vs
  April), Visayas P10.20, Mindanao P9.28, Luzon P7.02; both HVDC links frequently
  at max or security-limited.
- WESM suspended 2026-03-26 to 2026-05-01 (ERC, fuel-shock emergency, EO 110).
- Meralco June 2026: +P0.1488/kWh to P14.4833; generation charge P9.0704 on WESM
  at P7.0281 (Meralco advisory + BusinessWorld Jun 12).
- Sual coal plant: 2 x 647 MW, Pangasinan, largest single units on the Luzon grid.
- DC demand anchors: DICT 1.5 GW by 2028 (BusinessWorld Oct 2025); DOE 300-1500 MW
  added peak (PCIJ Jan 2026); Meralco 1,000 MW for 10 data centers (PCIJ);
  DCPH alliance 473 MW (Feb 2026); Cushman 73 MW operational / 156 MW pipeline (2025).
- NGCP TDP 2025-2050 PDF public at ngcp.ph/Attachment-Uploads/ (root 403s curl,
  attachment path serves 200).

## Status / next

SHIPPED and live at power-dispatch-studio.vercel.app (PERSONAL Vercel account) since
2026-07-06; the nightly archive cron + verify_claims oracle keep the bake and the
public prose in lockstep. Before any push that changes shipped numbers: re-run
`make qa`, re-run `make viz` for the OG card + montage, re-record the hero GIF (real
recording only) if a shown surface moved, then `make e2e BASE=<deploy>` + screenshot
read-back.

## Conventions

- Commits: simple messages, no prefixes, no AI attribution, --no-gpg-sign.
- data/raw/ is committed (the archive is the point). DIPCEF zips stay small
  (sample days only).
- New numbers need a source URL in the same commit.
- python3 always; ruff clean; tests are plain python (no pytest dependency).
