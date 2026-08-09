// A whole future year, solved day by day, read back as a summary.
//
// The browser never solves 366 days: pipeline/future_year.py builds the year as
// a data directory the same engine reads, solves it, and writes the summary this
// view displays. Every input is a published plan, so this is a scenario and
// never a forecast.

import type { FutureYear, GridKey } from '../lib/types'
import { useFutureYear } from '../lib/data'
import { Panel, StatTile, EmptyNote, Source } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const php = (v: number) => `P${v.toFixed(2)}`

/** Daily mean and evening price across the year, one line each. */
function YearLines({ d, grid }: { d: FutureYear; grid: GridKey }) {
  const W = 640
  const H = 200
  const padL = 42
  const padR = 10
  const padT = 12
  const padB = 26
  const days = d.series
  const mean = days.map((x) => x.mean_price[grid])
  const eve = days.map((x) => x.evening_price[grid])
  const lo = Math.min(...mean, ...eve)
  const hi = Math.max(...mean, ...eve)
  // 6 percent of headroom at each end: the evening line often sits on the
  // plateau, and a line drawn along the top gridline reads as clipped
  const raw = Math.max(hi - lo, 0.5)
  const span = raw * 1.12
  const mid = hi - lo >= 0.5 ? (lo + hi) / 2 : (lo + hi) / 2
  const base = mid - span / 2
  const X = (i: number) => padL + ((W - padL - padR) * i) / (days.length - 1 || 1)
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - base) / span)
  const path = (vals: number[]) =>
    vals.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  const ticks = [base + span, base + span / 2, base]
  // one label per quarter: 366 date labels would be a grey smear
  const marks = [0, 91, 182, 274].filter((i) => i < days.length)
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="yearlines"
      role="img"
      aria-label={`Daily mean and evening clearing price across ${d.year} in ${cap(grid)}`}
    >
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={Y(t)} x2={W - padR} y2={Y(t)} className="chart__gridline" />
          <text x={padL - 6} y={Y(t) + 4} className="chart__ax" textAnchor="end">
            {php(t)}
          </text>
        </g>
      ))}
      <polyline
        points={path(mean)}
        fill="none"
        stroke="var(--series-modeled)"
        strokeWidth={1.4}
      />
      <polyline points={path(eve)} fill="none" stroke="var(--accent)" strokeWidth={1.8} />
      {marks.map((i) => (
        <text key={i} x={X(i)} y={H - 6} className="chart__ax" textAnchor="middle">
          {days[i].date.slice(5)}
        </text>
      ))}
    </svg>
  )
}

