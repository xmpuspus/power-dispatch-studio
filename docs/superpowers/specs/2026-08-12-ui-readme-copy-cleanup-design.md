# UI and README copy cleanup design

## Goal

Remove AI-styled language from the main README and both public interfaces while
keeping the product's facts, technical meaning, links, layout, and behavior
unchanged.

## Surfaces

The cleanup covers these files and text.

- `README.md`.
- Visible copy and metadata on the public map at `/`.
- Visible copy, navigation, controls, empty states, explanations, and metadata
  in Studio at `/studio/`.
- Source strings that produce copy shown on those surfaces.
- Tests that pin any changed wording.

Internal documentation, code comments, source data, and unrelated media assets
are outside scope. A media asset enters scope only when a changed source string
appears in that asset on one of the three surfaces.

## Editorial rules

- Write in direct, neutral language suitable for power-market analysts,
  engineers, and interested readers.
- State what the product does without slogans, staged punchlines, sales
  language, fake quotations, or instructions to choose it over another tool.
- Remove canned contrasts, unnecessary second-person framing, anthropomorphic
  descriptions of software, repetitive rhetorical patterns, and narration
  about the writing or interface.
- Keep precise domain terms when they carry technical meaning. Do not replace a
  term merely because it sounds technical.
- Preserve facts, measured values, links, limitations, routes, data contracts,
  command examples, and model behavior.
- Keep interface labels task-oriented. Helper text must describe an input,
  result, or consequence without promotional framing.
- Do not change layout, information architecture, visual styling, model code,
  or calculation logic.

## Representative changes

- `Point the engine at your own system, not at ours` becomes `Use your own
  system data`.
- The competitor conclusion becomes a factual difference statement.
  `Power Dispatch Studio preserves IEMOP's rolling public files and reports
  replay error against recorded prices.`

These examples set the tone but do not limit the audit to exact phrase matches.

## Verification

- Check that the two quoted source phrases are gone.
- Run the project prose linter on `README.md` and the UI linter on changed UI
  sources, then review each remaining warning in context.
- Run `python3 scripts/verify_claims.py` so copy edits cannot silently change
  guarded facts.
- Run the focused tests that pin changed strings, followed by `make qa`.
- Run the Studio formatting check and the relevant browser tests.
- Inspect the public map and Studio at desktop and mobile widths for wrapping,
  clipping, broken labels, or misleading hierarchy after text lengths change.
- Inspect `git diff --check`, the changed-file list, and the final diff to make sure
  that no unrelated files or behavioral changes entered the patch.

## Acceptance criteria

The three public surfaces use plain, factual language with no obvious AI
fingerprints. All technical claims and navigation stay correct. Automated
checks pass, the interfaces stay readable at desktop and mobile widths, and
the diff has only copy, directly related tests, and any necessary regenerated
asset updates.
