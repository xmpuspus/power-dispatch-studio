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
| Execute | Run | One HiGHS linear program clearing the three grids together (the browser runs the same wasm solver build commercial tools embed); milliseconds per solve, so the Run gate is authentic without the queue |
| ST Schedule | Chronology | Hour-by-hour replay of an observed market day (or the week ending on it) from the IEMOP archive, on your edited model |
| LT Plan | LT Plan view | The DOE's committed and indicative project lists (reconciled to the DOE's own subtotals) as build candidates on a horizon slider; Apply writes them into the scenario as ordinary edits. No expansion optimizer runs |
| PASA | PASA view | The operator's own outage schedules (OUTRTD), sized against the DOE fleet, with the reliability Monte Carlo re-run on the day's scheduled-out MW |
| Execute a model list | Load sweep | The snapshot solve stepped over added flat load on one grid: where the corridor binds, where the marginal fuel flips, where unserved load begins |
| Stochastic samples | Window band | The scenario replayed across every full-coverage market day in the archive; per-hour price percentiles and the daily-mean distribution. The sample is the observed days, nothing synthetic |
| Binding-constraint reporting | What set the price | Every Chronology hour classified: marginal fuel block, saturated corridor on the importing side, or unserved load |
| Solution browser | Solution views | Merit order, Chronology, Load sweep, Window band, Coupled flows, N-1, Regions, a seeded Monte Carlo reliability, plus scenario compare |
| Solution files | Saved runs | Frozen solves (scenario snapshot, window, engine version, hourly results): diff two runs, export hourly CSV or a self-contained HTML report, restore as a scenario |
| Emissions accounting | Emissions view | Dispatched energy priced in operational tCO2 with sourced per-technology factors; biomass reported uncounted rather than assigned a contested factor |
| Datafiles | Baked JSON artifacts | Produced by the Python pipeline from archived IEMOP files; the frontend never computes a number the pipeline cannot reproduce |
| Model validation | Backcast view | Every full-coverage market day replayed against observed hourly LWAP, error stated per grid, nothing tuned |

What it is not: an LP, not a MILP: no unit commitment, no security
constraints, no nodal network, and no expansion optimizer (the LT Plan view
applies the DOE's own lists; it does not choose builds). The scope section
below states exactly what solves.

## The model, honestly scoped

Three zonal regions (Luzon, Visayas, Mindanao) with per-fuel merit-order
blocks, cleared together over the two HVDC corridors as one HiGHS linear
program with a small wheeling cost. Prices are the balance duals, real
locational marginal prices: a saturated corridor prices the downstream grid
above the upstream one by the congestion rent, and an unsaturated corridor
holds neighbours within the wheeling cost, so an importing grid can price at
its neighbour's marginal block instead of its own. Coal splits into a
committed must-run tranche (offered at the observed commitment level) and a
marginal tranche at the administered price. Chronology solves each observed
day as a single 24-hour LP: demand is the archive's dispatched generation per
hour, solar follows a stated 24-hour shape, storage is optimised across the
hours (it cycles only when the price spread beats the round-trip loss, and
idles on a flat day) with daily state-of-charge reset, and the reserve toggle
withholds the scheduled requirement from the dispatchable stack instead of
inflating demand.

| Included | Excluded (by design) |
| --- | --- |
| Coupled zonal dispatch with congestion rent | Nodal LMPs (the public PH LMP congestion component is structurally zero) |
| Per-unit fleet from the DOE list, unit-level N-1 | Security-constrained unit commitment, ramp rates, min up/down times |
| Chronological replay of observed days, with each day's scheduled-outage deviation applied (OUTRTD via the PASA mapping) | Load or price forecasting |
| Shortage priced at the P32/kWh WESM offer cap (published rule), labeled 'shortage' | Offer-behavior pricing below the cap (per-participant strategy) |
| Storage optimised over the day's hours (HiGHS LP) | Inter-day storage carryover |
| Reserve as a withheld-capacity constraint; OBSERVED official regional reserve prices shown beside it | Reserve co-optimisation inside the LP (needs per-participant reserve offer stacks) |
| Monte Carlo adequacy on forced-outage rates, with the day's scheduled outages removable (PASA lite) | Maintenance-schedule optimisation |
| DOE build pipeline as sourced candidates on a horizon (LT Plan lite) | Expansion optimisation, build-cost economics |
| Load sweep, window band, per-hour binding classification, operational CO2 | Build-cost economics |
| Energy-limited hydro: the day LP caps hydro at the day's OBSERVED water (DIPCEF per-resource schedules, derived daily; scaled with edits and the hydrology lever) | Inter-day water management (each day's budget stands alone) |

