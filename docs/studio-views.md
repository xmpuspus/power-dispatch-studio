# The studio is 42 views, and every one is a URL you can send

`studio/src/shell/nav.ts` declares all 42. Each row below is a deep link that
opens the studio on that view. Back to [the project front door](../README.md).


The full browser interface lives at
[/studio/](https://power-dispatch-studio.vercel.app/studio/). It takes the
same general form as a commercial production-cost tool. It has editable model
inputs, saved scenario changes, a Run button, results views, chronological replay
of archived market days, and a historical comparison against recorded prices.

The July 2026 update added planning functions. The long-term view places DOE
committed and indicative projects on a year slider. The adequacy view applies the
operator's scheduled outages. Other views step demand through the announced
range, repeat a scenario across all archived market days, report hourly binding
constraints and carbon dioxide, and export a self-contained HTML report.

Every planning layer computes from the archive or a sourced list, and no
optimizer chooses builds. The dispatch itself solves as a HiGHS linear program in
the browser. Storage optimises across the day's hours, and hydro stays
energy-limited to each day's recorded water where the archive carries the
operator's per-resource schedules. Prices come from the duals. The model's scope
and its accuracy statement live in [studio/README.md](../studio/README.md).

The Historical replay opens on the published-offer calculation by default because
it follows recorded prices more closely. The cost model is one click away for comparison. A companion
**Explain a day** view takes any past market day and breaks its evening peak into
the cost-model result, the offer premium implied by published bids
on top of it (the offer replay minus the cost model), and the named equipment the
operator's real-time dispatch held at a limit that day. It exports the breakdown
as CSV. The project exports separate CSV files for the congestion league,
both historical replay calculations per grid, and the day-by-day feed. The
scheduled build writes them to [`web/data/exports/`](../web/data/exports/), linked from the map's
Drivers panel and documented in
[`web/data/exports/index.json`](../web/data/exports/index.json).

### Search and question groups organize all 42 views

The navigation groups views by the question they answer. The clip below shows
three ways to move through the studio.

- **A command palette.** Cmd K, then type what you want to know. The ranker
  matches the label, the hint and a per-view alias list, so "price setter"
  finds Marginal units.
- **Question navigation.** The 42 views sit in 8 groups, and each group is a
  question. The eight are How today's market clears, Can supply cover demand,
  Where new demand can connect, Prices and bills, What new capacity is needed,
  Build and compare scenarios, Check the model against market records, and
  Review and edit model inputs.
- **A fixed run summary.** It holds the clearing price and the reserve margin for
  all three grids while you move around. Move a slider and it re-prices live,
  labelled a preview until you press Run.

![The studio shell in four parts. The command palette opens over the studio, and the query 'price setter' ranks Marginal units first. Pressing Enter opens that view and writes its link into the address bar. The question rail expands to show all 42 views in eight groups, and Loss of one major unit opens from it. A data-center slider then moves in the Quick scenario, and the run summary recalculates the Luzon clearing price from P6.00 to P12.00.](studio-shell.gif)

**Every view has a URL.** The interface writes `#v=<slug>` as you move, beside the
`#m=` scenario share, so
[`/studio/#v=backcast&g=visayas`](https://power-dispatch-studio.vercel.app/studio/#v=backcast&g=visayas)
opens the Visayas historical replay for whoever you send it to. This lets the
README link to all 42 views without embedding 42 clips. GitHub does not defer
GIF downloads, and 42 clips would total about 200 MB.

Here are all 42 in one frame, each tile a real screenshot of the running app.
Click it to open the sheet full size, because inline the tile names read and
the numbers inside them do not. `build/shoot_view_sheet.py` opens each view by
its deep link. It checks that the shell landed on the view it asked for, and
fails on any mismatch. The sheet checks all 42 links in one run.

[![A contact sheet of all 42 studio views, five across. Each tile is a real screenshot of the running app, labeled with its view name and question group. The rows cover today's market, supply adequacy, new-demand siting, prices and bills, new capacity, scenarios, checks against market records, and model inputs.](views-contact-sheet.png)](views-contact-sheet.png)

<details>
<summary><b>Open any of the 42 views directly</b></summary>

<!-- views table start -->

| Question | View | What it answers |
|---|---|---|
| How today's market clears | [Hourly market replay](https://power-dispatch-studio.vercel.app/studio/#v=chronology) | Every hour of one recorded day, three grids cleared together |
|  | [Explain a day](https://power-dispatch-studio.vercel.app/studio/#v=explain-a-day) | What set the price on a chosen day, hour by hour |
|  | [5-minute replay](https://power-dispatch-studio.vercel.app/studio/#v=five-minute-replay) | The operator's own 5-minute dispatch intervals, replayed |
|  | [Lowest-cost-first dispatch (merit order)](https://power-dispatch-studio.vercel.app/studio/#v=merit-order) | Which plants run, from the cheapest through the price-setting unit |
|  | [Marginal units](https://power-dispatch-studio.vercel.app/studio/#v=marginal-units) | The price-setting plant and its frequency |
|  | [Inter-day storage (168 hours)](https://power-dispatch-studio.vercel.app/studio/#v=native-week) | 168 hours solved as one program, storage carried across midnight |
| Can supply cover demand | [Power-shortfall risk](https://power-dispatch-studio.vercel.app/studio/#v=reliability) | Chance of a shortfall (LOLP) across simulated random plant outages |
|  | [Supply after scheduled outages](https://power-dispatch-studio.vercel.app/studio/#v=adequacy) | Whether supply covers demand across the outage schedule |
|  | [Loss of one major unit (N-1)](https://power-dispatch-studio.vercel.app/studio/#v=n-1) | What the price does when any one unit trips at the evening peak |
|  | [Price as demand grows](https://power-dispatch-studio.vercel.app/studio/#v=load-sweep) | Price against demand, swept across the whole range |
|  | [Price range across recorded days](https://power-dispatch-studio.vercel.app/studio/#v=window-band) | The price band the model produces when it replays every recorded day |
|  | [Hours above each price](https://power-dispatch-studio.vercel.app/studio/#v=price-duration) | Hours at or above each price, sorted |
| Where new demand can connect | [Siting a new load](https://power-dispatch-studio.vercel.app/studio/#v=siting) | Hourly load a named site can draw through its own lines |
|  | [Power between island grids](https://power-dispatch-studio.vercel.app/studio/#v=coupled-flows) | What moves over the high-voltage direct-current links and when a link reaches its limit |
|  | [Prices at grid connection points (nodal prices)](https://power-dispatch-studio.vercel.app/studio/#v=nodal-prices) | How each connection point differs from its regional price |
|  | [Generation by island grid](https://power-dispatch-studio.vercel.app/studio/#v=regional-split) | How the solved dispatch divides across the three grids |
| Prices and bills | [Bill impact](https://power-dispatch-studio.vercel.app/studio/#v=bill-impact) | How a spot-price change in WESM affects a Meralco household bill |
|  | [Your contract position](https://power-dispatch-studio.vercel.app/studio/#v=contract-position) | What a scenario does to a book of contracts, in pesos |
|  | [Average price earned by each technology (capture price)](https://power-dispatch-studio.vercel.app/studio/#v=capture-prices) | What each technology earns compared with the market average |
|  | [Possible future price range](https://power-dispatch-studio.vercel.app/studio/#v=forward-prices) | The forward band the archive window supports |
|  | [Supplier concentration and market power](https://power-dispatch-studio.vercel.app/studio/#v=market-power) | How much capacity the largest suppliers control and whether the grid can replace them |
|  | [Backup capacity market (reserves)](https://power-dispatch-studio.vercel.app/studio/#v=reserve-market) | How buying backup capacity with energy affects the energy price |
|  | [Emissions](https://power-dispatch-studio.vercel.app/studio/#v=emissions) | Solved tonnes per hour plus the carbon-price effect |
| What new capacity is needed | [Long-term supply plan](https://power-dispatch-studio.vercel.app/studio/#v=long-term) | Capacity needed over time compared with announced projects |
|  | [Lowest-cost expansion mix](https://power-dispatch-studio.vercel.app/studio/#v=expansion-mix) | Technology chosen by the least-cost build and its cost basis |
|  | [A whole year, solved](https://power-dispatch-studio.vercel.app/studio/#v=future-year) | Every date in a target year, on the published demand path and build list |
|  | [Prices and spare capacity by year](https://power-dispatch-studio.vercel.app/studio/#v=multi-year-path) | The price and margin path across years |
|  | [Generator portfolio value](https://power-dispatch-studio.vercel.app/studio/#v=portfolio) | Assets and earnings for one owner |
| Build and compare scenarios | [Quick what-if](https://power-dispatch-studio.vercel.app/studio/#v=quick-scenario) | Move a slider and all three grids recalculate immediately |
|  | [Compare scenarios](https://power-dispatch-studio.vercel.app/studio/#v=compare) | Two scenarios side by side, property by property |
|  | [Saved simulation runs](https://power-dispatch-studio.vercel.app/studio/#v=saved-runs) | Runs kept in this browser, ready to restore |
|  | [Compare one measure across runs](https://power-dispatch-studio.vercel.app/studio/#v=cross-run) | One measure tracked across every saved run |
|  | [Range across repeated simulations](https://power-dispatch-studio.vercel.app/studio/#v=ensembles) | Repeated simulations of one scenario and the range of results |
| Check the model against market records | [Historical replay](https://power-dispatch-studio.vercel.app/studio/#v=backcast) | Every market day replayed against the observed price |
|  | [Transmission-loss check](https://power-dispatch-studio.vercel.app/studio/#v=loss-validation) | Whether estimated transmission losses reproduce recorded price differences between connection points |
|  | [Unit-commitment test](https://power-dispatch-studio.vercel.app/studio/#v=commitment-test) | What happened when each thermal block had to commit and hold a floor |
|  | [Assumptions](https://power-dispatch-studio.vercel.app/studio/#v=assumptions) | Every constant, its source, and the date it was read |
| Review and edit model inputs | [Generators](https://power-dispatch-studio.vercel.app/studio/#v=generators) | Each sourced unit and its capacity, fuel price, and random-outage rate |
|  | [Fuels](https://power-dispatch-studio.vercel.app/studio/#v=fuels) | Fuel prices and how much of each is available per grid |
|  | [Inter-grid links](https://power-dispatch-studio.vercel.app/studio/#v=interfaces) | The power-flow limits between island grids |
|  | [Regions](https://power-dispatch-studio.vercel.app/studio/#v=regions) | Evening load and peak for each of the three grids |
|  | [Storage](https://power-dispatch-studio.vercel.app/studio/#v=storage) | Battery power and energy on each grid |

<!-- views table end -->

</details>

The end-to-end recording is the
[analyst walkthrough](findings.md#seven-steps-take-an-analyst-from-the-ability-list-to-pesos-then-to-a-file)
at the top of this page, and
[`build/record_analyst_walkthrough.py`](../build/record_analyst_walkthrough.py)
rebuilds it from the running app. An older studio recording sat here with no
script to rebuild it, so it went stale on every shell change with nothing to
catch it. Four shorter recordings show these tasks.
[Explain a day](../studio/docs/view-explain.gif),
[the DICT 1.5 GW data-center build](../studio/docs/workflow-1-datacenter.gif),
[tripping both 647 MW Sual units](../studio/docs/workflow-2-contingency.gif), and
[repricing Malampaya gas to imported LNG](../studio/docs/workflow-3-malampaya.gif).
[studio/README.md](../studio/README.md) carries one recorded clip per analysis view,
14 in all.

### Every run leaves the browser as a standalone HTML report or an hourly CSV

A number you cannot attach to a memo is a number you cannot use. Three exits
already exist and nothing on this page named them until now.

| Exit | Where | What you get |
|---|---|---|
| Run report | [Saved runs](https://power-dispatch-studio.vercel.app/studio/#v=saved-runs), or the run dock's take-away button | One self-contained HTML file: inputs, sources, and the frozen hourly result |
| Hourly CSV | The same view, plus six analysis views | One row per hour with price, demand, shortfall, flows, and storage |
| Archive CSVs | [/data/exports/](https://power-dispatch-studio.vercel.app/data/exports/index.json) | `market_by_day.csv`, `congestion_league.csv`, `backcast_by_grid.csv`, rebuilt nightly |
| Scenario file | Quick what-if, "Take this scenario to Python" | The run's own settings as JSON, which the command line reads back |

The report reads years after the browser storage that held the run is gone. The
archive CSVs carry a CC-BY-4.0 license and an `index.json` that documents each
column.

### A scenario drags out of a slider and runs on the command line

The studio used to keep its edits in a URL hash and the command line took its own
JSON, so a scenario built in one could not run in the other. Both now read
`pds-scenario/1`.

```bash
power-dispatch validate myscenario.json   # names every problem, one per line
power-dispatch run --scenario myscenario.json -o out.csv
```

A broken file prints what is wrong instead of a traceback: an unknown option
suggests the real one, a misspelled grid is named, and a text value where a
number belongs says which field. [`docs/scenario-schema.md`](scenario-schema.md)
carries the key table and says which three settings a round trip through the
browser drops. One fixture, `tests/fixtures/scenario_example.json`, is read by
the Python test and the browser test, so the two sides cannot drift apart.

**This page downloads 3.2 MB of media across 2 files.** The earlier version
downloaded 87.2 MB across 22 files. Browser tests show that GitHub downloads
media inside closed detail blocks. Longer recordings are links, and the 42 views
use one contact sheet plus 42 direct links.

`python3 tests/test_readme_views.py` re-measures that total against the files on
disk and fails when the stated number drifts.

**Long recordings have MP4 versions.** Short chart and analysis previews stay
GIF-only. The longer browser recordings are listed below.

- [The analyst walkthrough](analyst-walkthrough.mp4), and its [GIF](analyst-walkthrough.gif)
- [The map and studio](reel.mp4), and its [GIF](reel.gif)
- [The map hero](hero.mp4) and [the studio shell](studio-shell.mp4)
- [The nodal walkthrough](nodal-walkthrough.mp4), and its [gif](nodal-walkthrough.gif)
- [Siting a load at Pax Silica](siting-walkthrough.mp4), and its [gif](siting-walkthrough.gif)
- [The Pax Silica montage](pax-silica-scale.mp4), and its [gif](pax-silica-scale.gif)
- [The map's Simulate walkthrough](dispatch-demo.gif)

Three files stay in `docs/` on purpose and appear nowhere above.
`scripts/og_card.py` writes `docs/hero.png` from the calculated data, beside the social
preview card. `docs/pax-silica-social.gif` and `docs/pax-silica-social.mp4` are
the square crop for posting.

