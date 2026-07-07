# PLEXOS Studio (gridbill-ph SPA)

A single-page app that presents the gridbill-ph dispatch model as an open, modern
power-system modeling studio. It reads the same baked artifacts the map ships
(`../web/data/*.json`, produced by `../pipeline`) and renders them as a network map
plus a full "PLEXOS Studio" workspace with a model tree, result views, charts, an
interactive scenario builder that re-solves the dispatch in the browser as you drag,
and an hour-by-hour chronology that replays the archive's observed days on the model
you edited.

This is an independent, open homage. Not affiliated with Energy Exemplar. Not PLEXOS.

## What it does

The studio follows the PLEXOS desktop shape (build a model, Run it, browse the
Solution). A title bar and an Office-style ribbon (Home / Model / Solution tabs with
grouped commands) sit above an Explorer with a System tree (the object classes) and a
Simulation tree (the phases, plus the Solution and Analysis views). The Data pane has
working Objects, Memberships, and Properties tabs; Memberships shows the object
relations (a Generator to its Region and Fuel, a Region to its member units).

Authoring is the editable Properties grid. Pick a class (Generators, Fuels, Interfaces,
Regions) and type into a cell: a generator's max capacity, a fuel's price or available
MW, an interface flow limit, a region's load. Edits are tagged to the active Scenario
(shown in accent, with an x to revert to the base value). Press Run and the model
re-solves; the status flips from Unsolved to Solved. The solve is a typed transcription
of the pipeline's economic dispatch (`../pipeline/fleet_ph.py` +
`../pipeline/coupled_dispatch.py`) in `src/studio/engine.ts`, driven by the object model
in `src/studio/model.ts`. It runs in the browser in under a second, so the Run gate is
authentic without the wait. The pipeline stays the source of truth: `dispatch.json`
carries golden input/output pairs from the real Python solve that the tests assert the
browser engine and the model reproduce.

The Solution views recompute from the solved model (Merit order, Coupled flows, N-1,
Regions, and a live 4,000-draw Monte Carlo Reliability that trips the fleet's units at
their edited forced-outage rate) and carry a LIVE badge. Chronology replays an observed
day (or the week ending on it) hour by hour on the edited model: hourly prices with the
observed LWAP overlay, dispatch by fuel, the storage state of charge, and a duration
curve computed from the run, with a reserve co-clear toggle that prices each hour at
demand plus the scheduled reserve requirement. Compare scenarios solves every scenario
and tables the headline metrics with the changes highlighted; Saved runs freezes
chronological solves (scenario snapshot, window, engine version, hourly results) for
side-by-side deltas, CSV export, and restore, and a scenario plus its window also
encodes into the URL hash, so a link is the model. Price duration and Marginal units
read the calibrated base case behind a labeled banner (they need the full observed
window); the richer 20,000-draw pipeline distribution and the storage buy-back sit
below the live reliability as base-case reference. The Analysis group opens with the
Backcast (every full-coverage market day replayed with the base model against the
observed hourly LWAP, MAE/bias/correlation stated, nothing tuned) and keeps the WESM
Reserve Market prices, the contract-cover Bill impact, and the Market power lens. A
slider-driven Quick scenario stays under System as a fast what-if.

Honest block-dispatch stance, nothing per-plant fabricated: the Fuels class sets the
aggregate merit-order stack; the Generators class carries the DOE List of Existing
Power Plants at unit level (2025 editions, parsed and reconciled to the DOE's own
subtotals in `fleet.json`; DOE dependable capacity is the editable value) and drives
N-1 (editing a unit shifts its fuel's available capacity by the change, a labeled
approximation, not plant-level unit commitment). The Storage class cycles only in
Chronology runs, on a labeled heuristic; energy durations are stated assumptions.

## Walkthrough

![Screen recording of the app walking from the landing page into the PLEXOS Studio, editing a generator in the Properties grid, running the model, and browsing the solved views.](docs/demo.gif)

