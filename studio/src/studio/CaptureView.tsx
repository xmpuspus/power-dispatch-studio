// Capture prices: generation-weighted average price per technology for a
// saved run, the revenue signal a GEA or project analyst needs. A flat PPA
// misses the merit-order effect solar and wind create for themselves as more
// of them clear (their generation concentrates in the hours they set the
// price down).

import { useState } from 'react'
import type { GridKey } from '../lib/types'
import { fuelLabel, num, php } from '../lib/data'
import { Panel, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { capturePrices, type CaptureRow } from './insights'
import type { SavedRun } from './runs'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function CaptureView({ runsList, grid }: { runsList: SavedRun[]; grid: GridKey }) {
  const [runId, setRunId] = useState('')
  const withHours = runsList.filter((r) => r.hours.length > 0)
  const run = withHours.find((r) => r.id === runId) ?? withHours[0]

  if (!run)
    return (
      <div className="view">
        <Panel
          title="Capture prices"
          subtitle="Generation-weighted price per technology, for a saved run."
        >
          <EmptyNote>
            No saved run with hourly detail yet. Run a scenario first: open Chronology,
            configure a scenario and a window, and press Save run.
          </EmptyNote>
        </Panel>
      </div>
    )

  const rows = capturePrices(run.hours)
    .filter((r) => r.grid === grid)
    .sort((a, b) => b.gen_mwh - a.gen_mwh)

  const cols: Column<CaptureRow>[] = [
    { key: 'fuel', header: 'Fuel', render: (r) => fuelLabel(r.fuel) },
    {
      key: 'gen',
      header: 'Generation',
      align: 'right',
      mono: true,
      render: (r) => `${num(r.gen_mwh)} MWh`,
    },
    {
      key: 'cap',
      header: 'Capture price',
      align: 'right',
      mono: true,
      render: (r) => php(r.capture_price_php_kwh, 3),
    },
    {
      key: 'rate',
      header: 'Capture rate',
      align: 'right',
      mono: true,
      render: (r) =>
        r.capture_rate == null ? 'n/a' : `${Math.round(r.capture_rate * 100)}%`,
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Run
          <select
            className="ribbon__select"
            value={run.id}
            onChange={(e) => setRunId(e.target.value)}
            aria-label="Run to price"
          >
            {withHours.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Panel
        title={`Capture prices, ${cap(grid)}`}
        subtitle="Generation-weighted average price per technology over the run's window: sum(generation times price) divided by sum(generation)."
      >
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.fuel} />
      </Panel>

      <p className="note">
        Generation-weighted capture price per technology for the selected run, useful for
        GEA and project revenue analysis. Capture rate is the capture price divided by
        this run's time-average price on {cap(grid)}: below 100% means the technology
        earns less than the flat average, the usual solar and wind story as penetration
        rises.
      </p>
    </div>
  )
}
