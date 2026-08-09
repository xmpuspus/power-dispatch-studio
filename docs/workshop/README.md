# Three tasks in 90 minutes, on a laptop with no license

Written for a class or a team session. Every task runs in a browser and again in
Python, so a participant sees the same number twice and learns that the two are
one engine. No account, no key, no install for the browser half.

Before the session, ask each person to do both of these. The browser half needs
only the first.

```bash
pip install power-dispatch-studio
git clone https://github.com/xmpuspus/power-dispatch-studio
```

The clone is for one step: `examples/` ships in the repository and not in the
package, so Task 1 step 4 needs it. Everything else in Python runs from the
installed package alone.

## Task 1, 25 minutes. Site a 300 MW load and find where it stops fitting

The question a data-center developer brings: can this site draw what it needs,
and what does that do to the price?

1. Open [Siting a new load](https://power-dispatch-studio.vercel.app/studio/#v=siting).
   Pick a named site and read the hourly load it can draw through its own lines.
2. Open [Price as demand grows](https://power-dispatch-studio.vercel.app/studio/#v=load-sweep).
   It opens on the +1,500 MW range, where the line is flat. Ask the room why a
   flat line is the answer to a real question, then press **to +3,000 MW** and
   find the step. The "Price holds for another" tile names the MW that separates
   the two.
3. Open [Quick what-if](https://power-dispatch-studio.vercel.app/studio/#v=quick-scenario)
   and drag the data-center lever to 300 MW. The price does not move, and the
   levers preview live, so Run correctly stays disabled. Now drag to 2,500 MW and
   watch it step. That contrast is the lesson: a small load is free until the
   block that sets the price runs out.
4. In Python, from the clone, run the same thing across every recorded day:

```bash
python3 examples/03_sweep_the_window.py sweep.csv 10
```

Discussion: one day is not the answer. The bend moves with the day's supply.

## Task 2, 25 minutes. Price the loss of one large unit

1. Open [Loss of one major unit](https://power-dispatch-studio.vercel.app/studio/#v=n-1).
   Read which unit moves the price most, and by how much.
2. Open [Power-shortfall risk](https://power-dispatch-studio.vercel.app/studio/#v=reliability).
   Note that a shortfall chance is not a brownout forecast, and say why.
3. Reproduce the trip in Python by removing the unit's capacity from the stack:

```python
import power_dispatch as pd
day = pd.list_days()[-1]
base = pd.run_scenario({"date": day, "opts": {}})
trip = pd.run_scenario({"date": day,
                        "opts": {"fuel_avail_delta": {"luzon": {"coal": -647}}}})
print(base["summary"]["mean_price"]["luzon"], trip["summary"]["mean_price"]["luzon"])
```

Discussion: the model removes capacity, not a plant. Ask what that misses.

## Task 3, 25 minutes. Follow a spot-price change into a household bill

1. Open [Bill impact](https://power-dispatch-studio.vercel.app/studio/#v=bill-impact).
   Read the share of the bill that spot price can reach.
2. Change the spot price and watch the bill line. Note how small the move is.
3. Open [Historical replay](https://power-dispatch-studio.vercel.app/studio/#v=backcast)
   and read the model's own error before quoting any of it.

Discussion: a wholesale percent is not a bill percent. Anyone who reports one as
the other makes the most common error in this subject.

## Closing, 15 minutes. What this model refuses to do

Read the four limits on
[the analyst page](https://power-dispatch-studio.vercel.app/for-analysts.html)
together. Two of them carry a measurement rather than an opinion: the
unit-commitment test, and the loss surface that validates in two grids and fails
in the third.

Ask each participant to name one question their own work needs that this model
cannot answer. That list is more useful than the session.

## For the instructor

- Every link above is a deep link, so a slide can open the exact view.
- The studio solves in the browser, so a room with weak wifi still works after
  the first load.
- `docs/data-contract.md` is the follow-on for anyone who wants to point the
  engine at their own system.
- `docs/scenario-schema.md` is the follow-on for anyone who wants to script it.
