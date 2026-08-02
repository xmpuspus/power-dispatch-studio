# One palette keeps the map, studio, and published charts consistent

The project uses one color set across charts, share cards, the map, and the
studio. [scripts/vizstyle.py](../scripts/vizstyle.py) defines chart colors.
[studio/src/styles/tokens.css](../studio/src/styles/tokens.css) defines the
studio colors. [web/index.html](../web/index.html) defines the map colors.

## Luzon stays steel blue, Visayas coral, and Mindanao green

| Role | Hex | Where |
|------|-----|-------|
| Navy (ink, titles, primary line) | `#12335c` | Charts, map `--ink #10212b`, studio `--text` |
| Steel (secondary series, Luzon) | `#4e79a7` | Charts, studio `--fuel-gas`, map gas |
| Coral (main comparison, Visayas) | `#e2664b` | Charts, share-card figures, map `--sual/oil` family |
| Gold (third series, sparingly) | `#e8b04b` | Charts and map `--uc` under construction |
| Green (supply, operating, Mindanao) | `#1a7f48` | Charts, map `--op`, studio `--positive` |
| Mute (axis labels and captions) | `#7d8896` | Charts, map `--muted`, studio `--text-muted` |
| Grid / fill (faint) | `#e6eaee` / `#eef1f4` | gridlines, missing-data bands |

The three grids use the same colors everywhere. Luzon is steel blue, Visayas is
coral, and Mindanao is green. `vizstyle.REGION` defines the mapping. Line charts
label each grid at the line end.

## Charts, share cards, and the application use the palette differently

**Charts in the application and documentation.** Use a white background, navy
text, faint horizontal gridlines, direct labels, and a grey source line.
`vizstyle.apply()` and `vizstyle.tufte(ax)` set these rules.

**Social and share cards.** Use a deep navy background, coral main figure, white
title, and muted grey text. Green changes to `#4ec27f` for contrast.
[scripts/stat_card.py](../scripts/stat_card.py) imports the shared chart colors.

**The live application.** The map uses a light Carto Positron background. The
studio maps the same series colors into its light and dark themes.

Use the table above for every new chart, share image, and application screen.

## Typefaces distinguish interface text from figures

- Charts and share cards use Helvetica, Arial, or DejaVu Sans.
- The studio uses Fira Sans for text and Fira Code for figures.
- The map uses the system sans-serif font.
- Numbers are tabular / mono wherever they line up in a column.

## Direct labels keep the grid colors readable without color alone

Visayas coral and Mindanao green can be hard to separate for some readers. Every
chart labels the grid directly, so color never carries the name alone. Change
`vizstyle.REGION`, `tokens.css`, and the map variables together if this mapping
changes.
