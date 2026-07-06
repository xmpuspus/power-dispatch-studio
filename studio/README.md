# PLEXOS Studio (gridbill-ph SPA)

A single-page app that presents the gridbill-ph dispatch model as an open, modern
power-system modeling studio. It reads the same baked artifacts the map ships
(`../web/data/*.json`, produced by `../pipeline`) and renders them as a network map
plus a full "PLEXOS Studio" workspace: model tree, tabbed result views, and charts.

This is an independent, open homage. Not affiliated with Energy Exemplar. Not PLEXOS.

## Stack

- Vite + React 19 + TypeScript (strict)
- MapLibre GL for the network map (lazy-loaded)
- Fira Sans / Fira Code, self-hosted via `@fontsource` (offline-capable)
- oxlint + Prettier
- No backend: the pipeline is the source of truth; data is copied into `public/data`
  by `scripts/copy-data.mjs` on every `dev`/`build` (gitignored, never duplicated in git)

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

## Notes

- Every figure uses tabular mono numerals so data columns never shift.
- Light and dark themes are token remaps, toggled from the header or the studio bar.
- The Studio reads coupling, unit-commitment, reliability (Monte Carlo), storage,
  price-duration, and marginal-frequency blocks from `dispatch.json`.
- This app lives on a branch. The launch-ready site is the single-file `../web/index.html`.
