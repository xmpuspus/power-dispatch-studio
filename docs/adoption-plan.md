# Nine changes open this project to analysts who lost a licensed tool

An analyst who used a licensed production-cost tool asks two kinds of question.
The first kind is about the Philippine market. This project answers it today.
The second kind is about the analyst's own plants and contracts. The engine
refuses it, because the linear program holds fuel blocks per island grid and no
named units.

This file lists every edit each of the nine changes needs. It names the files,
the tests, the gates, and an effort estimate. It does not write code.

Effort is an estimate in days of focused work. It is not measured.

## The reader needs six items and the modeler needs three

| Group | Who | Blocked by | Items |
| --- | --- | --- | --- |
| Reader | DOE and ERC staff, students, NGOs, journalists, buyers | discovery only | I1 to I6 |
| Modeler | retail suppliers, developers, diligence teams | the engine | I7 to I9 |

## Every item clears the same seven gates

| Gate | Command or file | What it stops |
| --- | --- | --- |
| Data pins | `python3 tests/test_data.py` | a generated number moves with no source change |
| LP parity | `python3 tests/test_lp_parity.py` | the Python engine loses determinism or physics |
| Engine sync | `python3 tests/test_engine_sync.py` | the pip package drifts from `pipeline/` |
| View table | `python3 tests/test_readme_views.py` | the README view list drifts from `nav.ts` |
| Prose gate | `python3 tests/qa_gate.py` | banned framing, em dash, AI jargon in visible text |
| Claims oracle | `python3 scripts/verify_claims.py` | a prose number drifts from the data build |
| Browser checks | `zsh tests/e2e.sh $BASE`, `npm test` in `studio/` | a served file or a solved number breaks |

Two lists hold the gates and both need the same edit. `make qa` names them in
the `Makefile`. The `gates` job names them again in `.github/workflows/ci.yml`.
A new test that lands in one list only runs in one place.

## I1. A front-door page states what the model solves and what it refuses

| File | Change |
| --- | --- |
| `web/for-analysts.html` | NEW. Capability table, term-to-view map, replay accuracy, four ways to run |
| `web/index.html` | link it beside the methodology link |
| `README.md` | one row in the start-here table, one short section |
| `src/power_dispatch/README.md` | one link line, because PyPI renders this file |
| `studio/src/shell/Shell.tsx` | one link in the shell, one command-palette entry |
| `scripts/verify_claims.py` | add the file to `WRITABLE`, add a `BLOCKS` marker for the accuracy table |
| `tests/e2e.sh` | one check that the page serves and carries the capability table |
| `PROJECT_NOTES.md` | one row in the main-files list |

The page maps the terms an institutional reader types onto the studio slug that
answers each one. Use category words: production cost model, economic dispatch,
unit commitment, capacity expansion, reserve co-optimization, loss of load
probability, capture price, price duration curve. Name no product.

`tests/qa_gate.py` already globs `web/*.html`, so the new page enters the prose
gate with no edit. The accuracy numbers roll with the archive window, so they
need a `BLOCKS` marker. Without it the nightly `--write` pass cannot keep the
page current and the page freezes behind the map.

Effort: 1 day.

## I2. The mixed-integer commitment test is measured and unpublished

`pipeline/uc_probe.py` builds the mixed-integer commitment variant, prices it,
and scores it against recorded prices. `data/derived/uc_probe.json` holds the
result and `tests/test_data.py` pins it at line 1351. No page shows it.

Commitment lowers the price correlation in all five measured pairs, and mean
absolute error barely moves. The probe writes its own verdict string: commitment
does not improve the price backcast, so the LP stays the default engine. Visayas
MCP has no paired hours.

| Pair | LP correlation | Commitment correlation | Delta |
| --- | --- | --- | --- |
| Luzon LWAP | 0.297 | 0.128 | -0.169 |
| Visayas LWAP | 0.442 | -0.003 | -0.445 |
| Mindanao LWAP | 0.109 | -0.011 | -0.120 |
| Luzon MCP | 0.437 | 0.137 | -0.300 |
| Mindanao MCP | 0.113 | -0.006 | -0.119 |

Do not compare these numbers with the historical replay correlations in the
README. The two use different windows and different pairings.