export function FutureYearView({ grid }: { grid: GridKey }) {
  const q = useFutureYear()
  if (q.loading) return <EmptyNote>Loading the solved year.</EmptyNote>
  if (!q.data)
    return (
      <EmptyNote>
        No future year in this build. Run <code>make future YEAR=2028</code> to write one.
      </EmptyNote>
    )
  const d = q.data
  const m = d.meta
  const ratio = m.demand.ratio_per_grid[grid]
  const shortDays = d.days_with_unserved_load[grid]

  const addRows = Object.entries(m.supply.added_stack_mw[grid] ?? {}).sort(
    (a, b) => b[1] - a[1]
  )
  const addCols: Column<[string, number]>[] = [
    { key: 'fuel', header: 'Fuel', render: (x) => x[0].replace(/_/g, ' ') },
    {
      key: 'mw',
      header: 'MW added by this year',
      align: 'right',
      mono: true,
      render: (x) => x[1].toLocaleString('en-US'),
    },
  ]

  return (
    <div className="view">
      <Panel
        title={
          shortDays > 0
            ? `${cap(grid)} leaves load unserved on ${shortDays} of ${d.days_solved} days in ${d.year}`
            : `${cap(grid)} covers every one of its ${d.days_solved} days in ${d.year}, on this build list`
        }
        subtitle={
          `Every date in ${d.year} solved on its own, with demand grown by the ` +
          `Department of Energy's own peak path and supply raised by its published ` +
          `project list. A scenario built from plans, never a forecast.`
        }
        right={<Source href={m.demand.src} label="demand path" />}
      >
        <div className="stat-row">
          <StatTile
            label={`Peak demand, ${d.year}`}
            value={Math.round(d.peak_demand_mw[grid]).toLocaleString('en-US')}
            unit="MW"
            hint={`${((ratio - 1) * 100).toFixed(1)} percent above the ${m.base_year} recorded shape`}
          />
          <StatTile
            label="Mean price across the year"
            value={php(d.mean_price_php_kwh[grid])}
            unit="/kWh"
          />
          <StatTile
            label="Mean price, 6pm to 9pm"
            value={php(d.evening_price_php_kwh[grid])}
            unit="/kWh"
            hint="Solar is near zero here, so this is where firm capacity shows"
            tone="accent"
          />
          <StatTile
            label="Days that leave load unserved"
            value={`${shortDays} of ${d.days_solved}`}
            tone={shortDays > 0 ? 'danger' : 'positive'}
          />
        </div>
        <div className="legend">
          <span className="legend__item">
            <i style={{ background: 'var(--series-modeled)' }} />
            daily mean
          </span>
          <span className="legend__item">
            <i style={{ background: 'var(--accent)' }} />
            6pm to 9pm mean
          </span>
        </div>
        <YearLines d={d} grid={grid} />
        <p className="note">{m.label}</p>
      </Panel>

      <Panel
        title={`The build list adds ${Math.round(
          Object.values(m.supply.added_stack_mw[grid] ?? {}).reduce((s, v) => s + v, 0) +
            m.supply.added_solar_mw[grid]
        ).toLocaleString('en-US')} MW to ${cap(grid)} by ${d.year}, and retires nothing`}
        subtitle={`Projects from the published list whose target year falls at or before ${d.year}. Status included: ${m.supply.status_included.join(', ')}. List as of ${m.supply.as_of}.`}
      >
        <DataGrid
          columns={addCols}
          rows={addRows}
          getKey={(x) => x[0]}
          empty="No dispatchable projects reach this grid by this year."
        />
        <div className="stat-row">
          <StatTile
            label="Solar added"
            value={Math.round(m.supply.added_solar_mw[grid]).toLocaleString('en-US')}
            unit="MW"
            hint="Carried apart from the stack and derated hour by hour"
          />
          <StatTile
            label="Storage projects listed"
            value={Math.round(m.supply.storage_projects_mw[grid]).toLocaleString('en-US')}
            unit="MW"
            hint="Reported and not dispatched. Add storage as a scenario lever"
          />
        </div>
        <p className="note">
          Retirements: {m.supply.retirements}. A fleet that never retires reads optimistic
          about supply, so treat the spare capacity here as a ceiling.
        </p>
      </Panel>

      <Panel
        title="Four assumptions carry this year, and each one names its owner"
        subtitle="Change any of them and the year changes. They are inputs, not results."
      >
        <ul className="assum">
          <li>
            <b>Demand.</b> {m.demand.method}. Owner {m.demand.owner}, {m.demand.plan}.
            Ratio for {cap(grid)}: {ratio.toFixed(4)}.
          </li>
          <li>
            <b>Supply.</b> {m.supply.method}, list as of {m.supply.as_of}.
          </li>
          <li>
            <b>Links.</b>{' '}
            {Object.keys(m.links.added_mw).length
              ? Object.entries(m.links.added_mw)
                  .map(([k, v]) => `${k} plus ${v} MW`)
                  .join(', ')
              : 'no link upgrade reaches this year'}
            .
          </li>
          <li>
            <b>Calendar.</b> {m.calendar.days} dates, and {m.calendar.method}.
          </li>
        </ul>
      </Panel>
    </div>
  )
}
