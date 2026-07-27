# The Pax Silica visuals, each one shown with what it says in plain words

The live page is `web/pax-silica.html`. Below, first the moving version, then
every chart on the page, each with what it shows, where its numbers came
from, and the one thing worth double-checking.

## All nine charts animating, in 35 seconds

![A montage. A title card first, then each chart in turn, animating from empty and holding while it finishes, with a hard cut to the next](pax-silica-scale.gif)

A montage rather than a page scroll. It opens on a title card naming Pax Silica and both announced figures,
because a feed renders frame one as the thumbnail, then gives each chart its own beat.

Each beat's motion is meant to carry that chart's argument rather than decorate
it. The supply curve builds cheapest plant first, then demand walks right along
it and stops inside the plant that sets the price, then Pax Silica's 3,000 MW
pushes it further right onto oil. The mechanism is the animation. A pulse of
light runs the length of the two power lines that exist and nothing moves on the
three that do not, because nothing travels down a line nobody has built. The
solar day is uncovered midnight to midnight, so the hours arrive in the order
they happen and each label appears as the sweep reaches the hour it names. The
timeline bars grow along their own calendar axis and the court order appears only
once the bar has reached the month it began. The hectare grid fills the city pale
first and only then picks out Pax Silica's share, because Pax Silica is part of
that city rather than something added to it. The water drops count up before the
Makati bracket and the ratio ticks arrive, so the quantity lands before the
comparison. And the treemap flashes the Visayas block once as the dashed campus
block finishes growing beside it, which is the comparison the title makes. The
recorder drives the live page. It lifts one card onto a centered stage,
magnifies it to fill the frame, rebuilds it at that size, plays it from
empty, holds while it finishes, then cuts to the next. The own-station card
gets the longest beat because it flips to its broken-generator state partway
through. Nothing is drawn separately, so the clip cannot show a figure the
site does not. The smoother file to share is `docs/pax-silica-scale.mp4`. To
re-make it after a page change, run `make serve`, then
`python3 build/record_pax_silica_scale.py`.

## Pax Silica would use more power than the entire Visayas grid

![One rectangle tiled by the three grids. Luzon is the giant piece, holding a dashed rust block for Pax Silica that is slightly bigger than the whole Visayas block](pax-silica-figs/grids.png)

The whole Philippine grid as one rectangle, tiled like a jigsaw. Every
piece's area is the most power that grid actually used in any 5-minute
stretch of 105 days of the market operator IEMOP's published files, and
each piece names the people it serves (about 62 million on Luzon, 26 on
Mindanao, 20.6 in the Visayas, 2020 census). Luzon is the giant piece, and
Mindanao and Visayas share the right column. The rust block is Pax Silica on its own, dashed because it is
announced and not built, drawn inside the Luzon block because New Clark City sits on
Luzon and that is the grid it would join. It is not part of the 14,232 MW
already there. It takes the Visayas block's own shape and is scaled by area,
at the same baseline, so you can see that Pax Silica alone is bigger than that
whole grid, and bigger than Mindanao's too. The chip carries the translation, since 3,000 MW around the
clock is the electricity of 10.9 million homes at Meralco's 200 kWh a
month typical household. One thing to remember when reading it is that the
grid pieces were measured while the dashed square is a promise on paper.
Reporting on the project separately projects demand of at least 5,000 MW, and
neither report says how that fits with the announced 3,000.

## Pax Silica's signed solar farm covers 4.1% of the electricity it needs for a day

![One day in megawatts. A flat dashed line at 3,000 for Pax Silica. A low filled hump for the solar farm, peaking at 390 at noon](pax-silica-figs/acwa.png)

A real solar deal exists. ACWA Power leased 500 hectares in June 2026 to
build up to 500 MW of solar with batteries. The chart draws one day in
megawatts, so the sizes are the point rather than a percentage. The dashed
line is Pax Silica drawing 3,000 MW every hour of the day and night. The filled
shape is the farm on a perfect cloudless day, and at its noon best it reaches
390 MW. From 7pm it makes nothing at all, which is when the grid is busiest.
Added over the whole day it covers 4.1 percent of the electricity Pax Silica needs.

## Running Pax Silica on solar power alone would need 122 km² of panels

![A real map of Metro Manila with a large translucent rust square covering Manila, Makati, Pasay, and part of Taguig](pax-silica-figs/land.png)

This one is drawn on a real map. To average 3,000 MW around the clock you
would need at least 12,200 MW of panels. At the land density of a real
Philippine solar farm (MTerra Solar, 3,500 MW on 3,500 hectares) that is
122 square kilometers. The rust square is that area at true map scale,
laid over Metro Manila, and it swallows Manila, Pasay, all of Makati (marked
with a dot) and part of Taguig. The panels would not actually go there. Pax
Silica sits about 95 km north, and the map is only a place to see the size
against. The small solid rust square beside it is the farm they actually
signed, 5 km². For scale, all of New Clark City is 94.5 km² and MTerra
Solar itself, the biggest solar-and-battery build anywhere, is 35 km². After sunset you
would still need about 33,000 megawatt-hours of batteries, 7 times MTerra Solar's. The
basemap is OpenStreetMap and CARTO, the same one the project's grid map
uses.

