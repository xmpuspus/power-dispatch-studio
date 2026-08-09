# Known defects not yet fixed

Found during QA, left in place on purpose. Each entry says what is wrong, how it
was measured, and what fixing it costs.

## The live shortfall chance prints two decimals from a 4,000-draw simulation

`Shell.tsx` (the run dock) and `model-views.tsx` (the live reliability card)
both render the live loss-of-load probability as `pct(x / 100, 2)`, so Luzon
reads `1.40%`. That number comes from `MC_DRAWS = 4000` in `model.ts`. At a rate
of 1.4%, 4,000 draws carry a standard error of 0.19 percentage points, so the
true value sits near 1.4 plus or minus 0.4. The second decimal is an artifact of
the seed, not a measurement.

The simulation is seeded (`MC_SEED = 42`) and a test asserts the result repeats.
So the digit is stable across renders, which makes the false precision look
trustworthy.

Found 2026-08-04. Measured from `MC_DRAWS` in `studio/src/studio/model.ts` and
the render call in `studio/src/shell/Shell.tsx:474`.

Two ways to fix it, and both change what is on screen:

- Print one decimal (`1.4%`). One line in each of the two files.
- Raise the draws to 20,000, matching the baked base case. This costs about
  5 times the current simulation time, which measures 6.25 ms for a whole
  `solveModel` call, so the cost is small. It still changes the printed digits.

The run dock appears in every recorded studio demo, so either fix makes 6 GIFs
stale. That is why this waits for a pass that re-records them.

## The sweep chart draws a flat price line on top of the axis, where it reads as clipped

`HourLines` in `charts.tsx` anchors its y-axis at zero and scales to the largest
value, so a flat Luzon sweep at P6.00 renders as a line sitting exactly on the
top gridline. Nothing is cut off, but the eye reads it as a series running off
the top of the chart.

The band chart next door now pads a narrow range and centres it
(`bandDomain` in `insights.ts`). `HourLines` needs the opposite treatment,
because a price axis that starts anywhere but zero misleads in the other
direction. The likely fix is headroom above the maximum, not a moved floor.

Found 2026-08-04 in a screenshot of the load-sweep card at the default
+1,500 MW range. The text dump could not show it.
