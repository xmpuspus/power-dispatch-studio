// Scenario ensembles (roadmap item 5): a seeded Monte Carlo of joint draws
// (data-center load, hydrology, fuel price, a forced outage) through the day
// chronology, shown as a price distribution per grid. This is a scenario
// ensemble on ONE observed day, not a forecast: the draws span the plausible
// operating states, the seed makes it reproducible.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { php } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { runEnsemble, type GridDist } from './ensembles'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

interface DistRow {
  grid: GridKey
  dist: GridDist
}

export function EnsembleView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const marketDays = useMemo(
    () => profiles.days.filter((x) => x.market).map((x) => x.date),
    [profiles]
  )
  const [date, setDate] = useState(marketDays[marketDays.length - 1] ?? '')
  const [nDraws, setNDraws] = useState(60)
  const seed = 1

  const result = useMemo(
    () => (date ? runEnsemble(d, profiles, date, nDraws, seed) : null),
    [d, profiles, date, nDraws]
  )

  if (!marketDays.length)
    return (
      <div className="view">
        <Panel title="Scenario ensembles" subtitle="Price distribution from joint draws.">
          <EmptyNote>No market day available to run an ensemble on.</EmptyNote>
        </Panel>
      </div>
    )

  const rows: DistRow[] = GRIDS.map((g) => ({ grid: g, dist: result!.perGrid[g] }))
  const cols: Column<DistRow>[] = [
    { key: 'grid', header: 'Grid', render: (r) => cap(r.grid) },
    {
      key: 'p10',
      header: 'P10',
      align: 'right',
      mono: true,
      render: (r) => php(r.dist.p10),
    },
    {
      key: 'p50',
      header: 'Median',
      align: 'right',
      mono: true,
      render: (r) => php(r.dist.p50),
    },
    {
      key: 'p90',
      header: 'P90',
      align: 'right',
      mono: true,
      render: (r) => php(r.dist.p90),
    },
    {
      key: 'mean',
      header: 'Mean',
      align: 'right',
      mono: true,
      render: (r) => php(r.dist.mean),
    },
  ]
  const sel = result!.perGrid[grid]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Day
          <select
            className="ribbon__select"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Observed day to run the ensemble on"
          >
            {marketDays.map((dt) => (
              <option key={dt} value={dt}>
                {dt}
              </option>
            ))}
          </select>
        </label>
        <label className="chrono__ctl">
          Draws
          <select
            className="ribbon__select"
            value={nDraws}
            onChange={(e) => setNDraws(Number(e.target.value))}
            aria-label="Number of Monte Carlo draws"
          >
            {[30, 60, 120].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Panel
        title={`Price ensemble, ${cap(grid)}`}
        subtitle={`${nDraws} seeded joint draws on ${date}: data-center load, hydrology, fuel price, and a forced coal outage, cleared through the day model.`}
      >
        <div className="stat-row">
          <StatTile label="P10" value={php(sel.p10)} hint="cheap draws" />
          <StatTile label="Median" value={php(sel.p50)} hint="middle of the ensemble" />
          <StatTile label="P90" value={php(sel.p90)} hint="tight draws" />
        </div>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.grid} />
        <p className="note">
          A scenario ensemble on one observed day, not a forecast. The band is the spread
          across plausible operating states (load, water, fuel, an outage), seeded so a
          re-run reproduces it. Prices are the day-mean clearing price per grid in
          PhP/kWh.
        </p>
      </Panel>
    </div>
  )
}
