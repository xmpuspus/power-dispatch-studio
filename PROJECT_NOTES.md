# Power Dispatch Studio project notes

Power Dispatch Studio asks three questions about the Philippine power market.

1. Can existing supply cover announced data-center demand?
2. Where do transmission limits restrict new demand?
3. How could those changes affect wholesale prices and a Meralco bill?

## Claims stay within the public evidence

- Do not say that data centers raised Wholesale Electricity Spot Market
  (WESM) prices. Current demand is small compared with the Luzon peak. The model
  tests announced future demand against recorded supply and transmission limits.
- Label every forecast with its owner and date. Show contested capacity figures
  as a sourced range or omit them.
- Treat a Sual outage as a scenario. It is not a prediction. The model removes
  the listed unit capacity and recalculates the chosen day.
- Cite the source of each published input. Label calculations and assumptions
  separately.
- OpenStreetMap gives the transmission routes. They are not official National
  Grid Corporation of the Philippines (NGCP) records. Site pins have city or
  campus precision unless a source gives an exact location.
- Describe companies and projects in neutral terms.

## Data flow

- `pipeline/archive_iemop.py` downloads public Independent Electricity Market
  Operator of the Philippines (IEMOP) files into `data/raw/`.
- `pipeline/build_data.py` calculates the JSON files in `web/data/`.
- `studio/scripts/copy-data.mjs` copies those files into the browser app.
- `tests/test_data.py` checks the published figures and source fields.
- `scripts/verify_claims.py` checks that documentation figures match current
  calculated data.

The archive includes 5-minute constraints, regional summaries, final prices,
inter-island transfer limits, outages, and selected per-node price files. See
`web/methodology.html` for each source and known limit.

## Main files

- `web/index.html` has the public map and market summary.
- `web/methodology.html` lists sources, calculations, assumptions, and limits.
- `web/for-analysts.html` states what the model solves and what it leaves out,
  for a reader who arrives from a licensed production-cost tool.
- `docs/data-contract.md` documents the two files the engine reads, so anyone can
  point it at their own system.
- `examples/` holds three Python scripts that run on the bundled snapshot.
- `studio/src/` has the interactive dispatch model.
- `pipeline/` has archive readers and calculations.
- `src/power_dispatch/` has the installable Python package.
- `tests/` has data, model, and browser checks.

## Local commands

```bash
make archive    # download newly available public market files
make data       # recalculate web/data/ from the archive
make serve      # serve the map on port 8789
make qa         # run the data and wording checks
make e2e        # run browser checks against a running site
```

Run `make qa`, rebuild figures, and inspect the relevant pages and recordings
before publishing a change to a displayed figure.