## Today's power lines can deliver only a quarter of what Pax Silica needs

![Transmission towers in two bands. Two solid navy lines exist and carry 769 MW. Three dashed rust lines do not exist yet](pax-silica-figs/wires.png)

The chart is the transmission itself. Every line drawn is one circuit into
the site, with towers on it. The two solid navy lines are the circuits that
exist, and together they have 769 MW of room at the modeled 7pm on a real day
(25 June 2026). The three dashed rust lines do not exist. They are how many
more circuits of the same kind the remaining 2,231 MW would take, at the
standard rating for a 230 kilovolt line, or one 500 kilovolt line instead. The
line at the bottom closes the arithmetic. 769 that can arrive plus 2,231 that
cannot is the 3,000 MW Pax Silica needs every hour. This form answers the question a grid planner
actually asks, which is not how full a tank is but the number of circuits
missing. The answer is three.

## The last two big Philippine grid builds took 13 and 9 months between first power and full service

![Three timelines. Two finished builds from 2023 to 2024, one with a rust stretch marking a court stop, then the Pax Silica substation's own 2026-to-2028 window](pax-silica-figs/record.png)

The promised fix for Pax Silica is a P6.95 billion substation due by the end
of 2028. These two timelines show how NGCP's two most recent big builds
actually went. On top, the Hermosa-San Jose line turned on in May 2023 at a
quarter of its capacity and reached full capacity only in June 2024, because
a court order over nine towers stopped work for nine months (the rust
stretch), which is most of why that build took 13 months. Below it, the
Mindanao-Visayas undersea link, first power April 2023, full service
January 2024, nine months. Both bars sit on one 24-month axis, so the first
bar being visibly longer is the 13 against the 9. The third strip is the Pax Silica substation's
own promised window on its own 2026-to-2028 axis, with today marked. Pax
Silica's construction starts in the first quarter of 2028 and the substation is due at
the end of it. Depending where in that quarter it starts, that leaves nine to
twelve months against the 13 and 9 months the two builds above took.

## Serving Pax Silica from the grid would double the modeled price of Luzon electricity

![Plant blocks lined up cheapest to priciest. A dark demand line lands on the navy coal block, a white one on the rust oil block](pax-silica-figs/priceb.png)

This is the actual price mechanism, drawn. Every Luzon plant is lined up
cheapest to priciest. Each block's width is its megawatts, its height is
its cost, and the most expensive plant that has to run sets the price for
everyone. Coal appears twice, at P4.14 and at P6.00, because two coal plants
are not equally cheap, so each block carries its own cost. The first line is this evening's demand, 12,018 MW. It lands inside
the navy coal block, so coal sets the price at P6.00 per kWh. The second line
adds Pax Silica, 15,018 MW. It lands on the rust oil block, so oil sets the
price at P12.00, for every buyer on Luzon, all 24 hours of the replayed day.
The small print adds what that means at home. If generation cost were
passed through, P6.00 more per kWh is P1,200 a month more for the typical
200 kWh household, a model figure rather than a forecast. The links between
islands go from about zero to P38 million of congestion rent in the
modeled day. A what-if inside
a model rather than a forecast, and it ignores that the wires to the site
cap out at 770 MW in the first place.

## Even with its own 2,500 MW power station, one generator down leaves 331 MW of Pax Silica with no power

![Two bars of 3,000 MW. On a normal night Pax Silica's own station plus the lines cover it. With one generator down, a rust block of 331 MW is left over](pax-silica-figs/own.png)

BCDA's actual plan is for Pax Silica to build its own power station instead
of drawing from the grid. The 2,500 MW size is one this page chose to
illustrate the plan. No station size has been announced. The 769 MW is all the two existing lines have left at
that hour, which is why they cannot cover the whole 600 MW loss. Both bars are the same 3,000 MW, so the two nights sit
side by side and one screenshot carries the whole story. On a normal night,
2,500 MW from its own station plus 500 over the power lines covers everything.
On the second bar one 600 MW generator is down, about the size of one of the two
units at the Sual coal plant in Pangasinan, and the lines are already carrying everything they can, so 331 MW
has nothing behind it, the electricity of 1.2 million homes. Building your own
power does not remove the grid. It turns the grid into your backup, and the
backup runs down the same two lines. The card makes one more point, that a unit
being out is routine rather than freak. Across the same 105 archived days, San Gabriel, a
417 MW gas unit in Batangas, was listed out on 33 of them, and Masinloc's
second unit on 9.

## The water Pax Silica asked for is 1.4 to 1.9 times the daily water planned for everyone in Makati

![Rows of water drops. Rust drops for Pax Silica, fewer navy for Makati, outlined for the promised pond, and a 100-square grid with 2 colored](pax-silica-figs/water.png)

No model needed here. BCDA itself said Pax Silica will use 65 to 90 million
liters of water a day, which is 26 to 36 Olympic pools every single day, and the
chart makes it countable. One drop is 5 million liters a day, grouped in fives.
Makati's own figure is what its 309,770 residents are planned for at home, at 150
liters each a day, so it leaves out every office, mall and factory in the
district and the ratio above it is a ceiling rather than a measurement.
The row that used to sit underneath for Makati is gone. Makati is now a navy
bracket under the same run of drops, ending 9 and a bit drops in, so the
headline ratio is something you see rather than something you work out. Two rust
ticks mark where the run passes 1.4 and 1.9 times Makati. The promised rainwater
pond used to be 24 counted drops, the longest row on the card, which gave the
most ink to the one quantity that does not exist. It is now a single outlined bar
on the same scale, still visibly longer than what Pax Silica asked for. And the
last row zooms out. Angat dam is a size reference and not a shared tap. It
supplies Metro Manila, about 95 km south, while New Clark City draws on the
Sacobia watershed. Of every 100 liters Angat is allocated for Metro Manila, Pax
Silica would take about 2, the two colored squares in the grid. The small print carries the exact figures,
including that the same water would keep 520 to 900 hectares of rice
flooded. The National Water Resources Board says local sources are enough. Farmer
groups and Aeta communities on the land dispute that, and nobody has
published an independent study of the site's water.

## The site is 1,620 hectares, about nine tenths of Makati's land area

![Squares of 50 hectares. New Clark City is a grid of 189, with 32 marked in rust for Pax Silica. Below it, runs for Makati, Bonifacio Global City and the leased solar farm, at the same square size](pax-silica-figs/site.png)

This one answers the land question, and half the answer is that the number
people most want has never been published. BCDA's president put the
designated industrial area at 1,620 hectares, and the Manila Bulletin describes
the same footprint as a 4,000-acre Economic Security Zone. What grows on those
hectares is contested rather than surveyed. Listing the objections to the
project, the same Manila Bulletin piece reports that critics say "much of the
land under discussion supports rice, coconut, and other food production", which
describes the wider land at issue rather than this footprint. One
square on the chart is 50 hectares, the same size in every run, so a run's
length is the whole comparison. The first grid is all of New Clark City,
9,450 hectares, with 32 of its 189 squares in rust. Pax Silica is 17.1 percent
of the city it sits in. Below that, the same squares against places whose size
people know. Pax Silica's own land comes first, so the site sits above the
500-hectare solar farm already leased to help power it, which it is 3.2 times
over. Then come the outside anchors. It is 0.89 times Makati's land area and
6.8 times Bonifacio Global City.

What the chart does not show is a tree count, because no tree count exists.
Nobody publishes a tree inventory or a tree-cutting permit for Pax Silica, and no
authoritative count of trees per hectare covers this land cover. Any number of
trees felled would be an invention, including one from this page, so the card
says that instead of drawing it. The environmental review is further along than
the tree question. BCDA says the Department of Environment and Natural Resources
issued an environmental compliance certificate for the project masterplan, and
that each company locating inside Pax Silica must still get its own.
The published counts of people do not settle the displacement question
either, and they do not measure the same ground. BCDA says about 10 farmers
are directly affected by those hectares. BCDA also published an initial list of
Project Affected Persons that reaches residents of three Capas barangays,
O'Donnell, Aranguren and Santa Lucia. Kalikasan puts displacement from the
whole New Clark City project at 20,000 Indigenous people and 15,000 farmers. One
count covers the site, the other the city around it. For the wider setting, over
30 percent of Capas is productive agricultural land on the municipal
government's own data, and BCDA puts the project at 130,000 to 190,000 direct
jobs.

## Every chart rests on at least one number nobody has published, whether line ratings, the connection point, or the site's water

NGCP does not publish what its lines can carry, so the 770 MW limit is a
standard assumption and everything built on it moves with it. The map puts
Pax Silica 8.6 km from the real site, because the real connection point is
not public. The solar day is cloudless and Pax Silica's demand is held
flat, both of which are generous to the supply side. The water arithmetic
uses a per-person standard rather than a study of the site. And every announced
number is one side's announcement. Nobody has independently checked BCDA's
power or water figures, including us.

An earlier, deeper look at the supply question (four ways of powering Pax
Silica, each checked against the whole Luzon grid) is described in
`docs/pax-silica-embedded.md`.
