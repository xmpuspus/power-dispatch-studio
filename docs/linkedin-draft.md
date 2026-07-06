# gridbill-ph LinkedIn draft

Written to the proven civic-tech pattern (leaves.ph, solar-map-ph): a live hook,
specific numbers early, "computed from public data," "measurement not a verdict,"
open code and data, a "check it yourself" close, dated sources. Honesty-lock-safe:
never blame the buildout for this year's prices, no brownout prophecy, forecasts
carry owners, the wholesale price and the retail bill are kept apart. Do not post
until every
pre-post gate is true. Links go in the FIRST COMMENT, not the body.

## Pre-post gates (all must be true before posting)

- [ ] Live URL returns 200 (deployed to the personal Vercel account). ONLY hard blocker.
- [ ] og.png preview renders when the link is pasted into the LinkedIn composer.
- [ ] The July Meralco advisory and the June IEMOP report have landed (Jul 8-12) and
      their numbers are baked in, OR the post ships on the May/June numbers with the
      July print teased. Decide on the day.
- [ ] Post the map, GitHub, and methodology links in the FIRST COMMENT (off-platform
      links in the body are down-ranked).
- [ ] Hero: upload the story GIF as a native clip or the og.png card, not a bare link.
- [ ] Re-read against the rails: never blame the buildout for prices, no
      brownout prophecy, forecasts labeled with owners.

## Primary hook (the receipts angle, safe today)

Everyone is arguing about whether Philippine data centers will break the grid. I
wanted to see what the grid itself already says, so I built an open map from the
market operator's own public files, with every number linked to its source.

The surprising part: the choke points are not a forecast. IEMOP publishes a file
that names the exact transmission equipment sitting at its limit, every five
minutes. I archived 90 days of it and ranked them. A line literally named
LEYTE_TO_CEBU shows up at a binding limit on 68 of those 90 days. The 230 kV lines
that carry that corridor top the list at 87 of 90 days. The grid names its own
choke point; the map just keeps the receipts.

What it shows, in three questions:

- Supply. DICT forecasts 1,500 MW of data-center capacity by 2028 (their number, a
  forecast, not mine) and Meralco has committed 1,000 MW for 10 data centers. The
  whole system's supply margin in May was 3,629 MW. The announced wave is the size
  of the margin, and a data center draws that power around the clock, not just at
  peak.
- Infrastructure. In the operator's own dispatch schedules, Luzon reserves ran
  below the requirement on 54 of 90 days, and one 647 MW Sual unit equals 18% of
  the May margin, which is why a single trip moves the whole grid. Observed
  curtailment and arithmetic, not a brownout prediction.
- Prices. One market on paper, three prices in practice. While trading was
  suspended the three island grids priced within a few centavos of each other; once
  the market reopened they fanned apart, with a widest daily gap of P15.72/kWh. The
  links between the islands are the geography, and the market prices it daily.

Where I stopped, on purpose: I do not pin this year's bill on the buildout. Current
data-center load is small against a roughly 15 GW Luzon peak, and this year's prices
are driven by fuel, outages, and the market restart. What the map shows is the
machinery any new 24/7 load plugs into, and who currently pays for which cost.

Open code, open data, reproducible from a clean clone. Check any number yourself.

## Alternate first line (if the July Meralco print lands first)

The July Meralco rate just [rose/held] at P__/kWh. Underneath that one number is a
grid that names its own choke points every five minutes, and I built an open map of
it from the market operator's public files.

[then continue from "The surprising part:" above]

## First comment (links live here)

Live map: [LIVE URL]
Code and data (MIT / CC-BY-4.0): https://github.com/xmpuspus/gridbill-ph
Method and every source: [LIVE URL]/methodology.html

Sources: congestion, prices, reserves, and outages from IEMOP's public market-data
files (archived daily); the WESM monthly figures from IEMOP's monthly report; the
bill pass-through from the Meralco June 2026 advisory; data-center sites from
company announcements and DataCenterDynamics. Forecasts carry their owners (DICT,
DOE, Meralco).

#opendata #civictech #geospatial #energy #datacenters #electricity #Philippines #grid

## Why this framing

The receipts angle (the grid naming its own choke point) is the one thing no other
grid map does and no forecast can match, so it leads. The three questions carry the
supply-infrastructure-price arc. The "where I stopped" paragraph is the honesty lock
that keeps the post defensible: it refuses the viral bill-blame framing while still
showing the machinery. Every number in the body is one a reader can reproduce from
the repo, which is the whole point of a civic-data post.
