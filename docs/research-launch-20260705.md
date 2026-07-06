# Research synthesis for the gridbill-ph launch window

2026-07-05. Four parallel research agents (prior art, WESM price-determination
methodology, PH energy news sweep, README and hero-media patterns), each claim
carrying a URL, plus first-party re-verification of anything bound for baked copy.
Confidence flags: [VERIFIED-FETCHED] the page was loaded and read, [SEARCH-RESULT]
search snippets only, [FIRST-PARTY] we re-fetched it ourselves this session.

## Part 1: prior art, and the honest novelty claim

The survey covered the Philippine sources this project reads and reconciles against,
plus international grid-data projects for method precedent: IEMOP's own market-data
pages and monthly reports, WESM Market Watch, NGCP and DOE outlooks, ICSC's Power
Outlook, and independent market-monitor reports. The ingredient-by-ingredient
verdict:

- Named-equipment congestion receipts are, as a technique, published elsewhere: some
  market operators expose a shadow-price / binding-constraint feed that names the
  overloaded element, stations, kV, and price per event, on a short (roughly weekly)
  public window [SEARCH-RESULT]. The technique is not the new part.
- Nobody does it for IEMOP/WESM. IEMOP publishes the "congestions manifesting" files
  but its public pages roll off after a rolling window, and the one-year MIND
  repository is restricted to registered trading participants [SEARCH-RESULT]. No
  third party archives the files; no constraint league table for the Philippine grid
  exists.
