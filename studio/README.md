# Power Dispatch Studio

Power Dispatch Studio is an
open, browser-based dispatch studio for the Philippine wholesale electricity
market (WESM). It carries the working shape of a commercial production-cost
tool: an object model you edit in a properties grid, scenarios as tagged
overrides, a Run gate, a solution browser, chronological simulation over
observed market days, and a backcast that scores the model against the actual
price tape. Everything runs client-side on baked public data. There is no
license server, no import wizard, and no project file: a scenario and its run
window encode into the URL.

This is an independent, open homage. Not affiliated with Energy Exemplar. Not
PLEXOS.

![Screen recording: opening the studio, editing a generator in the properties grid, running the model, replaying an observed day in Chronology, and reading the backcast against observed prices.](docs/demo.gif)

## If you use PLEXOS

The studio deliberately follows the concepts you already have, at a fraction of
the fidelity and none of the setup cost. The honest mapping:

| PLEXOS concept | Studio equivalent | What to expect |
| --- | --- | --- |
| Objects and classes | System tree: Generators, Fuels, Interfaces, Regions, Storage | Generators are the DOE List of Existing Power Plants at unit level (355 units, 2025 editions); Interfaces are the two HVDC corridors (Leyte-Luzon, MVIP) |
| Properties grid, scenario tagging | Same interaction: edit a cell, the edit is tagged to the active scenario, revert per cell | Base values return with the x on a changed cell |
| Execute | Run | A coordinate-descent coupled clear of the three grids; under a second in the browser, so the Run gate is authentic without the queue |
| ST Schedule | Chronology | Hour-by-hour replay of an observed market day (or the week ending on it) from the IEMOP archive, on your edited model |
| Solution browser | Solution views | Merit order, Chronology, Coupled flows, N-1, Regions, a seeded Monte Carlo reliability, plus scenario compare |
| Solution files | Saved runs | Frozen solves (scenario snapshot, window, engine version, hourly results): diff two runs, export hourly CSV, restore as a scenario |
| Datafiles | Baked JSON artifacts | Produced by the Python pipeline from archived IEMOP files; the frontend never computes a number the pipeline cannot reproduce |
| Model validation | Backcast view | Every full-coverage market day replayed against observed hourly LWAP, error stated per grid, nothing tuned |

What it is not: there is no MILP, no security-constrained unit commitment, no
nodal network, and no capacity expansion. The scope section below states
exactly what solves.

## The model, honestly scoped

Three zonal regions (Luzon, Visayas, Mindanao) with per-fuel merit-order
blocks, cleared together over the two HVDC corridors by coordinate descent
with a small wheeling cost; a saturated corridor prices the downstream grid
above the upstream one by the congestion rent. Coal splits into a committed
must-run tranche (offered at the observed commitment level) and a marginal
tranche at the administered price. Chronology replays observed days: demand is
the archive's dispatched generation per hour, solar follows a stated 24-hour
shape, storage cycles on a labeled charge-cheap, discharge-dear heuristic with
daily state-of-charge reset, and an optional reserve co-clear prices each hour
at demand plus the scheduled reserve requirement.

| Included | Excluded (by design) |
| --- | --- |
| Coupled zonal dispatch with congestion rent | Nodal LMPs (the public PH LMP congestion component is structurally zero) |
| Per-unit fleet from the DOE list, unit-level N-1 | Security-constrained unit commitment, ramp rates, min up/down times |
| Chronological replay of observed days | Load or price forecasting |
| Storage cycling (heuristic) | Inter-temporal optimisation, inter-day storage carryover |
| Reserve co-clear approximation | Full energy-reserve co-optimisation |
| Monte Carlo adequacy on forced-outage rates | Capacity expansion (LT Plan), maintenance scheduling (PASA) |

The model's honesty gate is calibration against the observed load-weighted
average price (LWAP). A competitive cost stack under-prices tight hours; that
residual is the scarcity and offer premium a cost model cannot see, and it is
reported, not tuned away.

## Validation

The Backcast view replays every full-coverage market day with the base model
against the observed hourly LWAP. At the July 2026 bake (window 2026-05-01 to
2026-06-25, 56 market days, 24 hourly points each per grid):

| Grid | Observed mean | Modeled mean | MAE | Bias | Correlation |
| --- | --- | --- | --- | --- | --- |
| Luzon | P7.63/kWh | P5.97/kWh | P4.29 | -P1.66 | 0.20 |
| Visayas | P12.91/kWh | P5.93/kWh | P8.60 | -P6.98 | 0.24 |
| Mindanao | P11.48/kWh | P6.07/kWh | P7.52 | -P5.42 | 0.15 |

Read that table before trusting any scenario: the model explains the cost
floor and the congestion geometry, and it under-prices scarcity everywhere,
most of all in the Visayas. The high-hour hit rate reports n/a when the flat
cost model cannot rank hours, instead of a fake 100%. The live view recomputes
these numbers from the current archive window.

Engine correctness is pinned by a golden parity harness: the Python pipeline
is the source of truth, and it bakes input/output fixtures (five snapshot
cases, six chronological day-runs) that the browser engines must reproduce to
P0.02/kWh and 1 MW, including exact marginal-block labels. Any change to one
engine that does not land in the other fails the suite.

## Three workflows to try

