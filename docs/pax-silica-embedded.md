# Pax Silica needs 3,000 MW while its modeled feeding route carries 769 MW

![Four supply cases compared with Pax Silica's 3,000 MW demand](pax-silica-embedded.png)

BCDA says Pax Silica will need 3,000 MW at full development. BCDA expects
construction to begin in 2028 and full development 10 to 15 years later.

BCDA plans an embedded renewable power station and has not ruled out grid power.
NGCP includes a dedicated substation in its transmission plan. This calculation
checks the announced demand against the mapped network.

## Each bar separates local power, grid supply, and unmet demand

Each bar totals 3,000 MW at 7pm. Solar output is zero in this cloudless-day
profile at that hour. Red marks demand with no supply source.

The model gives the feeding route 769 MW of room. It maps two 230 kilovolt
routes near Pax Silica, but only one connects the site to the wider grid.

| Supply case | Feeding route | Unmet at site | Unmet in wider grid check |
|---|---|---|---|
| Grid only | 769 MW | 2,231 MW | 2,471 MW |
| Grid plus 500 MW solar | 769 MW | 2,231 MW | 2,471 MW |
| 2,500 MW local station plus grid | 500 MW | none | 163 MW |
| Same station with one 600 MW unit unavailable | 769 MW | 331 MW | 661 MW |

The first two rows match because solar output reaches zero by 7pm. Solar helps
during the day and does not cover the evening peak.

The third row covers the site through local supply and the feeding route. The
wider Luzon calculation still finds a 163 MW shortfall upstream.

The fourth row tests a 600 MW unit outage. This document chose the local station
and unit sizes. BCDA did not announce either figure. A 417 MW outage leaves a
148 MW site gap.

## Public records supply the demand figures while the model calculates the grid limits

| Number | Basis |
|---|---|
| Feeding-route room of 769 MW | Model result for 25 June 2026 at the site's mapped bus |
| Wider shortfalls of 2,471, 163, and 661 MW | Whole-Luzon model result for the same day |
| Demand of 3,000 MW | BCDA figure for full development |
| Solar capacity of 500 MW | ACWA lease announcement |
| Solar output by hour | Cloudless-day model assumption |
| Local station of 2,500 MW | Example chosen for this case |
| Unavailable unit of 600 MW | Example chosen for this case |

## Unpublished line ratings and connection details limit the 769 MW supply estimate

NGCP does not publish the rating of these lines. The model assigns each 230
kilovolt circuit a 400 MW class value, or 800 MW for a two-circuit route.

The model connects Pax Silica to a mapped bus 8.6 km away. The final connection
point is not public. The real grid may include a route missing from OpenStreetMap.

Demand stays at 3,000 MW all day from the first modeled day. The calculation
does not phase demand over the announced 10-to-15-year development period.

## The studio runs the same siting check for other announced sites

![Studio recording of the Pax Silica demand, solar, local-station, and outage cases](siting-walkthrough.gif)

Open **Siting a new load** in the studio to choose a named project and change
its demand or local supply. The view recalculates the hourly network result.

## pax_silica_figure.py writes the current supply bars

```bash
python3 scripts/pax_silica_figure.py
```

The script saves `docs/pax-silica-embedded.png`. It stays outside `make viz`
because the nightly data job does not need this separate chart.
