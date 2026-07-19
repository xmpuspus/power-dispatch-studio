# Latent bugs (found during QA, not bundled into in-flight work)

- 2026-07-19, web/methodology.html: the datasets table renders at a 449px
  natural width and overflows the 375px mobile viewport by 92px (horizontal
  scroll on phones). Pre-existing: the same 92px overflow measures on the
  HEAD version before the price-model-levers entry was added. Fix candidates:
  `overflow-x: auto` on a table wrapper, or let the table's cells wrap.
  Desktop (1920px) is clean.