The model's honesty gate is calibration against two observed targets: the
load-weighted average price (LWAP, the settlement-side series) and the
regional market clearing price (MCP, the ex-ante series commensurate with a
dispatch dual). A competitive cost stack under-prices tight hours; that
residual is the scarcity and offer premium a cost model cannot see, and it is
reported, not tuned away.

## Validation

The Backcast view replays every full-coverage market day with the base model
against the observed hourly LWAP. At the July 2026 bake (window 2026-05-01 to
2026-06-25, 56 market days, 24 hourly points each per grid):

Against the settlement-side LWAP (1,344 hours per grid):

| Grid | Observed mean | Modeled mean | MAE | Bias | Correlation | High-hour hit |
| --- | --- | --- | --- | --- | --- | --- |
| Luzon | P7.63/kWh | P6.00/kWh | P4.33 | -P1.63 | 0.38 | 43% |
| Visayas | P12.91/kWh | P6.00/kWh | P8.66 | -P6.91 | 0.46 | 45% |
| Mindanao | P11.48/kWh | P6.00/kWh | P7.58 | -P5.48 | 0.07 | 7% |

Against the observed regional clearing price (MCP, the ex-ante series
commensurate with a dispatch dual; tied intervals averaged per interval
before the hourly mean). Coverage is stated because it is uneven: the MCP
files name a price in fewer Visayas intervals than Luzon ones, and if the
missing intervals skew toward substituted extremes the observed means here
are subset statistics:

| Grid | Coverage | Observed mean | Modeled mean | MAE | Bias | Correlation | High-hour hit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Luzon | 1,310 of 1,344 h | P7.03/kWh | P6.00/kWh | P4.01 | -P1.02 | 0.38 | 43% |
| Visayas | 777 of 1,344 h | P14.78/kWh | P6.00/kWh | P10.91 | -P8.78 | 0.32 | 30% |
| Mindanao | 1,196 of 1,344 h | P11.58/kWh | P6.00/kWh | P8.21 | -P5.58 | 0.06 | 15% |

And the corridors themselves, the third table (modeled flow vs the observed
net market imports and exports in the same files):

| Corridor | Observed mean | Modeled mean | MAE | Direction agreement |
| --- | --- | --- | --- | --- |
| Luzon to Visayas | 46 MW | -2 MW | 92 MW | 7% |
| Visayas to Mindanao | -373 MW | -4 MW | 369 MW | 4% |

