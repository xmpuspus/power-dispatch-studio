// Backcast: the trust artifact. Every full-coverage market day replayed with the
// BASE model against the observed hourly LWAP, error stated, nothing tuned. The
// gap (scarcity, offers, caps, outages the model cannot see) is the finding.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php, pct } from '../lib/data'
import { Panel, StatTile } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { HourLines } from './charts'
import { runChronology } from './chrono'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function BackcastView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const bc = profiles.backcast
  const marketDays = useMemo(
    () =>
      profiles.days.filter(
        (x) =>
          x.market &&
          GRIDS.every(
            (g) =>
              (x.lwap?.[g] ?? []).length === 24 && x.lwap![g]!.every((v) => v != null)
          )
      ),
    [profiles.days]
  )
  const [date, setDate] = useState(
    () => profiles.default_day ?? marketDays[marketDays.length - 1]?.date
  )
  const day = marketDays.find((x) => x.date === date) ?? marketDays[0]
  // base model, no levers, no storage cycling: the same run the baked stats score
  const run = useMemo(
    () => (day ? runChronology(d, profiles, day.date, {}) : null),
    [d, profiles, day]
  )

  if (!bc.available || !day || !run)
    return (
      <div className="view">
        <Panel title="Backcast" subtitle="Model vs observed prices.">
          <p className="note">No full-coverage market day in the archive window yet.</p>
        </Panel>
      </div>
    )

  const stats = bc.per_grid[grid]
  const residual = day.lwap![grid]!.map((obs, h) =>
    obs == null ? null : obs - run.hours[h].price[grid]
  )
  const peakResid = residual.slice(17, 22).filter((v): v is number => v != null)
  const peakResidMean = peakResid.length
    ? peakResid.reduce((s, v) => s + v, 0) / peakResid.length
    : null

  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Grid', render: (g) => cap(g) },
    {
      key: 'obs',
      header: 'Observed mean',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.observed_mean_php_kwh),
    },
    {
      key: 'mod',
      header: 'Modeled mean',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.modeled_mean_php_kwh),
    },
    {
      key: 'mae',
      header: 'MAE',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.mae_php_kwh),
    },
    {
      key: 'bias',
      header: 'Bias',
      align: 'right',
      mono: true,
      render: (g) => php(bc.per_grid[g]?.bias_php_kwh),
    },
    {
      key: 'corr',
      header: 'Correlation',
      align: 'right',
      mono: true,
      render: (g) => num(bc.per_grid[g]?.correlation ?? NaN, 2),
    },
    {
      key: 'hit',
      header: 'High-hour hit rate',
      align: 'right',
      mono: true,
      render: (g) => {
        const v = bc.per_grid[g]?.high_hour_hit_rate_pct
        return v == null ? 'n/a (flat model)' : pct(v / 100, 0)
      },
    },
  ]

  return (
    <div className="view">
      <div className="stat-row">
        <StatTile
          label={`MAE, ${cap(grid)}`}
          value={php(stats?.mae_php_kwh)}
          hint={`${bc.days} market days, hourly`}
        />
        <StatTile
          label="Bias"
          value={php(stats?.bias_php_kwh)}
          hint="model minus observed; negative = under-priced"
        />
        <StatTile
          label="Correlation"
          value={num(stats?.correlation ?? NaN, 2)}
          hint="hourly, whole window"
        />
        <StatTile
          label={`Evening residual, ${date}`}
          value={peakResidMean == null ? '-' : php(peakResidMean)}
          hint="observed minus modeled, hours 17-21"
          tone={peakResidMean != null && peakResidMean > 2 ? 'danger' : 'default'}
        />
      </div>

      <Panel
        title="Model vs observed, whole market window"
        subtitle={`Every full-coverage market day since ${bc.window?.from} replayed with the base model. Nothing tuned; the residual is the finding.`}
      >
        <DataGrid columns={cols} rows={GRIDS} getKey={(g) => g} />
        <p className="note">{bc.high_hour_note}</p>
      </Panel>

      <Panel
        title={`One day against the tape, ${cap(grid)}`}
        subtitle="Base model (no edits, no storage cycling) against the observed hourly LWAP."
      >
        <div className="chrono__controls">
          <label className="chrono__ctl">
            Market day
            <select
              className="ribbon__select"
              value={day.date}
              onChange={(e) => setDate(e.target.value)}
              aria-label="Backcast day"
            >
              {marketDays.map((x) => (
                <option key={x.date} value={x.date}>
                  {x.date}
                </option>
              ))}
            </select>
          </label>
        </div>
        <HourLines
          series={[
            {
              label: 'modeled',
              color: 'var(--series-modeled)',
              pts: run.hours.map((h) => h.price[grid]),
            },
            {
              label: 'observed',
              color: 'var(--series-observed)',
              pts: day.lwap![grid]!,
              dash: '4 3',
            },
          ]}
        />
      </Panel>

      <p className="note">{bc.note}</p>
    </div>
  )
}
