// Window distribution: replay the ran scenario across EVERY full-coverage market
// day in the archive and read the outcome as a band, not a single day. The
// browser analog of a PLEXOS stochastic sample set: the sample is the archive's
// own observed days, nothing synthetic.

import { useMemo } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php } from '../lib/data'
import { Panel, StatTile } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { BandChart, DurationCurve } from './charts'
import { runChronology, type ChronoResult } from './chrono'
import { chronoOptsFrom, type ClassId, type ObjRow, type Overrides } from './model'
import { hourlyBand, pooledDuration, windowStats, type WindowStats } from './insights'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

function marketDaysOf(profiles: Profiles): string[] {
  return profiles.days
    .filter((x) => x.market && GRIDS.every((g) => (x.demand?.[g] ?? []).length === 24))
    .map((x) => x.date)
}

export function DistributionView({
  d,
  profiles,
  objects,
  overrides,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  grid: GridKey
}) {
  const dates = useMemo(() => marketDaysOf(profiles), [profiles])
  const opts = useMemo(() => chronoOptsFrom(objects, overrides), [objects, overrides])
  const runs = useMemo<ChronoResult[]>(
    () => dates.map((dt) => runChronology(d, profiles, dt, opts)),
    [d, profiles, dates, opts]
  )
  // the base model across the same days, for the dashed comparison line
  const baseRuns = useMemo<ChronoResult[]>(
    () => dates.map((dt) => runChronology(d, profiles, dt, {})),
    [d, profiles, dates]
  )

  if (!dates.length)
    return (
      <div className="basecase-banner">
        No full-coverage market day in the archive window yet.
      </div>
    )

  const edited = Object.keys(overrides).length > 0
  const band = hourlyBand(runs, grid)
  const baseMedian = hourlyBand(baseRuns, grid).map((b) => b.p50)
  const stats = windowStats(runs, grid)
  const baseStats = windowStats(baseRuns, grid)
  const rents = runs.map((r) => r.summary.leyteRentMPhp + r.summary.mvipRentMPhp)
  const rentTotal = rents.reduce((s, v) => s + v, 0)
  const unserved = runs.reduce(
    (s, r) => s + GRIDS.reduce((a, g) => a + r.summary.unservedMwh[g], 0),
    0
  )

  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Grid', render: (g) => cap(g) },
    ...(['p10', 'p50', 'p90'] as (keyof WindowStats)[]).map((p) => ({
      key: p as string,
      header: `${(p as string).toUpperCase()} daily mean`,
      align: 'right' as const,
      mono: true,
      render: (g: GridKey) => php(windowStats(runs, g)[p] as number),
    })),
    {
      key: 'max',
      header: 'Dearest day',
      align: 'right',
      mono: true,
      render: (g) => {
        const s = windowStats(runs, g)
        return `${php(s.max)} (${s.maxDate.slice(5)})`
      },
    },
  ]

  return (
    <div className="view">
      <div className="stat-row">
        <StatTile
          label={`Median daily mean, ${cap(grid)}`}
          value={php(stats.p50)}
          hint={edited ? `base ${php(baseStats.p50)}` : 'base model'}
          tone={edited && stats.p50 > baseStats.p50 + 0.005 ? 'accent' : 'default'}
        />
        <StatTile
          label="P10 to P90 daily mean"
          value={`${php(stats.p10)} to ${php(stats.p90)}`}
          hint={`${num(stats.days)} market days replayed`}
        />
        <StatTile
          label="Unserved energy, window"
          value={num(unserved)}
          unit="MWh"
          tone={unserved > 0 ? 'danger' : 'positive'}
        />
        <StatTile
          label="Congestion rent, window"
          value={`₱${num(rentTotal, 1)}M`}
          hint="both corridors, all days"
        />
      </div>

      <Panel
        title={`Hourly price band, ${cap(grid)}`}
        subtitle={`The ran scenario replayed over all ${num(stats.days)} market days with full demand coverage. Shaded band spans the 10th to 90th percentile per hour; the dashed line is the base model's median.`}
      >
        <BandChart band={band} compare={edited ? baseMedian : undefined} />
      </Panel>

      <Panel
        title={`Scenario price duration, ${cap(grid)}`}
        subtitle="Every hour of every replayed day sorted dear to cheap, against the observed duration curve from the same window."
      >
        <DurationCurve
          modeled={pooledDuration(runs, grid)}
          observed={d.price_duration[grid]?.observed ?? []}
        />
      </Panel>

      <Panel
        title="Daily-mean distribution by grid"
        subtitle="Percentiles of the scenario's daily mean price across the replayed days."
      >
        <DataGrid columns={cols} rows={GRIDS} getKey={(g) => g} />
        <p className="note">
          The sample is the archive's own observed market days, replayed as-is on the ran
          scenario; nothing synthetic is drawn. A single day can flatter or damn a
          scenario, so read the band first and the dearest day second. The observed
          duration overlay carries the scarcity tail this cost model does not price; the
          Backcast view states that gap per grid.
        </p>
      </Panel>
    </div>
  )
}
