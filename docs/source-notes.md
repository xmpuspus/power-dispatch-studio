# Public records support the market model and its stated limits

These notes record the public sources behind the first release. The method page
lists each file used by the current calculation. These notes explain two source
questions that need more context.

## IEMOP files need a separate archive because the public window rolls forward

IEMOP publishes dispatch, price, reserve, outage, and transmission-limit files
for a rolling period. The project copies those public files into `data/raw/` so
older days stay available after the public window moves.

The project measured a window of about 90 days on 5 July 2026. IEMOP describes
the window as rolling but does not publish a fixed day count. The archive job
checks whether each source keeps advancing instead of assuming an exact
retention period.

## A zero nodal congestion field does not mean the grid had no limits

The archived DIPCEF node-price files split each locational marginal price into
energy, loss, and congestion fields. The congestion field can stay at zero even
when the real-time dispatch file names equipment at a limit.

WESM can replace prices under its price-substitution rules. In those intervals,
the published node rows do not show an ordinary congestion shadow price. WESM
expresses much inter-island congestion through different regional prices
for Luzon, Visayas, and Mindanao.

The public map shows regional price differences and recorded
connection-point deviations. It does not label the zero congestion field as
proof that congestion was absent.

Primary and supporting records include the following documents.

- [WESM Price Determination Method](https://www.wesm.ph/downloads/download/TWFya2V0IFJlcG9ydHM=/MTUzMQ==)
- [DOE copy of the revised price method](https://legacy.doe.gov.ph/sites/default/files/pdf/issuances/annex_a_revised_price_determination_methodology.pdf)
- [Energy Transition Partnership assessment of WESM prices](https://www.energytransitionpartnership.org/wp-content/uploads/2024/09/Assessment-of-WESM-Price-Analysis_v4_Final.pdf)
- [ERC price-substitution coverage](https://powerphilippines.com/erc-approves-new-wesm-pricing-scheme/)
- Archived IEMOP files under `data/raw/`

## The Visayas alert example uses a dated market event

The Visayas grid ended a 52-day yellow-alert period on 1 July 2026 after a 150 MW
unit returned. On that day, published reports listed 2,599 MW available against
a 2,411 MW peak, with 935.3 MW unavailable. The historical replay uses this dated
event to compare a calculated island-price difference with the recorded one.

- [SunStar report on the end of the alert period](https://www.sunstar.com.ph/cebu/visayas-grid-exits-daily-yellow-alerts)
- [GMA report on the 1 July supply figures](https://www.gmanetwork.com/news/money/economy/993308/ngcp-visayas-grid-on-yellow-alert-on-wednesday-july-1-2026/story/)

The event is a historical check. It does not show what a future outage or demand
increase will do.