| File | Change |
| --- | --- |
| `web/methodology.html` | new section above the limits, with the measured delta, and a rewrite of the omission clause at line 198 |
| `studio/src/studio/UcProbeView.tsx` | NEW. Read `market_ops.json.uc_probe`, show the LP and commitment rows |
| `studio/src/shell/nav.ts` | new `AnalysisId`, new destination in the `trust` group |
| `studio/src/studio/Studio.tsx` | one route line in the `analysis` branch |
| `README.md` | one short section, then regenerate the view table |
| `src/power_dispatch/README.md` | one line in the limits list |
| `tests/test_readme_views.py` | line 34 asserts 39 destinations, so raise it to 40 |
| six more files | the view count, listed in the table below |

A new view moves the count from 39 to 40, and to 41 when I7 ships its view too.
That count appears 39 times across 11 files. One of them is a hard assertion and
it fails on the first new destination.

| File | Occurrences |
| --- | --- |
| `README.md` | 17, including the heading and its anchor at line 54 |
| `tests/test_readme_views.py` | 7, and line 34 asserts `len(dests) == 39` |
| `build/shoot_view_sheet.py` | 3, in the docstring |
| `studio/src/shell/nav.ts` | 2, lines 1 and 449 |
| `studio/src/shell/Shell.tsx` | 2, lines 6 and 320, one of them a search placeholder |
| `build/record_studio_shell.py` | 2, in the recorded captions |
| `build/gen_view_table.py` | 2, in the docstring |
| `studio/README.md` | 1, line 530 |
| `studio/src/studio/Studio.tsx` | 1, line 72 |
| `studio/src/styles/shell.css` | 1, line 6 |
| `build/shoot_readme.py` | 1, a DOM query on the literal string `39 views` |

Grep, fix each, grep again to zero. Regenerate the README table with
`python3 build/gen_view_table.py --write`. Watch the alt text in `README.md`,
because four lines count clips and links rather than views and they move too.
`build/shoot_readme.py` line 78 breaks silently, because a DOM query that finds
nothing returns no error.

The probe derives on demand rather than nightly, so `tests/test_data.py` stays the
right guard and the claims oracle needs no entry.

Effort: 1 day.

## I3. Three Python examples give the package a first hour

| File | Change |
| --- | --- |
| `examples/01_replay_a_day.py` | NEW. List days, replay one, print the hourly table |
| `examples/02_add_a_data_center.py` | NEW. Add 1,500 MW to Luzon, print the price delta |
| `examples/03_sweep_the_window.py` | NEW. Replay every bundled day, write a CSV |
| `examples/README.md` | NEW. What each script shows and what it costs to run |
| `src/power_dispatch/README.md` | link the three scripts |
| `README.md` | one row in the start-here table |
| `.github/workflows/ci.yml` | run the three scripts in the `gates` job |

Use plain scripts rather than notebooks. The package depends on `highspy` alone, and a
notebook dependency would break that. The CI step stops the examples from
rotting against an engine change.

Effort: half a day.

## I4. The bring-your-own-data path exists and no page names it

`src/power_dispatch/__init__.py` resolves the data directory from `--data-dir`,
then `POWER_DISPATCH_DATA`, then the bundled snapshot. `src/power_dispatch/cli.py`
carries the flag at line 120. Neither README documents it.

| File | Change |
| --- | --- |
| `docs/data-contract.md` | NEW. The keys `dispatch.json`, `profiles.json`, `meta.json` must carry |
| `src/power_dispatch/README.md` | new section: run it against your own data build |
| `src/power_dispatch/cli.py` | add the flag to the module docstring examples |
| `README.md` | one line under "Reproduce locally" |
| `tests/test_data_contract.py` | NEW. The bundled snapshot satisfies the documented contract |
| `PROJECT_NOTES.md` | one row for the contract document |

The contract document is the same one that I7 and I8 need, so write it once.
The new test belongs in both gate lists.

Effort: 1 day, and half of that is the contract.

## I5. The run report and the CSV exports ship today with no signpost

`studio/src/studio/report.ts` builds a self-contained HTML run report.
`studio/src/studio/RunsView.tsx` downloads it. Six views download CSV.
`pipeline/build_exports.py` writes three tidy CSVs to `web/data/exports/`.

