# Running the workshop found five instruction defects and no product defect

Verdict: the lab does not survive a live run as written. Five steps mislead a
participant, and the product behaves correctly at every one of them. Nothing here
blocks a room that has an instructor who knows the tool; every one of them stops a
participant who is following the page.

## Build identity (Gate 0)

| Target | Identity | Method | When |
| --- | --- | --- | --- |
| Studio bundle | `index-XkH08CsY.js` sha256 `e78ca2e6c8fbd75a` | curl with cache buster, matches the local build byte for byte | 2026-08-09T12:23Z |
| Map `/` | sha256 `70c7256b1a00732b`, 123,428 bytes | same | 2026-08-09T12:23Z |
| Analyst page | sha256 `d0fb8a551e546888`, 15,152 bytes | same | 2026-08-09T12:23Z |
| Package | `power-dispatch 0.2.1`, sources sha256 `ae2b25696d328483` | fresh venv, pip install from PyPI | 2026-08-09T12:24Z |

The served studio bundle hashes identical to the local build, so this pass ran
against the commit under test.

## Blast radius (Gate 1)

Every action the lab asks for is SAFE: reads, browser-local state, and a local
CSV write. The target carries no PAID and no IRREVERSIBLE action. Gate 2 has
nothing to snapshot, and this pass changed no shared state.

## Coverage

| Check | What it covers | Verdict |
| --- | --- | --- |
| C1 | Siting names a site and its hourly limit | PASS |
| C2 | The sweep shows price against demand | PASS WITH OBSERVATION, see W4 |
| C3 | Adding 300 MW in Quick what-if | PARTIAL FAIL, see W1 and W2 |
| C4 | `examples/03_sweep_the_window.py` runs | FAIL, see W3 |
| C5 | N-1 names a unit and its price move | PASS |
| C6 | Shortfall chance per grid | PASS |
| C7 | The lab's Python snippet, verbatim | PASS |
| C8 | 647 MW is one Sual unit | PASS |
| C9 | Bill impact shows the spot share | PASS |
| C10 | The bill line moves with the spot control | PASS |
| C11 | Historical replay shows the model's error | PASS |
| C12 | The closing's limit list | FAIL, see W5 |
| C13 | Two limits carry a measurement | PASS |
| C14 | The two follow-on documents resolve | PASS |
| C15 | All 7 deep links reach the view they name | PASS |
| C16 | The weak-wifi claim | PASS |

16 planned, 16 with a verdict. NOT RUN: none.

One instrument error, disclosed: C2's first regex looked for `P` where the app
renders `₱`, which reported a false FAIL. Re-measured from the rendered tiles.

## W3. The lab's setup does not produce the file its first code block runs

- Severity HIGH, class DOC
- Surface `docs/workshop/README.md`, Task 1 step 4
- Precondition a participant who followed the setup line, which says only
  `pip install power-dispatch-studio`
- Steps: install the package into a clean venv, then run the block as printed
- Expected: a sweep over ten days, written to `sweep.csv`
- Actual: `can't open file '.../examples/03_sweep_the_window.py'`
- Method: fresh venv, `pip install power-dispatch-studio`, then the block verbatim
  in an empty directory. `examples/` is absent from the wheel and from
  site-packages.
- Impact: every participant fails at the first Python step of the first task.
- Root cause: `pyproject.toml` sdist includes `src/power_dispatch`, `LICENSE` and
  `README.md`. `examples/` ships in the repository, never in the package.
- Status reproduced

## W1. Task 1 tells the room to press a Run button that stays disabled

- Severity MEDIUM, class DOC
- Surface Task 1 step 3
- Steps: open `#v=quick-scenario`, move the data-center lever, read the Run button
- Expected: "press Run"
- Actual: Run reads `Solved` and is disabled, both before and after the lever
  moves. The rail footer reads "No edits yet."
- Method: `locator('.bar__run').is_disabled()` before and after a native-setter
  input event, in `w1-run-button.json`
- Impact: a participant stalls looking for a control that is correctly inert. The
  levers preview and never write the model, which is the documented design.
- Status reproduced

## W2. Three hundred MW moves no price, so the comparison the lab asks for is empty

- Severity MEDIUM, class DOC
- Surface Task 1 step 3
- Steps: add 300 MW on Luzon, read the clearing price
- Expected: "Compare the price with the sweep"
- Actual: ₱6.00 before and ₱6.00 after. At 2,500 MW the same control gives ₱12.00.
- Method: `c3-c10.json`, native setter input, price read from the clearing tile
- Impact: the room sees nothing and cannot tell a working model from a broken one.
- Status reproduced

## W4. The sweep opens on a range with no bend in it

- Severity MEDIUM, class DOC
- Surface Task 1 step 2
- Steps: open `#v=load-sweep`, read the tiles at each range
- Expected: "Find the load level where the curve bends"
- Actual: flat at +500 MW and at +1,500 MW, both ₱6.00 to ₱6.00. Only +3,000 MW
  bends, ₱6.00 to ₱12.00. The view opens on +1,500 MW.
- Method: `w4-bend.json`, all three range buttons, tiles parsed from the rendered
  view
- Impact: the room hunts for a bend that is off the selected range. The view
  already answers the question in a tile: "Price holds for another 1,521 MW".
- Status reproduced

## W5. The closing sends the room to read five limits, and the page lists four

- Severity LOW, class DOC
- Surface Closing, line 62
- Expected: "Read the five limits"
- Actual: the analyst page lists four, after contracts moved from a refusal to a
  stated partial ability
- Method: parsed the page's own list, `c12-c14.txt`
- Status reproduced

## State ledger

Snapshotted: nothing, because no action reachable in this lab writes shared
state. Changed: nothing on the target. Local artifacts only, inside this run
directory.

## Fixes applied and re-checked

| Finding | Fix | Re-check |
| --- | --- | --- |
| W3 | The setup adds `git clone`, and says the clone exists for one step | A fresh venv plus a fresh clone ran the block and wrote 41 rows |
| W1 | Step 3 now says the levers preview and Run correctly stays disabled | Matches the measured button state |
| W2 | Step 3 drags to 300 MW, reads no move, then drags to 2,500 MW | Matches the measured 6.00 and 12.00 |
| W4 | Step 2 says the view opens flat, and names the +3,000 MW button | Matches the three measured ranges |
| W5 | The closing reads "four limits" | Matches the page's list of four |

The +1,500 MW range is flat because the view's own tile says the price holds for
another 1,521 MW. The default range stops 21 MW short of the step, which is now
the teaching moment rather than a dead end.

tests/test_readme_views.py gains a guard: every deep-link slug the lab names has
to be a view nav.ts declares. That is the cheap half. The live half is this pass.
