# Contributing

## Run the gate before you open a pull request

```bash
pip install -r requirements.txt
make data     # rebuild web/data/ from the committed archive, no network needed
make qa       # 18 checks plus the claims oracle
```

CI runs the same list plus `ruff check .`, which `make qa` does not. So run
`ruff check .` too. `tests/qa_gate.py` fails if the two lists ever disagree.

For a studio change:

```bash
cd studio && npm ci && node scripts/copy-data.mjs
npm run typecheck && npm run lint && npm test -- --run
npm run build -- --base=/studio/
```

The `--base` flag matters, because the studio serves from a subpath.

## A new test joins both gate lists

Add it to the `qa` target in the `Makefile` and to `.github/workflows/ci.yml`. A
test in one list only runs half the time and rots. `tests/qa_gate.py` blocks a
pull request that adds it to one list only.

## Every number in the prose belongs to the oracle

`scripts/verify_claims.py` checks every rolling figure in `README.md`,
`studio/README.md`, `web/for-analysts.html` and `web/methodology.html` against
the data build. The archive window rolls each night, so a number outside the
oracle freezes while the data moves under it.

Add a registry entry for any number you put in those four files, then run
`python3 scripts/verify_claims.py` and read the result. `--write` syncs numbers,
never sentences: a figure that moves enough to break the sentence around it
needs a human edit.

## Both engines change together

`pipeline/dispatch.py` and the browser solver write the same LP text, byte for
byte, and `tests/test_lp_parity.py` pins the hash. Run `make sync-engine` after
any engine edit, because the pip package carries its own copy.

## Claims stay inside the public evidence

These rules came from reviewing the project against what the records support.

- Do not write that data centers raised WESM prices. Current data-center load is
  small next to the Luzon peak. The model tests announced future demand against
  recorded supply and transmission limits.
- Label every forecast with its owner and its date. Give a contested capacity
  figure as a sourced range, or leave it out.
- A plant outage is a scenario, never a prediction. The model removes the listed
  unit capacity and solves the chosen day again.
- Cite the source of each published input. Keep calculations and assumptions
  labeled apart from measurements.
- OpenStreetMap gives the transmission routes. They are not official NGCP
  records. A site pin has city or campus precision unless a source gives an
  exact location.
- Describe companies and projects in neutral terms.

## No test touches the studio DOM

The six recorders are the only end-to-end check of the studio shell:
`studio/scripts/record-demo.py`, `record-views.py`, `record-workflows.py`, and
`build/record_*.py` for the map. Nothing fails when a selector stops matching,
so run them yourself after a change to the top bar, the nav, or the shell.

## Reporting a bug

Open an issue with the date you ran, the command, and the output. For anything
touching a published number, say which figure and where you read it.