| File | Change |
| --- | --- |
| `README.md` | new section naming the run report and the three CSVs |
| `web/for-analysts.html` | a take-it-away row, built in I1 |
| `web/index.html` | link `/data/exports/index.json` from the data section |
| `studio/src/shell/Shell.tsx` | a palette command that exports the current run |
| `tests/e2e.sh` | one check that the exports index serves and lists three files |

Effort: half a day.

## I6. A paper and a workshop put this in other people's citations

| File | Change |
| --- | --- |
| `paper/paper.md` | NEW. Short software paper, statement of need, the replay accuracy |
| `paper/paper.bib` | NEW. IEMOP, DOE, NREL ATB, HiGHS references |
| `CITATION.cff` | add the paper identifier once it exists |
| `docs/workshop/README.md` | NEW. A 90-minute lab with three tasks and three deep links |
| `README.md` | a cite-this line |

The three lab tasks reuse work that already runs: site a load, price the loss of
one unit, check the bill effect. Each task is one studio link plus one Python
snippet from I3.

Effort: 2 days for the paper draft, 1 day for the lab. Review time sits outside
that estimate.

## I7. A future year needs only a data build, and the engine stays as it is

`run_chronology_lp` reads a day from `profiles["days"]` and supply from
`dispatch["merit_order"][g]["fuel_avail_mw"]`. So a synthetic year is a
generated data directory that the existing `--data-dir` flag already accepts.
The four inputs sit in the repo now.

| Input | Where |
| --- | --- |
| Peak demand per grid per year to 2050 | `pipeline/pdp_demand.py`, gated to 2 MW against the plan total |
| Committed and indicative projects | `web/data/projects.json` |
| Generic new-build cost anchors | `pipeline/expansion.py` |
| Hourly demand and solar shapes | `web/data/profiles.json`, 118 recorded days |

| File | Change |
| --- | --- |
| `pipeline/future_year.py` | NEW. Scale shapes to the year peak, add builds, subtract retirements, write the three files |
| `data/derived/future/<year>/` | NEW output: `dispatch.json`, `profiles.json`, `meta.json` |
| `Makefile` | a `future` target |
| `studio/src/studio/FutureYearView.tsx` | NEW. Read a written year summary. Never solve 365 days in the browser |
| `studio/src/shell/nav.ts`, `Studio.tsx` | one destination, one route line |
| `web/methodology.html` | the method, every assumption with an owner and a date |
| `tests/test_future_year.py` | NEW. Contract keys, day count, peak reconciles to the DOE path |
| `scripts/verify_claims.py` | register any README number the year run produces |

The command needs no new code: `power-dispatch run --data-dir data/derived/future/2028 --date 2028-06-15`.

Three modeling decisions carry the work, and each one needs a labeled
assumption. How the 118 recorded shapes map onto 365 days. Which plants retire.
Whether fuel prices hold flat or follow a path.

State the horizon exactly, because this is the first thing a planner tests. A
year built this way is 365 separate 24-hour programs. `pipeline/lp_model.py`
gives each day a free terminal storage state, so the battery resets at every
midnight. The hydro budget in `profiles.json` is a per-day energy limit, so no
water carries from one month into the next. Seasonal hydro carry and multi-day
storage cycling stay outside this build. The 168-hour program in `WeekView` is
the only variant that carries storage across midnight, and it stops at a week.

A synthetic year is a scenario and never a forecast. The label rule in
`PROJECT_NOTES.md` applies to every figure the year produces.

Effort: 5 to 7 days. The modeling judgment costs more than the code.

## I8. The scenario file exists for the CLI and not for the studio

`power-dispatch run --scenario s.json` reads a scenario today. The studio shares
state as a URL hash through `encodeShare` in `studio/src/studio/runs.ts`. The two
formats differ, so a browser scenario cannot re-run in Python.

