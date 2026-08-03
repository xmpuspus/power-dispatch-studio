// One matrix shows each saved run's main measures. A second calculation changes
// one Quick setting at a time and ranks the selected grid's price change.

import { useMemo } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { num, php, useGenerators } from '../lib/data'
import { Panel, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { leverTornado } from './crossrun'
import { initLevers } from './levers'
import type { TrippableUnit } from './engine'
import type { SavedRun } from './runs'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

interface RunMetrics {
  name: string
  meanLuzon: number
  meanVisayas: number
  meanMindanao: number
  peakLuzon: number
  unserved: number
  rent: number
}

function metricsOf(run: SavedRun): RunMetrics {
  const s = run.summaries
  const n = s.length || 1
  const mean = (g: GridKey) => s.reduce((a, x) => a + x.meanPrice[g], 0) / n
  return {
    name: run.name,
    meanLuzon: mean('luzon'),
    meanVisayas: mean('visayas'),
    meanMindanao: mean('mindanao'),
    peakLuzon: Math.max(...s.map((x) => x.peakPrice.luzon)),
    unserved: s.reduce((a, x) => a + GRIDS.reduce((b, g) => b + x.unservedMwh[g], 0), 0),
    rent: s.reduce((a, x) => a + x.leyteRentMPhp + x.mvipRentMPhp, 0),
  }
}

export function CrossRunView({
  runsList,
  d,
  grid,
}: {
  runsList: SavedRun[]
  d: Dispatch
  grid: GridKey
}) {
  const gens = useGenerators()
  const units: TrippableUnit[] = useMemo(
    () =>
      (gens.data?.features ?? []).map((f) => ({
        name: f.properties.name,
        grid: f.properties.grid,
        fuel: f.properties.fuel,
        capacity_mw: f.properties.capacity_mw,
      })),
    [gens.data]
  )
  const bars = useMemo(
    () => leverTornado(d, initLevers(d, grid), units),
    [d, grid, units]
  )
  const maxAbs = Math.max(1e-6, ...bars.map((b) => Math.abs(b.deltaPhpKwh)))

  const rows = runsList.map(metricsOf)
  const cols: Column<RunMetrics>[] = [
    { key: 'name', header: 'Saved run', render: (r) => r.name },
    {
      key: 'ml',
      header: 'Mean Luzon',
      align: 'right',
      mono: true,
      render: (r) => php(r.meanLuzon),
    },
    {
      key: 'mv',
      header: 'Mean Visayas',
      align: 'right',
      mono: true,
      render: (r) => php(r.meanVisayas),
    },
    {
      key: 'mm',
      header: 'Mean Mindanao',
      align: 'right',
      mono: true,
      render: (r) => php(r.meanMindanao),
    },
    {
      key: 'pl',
      header: 'Peak Luzon',
      align: 'right',
      mono: true,
      render: (r) => php(r.peakLuzon),
    },
    {
      key: 'un',
      header: 'Unserved MWh',
      align: 'right',
      mono: true,
      render: (r) => num(r.unserved),
    },
    {
      key: 'rent',
      header: 'Rent M PhP',
      align: 'right',
      mono: true,
      render: (r) => r.rent.toFixed(2),
    },
  ]

  return (
    <div className="view">
      <Panel
        title="Each saved run keeps its own settings, so the gaps here are the settings you changed"
        subtitle="Prices, unmet demand, and constrained-link value for every saved run."
      >
        {rows.length ? (
          <DataGrid columns={cols} rows={rows} getKey={(_, i) => i} />
        ) : (
          <EmptyNote>
            No saved runs yet. Save an hourly market replay and it will appear here.
          </EmptyNote>
        )}
      </Panel>

      <Panel
        title={`Price effect of each quick what-if, ${cap(grid)}`}
        subtitle="Each setting changes by itself from the base case. The list is ranked by how far it moves this grid's clearing price."
      >
        <div className="tornado">
          {bars.map((b) => {
            const w = (Math.abs(b.deltaPhpKwh) / maxAbs) * 100
            const up = b.deltaPhpKwh >= 0
            return (
              <div className="tornado__row" key={b.lever}>
                <div className="tornado__label">
                  {b.label} <span className="tornado__step">{b.step}</span>
                </div>
                <div className="tornado__track">
                  <div
                    className={`tornado__bar tornado__bar--${up ? 'up' : 'down'}`}
                    style={{ width: `${w}%` }}
                  />
                </div>
                <div className="tornado__val mono">
                  {up ? '+' : ''}
                  {b.deltaPhpKwh.toFixed(3)}
                </div>
              </div>
            )
          })}
        </div>
        <p className="note">
          Price change in PhP/kWh at the evening reference hour. Positive raises the
          price, negative lowers it. The base case is the sourced fleet with no edits.
        </p>
      </Panel>
    </div>
  )
}
