# PLEXOS Studio (gridbill-ph SPA)

A single-page app that presents the gridbill-ph dispatch model as an open, modern
power-system modeling studio. It reads the same baked artifacts the map ships
(`../web/data/*.json`, produced by `../pipeline`) and renders them as a network map
plus a full "PLEXOS Studio" workspace with a model tree, tabbed result views, and charts.

This is an independent, open homage. Not affiliated with Energy Exemplar. Not PLEXOS.

## Walkthrough

![Screen recording of the app walking from the landing page into the PLEXOS Studio and through its result views.](docs/demo.gif)

The landing page opens with the headline question and three live model figures. The
Open PLEXOS Studio button drops into the coupled-flows view of the three grids and
their HVDC links. From there the flow steps through the price-duration curve, switches
the grid to Visayas, opens the reliability view with the Monte Carlo loss-of-load
numbers, opens the merit-order stack, and flips to the dark theme before closing.

This is a real capture of the running app, recorded with Playwright (see Record the
demo). The
basemap tiles stay blank in the headless recorder because it has no tile network, so the
walkthrough spends its time in the studio, where every view reads from the local model.
The landing map fills in on a normal browser.

## Stack

- Vite + React 19 + TypeScript (strict)
- MapLibre GL for the network map (lazy-loaded)
- Fira Sans / Fira Code, self-hosted via `@fontsource` (offline-capable)
- oxlint + Prettier
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
npm run typecheck  # tsc --noEmit
npm run lint       # oxlint
npm run format:check
npm run build      # production build to dist/
```

## Structure

```text
src/
  lib/       types.ts (dispatch model types), data.ts (loader hooks + formatters)
  ui/        kit.tsx (Panel, StatTile, Chip, Segmented, ThemeToggle), DataGrid.tsx
  map/       MapView.tsx (MapLibre network view)
  studio/    Studio.tsx (shell + model tree), views.tsx (per-tab), charts.tsx (SVG)
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
  price-duration, and marginal-frequency blocks from `dispatch.json`.
- This app lives on a branch. The launch-ready site is the single-file `../web/index.html`.
