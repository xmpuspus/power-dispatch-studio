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

- 2026-07-31, ruff rule set: the CI gate now names four rule groups
  (E4, E7, E9, F), which is what it enforced the last time it was green. Ruff's
  wider 0.16 defaults report 116 more findings under E4,E7,E9,F,I,B,DTZ,UP:
  32 unsorted imports, 38 naive-datetime calls (DTZ, which CLAUDE.md calls a
  real gotcha), 27 zip-without-strict, 10 unused loop variables. None is a bug
  today. The three B023 late-binding hits are false positives, because all
  three closures are called inside the iteration that builds them
  (pipeline/coupled_dispatch.py:163,167 and pipeline/merit_order.py:230).
  Widening the select and fixing the 116 is a worthwhile pass over
  pipeline/ and scripts/, and it is not a bug fix.

