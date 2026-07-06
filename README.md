# gridbill-ph

Can the Philippine grid host the announced data-center wave? An interactive map and
a daily archive built on the market operator's own public files: where transmission
already binds (named equipment, 5-minute receipts), where the announced data-center
megawatts land, and what the spot market and the Meralco bill are doing. Open the
map, switch between the three questions, hover any line or pin for its source.

[![License: MIT (code) / CC-BY-4.0 (data)](https://img.shields.io/badge/license-MIT%20%2F%20CC--BY--4.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](README.md)

## The three questions

**1. If the Philippines builds more data centers, is there supply for them?**
DICT's own forecast is 1.5 GW of data-center capacity by 2028 (a labeled forecast,
not a measurement); Meralco has committed 1,000 MW for 10 data centers (PCIJ). The
whole system's supply margin in May 2026, the first full month after WESM trading
resumed, was 3,629 MW (IEMOP). The forecast alone is about 41% of that margin, and
a data center is near-flat 24/7 load. In the same archive window, the operator's
dispatch schedules recorded load curtailed on dozens of grid-days. Headroom for a
wave this size means new firm supply; the map draws the announced megawatts against
the margin so the arithmetic is visible.

**2. Is the infrastructure ready, and where would data centers have to sit?**
The choke points are named, public, and already binding. IEMOP's December 2025
report has the Leyte-Luzon HVDC (440 MW nameplate, 250 MW operating limit) at its
limit or offline 69% of the billing period; the May 2026 report has both HVDC
links frequently at maximum. Our own archive of IEMOP's "congestions manifesting"
files counts named equipment at 100% of its binding limit across tens of thousands
of 5-minute intervals in 90 days, led by the Tabango-Daanbantayan corridor
(Leyte-Cebu), the same corridor the reports name. Nearly every pinned data-center
site sits in the Luzon load pocket, on the importing side of those links. Sual's
two 647 MW units are the largest single contingencies on the Luzon grid; one unit
equals about 18% of the May margin, which is why a single trip moves the whole
grid. The map's toggle does that subtraction in the open.

**3. What would it do to wholesale and retail prices?**
One market on paper, three prices in practice. May 2026 averaged P7.79/kWh
system-wide (+38.5% vs April): Luzon P7.02, Visayas P10.20, Mindanao P9.28. The
archived daily LWAP series shows the islands pricing apart when the links bind,
with double-digit peso spreads on the worst days. WESM passes into the Meralco
generation charge monthly: the June 2026 advisory carried WESM at P7.03/kWh inside
a P9.07/kWh generation charge on a P14.48/kWh total rate. The map never claims
data centers set today's prices (current data-center load is small against a
roughly 15 GW Luzon peak); it shows the pricing machinery that any new flat 24/7
load plugs into.

## What this is

- **A daily archive.** IEMOP's public window is a rolling ~90 days per dataset.
  `pipeline/archive_iemop.py` plus a GitHub Actions cron turns that window into a
  permanent public archive under `data/raw/` (the git history is the archive):
  named binding constraints (RTD + DAP), regional summaries (demand, curtailment,
  reserve slack), load-weighted average prices, HVDC limits, outage schedules.
- **A baked, checkable map.** `pipeline/build_data.py` computes every number the
  site shows into `web/data/*.json`; the page renders only baked artifacts, so
  copy cannot drift from data. `web/index.html` is a single-file MapLibre map.
- **A sourced constants layer.** Choke-point corridors (schematic lines between
  named converter stations and substations), 14 data-center sites with a citable
  source each (public MW on 11 of them, 591.3 MW named total), and every market
  anchor with its primary source, in `pipeline/constants_ph.py`.

## What it is not

- Not a claim that data centers raised Philippine electricity prices. The window's
  prices are driven by fuel, outages, weather, and the market restart.
- Not a brownout forecast. It shows observed curtailment in dispatch schedules,
  observed reserve shortfalls, and arithmetic on published margins.
- Not a complete data-center inventory (Cushman counts 24 operational facilities;
  DataCenterMap lists 44; only publicly sourced sites are pinned, at city
  precision).
- Not route maps: corridor lines are schematic links between named endpoints.

## Reproduce locally

Requires Python 3.11+ and curl. No accounts, no keys.

```bash
git clone https://github.com/xmpuspus/gridbill-ph
cd gridbill-ph
make backfill    # pull the full public window from iemop.ph (~15 min, ~50 MB)
make data        # bake web/data/ from the archive + sourced constants
make qa          # data-integrity pins + banned-framing gate
make serve       # http://localhost:8789
make e2e         # behavioral checks against the running map
```

The committed `data/raw/` means `make data` works offline from a clean clone;
`make backfill` tops up any days the archive is missing (fetches are sequential
and throttled out of courtesy to IEMOP's servers).

## Data products

| File | What it is |
|---|---|
| `data/raw/RTDCV/`, `data/raw/DAPCV/` | IEMOP "congestions manifesting" daily CSVs: named equipment, station, binding limit, MW flow, overload, per 5-minute interval |
| `data/raw/RTDSUM/` | RTD regional summaries: energy and reserve rows per grid (demand bids, load curtailed, reserve requirement vs scheduled) |
| `data/raw/LWAPF/` | Load-weighted average prices, final, per grid per 5-minute interval (PhP/MWh) |
| `data/raw/HVDCRTD/`, `data/raw/OUTRTD/` | HVDC limits imposed in RTD; outage schedules used in RTD |
| `web/data/*.json` | The baked layers: constraint league, reliability series, daily price series and spreads, choke points, data-center sites, the three answers |

## Methodology

Every number, source, unit conversion, and caveat: [`web/methodology.html`](web/methodology.html).
Working notes and the non-negotiable stance (no attribution claims, no prophecy,
labeled forecasts, schematic lines, city-precision pins): [`CLAUDE.md`](CLAUDE.md).

## Roadmap

- DIPCEF nodal congestion-premium layer (hourly zips; the first listing attempt
  hit a transient TLS failure, the archiver retries daily).
- Per-interval HVDC limit series from the archived HVDCRTD files.
- Node-code to location mapping for nodal price geography (the resource codes
  need a hand-built reference join, the same way community reserve-market
  dashboards do it).
- Meralco generation-charge series scraped from the monthly advisories.

## License and attribution

Code: MIT. Baked data products: CC-BY-4.0. Upstream market data belongs to its
publishers (IEMOP, NGCP, Meralco); this repository mirrors public files as-is for
research with attribution, and will honor any takedown request from the publisher.

Attribution when redistributing the baked data: *gridbill-ph (2026), IEMOP public
market data archive, https://github.com/xmpuspus/gridbill-ph*.

## Public-record disclaimer

All data sourced from public records (IEMOP market files, NGCP publications,
Meralco advisories, PCIJ reporting, company announcements). This tool computes
statistical indicators only. Patterns may have legitimate explanations. Specific
allegations, if any, require independent investigation and corroboration.