- No surveyed project fuses the three questions in one reproducible artifact for the
  Philippines: named congestion receipts, announced data-center siting against the
  importing load pocket, and the wholesale price next to the retail (Meralco
  generation charge) pass-through. ICSC's Philippine Power Outlook
  (https://icsc.ngo/tag/philippine-power-outlook/) is the PH-native neighbor for the
  supply question, as an annual PDF [SEARCH-RESULT].

So the README positioning is PH-native: the first public archive and constraint
league for the Philippine market, and the only artifact tying IEMOP receipts to
data-center siting and the Meralco bill. IEMOP's own files self-delete after a
rolling window, which is exactly the argument for a public archive. That claim
survives the survey; any stronger claim does not.

Where-the-data-comes-from entries adopted for the README are the Philippine primary
sources: IEMOP market data and monthly reports, NGCP TDP, DOE Power Statistics,
WESM/PEMC, ICSC Power Outlook, and the public data-center inventories (URLs in the
README section).

Caveat kept honest: the "~90-day rolling window" figure is our own first-party
measurement of the min_date carried in each IEMOP market-data page's config
(2026-07-05); IEMOP's pages confirm a rolling window but do not state a day count.

## Part 2: WESM price determination and the DIPCEF congestion column

The puzzle: on the two archived DIPCEF sample days (2026-06-25/26, 358,800
node-rows), LMP_CONGESTION reads 0.0 on every row while nodal LMPs spread by
multiples, and the same days' RTDCV files list 255 equipment-binding rows.
Resolved as follows, against the WESM Price Determination Methodology (read via a
reader-proxy extraction of the wesm.ph PDF; the official PDFs 403 or resist
parsing, so section numbers are approximate and must be checked against the
official document before public quotation):

- The PDM's nodal price is LMP_j = lambda + (1/TLF_j - 1) x lambda + sum of
  (shadow price x shift factor) over binding constraints. The congestion term is
  nonzero only when a constraint carries a nonzero shadow price in the PRICING
  optimization. Physical binding in real-time dispatch is neither necessary nor
  sufficient. [Proxy-extracted PDM; formula shape is standard]
- 72% of the sampled intervals carry PRICING_FLAG = PSM (price substitution
  methodology) and 0.4% AP (administered). PSM fires when a price-separation
  factor exceeds 0.2 and re-prices at the unconstrained solution's marginal
  price, which has no congestion by construction. On PSM rows, LMP equals
  LMP_SMP and both LOSS and CONGESTION are zero. [VERIFIED-LOCAL-DATA]
- Even on the 27% of normal (OK) intervals, the spread is inter-regional:
  LMP_SMP takes exactly one value per island grid (verified across the whole
  sample: max distinct SMP within any interval-region is 1), e.g. Luzon 8,985
  vs Visayas 33,784 PhP/MWh in the same interval. Within a region, loss factors
  move nodes about 5 to 8%. WESM expresses congestion between the islands as
  regional SMP separation, not as a per-node congestion charge; violated soft
  constraints are relaxed (zero shadow price) inside a region.
  [VERIFIED-LOCAL-DATA]
- Settlement asymmetry confirmed from our own archive: generators settle at
  nodal ex-post LMP (DIPCEF), loads settle at the regional load-weighted average
  price (the LWAPF files' region names are CLUZ/CVIS/CMIN, customer prices).
  Inter-island congestion reaches consumers as regional price separation.
  One proxy-extracted PDM clause said loads settle nodally; the published
  per-region LWAP files contradict that reading, so the files win until the
  official PDF is checked. [VERIFIED-LOCAL-DATA]

Verdict for the map: keep the nodal LMP_CONGESTION layer archived and do NOT
display "congestion premium = 0" as a finding. Congestion was present on those
days; the column is zero because of the substitution methodology and the
regional-SMP structure. The honest displayable quantities are the regional price
separation (already the map's Q3 frame) and, as a future layer, PSM/AP incidence
per interval. The map's existing framing survives contact with the methodology.

Sources: wesm.ph PDM download (served but compressed;
https://www.wesm.ph/downloads/download/TWFya2V0IFJlcG9ydHM=/MTUzMQ==), DOE annex
(https://legacy.doe.gov.ph/sites/default/files/pdf/issuances/annex_a_revised_price_determination_methodology.pdf,
403 to automated fetch), ETP WESM price-pattern assessment
(https://www.energytransitionpartnership.org/wp-content/uploads/2024/09/Assessment-of-WESM-Price-Analysis_v4_Final.pdf),
ERC pricing-scheme coverage
(https://powerphilippines.com/erc-approves-new-wesm-pricing-scheme/), and the
local archive under data/raw/.

## Part 3: news sweep, Jun 28 to Jul 5, and the launch pegs

Neither launch print has landed as of 2026-07-05:

- Meralco July 2026 rate advisory: not out. June's was announced Jun 11 (+P0.1488/kWh
  to P14.4833; generation charge P9.0704; WESM cost P7.0281). July advisory expected
  roughly Jul 8-12. Watch
  https://company.meralco.com.ph/news-and-advisories/rates-archives (403s automated
  fetch; open in a browser) and the GMA/Rappler mirrors. [VERIFIED-FETCHED via GMA]
- IEMOP June 2026 monthly report: not out. Expected first half of July. Watch
  https://www.iemop.ph/ and https://www.iemop.ph/the-market/market-reports/.
  Trap: search engines surface iemop.ph/news/june-wesm-prices-decline/ as if
  current; it is dated 16 June 2023. Do not use it. [VERIFIED-FETCHED]

The one hard in-window fact, re-verified first-party this session:

- The Visayas daily yellow-alert streak ended Jul 1, 2026 at 2:40 pm, after 52 days
  (May 11 to Jul 1), when PEDC Unit 3 returned 150 MW. TVI Units 1 and 2 (169 MW
  each) and Kepco SPC Unit 1 remained on outage.
  https://www.sunstar.com.ph/cebu/visayas-grid-exits-daily-yellow-alerts
  [FIRST-PARTY]
- On Jul 1 the Visayas grid ran 2,599 MW available against a 2,411 MW peak with
  935.3 MW unavailable.
  https://www.gmanetwork.com/news/money/economy/993308/ngcp-visayas-grid-on-yellow-alert-on-wednesday-july-1-2026/story/
  [FIRST-PARTY]

Map copy consequence: every present-tense "7 straight weeks of yellow alerts"
reference flips to the past-tense, dated 52-day streak.

Rejected anchor: "Meralco has 30 hyperscale applications, a 1,200 MW pipeline."
The underlying article (powerphilippines.com/meralco-eyes-more-hyperscale-data-centers/)
is dated May 7, 2024, two years stale, and the page carries spam injection
[FIRST-PARTY]. The PCIJ Jan 2026 Meralco 1,000 MW commitment stays as the anchor.

Nothing new in-window on: Sual or Ilijan trips (May 13 Ilijan transmission event is
pre-window), ERC secondary-price-cap action (latest is the May 27 review signal,
https://www.philstar.com/business/2026/05/27/2530719/erc-mulls-review-wesm-secondary-price-ceiling
[SEARCH-RESULT]), data-center announcements, or NGCP energizations.

Launch pegs to hot-swap the moment they drop (Jul 8-12): (1) Meralco July overall
rate, delta, generation charge, WESM cost; (2) IEMOP June system average, three
regional prices, margin MW; (3) the Visayas streak stays framed "ended Jul 1."

## Part 4: README first-screen and hero-media patterns

From reading the actual README markdown of a set of best-in-class open mapping and
data repos (datasette, kepler.gl, streamlit, openfreemap, tar1090, deck.gl,
protomaps, Overture) [VERIFIED-FETCHED each]:

- Almost none of the best-in-class repos lead with an animated GIF; heroes are
  logos or linked screenshots, and Streamlit's GIF sits below the fold. A good
  animated hero is a differentiator, not table stakes, and it must earn its weight.
- The strongest structural idiom is kepler.gl's: a width-pinned image wrapped in a
  link to the live site, [<img width="600" alt="..." src="...">](live-url).
- GitHub constraints: the Camo image proxy caps payloads at 5 MB (target under
  3 MB), caches by URL (bust with a new filename), and committed GIFs autoplay and
  loop. Width control is HTML-only.
- Recording guidance: 8 to 15 seconds, about 15 fps, record at 2x and downscale.
- Alt text is where every famous repo fails (alt="image", alt="docs"); the house
  pattern of a full-sentence alt that carries the headline finding is the edge.
  Keep it.
- Badge rows push heroes below the fold; keep one compact row and land the hero
  within the first two elements.

Adopted for the README rework: hero GIF first (width-pinned, linked to the live
site, long finding-carrying alt), one compact badge row after the lead paragraph,
featured plain-English finding sections with bolded numbers and inline caveats,
related-projects section from Part 1.
