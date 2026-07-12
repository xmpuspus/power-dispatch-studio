# Power Dispatch Studio visual system

One palette, three contexts. This is the rule the assets already mostly follow; writing it
down keeps new charts, cards, and UI coherent. Source of truth for the chart colors is
[scripts/vizstyle.py](../scripts/vizstyle.py); the studio mirrors it in
[studio/src/styles/tokens.css](../studio/src/styles/tokens.css); the map mirrors it in the
CSS variables at the top of [web/index.html](../web/index.html).

## Core palette

| Role | Hex | Where |
|------|-----|-------|
| Navy (ink, titles, primary line) | `#12335c` | charts; map `--ink #10212b`; studio `--text` |
| Steel (secondary series, Luzon) | `#4e79a7` | charts; studio `--fuel-gas`, map gas |
| Coral (the thing to look at, Visayas) | `#e2664b` | charts; social hero number; map `--sual/oil` family |
| Gold (third series, sparingly) | `#e8b04b` | charts; map `--uc` under-construction |
| Green (supply, operational, Mindanao) | `#1a7f48` | charts; map `--op`; studio `--positive` |
| Mute (axis labels, captions, context) | `#7d8896` | charts; map `--muted`; studio `--text-muted` |
| Grid / fill (faint) | `#e6eaee` / `#eef1f4` | gridlines, missing-data bands |

The three grids read the same everywhere: **Luzon steel, Visayas coral, Mindanao green**
(`vizstyle.REGION`). They are always direct-labeled at the line end, never legend-only.

## The three contexts (lanes)

**Lane A, in-product and explanatory charts.** Light Tufte on white: navy text, no top/right
spines, faint y-grid only, direct labels, a sourced grey caption. Applied by `vizstyle.apply()`
and `vizstyle.tufte(ax)`. Assets: `web/og.png`, the chart GIFs (`price-spread`, `sual-margin`,
`price-shape`, `supply-demand-day`, `small-multiples`), `bill-wedge`, and the map's inline
price spark and the studio's charts.

**Lane B, social and share cards.** Deep navy background `#0d2137`, coral hero number, a
green lifted to `#4ec27f` for contrast on the dark ground, white headline, muted-grey body.
Same palette as Lane A, inverted onto navy. Built by [scripts/stat_card.py](../scripts/stat_card.py),
which imports `vizstyle`. Assets: `docs/linkedin-card*.png` and the `studio-e2e` opening card.

**Lane C, the live UI.** The map is a light Carto Positron basemap with the palette on top;
the studio is a light/dark token system that remaps the same palette (`tokens.css`). The app
chrome differs from a chart or a card on purpose; the series colors do not.

Rule of thumb: pick the lane by where the asset lives (a chart in a page or app is Lane A, a
standalone share image is Lane B, a screen of the running product is Lane C). Never invent a
fourth palette; pull from the table above.

## Type

- Charts (Lane A/B): Helvetica, Arial, DejaVu Sans (matplotlib `vizstyle.apply`).
- Studio (Lane C): Fira Sans for UI, Fira Code for every figure (mono numerals).
- Map (Lane C): system sans (`-apple-system, Helvetica, Arial`).
- Numbers are tabular / mono wherever they line up in a column.

## Colorblind note

Visayas coral and Mindanao green are a warm/green pair that can be hard to separate for
red-green color vision deficiency. Every place they appear together is **direct-labeled**, so
color is never the only channel; that is the mitigation in use today. If a future pass wants a
label-independent safe triad, change Mindanao off green (to a violet or the existing gold) in
`vizstyle.REGION` once, then regenerate the chart family and mirror the value in `tokens.css`
and the map variables. Not done here because it cascades through every baked chart and the
oracle-referenced `og.png` for a gain the direct labels already largely cover.
