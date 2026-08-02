// Repeated seeded simulations of joint inputs
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
        <Panel
          title="Price range across repeated simulations"
          subtitle="Each simulation changes demand, water, fuel price, and a plant outage together."
        >
          <EmptyNote>No market day available to run an ensemble on.</EmptyNote>
        </Panel>
      </div>
    )

  const rows: DistRow[] = GRIDS.map((g) => ({ grid: g, dist: result!.perGrid[g] }))
  const cols: Column<DistRow>[] = [
    { key: 'grid', header: 'Grid', render: (r) => cap(r.grid) },
    {
      key: 'p10',
      header: '10th percentile (P10)',
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
      header: '90th percentile (P90)',
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
          Repeated simulations
          <select
            className="ribbon__select"
            value={nDraws}
            onChange={(e) => setNDraws(Number(e.target.value))}
            aria-label="Number of repeated simulations"
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
        title={`Price range across ${nDraws} repeated simulations, ${cap(grid)}`}
        subtitle={`Each repeat on ${date} varies data-center demand, water availability, fuel price, and one forced coal outage. The results are repeatable.`}
      >
        <div className="stat-row">
          <StatTile
            label="10th percentile (P10)"
            value={php(sel.p10)}
            hint="lower-price result"
          />
          <StatTile label="Median" value={php(sel.p50)} hint="middle result" />
          <StatTile
            label="90th percentile (P90)"
            value={php(sel.p90)}
            hint="higher-price result"
          />
        </div>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.grid} />
        <p className="note">
          These are repeated scenarios on one recorded day, not a forecast. Eighty percent
          of the results fall between the 10th and 90th percentiles (P10 and P90). The
          calculation varies load, water, fuel, and one outage. Repeating the calculation
          gives the same sample. Prices are daily means in pesos per kWh.
        </p>
      </Panel>
    </div>
  )
}
