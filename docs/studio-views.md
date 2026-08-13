# Studio view catalog

Each row below links directly to one of the 26 Studio views. The views are
grouped into six analyst workspaces. Back to [the project front door](../README.md).


The browser interface is at
[/studio/](https://power-dispatch-studio.vercel.app/studio/). It includes
editable model inputs, saved scenario changes, chronological market replay,
scenario comparison, and replay accuracy against published prices.

The long-term view puts DOE committed and indicative projects on a year slider.
The adequacy view applies the operator's scheduled outages. Other views step
demand across a range, report hourly link limits and emissions, and export a
self-contained HTML run report.

Every planning layer computes from the archive or a sourced list, and no
optimizer chooses builds. The dispatch itself solves as a HiGHS linear program in
the browser. Storage optimises across the day's hours, and hydro stays
energy-limited to each day's recorded water where the archive carries the
operator's per-resource schedules. Prices come from the duals. The model's scope
and its accuracy statement live in [studio/README.md](../studio/README.md).

Replay accuracy opens on the published-offer calculation because it follows
recorded prices more closely. The cost calculation remains available for
comparison. Explain a day separates the cost result, the difference produced by
published offers, and equipment held at a limit. It exports the breakdown as
CSV. The scheduled build also writes archive CSV files to
[`web/data/exports/`](../web/data/exports/). Their columns are documented in
[`web/data/exports/index.json`](../web/data/exports/index.json).

### Replay a recorded market day

The clip below follows the first workflow in the project README.

- Choose a recorded day and island grid.
- Click one hour to read the recorded price, replay price, demand, and
  price-setting block.
- Switch between the cost model and the published offer book.
- Open the source panel and copy a link to the exact view.

![Recording: choose a date, grid, and hour; switch to the offer-book replay; open evidence; copy the exact view.](studio-shell.gif)

**Every view has a URL.** The interface writes `#v=<slug>` as you move, beside the
`#m=` scenario share, so
[`/studio/#v=backcast&g=visayas`](https://power-dispatch-studio.vercel.app/studio/#v=backcast&g=visayas)
opens Visayas replay accuracy. The catalog uses direct links instead of one
recording per view.

<details>
<summary><b>Open any of the 26 views directly</b></summary>

<!-- views table start -->

| Source group | View | What it answers |
|---|---|---|
| Market day | [Hourly market replay](https://power-dispatch-studio.vercel.app/studio/#v=chronology) | Every hour of one recorded day, three grids cleared together |
|  | [Explain a day](https://power-dispatch-studio.vercel.app/studio/#v=explain-a-day) | What set the price on a chosen day, hour by hour |
|  | [5-minute dispatch replay](https://power-dispatch-studio.vercel.app/studio/#v=five-minute-replay) | Published five-minute dispatch intervals compared with the replay |
|  | [Supply stack and marginal block](https://power-dispatch-studio.vercel.app/studio/#v=merit-order) | Which fuel blocks run and which block sets the modeled price |
|  | [Replay accuracy](https://power-dispatch-studio.vercel.app/studio/#v=backcast) | Recorded prices and flows compared with the cost and offer replays |
| Supply and risk | [Power-shortfall risk](https://power-dispatch-studio.vercel.app/studio/#v=reliability) | Chance that demand exceeds supply across repeated random-outage cases |
|  | [Supply after scheduled outages](https://power-dispatch-studio.vercel.app/studio/#v=adequacy) | Whether supply covers demand across the outage schedule |
|  | [Price as demand grows](https://power-dispatch-studio.vercel.app/studio/#v=load-sweep) | Price against demand, swept across the whole range |
|  | [Price range across recorded days](https://power-dispatch-studio.vercel.app/studio/#v=window-band) | The price band the model produces when it replays every recorded day |
| Grid and connection | [Site headroom check](https://power-dispatch-studio.vercel.app/studio/#v=siting) | Recorded and estimated site headroom, with unavailable line limits marked |
|  | [Power between island grids](https://power-dispatch-studio.vercel.app/studio/#v=coupled-flows) | What moves over the high-voltage direct-current links and when a link reaches its limit |
|  | [Recorded connection-point price differences](https://power-dispatch-studio.vercel.app/studio/#v=nodal-prices) | Observed price differences from each island grid reference price |
| Prices and exposure | [Contract position](https://power-dispatch-studio.vercel.app/studio/#v=contract-position) | What a scenario does to a book of contracts, in pesos |
|  | [Average price earned by each technology (capture price)](https://power-dispatch-studio.vercel.app/studio/#v=capture-prices) | What each technology earns compared with the market average |
|  | [Supplier concentration](https://power-dispatch-studio.vercel.app/studio/#v=market-power) | Published national capacity shares and concentration measures |
|  | [Reserve market](https://power-dispatch-studio.vercel.app/studio/#v=reserve-market) | Published reserve prices and the offer replay against final results |
|  | [Emissions](https://power-dispatch-studio.vercel.app/studio/#v=emissions) | Solved tonnes per hour plus the carbon-price effect |
|  | [Generator portfolio value](https://power-dispatch-studio.vercel.app/studio/#v=portfolio) | Value a declared fuel-share position against a saved run |
| Planning and scenarios | [PDP demand-path price sensitivity](https://power-dispatch-studio.vercel.app/studio/#v=forward-prices) | Recorded days re-priced under the published demand path and stated ranges |
|  | [Annual demand and supply outlook](https://power-dispatch-studio.vercel.app/studio/#v=long-term) | Published demand growth and project additions, with assumptions and limits |
|  | [Inter-day storage test](https://power-dispatch-studio.vercel.app/studio/#v=native-week) | A 168-hour storage case with energy carried across midnight |
|  | [Scenario builder](https://power-dispatch-studio.vercel.app/studio/#v=quick-scenario) | Change load, fuel cost, fuel availability, or transfer capacity |
|  | [Compare scenarios](https://power-dispatch-studio.vercel.app/studio/#v=compare) | Two scenarios side by side, property by property |
|  | [Saved runs](https://power-dispatch-studio.vercel.app/studio/#v=saved-runs) | Runs kept in this browser, ready to restore |
| Model and data | [Transmission-loss check](https://power-dispatch-studio.vercel.app/studio/#v=loss-validation) | Whether estimated transmission losses reproduce recorded price differences between connection points |
|  | [Assumptions and model inputs](https://power-dispatch-studio.vercel.app/studio/#v=model-inputs) | Sources, dates, and editable plant, fuel, grid, link, and storage inputs |

<!-- views table end -->

</details>

The
[scenario walkthrough](findings.md#save-compare-and-export-a-scenario-in-the-browser)
shows how to save the base run, run a changed case, save it, compare both, and
export the results.
[`build/record_analyst_walkthrough.py`](../build/record_analyst_walkthrough.py)
rebuilds it from the running app. Four shorter recordings cover specific tasks.
[Explain a day](../studio/docs/view-explain.gif),
[the DICT 1.5 GW data-center build](../studio/docs/workflow-1-datacenter.gif),
[tripping both 647 MW Sual units](../studio/docs/workflow-2-contingency.gif), and
[repricing Malampaya gas to imported LNG](../studio/docs/workflow-3-malampaya.gif).
[studio/README.md](../studio/README.md) carries one recorded clip per analysis view,
14 in all.

### Export formats

The browser exports saved runs in the formats below.

| Exit | Where | What you get |
|---|---|---|
| Run report | [Saved runs](https://power-dispatch-studio.vercel.app/studio/#v=saved-runs) | Self-contained HTML with inputs, sources, and the hourly result |
| Hourly CSV | The same view, plus six analysis views | One row per hour with price, demand, shortfall, flows, and storage |
| Archive CSVs | [/data/exports/](https://power-dispatch-studio.vercel.app/data/exports/index.json) | `market_by_day.csv`, `congestion_league.csv`, `backcast_by_grid.csv`, rebuilt nightly |
| Scenario file | Scenario builder, "Take this scenario to Python" | The run settings as JSON, which the command line reads back |

The HTML report is self-contained and does not depend on browser storage. The
archive CSVs carry a CC-BY-4.0 license. Their `index.json` documents each column.

### Run a browser scenario from the command line

The browser and command line both read the `pds-scenario/1` schema.

```bash
power-dispatch validate myscenario.json   # names every problem, one per line
power-dispatch run --scenario myscenario.json -o out.csv
```

The validator reports each problem in a broken file. It suggests a valid setting
for an unknown name, finds a misspelled grid, and finds text where a number is
needed. [`docs/scenario-schema.md`](scenario-schema.md) lists the supported keys
and browser round-trip rules. The Python and browser tests both read
`tests/fixtures/scenario_example.json`.

**This page downloads 1.5 MB of media across 1 file.** Longer recordings are
links. The catalog uses 26 direct links.

`python3 tests/test_readme_views.py` re-measures that total against the files on
disk and fails when the stated number drifts.

**Long recordings have MP4 versions.** Short chart and analysis previews stay
GIF-only. The list below links to each longer browser recording.

- [The analyst walkthrough](analyst-walkthrough.mp4), and its [GIF](analyst-walkthrough.gif)
- [The map and studio](reel.mp4), and its [GIF](reel.gif)
- [The map hero](hero.mp4) and [the studio shell](studio-shell.mp4)
- [The nodal walkthrough](nodal-walkthrough.mp4), and its [gif](nodal-walkthrough.gif)
- [Siting a load at Pax Silica](siting-walkthrough.mp4), and its [gif](siting-walkthrough.gif)
- [The Pax Silica montage](pax-silica-scale.mp4), and its [gif](pax-silica-scale.gif)

Three files stay in `docs/` on purpose and appear nowhere above.
`scripts/og_card.py` writes `docs/hero.png` from the calculated data, beside the social
preview card. `docs/pax-silica-social.gif` and `docs/pax-silica-social.mp4` are
the square crop for posting.
