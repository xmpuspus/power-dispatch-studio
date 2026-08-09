---
title: 'Power Dispatch Studio: an open production-cost model of the Philippine spot electricity market, checked against published prices'
tags:
  - Python
  - TypeScript
  - electricity markets
  - power systems
  - linear programming
  - Philippines
authors:
  - name: Xavier Puspus
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent researcher
    index: 1
date: 8 August 2026
bibliography: paper.bib
---

# Summary

Power Dispatch Studio replays the Philippine Wholesale Electricity Spot Market
(WESM) on a three-zone economic dispatch, tests scenarios against it, and reports
its own error against published prices. It runs in a browser with no license and
no install, as a Python package, and as a repository that rebuilds every figure
from committed public files.

The model clears Luzon, Visayas, and Mindanao together as one linear program.
It carries transfer limits on the two high-voltage direct-current links, storage
state of charge, co-optimized reserve, a daily hydro energy budget, and a value
of lost load set at the published market offer cap. The Python reference engine
and the browser engine construct the same linear program as the same text, byte
for byte, and a test pins its hash, so "the browser runs the same model" is a
check rather than a claim.

# Statement of need

Production-cost models decide where transmission gets built and what a
connection costs, and the tools that run them are licensed. In the Philippines
that puts the analysis out of reach of the people who most need to check it:
university researchers, agency staff without a seat, non-government analysts, and
industrial buyers negotiating a supply contract. The market operator publishes
enough to rebuild a simplified version of that analysis, and nobody did it until
now.

Three properties separate this from a teaching model. First, its inputs are the
market operator's own files, archived daily, including the 5-minute records that
name transmission equipment at a binding limit. Second, it publishes its error:
replaying the operator's own offer book reproduces recorded hourly prices with a
correlation between 0.69 and 0.86 across the three grids, and the tables state
the bias that remains. Third, its limits are measured rather than asserted. A
mixed-integer unit-commitment variant was built, priced, and scored; it lowered
the price correlation in all five scored series, so the linear model stays the
default and the measurement is published beside the claim.

The project is deliberately not a replacement for a utility planning model. It
holds fuel blocks per zone rather than named units, it has no network model below
the island grid, and each day solves on its own. Those five limits are stated on
the front page, and each one carries the reason it exists.

# Functionality

The Python package exposes one call:

```python
import power_dispatch as pd
result = pd.run_scenario({"date": "2026-06-17",
                          "opts": {"demand_delta": {"luzon": 1500}}})
```

A scenario is a versioned file that the browser writes and the command line
reads, so an analyst can drag a slider, download the run, and re-run it in a
notebook. The engine reads a directory of two documented files, so pointing it at
a different directory models a different system: the same code runs a synthetic
future year built from the national demand plan and the published project list,
and it runs a hand-written two-fuel system in thirty lines.

The browser application carries 41 views addressable as deep links, including
historical replay against recorded prices, loss of load probability across
sampled forced outages, capture prices by technology, market concentration, and a
reduced nodal loss surface validated per grid.

# Reproducibility

Every published figure derives from committed raw files. The narrative numbers in
the README, the method page, and the analyst page regenerate nightly from the
data build through a claims oracle, which fails the build when prose and data
disagree. The archive is the git history: the operator's public window rolls at
90 days, and the repository preserves each day on the date it arrives.

# Acknowledgements

Market data comes from the Independent Electricity Market Operator of the
Philippines. Network geometry comes from OpenStreetMap contributors under the
Open Database License. Capacity and demand plans come from the Department of
Energy and the National Grid Corporation of the Philippines. The solver is
HiGHS [@huangfu2018].

# References
