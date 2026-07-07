# A real solver for the studio: scope

Written 2026-07-07, after the planning-layers pass. The question on the table:
replace the hand-written block clear and the storage heuristic with a linear
program solved by HiGHS, in both engines. This is the one carry-over that
changes what the tool is rather than adding a view, so it gets a scope document
and its own pass instead of riding along.

## What it buys, by surface

- **Storage**: true inter-temporal optimisation over the day (state of charge
  coupling hours together), replacing the labeled charge-cheap, discharge-dear
  heuristic. The heuristic is the weakest labeled approximation in the model
  today: it picks hours from a first pass and cannot see that its own charging
  moves the price.
- **Reserves**: energy and reserves co-optimised as constraints (each grid's
  reserve requirement held by capacity that is then not available for energy),
  replacing the demand-plus-requirement toggle, which is a stated
  approximation of the co-optimised market.
- **Duals**: exact shadow prices. The what-set-the-price strip and the
  corridor rent become solver duals instead of derived reads, and the load
  sweep can state the marginal price of each binding constraint.
- **A base for later fidelity**, which stays out of scope until the data
  exists: ramp rates and minimum up and down times need per-unit data the
  Philippine sources do not publish.

## The formulation (v1 is an LP, not a MILP)

One linear program per day, 24 coupled hours. Variables: dispatch per merit
block per grid per hour, corridor flows bounded by the operating limits,
storage charge, discharge, and state of charge, and unserved load priced at a
value-of-lost-load penalty. Objective: minimise cost. The coal commit tranche
stays exactly as calibrated today (its own block at the commit offer), so the
calibration story carries over unchanged. Rough size: about 1,000 variables by
500 constraints per day. HiGHS solves that in milliseconds, native or wasm;
the window band's 66 day-solves stay interactive.

## Costs

- **Dependencies**: the studio takes `highs` 1.14.2 from npm (HiGHS compiled
  to WebAssembly, about 3.2 MB unpacked, maintained, May 2026 release); the
  pipeline takes `highspy` 1.15.1 (the HiGHS project's own Python wrappers).
  These are the first runtime dependencies the engines have ever taken; today
  both sides are dependency-free hand transcriptions of each other.
- **Bundle**: roughly 2.5 to 3 MB of wasm on studio load, loaded async when
  the studio opens and cached after. For scale, the map chunk is 1 MB today.
- **Honesty statements**: every line that says "no inter-temporal
  optimisation", "a labeled heuristic, not an optimisation", or "no MILP"
  gets rewritten: the studio README scope table, the methodology page, view
  copy, and the run report's provenance block.
- **The backcast is re-run and re-stated.** The numbers will change; whatever
  they become is the new accuracy statement, reported, not tuned. Saved runs
  from the heuristic engine flag stale through the existing ENGINE_VERSION
  mechanism, by design.

## The one hard risk: parity across two builds of the same solver

Golden parity today pins two hand transcriptions to P0.02/kWh and 1 MW. With
HiGHS, the Python reference and the browser run different builds (native
versus WebAssembly) of the same solver. Objective values agree to solver
tolerance, but this model is one big flat cost plateau, and flat plateaus mean
degenerate optima: tied solutions where different builds can legitimately
return different flows and different duals at the same total cost. Plan, in
order:

1. Tie-break block costs with tiny deterministic perturbations so the optimum
   is unique. Labeled as an epsilon in the methodology, like every other
   assumption.
2. Pin parity on objective value, flows, and prices, with prices taken from a
   re-solve at demand plus 1 MW (a finite-difference marginal price) wherever
   raw duals stay degenerate.
3. Keep the current coordinate-descent clear in the test suite as a second
   oracle: the LP's cost may never exceed the heuristic clear's cost, and the
   two must agree on non-degenerate cases.

If exact goldens cannot be pinned, the fallback is property pins (bounds,
monotonicity, energy conservation, corridor limits respected). Weaker, but
honest, and stated as such.

## Order of work (its own pass, on the order of one working session)

- **Phase A, the decision gate**: `pipeline/lp_dispatch.py` on highspy.
  Formulation, property tests, the old engine as cross-check oracle. Re-run
  the full backcast on the LP engine and publish the old-versus-new accuracy
  table BEFORE any frontend work. If the LP materially degrades calibration,
  stop there and report; nothing user-facing has changed yet.
- **Phase B**: golden fixtures from the Python side, the wasm engine in the
  studio behind an async loader, the parity suite, ENGINE_VERSION bump.
- **Phase C**: views. The state-of-charge chart reads the LP schedule, the
  reserve toggle becomes real constraints, the binding strip and sweep read
  duals or the marginal re-solve. Copy and docs rewrite; demo re-record.
- **Phase D**: the usual gates (whole suites, screenshots read back, live
  verify on the alias), then ship.

## What stays out, still

MILP unit commitment, ramps, minimum up and down times (no public per-unit
data; modeling them would be invented fidelity), nodal networks, and
expansion optimisation. The LP changes how the model solves, not what it
claims to know.

## Recommendation

Full swap, not a solver toggle: keeping both engines user-selectable doubles
the parity surface forever and splits the backcast into two accuracy
statements. Gate the whole pass on Phase A's backcast table, so the first
deliverable is evidence about whether the solver earns its 3 MB.
