# LinkedIn launch kit: Power Dispatch Studio

Assembled 2026-07-11 for the live news peg (NGCP Visayas red alerts July 8 and 9;
the June WESM/Meralco print landing now). This is a ready-to-post kit. Every
rolling number is tagged; re-pull the tagged ones the morning you post.

## The one rule for numbers

Three different prices exist. Keep them apart or the energy-literate crowd tears it up.
- THE TOOL'S OWN OUTPUT (safe to attribute to the studio): over the market-priced
  archive days, Luzon P7.65, Visayas P12.96, Mindanao P11.52; widest daily spread
  P15.72 on 2026-06-08. These roll as the window advances. [ROLLS]
- THE MERALCO BILL (sourced constant): June 2026 WESM P7.03 inside a P9.07 generation
  charge, P14.48 total rate.
- A NEWS PRINT is a news print. If you cite the June WESM system/Visayas averages,
  attribute the outlet and never call them the tool's output. Better: skip them and
  use the tool's own numbers above.

## Image (this is what fixes the scroll-past)

Lead with `docs/linkedin-card.png` (the 41% stat card). On LinkedIn a shared video
autoplays muted and the feed shows its real first frame, and the studio MP4 opens on
a blank white frame, so DO NOT lead with the video. Best formats, in order:
1. The single stat card as the post image (simplest, strongest).
2. A 3-image carousel: (1) `docs/linkedin-card.png`, (2) `docs/story-montage.gif`
   exported to a still or the four-panel image, (3) a screenshot of the live map's
   "Is there room for the wave?" panel with the CTA. Carousels dwell well on LinkedIn.
Only use the MP4 if the stat card is baked into its first ~2 seconds (a custom poster
does NOT override in-feed muted autoplay).

## The post

Hook (primary, evergreen arithmetic, zero moving target):

> Announced data-center demand in the Philippines: 1,500 MW.
> The grid's entire spare margin: 3,629 MW. One is 41% of the other.

This is the locked hook, and it matches the stat card. It carries no rolling number,
so it stays true whenever you post.

Hook (alternate, rides the live peg, only while July 8-9 is fresh):

> The Visayas grid went on red alert twice this week.
>
> Here's the plan on the table: plug in data centers the size of the grid's ENTIRE spare margin.

Body:

> The announced wave is 1,500 MW by 2028 (DICT's own forecast). The whole system's
> spare supply margin in May was 3,629 MW (from the market operator's own files). One
> is 41% of the other, and a data center runs flat 24/7, so it eats that margin in
> every interval, not just at the evening peak.
>
> To be clear: today's data centers are small (a couple hundred MW, and the exact
> figure is contested) and did NOT cause this week's alerts, which were plant trips.
> The point is what the announced load does to a grid that is already thin. Luzon's
> scheduled reserves fell below the requirement on 59 of the last 95 archive days, and
> the Visayas just ended a 52-day yellow-alert streak. [ROLLS: 59/95]
>
> And the grid already names its own weak spot. The operator publishes a file that
> names the exact line at its limit every 5 minutes. One corridor, Leyte to Cebu, sits
> at its day-ahead limit on 92 of the last 95 days, and it carries 98% of every
> line-limitation instruction the operator wrote down. Fewer than three of the ten data
> centers Meralco has committed to serve would, if sited in the Visayas, saturate the
> Leyte-Luzon link on a normal evening. [ROLLS: 92/95]
>
> When the grid binds, the market prices it, and that shows up on the Meralco bill: in
> June, WESM was P7.03 of a P9.07 generation charge inside a P14.48/kWh rate.
>
> So I built a free tool to see it yourself. Toggle a Sual unit offline and watch 18%
> of the country's spare power vanish. Replay the day the three islands split by
> P15.72/kWh. Every number links to its IEMOP, NGCP, or Meralco source.
>
> No license. No install. Runs in your browser: https://power-dispatch-studio.vercel.app

First comment (keeps the tags out of the body so a mis-tag doesn't throttle reach):

> Built on IEMOP's public market files, archived daily so the record doesn't disappear.
> Method and every source: https://power-dispatch-studio.vercel.app/methodology.html
> Curious what the energy-data folks make of it. An independent, open project on public
> files; not affiliated with any operator or vendor.

Hashtags (3-5): #Philippines #Energy #DataCenters #WESM #OpenData

## Pre-post checklist

- [ ] Lead image is `docs/linkedin-card.png` (the 41% card), NOT the blank-opening video.
- [ ] The card's number (41%) matches the hook.
- [ ] Every price labeled by period + source; no news print presented as the tool's output.
- [ ] The "did not cause the alerts" guardrail line is in.
- [ ] Re-pull [ROLLS] numbers (59/95, 92/95, the regional prices, P15.72) from the live
      map / `web/data/` the morning of posting; they advance ~1/day.
- [ ] Posted within ~48h of the July 8-9 red alerts while the peg is warm; PH time
      Tue-Thu 8-9am, 12-1pm, or 7-9pm.
- [ ] Tag energy journalists / ICSC / PCIJ in a follow-up comment, never as an accusation.
