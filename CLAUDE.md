# Working rules for power-dispatch-studio

A free dispatch model of the Philippine wholesale electricity market. A map at
`/`, a studio at `/studio/`, a Python package on PyPI, and a nightly archive of
market data. This file holds the rules that a session here breaks most often.

## Never name the licensed competitor on a public surface

No public file names PLEXOS or Energy Exemplar. The project stands on its own
backcast validation, so lead with that number instead. The DOE planning document
under `docs/` is the one exception, because it is a quoted source.

## Two gate lists exist, and a new test must join both

`make qa` runs 18 checks plus the claims oracle. `.github/workflows/ci.yml` runs
its own list, and it also runs `ruff check .`, which `make qa` does not. So a
green `make qa` proves nothing about lint. Run `pipx run --spec ruff==0.16.1
ruff check .` before every push.

A new test file goes in the `qa` target of the `Makefile` **and** in `ci.yml`. A
test in one list only runs half the time and rots.

The studio has a second CI job: `npm ci`, `node scripts/copy-data.mjs`, types and
lint and format, `npm test -- --run`, then `npm run build -- --base=/studio/`.
The base flag matters, because the studio serves from a subpath.

## The claims oracle owns every rolling number in the prose

`scripts/verify_claims.py` checks 108 claims across 4 files against the data
build. Two mechanisms:

- `REGISTRY`: one regex per scalar, anchored on the sentence around it.
- `BLOCKS`: marker-delimited tables that the oracle regenerates whole.

`--write` rewrites only the four files in `WRITABLE`: `README.md`,
`studio/README.md`, `web/for-analysts.html`, `web/methodology.html`. Two traps
follow from that set:

1. The nightly `archive.yml` must `git add` every WRITABLE file. A rewrite that
   nobody stages gets thrown away, and CI turns red days later.
   `tests/test_writable_staged.py` guards the list.
2. `--write` syncs numbers, never sentences. A number that moves enough to break
   the sentence around it needs a human edit.

Every narrative number in those four files belongs in the oracle. A number that
sits outside it freezes while the window rolls forward each night.

## The window rolls every night, so prose drifts on its own

`archive.yml` fetches yesterday's files, derives, rebuilds `web/data`, re-marks
the worked contract case, then runs `verify_claims.py --write`. It commits the
raw archive first and the data build second, because the archive is the
irreplaceable half. A moved data pin leaves `main` red with raw files and no
build. Read the `archive-bake-split` memory for the four-command recovery.

After any re-bake, run `python3 scripts/verify_claims.py --write` and read the
diff. After a merge with cron commits, re-derive before you push.

## Four model decisions are measured, not preferences

Do not undo one of these without a new measurement.

1. The engine dispatches **fuel blocks per grid, not named units**. Named units
   moved daily energy by 0.0 MWh and price by P0.004/kWh. See
   `pipeline/unit_probe.py`.
2. **Unit commitment stays off.** It lowered the price correlation in all five
   scored series, from 0.442 to -0.003 in Visayas.
3. **A year is 365 separate 24-hour programs.** Storage resets at midnight and
   the hydro budget caps one day. Never call the run 8760.
4. **Contracts settle energy against modeled spot only.** No capacity fee, no
   wheeling charge, no tax, no credit terms.

Both engines change together. `pipeline/dispatch.py` and the browser solver must
write the same LP text, byte for byte, and `tests/test_lp_parity.py` pins the
hash. Run `make sync-engine` after any engine edit, because the pip package
carries its own copy.

## No test touches the studio DOM, so run the recorders yourself

The six recorders are the only end-to-end check of the studio shell:
`studio/scripts/record-demo.py`, `record-views.py`, `record-workflows.py`, and
`build/record_*.py` for the map side. Nothing fails when a selector stops
matching, so a broken recorder stays broken in silence.

Run every recorder after a change to the top bar, the nav, or the shell. Three
of them broke on 2026-08-09, and one died several commits earlier, when a
deleted button took its selector away.

## Believe a failing UI check only after the instrument proves it looked

A surprising FAIL from a driven browser check is usually the selector, not the
product. Prices render as `₱`, not `P`. The segmented control marks its active
item `is-active`, not `is-on` or `aria-pressed`. GitHub proxies every README
image through `camo.githubusercontent.com`, so a `shields.io` filter finds
nothing. Count the elements a selector matched and print them first.

A screenshot only tests the first render. Drive the control and read the value
back.

## The studio view count lives in prose and in a hard assert

`studio/src/shell/nav.ts` declares 42 destinations.
`tests/test_readme_views.py:34` asserts that number, and the README lists all 42
as `#v=<slug>` deep links rather than 42 clips. Adding a view means a sweep:
`nav.ts`, both READMEs, `Shell.tsx`, the test, and the recorders. A plain
`grep 42` also matches unrelated fleet numbers, so read each hit.

## Local commands

```
make qa                     # the local gate (does not run ruff)
make data                   # rebuild web/data from the archive
make serve                  # range-capable dev server on 8789
make e2e BASE=<url>         # behavioral checks against a running map
make future YEAR=2028       # build a future year as its own data directory
make package                # wheel and sdist from the current data build
```

`make viz` is toolchain-bound. matplotlib is unpinned, so another version moves
text past a card's own overflow guard. Regenerate the figures on the machine
that last wrote them. `make qa` never runs that target.

Always `python3`, never `python`. The map and the studio share the `pds.theme`
key. `tests/test_contrast.py` gates every color token against WCAG AA.

## What is still open

The Visayas loss surface fails validation at -0.57. No one submitted the paper in
`paper/` yet. No real room ran the workshop in `docs/workshop/` yet. Known latent
bugs live in `docs/latent-bugs.md`, and a pre-existing one never rides along in
an unrelated change.
