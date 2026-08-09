# The corrected lab runs clean, and the re-run found one instrument error of mine

Mode VERIFY-FIX. Every one of the five findings from
`qa/workshop-20260809T122320Z` is closed against a re-measured build, and the
whole lab was walked again from its first setup line rather than spot-checked.

## Gate 0, re-hashed after the fixes

| Target | Identity | Against the first pass |
| --- | --- | --- |
| Studio bundle `index-XkH08CsY.js` | sha256 `e78ca2e6c8fbd75a` | unchanged, as expected: the fixes touched a document and a test |
| Analyst page | sha256 `d0fb8a551e546888` | unchanged |
| Package | `power-dispatch 0.2.1`, fresh venv from PyPI | same |
| Lab | commit `0561ef0`, sha256 `4a70c69bbe9c23a3` | the corrected file |

The clone in this pass pulled `0561ef0` from GitHub, so the Python half ran
against the same corrected text a participant would download.

## Every step of the corrected lab, walked

| Step | What the lab now says | Measured |
| --- | --- | --- |
| Setup | pip install, then git clone, and the clone is for one step | both ran, 0.2.1 installed, clone at 0561ef0 |
| T1.1 | pick a named site, read its hourly load | Pax Silica, 769 MW at 7pm |
| T1.2 | opens flat on +1,500 MW | `is-active` on "to +1,500 MW", tile reads "Price at +1,500 MW", 6.00 to 6.00 |
| T1.2 | press to +3,000 MW and find the step | 6.00 to 12.00 |
| T1.2 | the holds-for tile names the separating MW | 1,521 MW |
| T1.3 | 300 MW does not move the price | 6.00 at 300 |
| T1.3 | Run correctly stays disabled | label "Solved", disabled true |
| T1.3 | 2,500 MW steps | 12.00 |
| T1.4 | run examples/03 from the clone | 40 rows, 41 lines, 5.743 to 6.952 |
| T2.1 | N-1 names a unit and a price | named units present, price column present |
| T2.2 | shortfall chance per grid | three percentages |
| T2.3 | the snippet prints two prices | 5.223 and 5.414 |
| T3.1 | the bill view shows the spot share | a percentage present |
| T3.2 | the bill line moves with the control | text changed at the control's maximum |
| T3.3 | historical replay shows the error | present |
| Closing | four limits on the analyst page | four |

Sixteen steps, sixteen measured. No step of the corrected lab strands a
participant. Zero page errors across the whole walk.

## One instrument error, disclosed

The first automated read of the sweep reported the selected range as
"to +500 MW". That was my selector, not the app: it looked for `is-on` or
`aria-pressed` and this component marks the active item with `is-active`, so it
fell back to the first button. Re-measured from the class list and from the
view's own "Price at +1,500 MW" tile, the view opens on +1,500 MW, which is what
the corrected lab says. No new defect.

This is the second instrument error in two passes on this target, both mine and
both caught by re-measuring rather than by re-reading. The first was a regex
looking for `P` where the app renders the peso sign.

## State ledger

Nothing on the target changed. Local artifacts only: a throwaway venv, a
throwaway clone, and this directory.
