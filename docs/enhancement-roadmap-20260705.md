# gridbill-ph enhancement roadmap

2026-07-05. Combines the product audit (`docs/product-audit-20260705.md`) with the
launch research (`docs/research-launch-20260705.md`). Sequenced so the
goal-unblocking work and the two data-integrity fixes ship first, new layers second.
Most of Phase 0 and Phase 1 shipped in the same ultrawork session; this records what
shipped and what is next.

## Sequencing principle

The map is a share-first artifact timed to the Jul 8-12 print window (July Meralco
advisory and June IEMOP report). Two things gate a trustworthy launch: the numbers
must survive a fact-check (the league and price-regime findings) and the map must be
linkable, readable on a phone, and previewable in a LinkedIn card. Those ship first.
New data layers make the map broader but none matter if a headline number is
mislabeled or the post has no share image.

## Phase 0: integrity and launch mechanics (shipped this session)

1. **League ranked by days, RT and DAP counts separated.** The old "5-min rows"
   count was 82% hourly day-ahead re-runs. Ranking by days is re-run-proof; the two
   markets are now separate labeled columns.
2. **Price series split by regime.** The 24 pre-resumption administered days are
   labeled and never folded into a market-outcome mean. Every displayed mean says
   which regime it covers.
3. **Findings drawer.** Six computed cards, each flying the map to its evidence
   (mode plus center plus zoom), baked from the data so copy cannot drift.
4. **Deep-linkable URL state.** `?q=<mode>&finding=<id>` round-trips, so a reader
   can be linked straight to "the grid names its own choke point."
5. **Per-corridor receipts on hover.** The Leyte-Cebu line now carries its archive
   join (87 days, the matched named lines) instead of a static constant string.
6. **Archiver hardened.** Nonzero exit on any dataset failure, a `--check`
   staleness gate, partial-download cleanup, daily fetch keyed to newest-on-disk so
   an outage self-heals within the public window. Cron re-bakes and runs the gates.
7. **og.png tag, failure banner, mobile layout, meta freshness surfaced, CI, LICENSE.**

## Phase 1: tighten what is claimed (S-M each, next)

8. **Methodology copy pass.** Correct "peak demand" to "bid-in load," state the
   unweighted-daily-mean-of-load-weighted-5-min price definition, add the
   regime-split and league-ranking notes, and add the corridor-receipts method.
9. **Hot-swap the launch pegs when they drop (Jul 8-12).** The July Meralco advisory
   and the June IEMOP report land in the window. Bake the July overall rate, delta,
   generation charge, and WESM cost; the June system average, three regional prices,
   and margin MW. URLs to watch are in the research doc.
10. **Privacy-friendly analytics.** One script tag (GoatCounter or Plausible) so the
    launch is measurable. Without it there is no way to tell which layer landed.

## Phase 2: new layers (M each, ranked by openness x novelty x honesty-fit)

11. **PSM/AP incidence per interval from DIPCEF.** The research resolved why
    LMP_CONGESTION reads zero: 72% of intervals are re-priced under the price
    substitution methodology. The honest, displayable nodal quantity is not a
    "congestion premium" but the share of intervals under substitution or
    administered pricing, and the inter-island SMP separation. A small, novel layer
    that no other PH tool shows.
12. **Per-interval HVDC limit series.** Zero RTD HVDC limit rows landed in this
    window, so this waits for a window that has them; the schema is captured.
13. **Meralco generation-charge series.** Scrape the monthly advisories into a
    series so the bill panel is a trend, not a single month.
14. **Node-code to location join for nodal price geography.** The resource codes need
    a hand-built reference join, the way community reserve-market dashboards do it.

## Deferred for honesty, not difficulty

- **Nodal congestion-premium choropleth: still deferred.** LMP_CONGESTION is
  structurally zero in the settlement-final files (substitution methodology plus
  regional-SMP pricing), so a "congestion premium" layer would assert the opposite
  of what the data says. Resolved and documented; the archived layer stays archived.
- **A complete data-center inventory: still deferred.** Only publicly-sourced sites
  are pinned (14, city-precision). Cushman counts 24 operational, DataCenterMap 44;
  the gap is stated on the map, not filled with unsourced pins.

## Not usable (verified this session)

- The "Meralco 1,200 MW / 30 hyperscale applications" figure traces to a May 2024
  Power Philippines article, two years stale and spam-injected. The PCIJ Jan 2026
  Meralco 1,000 MW commitment is the anchor instead.

## The single highest-value move

Ship the current map (integrity fixes and launch mechanics done) the moment the
July Meralco and June IEMOP prints land Jul 8-12, with the pegs hot-swapped and the
share image previewed in the composer. That sequences a shipped-and-measured launch
against the news hook, ahead of the Phase 2 layers.
