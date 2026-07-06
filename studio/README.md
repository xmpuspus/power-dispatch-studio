# PLEXOS Studio (gridbill-ph SPA)

A single-page app that presents the gridbill-ph dispatch model as an open, modern
power-system modeling studio. It reads the same baked artifacts the map ships
(`../web/data/*.json`, produced by `../pipeline`) and renders them as a network map
plus a full "PLEXOS Studio" workspace with a model tree, result views, charts, and an
interactive scenario builder that re-solves the dispatch in the browser as you drag.

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
Regions, and a live 4,000-draw Monte Carlo Reliability that trips the named units at
their edited forced-outage rate) and carry a LIVE badge. Compare scenarios solves every
scenario and tables the headline metrics with the changes highlighted. Price duration
and Marginal units read the calibrated base case behind a labeled banner (they need the
full observed window); the richer 20,000-draw pipeline distribution and the storage
buy-back sit below the live reliability as base-case reference. The Analysis group keeps
the WESM Reserve Market prices, the contract-cover Bill impact, and the Market power
lens. A slider-driven Quick scenario stays under System as a fast what-if.

Honest block-dispatch stance, no fabricated per-plant fleet: the Fuels class sets the
aggregate merit-order stack; the Generators class names the 11 sourced units and drives
N-1 (editing a unit shifts its fuel's available capacity by the change, a labeled
approximation, not plant-level unit commitment).

## Walkthrough

![Screen recording of the app walking from the landing page into the PLEXOS Studio and through its result views.](docs/demo.gif)

Note: this GIF predates the interactive views (it walks the read-only result tabs). It
is re-recorded at the publish gate, where real recordings are the rule; the prose above
describes the current studio.

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
  `bill.json`, and `market_power.json`.
- Every added number is sourced (URL in the same commit) and labeled NOT PLEXOS.
  Reserve product-code mapping and the market-power HHI carry their own caveats in
  the baked notes.
- This app lives on a branch. The launch-ready site is the single-file `../web/index.html`.
