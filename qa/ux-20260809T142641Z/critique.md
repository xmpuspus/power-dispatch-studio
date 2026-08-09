# Desktop is close to intuitive. A phone user cannot reach a single control.

Measured on the live build at 1440x900 and 375x812, cold, no instruction.

## The five defects, measured

| # | Defect | Measurement | Heuristic |
| --- | --- | --- | --- |
| U1 | The first control sits below the fold on a phone | slider top 843px in an 812px viewport, 91px of scroll to reach it, 0 controls in view | Krug 2, visual hierarchy |
| U2 | 77 words of explanation come before the first control | word count from the pane's own text, both viewports | Krug 4 and 6 |
| U3 | The most prominent control is disabled and reads a status | `.bar__run` is filled, top right, `disabled=true`, text "Solved", `aria-label="Run the simulation"` | Nielsen 1 and 4 |
| U4 | Five of nine top-bar buttons carry no visible label | including Close, which sits beside the theme toggle | Norman signifiers |
| U5 | The region chips look live and are inert on this view | disabled when the view reads all three grids, explained on hover only | Nielsen 1 |

## What already works, and should not be touched

- The rail asks "What do you want to know?" and groups 42 views into 8 questions
  with counts. That is recognition over recall, done well.
- The run dock keeps the answer on screen at every view.
- The what-if preview band says "NOT YET IN THE MODEL" in words, which is the
  honest half of the U3 problem already solved in one place.
- Every deep link is a URL, so a view survives being sent.

## Weighting

The studio is the analyst surface and the map at `/` is the front door, so U1
costs less than its severity suggests. U2 and U3 cost every user on every device.