| File | Change |
| --- | --- |
| `src/power_dispatch/schema.py` | NEW. Versioned schema plus a validator with readable errors |
| `src/power_dispatch/cli.py` | a `validate` subcommand, and `run` validates first |
| `src/power_dispatch/__init__.py` | export the validator, and keep `OPT_KEYS` as the one key list |
| `studio/src/studio/scenarioFile.ts` | NEW. Map the studio `Overrides` to the schema and back |
| `studio/src/studio/Scenario.tsx` | download and load buttons beside the CSV import |
| `tests/fixtures/scenario_example.json` | NEW. One fixture both sides read |
| `tests/test_scenario_file.py` | NEW. Python round trip on the fixture |
| `studio/src/studio/scenarioFile.test.ts` | NEW. Browser round trip on the same fixture |
| `docs/scenario-schema.md` | NEW. The key table, generated from `OPT_KEYS` |

Version 1 carries the ten keys the engine honors today plus metadata. Added
units and contracts wait for I9, and the schema version says so.

Effort: 3 to 4 days.

## I9. Unit-level dispatch changes three engines and needs inputs nobody publishes

The LP text lives in `pipeline/lp_model.py`. `tools/sync_engine.py` copies it to
`src/power_dispatch/engine/lp_model.py`. `studio/src/studio/lpText.ts` builds the
same text in TypeScript. `dispatch.scenario_golden.lp_sha256` pins all three to
one hash. Any change goes into three places on the same commit.

| File | Change |
| --- | --- |
| `pipeline/dispatch.py` | emit `merit_order[g].units[]` beside `fuel_avail_mw` at line 937 |
| `pipeline/fleet_ph.py` | carry per-unit capacity, fuel, cost, minimum stable level |
| `pipeline/lp_model.py` | a `units=` branch, and the block path stays the same byte for byte without it |
| `src/power_dispatch/engine/lp_model.py` | regenerate with `make sync-engine` |
| `studio/src/studio/lpText.ts` | the same branch and the same test vectors |
| `pipeline/uc_probe.py` | extend to the unit level and re-measure |
| `tests/test_lp_parity.py` | new golden cases on the unit path |
| `studio/src/studio/engine.test.ts` | new hash and output pairs |
| `web/methodology.html`, both READMEs | the new limits and the measured delta |

Two facts decide the shape. No public Philippine source gives per-unit minimum
stable levels or heat rates, which `pipeline/uc_probe.py` already states. And a
24-hour mixed-integer program over the 355 plants in `web/data/fleet.json` will not stay interactive in
the browser. So the build that stays inside the evidence is a unit-level linear
program in both engines, with mixed-integer commitment in Python only.

Keep the block path the same byte for byte when `units` is absent. Every
existing golden hash then survives, and the new path carries its own pins.

Publish the replay delta before the flag changes any default. The project
already follows that rule for engine work.

Effort: 10 to 15 days.

## Order the work by what unblocks the next item

| Step | Items | Days | Why here |
| --- | --- | --- | --- |
| 1 | I2, I5 | 1.5 | Both publish work that already exists |
| 2 | I1, I4 | 2 | The front door needs the data contract from I4 |
| 3 | I3 | 0.5 | The examples fill the front door's Python row |
| 4 | I7 | 5 to 7 | The largest gain that needs no engine change |
| 5 | I8 | 3 to 4 | The schema now has a year to point at |
| 6 | I6 | 3 | The paper describes a finished surface |
| 7 | I9 | 10 to 15 | Last, and gated on its own replay delta |

Steps 1 to 3 total four days and need no new modeling.

## Four cross-cutting edits are easy to miss

- A new studio view moves the count of 39 in 39 places across eleven files.
- `PROJECT_NOTES.md` lists the main files, so every new page needs a row.
- A new test needs a line in `Makefile` and a line in `.github/workflows/ci.yml`.
- A new rolling number in prose needs a `REGISTRY` or `BLOCKS` entry.
- A studio UI change needs a demo re-record from `build/record_studio_shell.py`.
- A new colour token must clear `tests/test_contrast.py` and `tests/test_palette.py`.
- A new view needs a screenshot in the contact sheet from `build/shoot_view_sheet.py`.

## The modeler stays blocked until I9 lands, and no public source holds I9's inputs

The modeler still cannot load their own plant until I9 lands, and I9 is the one
item this plan cannot fully cost. It depends on unit data that no public
Philippine source publishes today. The generic labeled values the commitment
probe uses are a stated approximation rather than a fleet registry.

Steps 1 to 3 will feel like progress and they will not move that wall. Say so
before starting, because the group that needs I9 is the group with a budget.
