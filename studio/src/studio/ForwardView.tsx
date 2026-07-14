// Forward price scenarios (roadmap item 1): a forward price band per year built
// by sampling the observed day library, applying the DOE PDP peak-demand growth,
// and drawing joint operating states through the day model. Never a forecast: a
// scenario ensemble on observed days, one regime because the library is a single
// post-suspension quarter.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { php, useDemandPath } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { forwardPath, type PdpPath, type YearBand } from './forward'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const BASE_YEAR = 2026
const YEARS = [2026, 2027, 2028, 2029, 2030]

export function ForwardView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const pdp = useDemandPath()
  const [draws, setDraws] = useState(30)

  const bands = useMemo<YearBand[] | null>(() => {
    if (!pdp.data?.years || !pdp.data.per_grid_mw) return null
    const path: PdpPath = { years: pdp.data.years, per_grid_mw: pdp.data.per_grid_mw }
    return forwardPath(d, profiles, path, BASE_YEAR, YEARS, draws, 11)
  }, [d, profiles, pdp.data, draws])

  if (!bands)
    return (
      <div className="view">
        <Panel
          title="Forward prices"
          subtitle="A price band per year from the observed library."
        >
          <EmptyNote>
            The DOE PDP demand path is unavailable, so the forward band cannot be built.
          </EmptyNote>
        </Panel>
      </div>
    )

  // band chart: P10-P90 area plus the P50 line across the years
  const W = 780
  const H = 240
  const padL = 46
  const padB = 26
  const padT = 10
  const vals = bands.flatMap((b) => [b.perGrid[grid].p10, b.perGrid[grid].p90])
  const lo = Math.min(0, ...vals)
  const hi = Math.max(1, ...vals) * 1.05
  const X = (i: number) => padL + (i / (bands.length - 1)) * (W - padL - 12)
  const Y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB)
  const areaTop = bands.map(
    (b, i) => `${X(i).toFixed(1)},${Y(b.perGrid[grid].p90).toFixed(1)}`
  )
  const areaBot = bands
    .map((b, i) => `${X(i).toFixed(1)},${Y(b.perGrid[grid].p10).toFixed(1)}`)
    .reverse()
  const area = `${areaTop.join(' ')} ${areaBot.join(' ')}`
  const median = bands
    .map((b, i) => `${X(i).toFixed(1)},${Y(b.perGrid[grid].p50).toFixed(1)}`)
    .join(' ')

  const rows = bands
  const cols: Column<YearBand>[] = [
    { key: 'yr', header: 'Year', render: (r) => String(r.year) },
    {
      key: 'g',
      header: 'PDP load growth',
      align: 'right',
      mono: true,
      render: (r) => `+${(r.demandGrowthMw[grid] ?? 0).toLocaleString('en-US')} MW`,
    },
    {
      key: 'p10',
      header: 'P10',
      align: 'right',
      mono: true,
      render: (r) => php(r.perGrid[grid].p10),
    },
    {
      key: 'p50',
      header: 'Median',
      align: 'right',
      mono: true,
      render: (r) => php(r.perGrid[grid].p50),
    },
    {
      key: 'p90',
      header: 'P90',
      align: 'right',
      mono: true,
      render: (r) => php(r.perGrid[grid].p90),
    },
  ]
  const last = bands[bands.length - 1].perGrid[grid]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Draws per year
          <select
            className="ribbon__select"
            value={draws}
            onChange={(e) => setDraws(Number(e.target.value))}
            aria-label="Draws per year"
          >
            {[20, 30, 60].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Panel
        title={`Forward price band, ${cap(grid)}, to ${YEARS[YEARS.length - 1]}`}
        subtitle="Observed days re-priced under the DOE PDP demand growth and joint operating draws. A scenario ensemble, not a forecast."
      >
        <div className="stat-row">
          <StatTile
            label={`${YEARS[YEARS.length - 1]} median`}
            value={php(last.p50)}
            hint="middle of the band"
          />
          <StatTile
            label={`${YEARS[YEARS.length - 1]} P90`}
            value={php(last.p90)}
            hint="tight draws"
          />
          <StatTile
            label="PDP load by 2030"
            value={`+${(bands[bands.length - 1].demandGrowthMw[grid] ?? 0).toLocaleString('en-US')} MW`}
            hint="vs 2026"
          />
        </div>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="fwdchart"
          role="img"
          aria-label={`Forward ${grid} price band to 2030`}
        >
          <line x1={padL} y1={Y(lo)} x2={W - 12} y2={Y(lo)} className="chart__ax" />
          <text x={padL - 6} y={Y(hi)} textAnchor="end" className="chart__ax">
            ₱{hi.toFixed(0)}
          </text>
          <text x={padL - 6} y={Y(lo)} textAnchor="end" className="chart__ax">
            ₱{lo.toFixed(0)}
          </text>
          <polygon points={area} className="fwdchart__band" />
          <polyline points={median} className="fwdchart__median" />
          {bands.map((b, i) => (
            <text
              key={b.year}
              x={X(i)}
              y={H - 8}
              textAnchor="middle"
              className="chart__ax"
            >
              {b.year}
            </text>
          ))}
        </svg>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.year} />
        <p className="note">
          One regime: the observed day library spans a single post-suspension quarter, so
          this carries seasonality from that quarter only and cannot be a forecast. It is
          a band of what observed days would clear at under the PDP load path and
          plausible operating states, the question a DU or IPP asks before a PSA or CSP
          bid. Every input traces to a source (the demand path is the DOE PDP peak
          forecast).
        </p>
      </Panel>
    </div>
  )
}
