# Latent bugs (found during QA, not bundled into in-flight work)

- 2026-07-19, web/methodology.html: the datasets table renders at a 449px
  natural width and overflows the 375px mobile viewport by 92px (horizontal
  scroll on phones). Pre-existing: the same 92px overflow measures on the
  HEAD version before the price-model-levers entry was added. Fix candidates:
  `overflow-x: auto` on a table wrapper, or let the table's cells wrap.
  Desktop (1920px) is clean.

- 2026-07-31, studio table headers: `.grid thead th` and `.propgrid thead th`
  set `position: sticky; top: 0`, and the header never pins. Their wrapper sets
  `overflow-x: auto`, which makes it the sticky containing block, and it has no
  bounded height, so there is nothing for the header to stick against.
  Pre-existing: both rules read the same at 92c7e1c, before the ScrollBox pass.
  Measured on Generators at 1440x900, after a 600px scroll the header sits at
  y=-340 while its scroll box starts at y=123. It needs a design call, not a
  patch: either bound the wrapper's height and accept a nested vertical scroll
  (which rules/ux warns against), or drop the sticky rule because it does
  nothing today.