The fourth set replays the same days with the operator's own OFFER BOOKS
(every resource's priced curve from the real-time generation offers, plus
self-scheduled capacity as price-takers) instead of the cost proxy: no
storage or water layers, because the books already embody unit behavior
(reserve withholding stays available as a stated whole-book
approximation). 55 derived days; the 56th, 2026-06-09, was refused by the
coverage gate and is named rather than hidden. Two framing caveats travel
with the set: the whole window sits inside the post-suspension restart
regime, so this validates one market quarter, not a climatology; and the
corridor DIRECTION agreement partly follows from native-load demand
construction (a net exporter's load sits below its book by construction),
so the load-bearing flow statistic is the MAE, not the direction column.

| Grid | Target | MAE | Bias | Correlation | High-hour hit |
| --- | --- | --- | --- | --- | --- |
| Luzon | LWAP | P2.94 | +P1.45 | 0.73 | 54% |
| Visayas | LWAP | P5.15 | -P0.64 | 0.68 | 53% |
| Mindanao | LWAP | P4.34 | -P1.09 | 0.73 | 46% |
| Luzon | MCP | P2.80 | +P1.94 | 0.78 | 69% |
| Visayas | MCP | P6.23 | -P5.36 | 0.73 | 49% |
| Mindanao | MCP | P3.08 | -P2.48 | 0.87 | 70% |

| Corridor (offer mode) | Observed mean | Modeled mean | MAE | Direction agreement |
| --- | --- | --- | --- | --- |
| Luzon to Visayas | 45 MW | 111 MW | 101 MW | 88% |
| Visayas to Mindanao | -375 MW | -337 MW | 57 MW | 99% |

Five engine steps sit inside these numbers, all reported rather than tuned:
the LP swap, the observed water budgets, the fleet-derived hydro split, the
observed layers (curtailment in demand, scheduled-outage deviations, the
P32/kWh offer cap on short hours), and now NATIVE-LOAD demand: generation
plus net market imports, so each grid carries the load it actually served
rather than a series that self-balances by construction. That last step
moved three things at once, in different directions, and the tables say so.
The Visayas finally has a rankable settlement-price shape (correlation
0.47, hit rate 45 percent, from unrankable) and its adequacy margin drops
to 1.6 percent at peak, which is what a grid living through a 52-day
yellow-alert streak should look like. The same change CUT the Visayas MCP
agreement (correlation 0.65 to 0.33, hit 93 to 30 percent): the old
self-balanced demand had flattered the sparse-coverage MCP subset, and
that flattery is gone.

The offer-mode set is the sixth step and the payoff. With the market's own
bids, the corridors move like the real grid (99 percent direction
agreement on Visayas-Mindanao, 57 MW MAE against a 375 MW mean flow,
where the cost proxy's three near-identical stacks agree with the
observed direction in under 10 percent of decisive hours), the Visayas
settlement bias collapses from -P6.91 to -P0.64, and Mindanao's
clearing-price correlation reaches 0.87. Subtract the two modes and the
offer premium stops being a residual and becomes a measured series. What
remains: Luzon OVER-prices settlement by P1.45 (the ex-ante book clears
above what substitution-shaved settlement pays, the same wedge the LWAP
vs MCP tables show), and the sparse Visayas MCP subset keeps a -P5.36
bias with its coverage stated.

The two engines also disagree about the marquee what-if, and that
disagreement is a published number, not a footnote: on the widest-swing
market day, the DICT 1.5 GW wave costs +P4.75/kWh on the cost stack but
+P9.08/kWh on the observed bids, with +P6.31 reaching the Visayas and
+P3.12 Mindanao where the cost stack moves nothing (both runs are pinned
in the golden cases; the Chronology engine toggle reproduces them). Read
every cost-mode scenario delta as a floor.

Read these tables before trusting any scenario: the cost model explains
the cost floor and the congestion geometry and under-prices scarcity; the
offer mode prices what the market as bid would do, one observed quarter
deep. The high-hour hit rate reports n/a when a flat model cannot rank
hours, instead of a fake 100%. The live view recomputes these numbers
from the current archive window.

Engine correctness is pinned by a two-layer parity harness. Both engines
build the SAME linear program as the same text, byte for byte (every
coefficient serialized from integer micro-units), and the fixtures pin its
sha256: a model-construction drift on either side fails the hash before any
solver runs. On top of that, the Python solve (highspy) bakes input/output
fixtures (five snapshot cases, six chronological day-runs) that the browser
solve (the HiGHS wasm build) must reproduce to P0.02/kWh and 1 MW, including
exact price-setter labels. Any change to one engine that does not land in the
other fails the suite, and the retired coordinate-descent clear stays in the
pipeline test suite as a cost cross-oracle.

## Three workflows to try

**Price a data-center build.** System > Regions, raise Luzon load by the
build's MW (flat, the data-center shape), Run. Chronology on the demand-peak
day shows which hours flip from coal to oil; Save run, revert the edit, save
the base, and Compare two runs gives the price and congestion-rent delta.

![Recorded studio walkthrough of pricing a data-center build: on the demand-peak day the base evening clears on coal at P6.00/kWh; raising Luzon load by 1,500 MW (the DICT 2028 build) flips the evening to oil, mean P6.00 to P9.00 and peak P12.00, and saturates the Leyte-Luzon HVDC; Compare two runs reads +P3.00/kWh and +P15M congestion rent.](docs/workflow-1-datacenter.gif)

**Stress the single contingency.** System > Generators, set SPI U1 and SPI U2
(the two 647 MW Sual units) to zero, Run. N-1 and Reliability show the
adequacy hit; Chronology on the stress day shows whether the evening clears on
oil or sheds load, and its congestion-rent tile prices the corridors binding in
the peak hours.

![Recorded studio walkthrough of the single contingency: zeroing both 647 MW Sual units lifts Luzon loss-of-load probability from 1.8% to 12.5% (expected shed 9 to 71 MW), leaves the rest of the fleet tripping P6 to P12 in N-1, and clears the observed stress evening on oil, mean P6.00 to P8.75 with P13.5M congestion rent.](docs/workflow-2-contingency.gif)

**Test the Malampaya cliff.** System > Fuels, reprice natural gas from the
Malampaya cost (P4.80/kWh) to the imported-LNG cost (P10.30/kWh), Run, and
read the Chronology price shape; then in the Quick scenario, stack the announced
build and a dry year on the LNG switch for the compounding view. Share the exact
scenario with Copy link.

![Recorded studio walkthrough of the Malampaya cliff: repricing gas from the Malampaya cost P4.80 to the imported-LNG cost P10.30 lifts the whole Luzon price shape to the gas cost, mean P6.00 to P10.30 with congestion rent P0.75M to P24.73M; then in the Quick scenario, stacking imported LNG, the announced 1,500 MW build, and a dry year tips the evening to oil at P12.00, +P6.00/kWh.](docs/workflow-3-malampaya.gif)

## Data

| Input | Source | Refresh |
| --- | --- | --- |
| Hourly demand and observed prices (90 observed days) | IEMOP RTD regional summaries and final LWAP files, archived daily by the repo's pipeline (the public window rolls ~90 days; the git history is the durable archive) | Daily cron |
| Per-unit fleet (355 units) | DOE List of Existing Power Plants, grid-connected: Luzon and Mindanao as of 2025-04-30, Visayas 2025-03-31 (Internet Archive captures of the DOE's own PDFs; doe.gov.ph refuses non-PH requests). The parser refuses any grid whose rows do not reconcile to the PDF's own per-fuel subtotals | Per DOE edition |
| Corridor limits | IEMOP monthly reports (Leyte-Luzon 250 MW operating limit) and the MVIP nameplate | Sourced constants |
| Fuel costs | ERC administered coal price, Malampaya FOI, imported-LNG estimate | Sourced constants |
| Reserve requirements and prices | IEMOP RTD reserve schedules (sample days; product-code mapping labeled INFERRED) | Sample top-ups |
| Hydro water budgets | Per-resource daily energy derived from DIPCEF schedules (data/derived/dipcef_daily/, reconciled to RTDSUM within 2 percent per day); grid-connected WESM hydro matched to the DOE fleet, pumped storage excluded | Daily cron |
| Storage fleet | DOE (634 MW BESS), CBK Power (Kalayaan 685 MW); energy durations are stated assumptions because the sources publish MW, not MWh | Sourced constants |
| Build pipeline (LT Plan) | DOE committed and indicative project lists, As of 31 December 2025 (Internet Archive captures); every fuel section reconciles to the DOE's printed subtotal and every grid to the DOE's LVM summary | Per DOE edition |
| Transmission candidates | NGCP TDP 2025-2050 (March 2025 + September 2025 revision); MW only where the TDP states transfer capacity | Per TDP edition |
| Scheduled outages (PASA) | IEMOP outage schedules used in RTD, sized against the DOE fleet through a hand-verified alias table; unmatched codes carry no MW | Daily cron |
| Emission factors | IPCC 2006 fuel defaults at the EMB's published Philippine heat efficiencies; EMB diesel figure; DOE grid factor as cross-check | Sourced constants |
| Supply-mix history | Meralco advisories April to June 2026 (WESM 6/7/10%), each month cross-checked in an independent news report | Monthly advisory |

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
             lpText.ts (canonical LP text, byte-mirror of pipeline/lp_model.py)
             solver.ts (the HiGHS wasm build, loaded once)
             engine.ts (snapshot clear on the single-hour LP), engine.test.ts +
             model.test.ts
             chrono.ts (day replay as one 24-hour LP), chrono.test.ts (parity
             vs pipeline/lp_dispatch.py goldens + LP text hashes)
             ChronoView.tsx (Chronology), BackcastView.tsx (model vs the tape)
             insights.ts (binding classification, percentile bands, horizon
             math, CO2), insights.test.ts
             SweepView.tsx (load sweep), DistributionView.tsx (window band)
             LTPlanView.tsx (DOE build pipeline), PasaView.tsx (outage-day
             adequacy), EmissionsView.tsx
             runs.ts + RunsView.tsx (frozen runs, compare, CSV, share links)
             report.ts (self-contained HTML run report), report.test.ts
             model-views.tsx (properties grid + solved views), views.tsx,
             charts.tsx (SVG), Scenario.tsx, Bill.tsx, MarketPower.tsx
  styles/    tokens.css (design tokens, light + dark), base.css, app.css
```

The Python counterparts live in `../pipeline/`: `lp_model.py` (the canonical
LP text) and `lp_dispatch.py` (the highspy reference solve + backcast bake),
`chrono.py` (assembly helpers + the retired clear kept as a cross-oracle),
`profiles.py` (observed-day bake incl. hydro water budgets), `fuelmix.py`
(DIPCEF daily deriver + hydro classification), `fleet_doe.py` (DOE list
parser with the reconciliation gate). The pipeline needs `highspy` (pip); the studio's wasm
solver installs with npm.

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

The three captioned workflow GIFs under "Three workflows to try" come from a
second script that drives one clip per workflow. Every number a caption states
is read live from the running studio, so a caption cannot drift from the model:

```bash
python3 scripts/record-workflows.py all   # wf1|wf2|wf3 webms to /tmp/studio-rec
names="wf1:workflow-1-datacenter wf2:workflow-2-contingency wf3:workflow-3-malampaya"
for pair in $names; do
  k=${pair%%:*}; out=${pair##*:}
  ffmpeg -y -ss 2 -i /tmp/studio-rec/$k.webm \
    -vf "fps=9,scale=1180:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
  ffmpeg -y -ss 2 -i /tmp/studio-rec/$k.webm -i /tmp/pal.png -lavfi \
    "fps=9,scale=1180:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" /tmp/raw.gif
  gifsicle -O3 --lossy=60 /tmp/raw.gif -o docs/$out.gif
done
```

## Limitations to keep in view

- Zonal, not nodal; three regions, two corridors. Intra-region congestion does
  not exist in this model.
- The snapshot solve prices one reference hour; Chronology prices 24 (or 168),
  with the storage state of charge as the only inter-temporal coupling.
- Editing a unit shifts its fuel's available capacity by the delta: a labeled
  approximation, not unit commitment (the LP dispatches blocks, not units).
- Storage optimisation resets daily: no inter-day carryover, and cycling that
  does not pay within the day does not happen, honestly reported as idle.
- Unserved load prices at the dearest block (the documented no-VoLL stance),
  so the model still does not price the scarcity tail.
- Observed-day replay is not a forecast. Forward cases (the LNG switch, dry
  hydrology, added load) are what-ifs on observed days.
- The backcast table above is the accuracy statement. If your use case needs
  the scarcity tail priced correctly, this model does not do that, and says so.

## License and attribution

Code MIT; baked data products CC-BY-4.0. Attribution when redistributing:
Power Dispatch Studio (2026), IEMOP public market data archive, DOE List of Existing
Power Plants. The interface is an original work; PLEXOS is a trademark of
Energy Exemplar, used here only to describe the homage.
