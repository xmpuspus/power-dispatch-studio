# Changelog

The archive window rolls every night, so the published figures move on their own.
This file records changes to the code and the interface, never the nightly data.

## Unreleased

### Added

- A simulated scenario travels in the URL. The five Simulate controls write to the
  query string and read back, so a shared link opens on the same result. Before
  this the link carried the mode only, and the reader saw an empty panel.
- A "Copy a link to this scenario" button, drawn once the scenario moves off the
  base case, which names the price change it carries.
- `requirements.txt`. `make data` needs `highspy` and no page said so, so the
  documented five-command path failed on the second command on a clean machine.
- `make help`, and it is the default target. A bare `make` started an
  undocumented 15-minute fetch against iemop.ph.
- Open Graph, Twitter and canonical tags on all five pages. The studio served
  none, so every shared studio link unfurled bare.
- `robots.txt` and `sitemap.xml`.
- `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `DATA-LICENSE.md`.
- Five response headers, a Content Security Policy among them.

### Changed

- `LICENSE` holds the MIT text alone. The appended scope note made GitHub read
  the licence as "Other". The note moved to `DATA-LICENSE.md`.
- The map writes the peso sign in all 52 places it used to write a capital P.
- The Simulate tab bar wraps onto two rows on a phone. The five tabs measured
  449 px against a 372 px track, so Simulate sat off the right edge at x=376.
- Every slider on the Simulate panel gets a 44 px hit area. They measured 16 px.
- The Menu and the map-details sheet close each other. Opening one over the
  other drew the second one underneath, at z-index 4 against 9.
- The map-details sheet carries a "Back to the map" control, and Escape closes
  it. The button that opened it hides itself, so a phone reader had no way out.
- The Pax Silica card leads with 3,000 MW rather than a water comparison.
- `ci.yml` and `archive.yml` both run `make qa`. The nightly ran 4 of 18 checks
  and then pushed to `main`, and a push made with the workflow token starts no
  other workflow, so nothing else checked it.

### Fixed

- The loss-surface heading said +0.72 and -0.57 while the body two paragraphs
  down said +0.73 and -0.58. The data build says +0.73 and -0.58. The heading,
  the contents link, its anchor and the figure's alt text are pinned to the
  claims oracle now, so the nightly keeps all four in step.
- `web/methodology.html` linked `../docs/source-notes.md`, which resolves above
  the deployed root and returned 404.

### Removed

- Internal working files left the public tree: `qa/` run output, the adoption
  plan, the latent-bug list, the paper draft, the workshop and the project notes.

## 0.2.1

Released 2026-08-09. A missing offer book left through a stack trace instead of
a message.

## Earlier releases

0.1.0 and 0.2.0 predate this file. `git log` carries their history, and PyPI
lists all three releases.
