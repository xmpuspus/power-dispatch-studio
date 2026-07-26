# Pax Silica needs 3,000 MW and the two power lines into the site carry 770

![Four ways of supplying the campus, each compared against the 3,000 MW it needs](pax-silica-embedded.png)

On 24 July 2026 the Bases Conversion and Development Authority said the Pax Silica
campus at New Clark City will build its own power station rather than take its
3,000 MW from the grid, so it does not compete with household supply. This checks that
plan against the network.

## Each bar is the same 3,000 MW, split by where it would come from

Each bar is the same length, because each one is the 3,000 MW the campus needs. The
colours split that 3,000 into where it would come from. Red is the part with no source
at all.

Everything is drawn at 7pm, because that is when demand is highest and when the solar
farm has stopped for the day. The small chart underneath shows the solar day, so you
can see the evening zero rather than take it on trust.

The dashed line at 770 MW is the only number the model works out. It is the most those
two lines can carry, and it is why the blue segment stops where it does.

## No row covers the full 3,000 once the whole grid is checked

| how it is supplied | over the two lines | no source | wider check |
|---|---|---|---|
| all of it from the grid | 770 MW | 2,230 MW | 2,470 MW |
| grid plus the 500 MW solar farm | 770 MW | 2,230 MW | 2,470 MW |
| its own 2,500 MW station, plus 500 from the grid | 500 MW | none | 160 MW |
| same station, one 600 MW unit down | 770 MW | 330 MW | 660 MW |

Rows one and two are identical because the sun has set by 7pm. The solar farm fills the
middle of the day and adds nothing in the evening, which is the part of the
announcement that does the least.

Row three is the plan working against the two lines alone, and it still takes 500 MW
from the grid. Making its own power covers most of what it needs but never all of it.
Checked against the whole grid it is 160 MW short, so no row here is fully covered.

Row four is the one that matters. Lose a single 600 MW unit and 330 MW has no source.
Building your own station moves the problem from supplying the campus to backing it up,
and the backup comes down the same two lines.

The last column is a wider check that looks at the whole Luzon grid instead of these two
lines alone. It finds more bottlenecks, so every shortfall gets bigger, including
row three, which the picture shows as covered.

## Which numbers the model produced, and which are inputs

| number | where it comes from |
|---|---|
| what the lines carry, 770 MW | worked out by the model, on recorded grid data for 25 June 2026 |
| 3,000 MW campus demand | the announced figure for full development, held flat |
| 500 MW solar | the ACWA lease, announced |
| how solar output varies through the day | an assumption used across this project, a cloudless day |
| 2,500 MW of its own station | chosen for the scenario, so the mix covers 3,000 |
| the 600 MW unit that fails | chosen for the scenario, a normal size for one unit |
| the red amounts | arithmetic, demand minus what the two lines carry |

## The line ratings are estimates, the site is 8.6 km off, and demand is held flat

The lines are not rated by anyone public. NGCP does not publish what its lines carry, so
770 is the standard figure for that voltage, and every number here moves with it.

The site is 8.6 km from the nearest point in the model, which is not the connection
anyone will actually build.

One of the two circuits turns out to be the site's only connection to the rest of the
grid, so losing it takes the site to zero. That is what the mapped network shows. The
real grid may have a second route that OpenStreetMap does not carry, and no line outage
is modelled in the picture itself.

Demand is held flat at 3,000 MW all day. That is close to right for a data centre and
only roughly right for the factories beside it. The solar assumes a cloudless day, which
flatters it, and matters for the separate sum showing 500 MW covers 4.1% of what a
3,000 MW campus uses.

## The studio answers this for any announced site, without a script

![The same question driven through the studio. Picking the site, adding the solar farm and watching the evening refuse to move, building its own 2,500 MW, then taking a circuit out](siting-walkthrough.gif)

Siting a new load, in the studio's Analysis list, answers this for any of the
announced sites without running a script. The picture above is the same question
driven through that view.

## Rebuilding the picture

```bash
python3 scripts/pax_silica_figure.py
```

It works out the line capacity on the first run, saves it, and writes
`docs/pax-silica-embedded.png`. It sits outside `make viz`, since the nightly rebuild
does not need it.
