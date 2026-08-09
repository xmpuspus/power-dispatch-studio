# EXECUTE plan: the 90-minute workshop, run as a participant

Target: https://power-dispatch-studio.vercel.app (bundle e78ca2e6c8fbd75a)
        power-dispatch-studio 0.2.1 from PyPI, clean venv

## Blast radius (Gate 1)

| Action | Class | Note |
| --- | --- | --- |
| Open a deep link, read a view | SAFE | read only |
| Move a slider, press Run | SAFE | browser state only, no upload |
| pip install into /tmp venv | SAFE | local |
| run examples/03 writing sweep.csv | SAFE | writes into the run dir, not the repo |
| No PAID or IRREVERSIBLE action exists on this target | | |

Nothing here writes shared state, so Gate 2 has nothing to snapshot.

## Checks

Task 1, site a 300 MW load
  C1  #v=siting opens Siting a new load, and names a site with an hourly figure
  C2  #v=load-sweep opens Price as demand grows, and the curve has a bend
  C3  #v=quick-scenario adds 300 MW to Luzon and the price moves
  C4  examples/03_sweep_the_window.py sweep.csv 10 runs and writes 40 rows

Task 2, price the loss of one large unit
  C5  #v=n-1 names a unit and a price move
  C6  #v=reliability shows a shortfall chance per grid
  C7  the Python snippet runs and prints two prices
  C8  the snippet's -647 MW is one Sual unit, and the text says so

Task 3, a spot change into a bill
  C9  #v=bill-impact shows the share of the bill spot can reach
  C10 the bill line moves when the spot price changes
  C11 #v=backcast shows the model's own error

Closing
  C12 the analyst page lists the limits the closing asks the room to read
  C13 the closing says two limits carry a measurement, and both do
  C14 docs/data-contract.md and docs/scenario-schema.md exist and are reachable

Instructor notes
  C15 every deep link in the file resolves to the view it names
  C16 the studio still solves after a hard reload with no network to the archive
