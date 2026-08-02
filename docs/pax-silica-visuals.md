# Nine charts compare Pax Silica with the power, land, water, and grid it would use

The live page is `web/pax-silica.html`. Each section below states what one chart
shows, where its figures come from, and which inputs stay uncertain.

## The 35-second recording shows all nine charts from the live page

![Recording of the nine Pax Silica charts](pax-silica-scale.gif)

The recorder opens each live chart at full size and plays its animation once.
Run `make serve` and `python3 build/record_pax_silica_scale.py` to rebuild it.

## Pax Silica would use more power than the entire Visayas grid

![Pax Silica demand compared with peak demand on the three island grids](pax-silica-figs/grids.png)

The island areas show the highest five-minute demand recorded across 117 days.
The 3,000 MW Pax Silica block is larger than the Visayas or Mindanao block.
BCDA announced the project figure. It is future demand and sits outside the
recorded Luzon total.

## The solar and battery project signed for New Clark City covers 4.1% of the electricity Pax Silica needs for a day

![One day of Pax Silica demand and output from a 500 MW solar farm](pax-silica-figs/acwa.png)

ACWA Power leased 500 hectares for up to 500 MW of solar with batteries. The
chart uses a cloudless-day solar profile. It peaks at 390 MW and reaches zero by
7pm. The daily energy equals 4.1 percent of a flat 3,000 MW load.

## Running Pax Silica on solar power alone would need 122 km² of panels

![A 122 square kilometer solar area drawn at map scale over Metro Manila](pax-silica-figs/land.png)

A flat 3,000 MW load needs at least 12,200 MW of panels under the stated solar
profile. MTerra Solar supplies the land-density reference. The resulting 122
square kilometers exceeds New Clark City's 94.5 square kilometers. The map uses
Metro Manila only as a familiar area comparison.

## The one route feeding Pax Silica delivers only a quarter of what it needs

![Existing and missing 230 kilovolt routes for Pax Silica](pax-silica-figs/wires.png)

The mapped feeding route has 769 MW of room at 7pm on 25 June 2026. The model
uses a 400 MW class rating for each circuit because NGCP publishes no rating.
Three more two-circuit routes of the same class would cover the 2,231 MW gap.

## NGCP's two most recent long-distance builds took 13 and 9 months between first power and full service

![Timelines for two NGCP projects and the planned Pax Silica substation](pax-silica-figs/record.png)

Hermosa-San Jose took 13 months from first power to full service. The
Mindanao-Visayas link took 9 months. BCDA targets the Pax Silica substation for
the end of 2028. The comparison does not predict its completion date.

## Serving Pax Silica from the grid would double the modeled price of Luzon electricity

![Luzon supply blocks with present demand and Pax Silica demand](pax-silica-figs/priceb.png)

The cost model places a typical 12,018 MW evening on the P6.00/kWh coal block.
Adding 3,000 MW moves the last needed supply to the P12.00 oil block. This is a
flat-block model result. It is not a price forecast, and the site route cannot
carry the full added load.

## Even with its own 2,500 MW power station, one generator down leaves 331 MW of Pax Silica with no power

![Normal and generator-outage supply cases for a 2,500 MW local station](pax-silica-figs/own.png)

The 2,500 MW station and 600 MW unit are examples chosen for this case. They are
not BCDA announcements. With the unit unavailable, the local station and 769 MW
route leave 331 MW unmet. A 417 MW outage leaves 148 MW unmet.

## The water Pax Silica asked for is 1.4 to 1.9 times the daily water planned for everyone in Makati

![Pax Silica water demand compared with household planning figures for Makati](pax-silica-figs/water.png)

BCDA states 65 to 90 million liters per day. The Makati comparison applies 150
liters per resident to 309,770 residents and excludes offices and industry. It
sets an upper bound. It does not replace a site water study.

## The site is 1,620 hectares, about nine tenths of Makati's land area

![Pax Silica land area compared with New Clark City, Makati, BGC, and the solar lease](pax-silica-figs/site.png)

BCDA states a 1,620-hectare project area. That equals 17.1 percent of New Clark
City, 0.89 times Makati, and 6.8 times Bonifacio Global City. No published tree
inventory supports a tree-count claim for the site.

## Unpublished line ratings, connection details, and site studies limit every chart

The model uses a class line rating and connects Pax Silica to a mapped bus 8.6
km away. The final connection point is not public. The solar profile assumes a
cloudless day, and the demand stays flat.

BCDA supplies the announced power, water, and land figures. No independent study
in the cited public record checks all three. Read
`docs/pax-silica-embedded.md` for the whole-Luzon supply calculation.
