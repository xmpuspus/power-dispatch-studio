// Multi-year price path (roadmap item 13): a median price trajectory per policy
// scenario to 2040, composing the forward draws (item 1) with the Malampaya gas
// cliff (item 14) and the carbon price lever (item 15). Serves the NDC pathway
// and long PSA question: how the price path bends under the gas cliff and a
// carbon price. Not a forecast, one regime, same caveats as the forward band.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { php, useDemandPath } from '../lib/data'
import { Panel, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import {
  multiYearTrajectory,
  type PdpPath,
  type PolicyScenario,
  type TrajectoryPoint,
} from './forward'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const BASE_YEAR = 2026
const YEARS = [2026, 2028, 2030, 2032, 2034, 2036, 2038, 2040]
const COLORS = ['#3b7ea1', '#e0603a', '#2f9e6f']

const SCENARIOS: PolicyScenario[] = [
  { label: 'Base' },
  { label: 'Malampaya cliff', gasBudgetLuzonMwh: 20000 },
  { label: 'Carbon PhP2000/tCO2', carbonPhpPerTco2: 2000 },
]

export function MultiYearView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const pdp = useDemandPath()
  const [draws, setDraws] = useState(15)

  const paths = useMemo<TrajectoryPoint[][] | null>(() => {
    if (!pdp.data?.years || !pdp.data.per_grid_mw) return null
    const path: PdpPath = { years: pdp.data.years, per_grid_mw: pdp.data.per_grid_mw }
    return SCENARIOS.map((sc, i) =>
      multiYearTrajectory(d, profiles, path, BASE_YEAR, YEARS, sc, draws, 23 + i)
    )
  }, [d, profiles, pdp.data, draws])

  if (!paths)
    return (
      <div className="view">
        <Panel
          title="Multi-year price path"
          subtitle="A median price trajectory to 2040."
        >
          <EmptyNote>
            The DOE PDP demand path is unavailable, so the trajectory cannot be built.
          </EmptyNote>
        </Panel>
      </div>
    )

  const W = 800
  const H = 250
  const padL = 46
  const padB = 26
  const padT = 10
  const allVals = paths.flatMap((p) => p.map((pt) => pt.median[grid]))
  const lo = Math.min(0, ...allVals)
  const hi = Math.max(1, ...allVals) * 1.05
  const X = (yr: number) =>
    padL + ((yr - YEARS[0]) / (YEARS[YEARS.length - 1] - YEARS[0])) * (W - padL - 12)
  const Y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB)

  const rows = YEARS.map((yr) => ({ year: yr }))
  const cols: Column<{ year: number }>[] = [
    { key: 'yr', header: 'Year', render: (r) => String(r.year) },
    ...SCENARIOS.map((sc, i) => ({
      key: sc.label,
      header: sc.label,
      align: 'right' as const,
      mono: true,
      render: (r: { year: number }) => {
        const pt = paths[i].find((p) => p.year === r.year)
        return pt ? php(pt.median[grid]) : ''
      },
    })),
  ]

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
            {[10, 15, 30].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Panel
        title={`Multi-year price path, ${cap(grid)}, to 2040`}
        subtitle="Median clearing price per year under the PDP load path, split by policy scenario. Not a forecast."
      >
        <div className="fwdlegend">
          {SCENARIOS.map((sc, i) => (
            <span key={sc.label} className="fwdlegend__item">
              <i style={{ background: COLORS[i] }} /> {sc.label}
            </span>
          ))}
        </div>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="fwdchart"
          role="img"
          aria-label={`Multi-year ${grid} price path to 2040`}
        >
          <line x1={padL} y1={Y(lo)} x2={W - 12} y2={Y(lo)} className="chart__ax" />
          <text x={padL - 6} y={Y(hi)} textAnchor="end" className="chart__ax">
            ₱{hi.toFixed(0)}
          </text>
          <text x={padL - 6} y={Y(lo)} textAnchor="end" className="chart__ax">
            ₱{lo.toFixed(0)}
          </text>
          {paths.map((p, i) => (
            <polyline
              key={i}
              points={p
                .map((pt) => `${X(pt.year).toFixed(1)},${Y(pt.median[grid]).toFixed(1)}`)
                .join(' ')}
              fill="none"
              stroke={COLORS[i]}
              strokeWidth={2}
            />
          ))}
          {YEARS.filter((_, i) => i % 2 === 0).map((yr) => (
            <text key={yr} x={X(yr)} y={H - 8} textAnchor="middle" className="chart__ax">
              {yr}
            </text>
          ))}
        </svg>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.year} />
        <p className="note">
          Each line is the median of the same seeded observed-day draws under the DOE PDP
          load growth. The Malampaya cliff caps Luzon gas fuel energy; the carbon line
          adds a price per tonne to each fuel's cost. The fleet is held at today's, no new
          builds, so the lines flatten at the offer cap once the PDP load outgrows the
          current fleet: that saturation is itself the signal that expansion is needed.
          One regime and not a forecast: it is the trajectory observed days imply under
          the load path and each policy, the question a long PSA or an NDC pathway asks.
        </p>
      </Panel>
    </div>
  )
}