The walkthrough goes end to end: open the studio, edit Sual down to 600 MW in the
Generators property grid, look at the Memberships tab, Run so the status flips to Solved,
browse the solved Merit order and Coupled flows, watch the live Monte Carlo Reliability
move with the edit, add a second scenario and Compare it against the base, open the
Market power lens, and flip to the dark theme before closing.

The recording is a real capture of the running app, made with Playwright (see Record the
demo). The basemap tiles stay blank in the headless recorder because it has no tile
network, so the walkthrough spends its time in the studio, where every view reads from
the local model. The landing map fills in on a normal browser.

## Stack

- Vite + React 19 + TypeScript (strict)
- MapLibre GL for the network map (lazy-loaded)
- Fira Sans / Fira Code, self-hosted via `@fontsource` (offline-capable)
- oxlint + Prettier + Vitest (engine parity and lever tests)
- No backend. The pipeline stays the source of truth, and data is copied into
  `public/data` by `scripts/copy-data.mjs` on every `dev`/`build` (gitignored, never
  duplicated in git)

## Develop

```bash
npm install
npm run dev        # copies baked data, starts Vite on :5173
```

## Verify

```bash
npm run typecheck  # tsc --noEmit (app + test configs)
npm run lint       # oxlint
npm run format:check
npm run test       # vitest: golden parity vs the Python engine + lever tests
npm run build      # production build to dist/
```

## Structure

```text
src/
  lib/       types.ts (baked-model types), data.ts (loader hooks + formatters)
  ui/        kit.tsx (Panel, StatTile, Chip, Segmented, ThemeToggle), DataGrid.tsx
  map/       MapView.tsx (MapLibre network view)
  studio/    Studio.tsx (PLEXOS shell: explorer, ribbon, Run gate)
             model.ts (editable objects + scenario overrides + solveModel)
             engine.ts (typed dispatch re-solve), engine.test.ts + model.test.ts
             chrono.ts (hour-by-hour replay engine), chrono.test.ts (parity vs
             pipeline/chrono.py golden fixtures)
             ChronoView.tsx (Chronology), BackcastView.tsx (model vs the tape)
             runs.ts + RunsView.tsx (frozen runs, compare, CSV, share links)
             model-views.tsx (editable Properties grid + solved Solution views)
             views.tsx (base-case reference views), charts.tsx (SVG)
             Scenario.tsx (Quick scenario sliders), Bill.tsx, MarketPower.tsx
  styles/    tokens.css (design tokens, light + dark), base.css, app.css
```

## Record the demo

With the dev server running on port 5173, capture the walkthrough and optimize it to a GIF.

```bash
python3 scripts/record-demo.py                 # Playwright video to /tmp/studio-rec
ffmpeg -y -i <video>.webm -vf \
  "fps=9,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -i <video>.webm -i /tmp/pal.png -lavfi \
  "fps=9,scale=1000:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  /tmp/raw.gif
gifsicle -O3 --lossy=60 /tmp/raw.gif -o docs/demo.gif
```

## Notes

- Every figure uses tabular mono numerals so data columns never shift.
- Light and dark themes are token remaps, toggled from the header or the studio bar.
- The Studio reads coupling, unit-commitment, reliability (Monte Carlo), storage,
  price-duration, marginal-frequency, and the scenario-engine inputs (per-fuel
  availability, golden parity cases) from `dispatch.json`, plus `reserve.json`,
  `bill.json`, `market_power.json`, `profiles.json` (observed hourly days, solar
  shape, storage fleet, reserve requirements, chronological golden fixtures, the
  backcast), and `fleet.json` (the DOE per-plant list).
- The demo GIF still shows the pre-chronology studio; it gets re-recorded at the
  publish gate (real recording only).
- Every added number is sourced (URL in the same commit) and labeled NOT PLEXOS.
  Reserve product-code mapping and the market-power HHI carry their own caveats in
  the baked notes.
- This app lives on a branch. The launch-ready site is the single-file `../web/index.html`.
