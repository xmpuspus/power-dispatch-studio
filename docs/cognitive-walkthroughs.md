# Cognitive walkthroughs for analyst tasks

These checks use the Studio without README help. A pass needs the stated conclusion, not only a completed click path.

| Task | Click budget | Hidden prerequisites allowed | Ambiguous labels allowed | Stale-result risk allowed | Dead ends allowed | Correct conclusion |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Replay a market day, inspect evidence, share the view | 4 | 0 | 0 | 0 | 0 | The analyst can state which values are recorded and which prices the replay recalculates. |
| Load a preset, run it, name it, save it, and compare it | 9 | 0 | 0 | 0 | 0 | The analyst can state the changed assumption, most affected grid, price movement, unserved energy, and bound corridor. |
| Import a CSV, calculate it, and export a case and report | 8 | 0 | 0 | 0 | 0 | The analyst can prove which input came from the local file and transfer the full case without browser storage. |
| Use a preset and reach the result with a keyboard | 16 Tab presses plus 2 actions | 0 | 0 | 0 | 0 | The analyst can load the case and see that Run is still needed. |

## Walkthrough 1: replay, evidence, share

1. Open Hourly market replay.
2. Pick 22 July 2026.
3. Read the result status before reading a price.
4. Open Evidence and sources.
5. Copy the link.

Pass when the status says that recorded system conditions sit beside recalculated prices. The recorded load-weighted average price must have its own label and line style.

## Walkthrough 2: preset, run, save, compare

1. Save the unchanged 22 July replay.
2. Open Scenario builder.
3. Load the DICT 1,500 MW reference case.
4. Confirm that the page says Preview, not calculated.
5. Press Run.
6. Open Hourly market replay.
7. Enter a useful run name and save it.
8. Open Saved runs.
9. Read the summary before the table.

Pass when the comparison names the +1,500 MW Luzon assumption, the most affected grid, the signed mean-price change, the unserved-energy change, and corridor status. A pending scenario must never copy or save stale headline results.

## Walkthrough 3: import, calculate, report

1. Open Scenario builder.
2. Import a CSV with one Luzon demand value.
3. Confirm that the value has a user-supplied label.
4. Press Run.
5. Open Hourly market replay and name the run.
6. Save the run.
7. Open Saved runs and export the case.
8. Export the report.

Pass when the case file has the imported key, active assumption, date, calculation version, source notes, summaries, hourly results, and chart series. The report must show the same input as user-supplied.

## Walkthrough 4: keyboard and narrow screens

1. Use Tab from the page start to reach the DICT preset.
2. Press Enter.
3. Read the pending-result status.
4. Repeat at 200% zoom and at 375 CSS pixels wide.

Pass when focus is visible, every control has a usable name, the preset stays inside the viewport, and the page has no document-level horizontal scroll. Wide result tables can scroll inside their labeled container and keep the first column visible.
