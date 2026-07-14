# UI/UX and demo look-and-feel roadmap (2026-07-12)

Design and craft only. Defensibility (the 21-claim oracle) is converged and out of scope;
no number changes, no touching the claims-verify pins or the launch kit.

Method: /screenshot-qa on the live site (power-dispatch-studio.vercel.app) at 1440x900 and
390px, light and dark, every screenshot Read back. Critique against Nielsen/Norman/Krug,
Tufte/dataviz, and the deslop AI-UI checklist. Evidence PNGs in
tmp/uiux-audit-20260712/.

## What is already strong (leave alone)

- The desktop studio app is the highlight: a credible production-cost studio (ribbon, System/Simulation
  explorer, Excel-like properties grid, Solved badge, HiGHS status bar). The Backcast cost-vs-offers
  toggle reads cleanly (MAE 4.33 to 2.94, correlation 0.36 to 0.73, and the red accent tile correctly
  drops off when the evening residual shrinks).
- Dark mode is well done across landing, app, and Backcast: deep navy, legible text, the red accent
  survives on dark. It honors the OS prefers-color-scheme. (Two small holdovers noted in item 11.)
- The Prices panel and the og.png / price-spread chart family are good editorial dataviz: direct-labeled
  series, a shaded WESM-suspended band, sourced footnotes.
- The dark-navy LinkedIn stat cards (41% card) are internally consistent and shareable.

## Ranked roadmap (highest payoff first)

### 1. Mobile map: the controls hide the map. SEVERE. Surface: map. Effort: M
On a 390px phone the layout is fixed and non-scrolling, so the map is squeezed into a thin band, and
the wrapped mode-pill cluster plus the Details button float dead-center over it. About 80 percent of the
map is covered; you can barely see the pins. The map is the public, shareable surface and it is close to
unusable on a phone.
Fix: give the map full viewport height on mobile; dock the modes as a bottom tab bar; put the right-panel
content and the three-questions card in a bottom sheet; collapse the head panel to a compact title bar with
a menu. Evidence: map/mb-01-default.png, map/mb-04-fullpage.png.

### 2. Mobile find-yours results are clipped after two items. Surface: map. Effort: S (fold into 1)
Search works (typing "a" matches Ilijan, Sual, and more), but the results list is cut off by the head
panel edge after about two rows, and the rest are unreachable. On mobile, search is broken for anything
past the first two matches. Fix as part of the item-1 mobile relayout (results in a scrollable overlay or
inside the bottom sheet). Evidence: map/mb-find-a.png.

### 3. Stale hero.gif and dispatch-demo.gif still show the old name "gridbill-ph". Surface: demo. Effort: M
hero.gif is the README's number-one image (820px, the first thing anyone sees on the repo) and it shows the
old product name, the old three-mode map, and an old bake date. Its alt text also describes the old flow.
dispatch-demo.gif has the same old name and is missing the Drivers mode. Both are real recordings, so the fix
is to re-record them against the current five-mode Power Dispatch Studio and rewrite the two alt texts. The
newer Jul-11 assets (story-montage, constraint-league, backcast-proof, studio-e2e, and the chart GIFs) are
correctly branded and current. Evidence: demo/hero-mid.png, demo/dispatch-demo-mid.png.

### 4. Choke-mode right panel overflows and clips its closing line. Surface: map. Effort: S
The Choke panel stacks two equipment tables plus running prose; it is tall enough that the last paragraph is
cut off behind the bottom-right zoom control. Constrain the panel height with an internal scroll, or trim the
prose, and keep clear of the zoom control. Evidence: map/dt-02-choke.png.

### 5. Unify the demo and social visual system. Surface: demo. Effort: M
Three families are each good alone but do not read as one system: dark-navy stat cards, light Tufte charts,
and live-UI app GIFs. Direction: keep light-Tufte for in-product and explanatory charts (it matches the light
app), reserve the dark-navy card system for social and share cards only, and share one type scale and one
categorical palette across both. Fix the Luzon/Visayas/Mindanao series once (Visayas red plus Mindanao green
is a colorblind-unsafe pair; direct labels help but the pairing should change) and apply it everywhere.
Write the two-lane rule down so future assets stay consistent.

### 6. Drivers and Simulate leave the bottom three-questions card stale on Q3. Surface: map. Effort: S
Those two modes are not part of the three-question rail, so the bottom card sits on Q3 and tells a different
story than the panel above it. Hide the card in Drivers and Simulate, or replace it with a mode-relevant
caption. Evidence: map/dt-04-drivers.png, map/dt-05-simulate.png.

### 7. Map legend completeness and color reuse. Surface: map. Effort: S
Drivers uses four pill colors (curtailed, HVDC, alert, spread) but the legend documents two, and red is reused
for both "curtailed" and "spread". The Simulate merit-order stack uses about six fuel colors with no adjacent
legend. The Supply panel's two curtailment rows have no bars while every other row does. Complete the legends,
give spread its own color, and add a fuel key to the stack. Evidence: map/dt-04-drivers.png, map/dt-05-simulate.png,
map/dt-01-supply.png.

### 8. Studio landing "Visayas minus Luzon spread P5.31" tile hint. Surface: studio. Effort: S
The sub-line "driven by scarcity" is vague. Make it concrete, for example "the price the geography adds when the
links bind", so the tile explains itself. Evidence: studio/dt-01b-landing-full.png.