**Price a data-center build.** System > Regions, raise Luzon load by the
build's MW (flat, the data-center shape), Run. Chronology on the demand-peak
day shows which hours flip from coal to oil; Save run, revert the edit, save
the base, and Compare two runs gives the price and congestion-rent delta.

**Stress the single contingency.** System > Generators, set SPI U1 and SPI U2
(the two 647 MW Sual units) to zero, Run. N-1 and Reliability show the
adequacy hit; Chronology on the stress day shows whether the evening clears on
oil or sheds load. The Leyte-Luzon corridor's rent responds in Coupled flows.

**Test the Malampaya cliff.** System > Fuels, reprice natural gas from the
Malampaya cost (P4.80/kWh) to the imported-LNG cost (P10.30/kWh), Run, and
read the Chronology price shape; add the dry-hydrology case from the Quick
scenario for the compounding view. Share the exact scenario with Copy link.

## Data

| Input | Source | Refresh |
| --- | --- | --- |
| Hourly demand and observed prices (90 observed days) | IEMOP RTD regional summaries and final LWAP files, archived daily by the repo's pipeline (the public window rolls ~90 days; the git history is the durable archive) | Daily cron |
| Per-unit fleet (355 units) | DOE List of Existing Power Plants, grid-connected: Luzon and Mindanao as of 2025-04-30, Visayas 2025-03-31 (Internet Archive captures of the DOE's own PDFs; doe.gov.ph refuses non-PH requests). The parser refuses any grid whose rows do not reconcile to the PDF's own per-fuel subtotals | Per DOE edition |
| Corridor limits | IEMOP monthly reports (Leyte-Luzon 250 MW operating limit) and the MVIP nameplate | Sourced constants |
| Fuel costs | ERC administered coal price, Malampaya FOI, imported-LNG estimate | Sourced constants |
| Reserve requirements and prices | IEMOP RTD reserve schedules (sample days; product-code mapping labeled INFERRED) | Sample top-ups |
| Storage fleet | DOE (634 MW BESS), CBK Power (Kalayaan 685 MW); energy durations are stated assumptions because the sources publish MW, not MWh | Sourced constants |

Every number in the interface is either computed by the pipeline from archived
files or a labeled constant with its primary source; `../web/methodology.html`
carries the full provenance, and assumptions ship in the artifacts themselves.

## Quickstart

```bash
cd studio
npm install
npm run dev        # copies the baked data, starts Vite on :5173
```

Requires the baked artifacts in `../web/data/` (committed; regenerate with
`make data` at the repo root).

## Verify

```bash
npm run typecheck  # tsc --noEmit (app + test configs)
npm run lint       # oxlint
npm run format:check
npm run test       # vitest: golden parity (snapshot + chronological) + invariants
npm run build      # production build to dist/
```

## Structure

```text
src/
  lib/       types.ts (baked-model types), data.ts (loader hooks + formatters)
  ui/        kit.tsx (Panel, StatTile, Chip, Segmented, ThemeToggle), DataGrid.tsx
  map/       MapView.tsx (MapLibre network view)
  studio/    Studio.tsx (shell: explorer, ribbon, Run gate, share-link hydration)
             model.ts (object model + scenario overrides + solveModel)
             engine.ts (coupled snapshot clear), engine.test.ts + model.test.ts
             chrono.ts (hour-by-hour replay engine), chrono.test.ts (parity vs
             pipeline/chrono.py golden fixtures)
             ChronoView.tsx (Chronology), BackcastView.tsx (model vs the tape)
             runs.ts + RunsView.tsx (frozen runs, compare, CSV, share links)
             model-views.tsx (properties grid + solved views), views.tsx,
             charts.tsx (SVG), Scenario.tsx, Bill.tsx, MarketPower.tsx
  styles/    tokens.css (design tokens, light + dark), base.css, app.css
```

The Python counterparts live in `../pipeline/`: `chrono.py` (reference
chronological engine + backcast), `profiles.py` (observed-day bake),
`fleet_doe.py` (DOE list parser with the reconciliation gate).

## Record the demo

With the dev server on :5173:

```bash
python3 scripts/record-demo.py                 # Playwright video to /tmp/studio-rec
ffmpeg -y -i <video>.webm -vf \
  "fps=9,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -i <video>.webm -i /tmp/pal.png -lavfi \
  "fps=9,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  /tmp/raw.gif
gifsicle -O3 --lossy=60 /tmp/raw.gif -o docs/demo.gif
```

## Limitations to keep in view

- Zonal, not nodal; three regions, two corridors. Intra-region congestion does
  not exist in this model.
- The snapshot solve prices one reference hour; Chronology prices 24 (or 168),
  with no inter-temporal coupling beyond the storage state of charge.
- Editing a unit shifts its fuel's available capacity by the delta: a labeled
  approximation, not unit commitment.
- Storage dispatch is a stated heuristic, not an optimisation, and resets daily.
- Observed-day replay is not a forecast. Forward cases (the LNG switch, dry
  hydrology, added load) are what-ifs on observed days.
- The backcast table above is the accuracy statement. If your use case needs
  the scarcity tail priced correctly, this model does not do that, and says so.

## License and attribution

Code MIT; baked data products CC-BY-4.0. Attribution when redistributing:
Power Dispatch Studio (2026), IEMOP public market data archive, DOE List of Existing
Power Plants. The interface is an original work; PLEXOS is a trademark of
Energy Exemplar, used here only to describe the homage.