### 9. Studio landing network map is blank in capture. VERIFY in your Chrome first. Surface: studio. Effort: S-M
The section below the hero shows only the NETWORK legend over an empty gray band. The MapLibre canvas mounts at
1440x300, centered over the Philippines, the Carto style loads, there are no console errors and no failed
requests, and forcing a resize or scroll does not paint it. That is the signature of a headless lazy-mount WebGL
paint throttle, which usually renders fine in a real browser (the main map renders fine in the same headless run).
Open the live studio in your Chrome. If the map is there, close this item. If it is blank there too, add an
IntersectionObserver that calls map.resize() when the section scrolls into view. Do not assume it is broken.
Evidence: studio/dt-01c-landing-map-verify.png, studio/dt-01d-landing-after-resize.png.

### 10. Studio on mobile is rough. Surface: studio. Effort: M
Lower priority because the studio is a desktop analytical tool. The properties grid overflows: only about three
and a half of seven columns show and the MW values are cut off with no scroll affordance. Make the grid
horizontally scrollable with a frozen Object column and a scroll hint. The hint paragraph breaks into cramped
columns around an inline Run pill; make it one flowing line. "Close studio" wraps to two lines; shorten it.
Evidence: studio/mb-02-app.png.

### 11. Dark-mode chip holdovers. Surface: studio. Effort: S
The cream "independent homage" disclaimer pill and the green "Solved" chip keep light backgrounds in dark mode,
and the Run button blue is a touch low-contrast on navy. Adapt the two chips and darken the button a step.
Evidence: studio/dk-02-app.png.

### 12. Backcast has no cost-vs-offers delta. Surface: studio. Effort: S
The 0.36 to 0.73 correlation jump is only legible if you remember the cost-model numbers. Add a small derived
delta on the offers view (for example "up from 0.36"). Derived from the two values already shown, not a new
claim. Optional craft touch. Evidence: studio/dt-04-backcast-cost.png, studio/dt-05-backcast-offers.png.

### 13. Search misses common owner names. Surface: map. Effort: S. (content, not layout)
Typing "Meralco", the utility everyone knows, returns "No plant or data center by that name". Alias common
owner and city names to their pins, or show a "try a plant name" hint. Evidence: map/mb-03-find.png.

## Stylistic note (not a defect)

The desktop map basemap is very pale and the data clusters near Manila, so the map center reads as empty ocean
while all the visual weight sits in the corner panels. It works as an editorial map, but a light island tint or a
tighter default framing would make the map feel like the star rather than a backdrop. Judgment call, left for you.

## Coverage

Audited: map (5 modes, legend, find-yours, island jump) desktop and mobile; studio landing and app (Home/Model/
Solution, System/Simulation, properties grid, Backcast cost and offers) desktop and mobile; dark mode on the
studio; all README-embedded demo assets. Not changed: any number, the oracle pins, or the launch kit.

## Execution status (2026-07-12)

Shipped and screenshot-gated at 1440x900 and 390px (evidence in tmp/uiux-audit-20260712/):

- **1, 2 Mobile map** DONE. Full-screen map; head collapses to a 44px title bar with a Find toggle; modes dock
  to a bottom horizontal-scroll bar (44px pills); the three-questions rail is a collapsible bottom sheet; the
  find-yours results flow inline and scroll (no clip); map credits stay visible; all touch targets measure 44px.
- **4 Choke panel** DONE. Scroll shadow signals the panel scrolls; the cut line now reads as "more below".
- **6 Drivers/Simulate rail card** DONE. Bottom card shows a mode caption instead of the stale Q3.
- **7 Legends** DONE. Drivers legend now lists all four pill colors; Simulate gets a fuel key under the stack.
- **8 Tile hint** DONE. "driven by scarcity" is now "the gap when the links bind".
- **3 Demo GIFs** DONE. hero.gif and dispatch-demo.gif re-recorded against the current five-mode UI (old name
  "gridbill-ph" gone), frame-verified, both smaller than before; README alt text rewritten to match the new
  recordings (the dispatch alt's shortfall and P13 claims did not hold and were corrected).
- **5 Visual system** DONE (as documentation). Wrote docs/visual-system.md; the palette was already unified
  through scripts/vizstyle.py, so this codifies the two-lane rule rather than re-coloring.
- **11 Dark-mode chips** WITHDRAWN. Re-checked the tokens: the homage pill and Solved chip do adapt to dark
  (dark-brown, green-on-dark); the first-pass "cream holdover" read was wrong. Not a bug.
- **9 Studio landing map** FIXED. It was a real bug, not a headless artifact (Xavier's own Chrome showed it blank
  too). Root cause found by querying the map instance: the map rendered fine (style loaded, 96 layers, 69 features)
  but its container had height 0. MapLibre adds `.maplibregl-map { position: relative }` to the container div,
  which has equal specificity to `.mapview__canvas { position: absolute }` and wins on source order, so the
  container collapsed and clipped the canvas. Fix: pin `width/height: 100%` on the container so it fills the
  631px `.mapview` parent regardless of position. Verified painting in light, dark, desktop, and mobile.
- **10 Studio mobile** DONE. Properties grid pins the Object column and shows a scrollbar so the MW values are
  reachable; the hint flows as one paragraph; Close studio no longer wraps; no horizontal overflow.
- **12 Backcast delta** DONE. The offer view shows each figure's move from the cost model in green (MAE from P4.33,
  correlation from 0.36, bias from P-1.63).
- **13 Search aliasing** DONE. "Meralco" and "NGCP" return a short sourced note plus a Jump button instead of a
  dead end; the generic no-match now suggests a plant name.

Both passes shipped to main and the personal Vercel on 2026-07-12.
