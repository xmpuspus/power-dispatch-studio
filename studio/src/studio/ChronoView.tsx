// Chronology view: replay an observed day (or the week ending on it) hour by
// hour on the current edited model. Prices, dispatch by fuel, storage state of
// charge, and the run's own duration curve all come out of the run, live.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php, fuelLabel } from '../lib/data'
import { Panel, Segmented, StatTile } from '../ui/kit'
import { DurationCurve, DispatchArea, HourLines, SocChart } from './charts'
import { ENGINE_VERSION, runChronology, runDuration, type ChronoHour } from './chrono'
import { chronoOptsFrom, type ClassId, type ObjRow, type Overrides } from './model'
import { downloadCsv, encodeShare, runCsv, saveRun, type SavedRun } from './runs'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const GRID_COLOR: Record<GridKey, string> = {
  luzon: 'var(--primary)',
  visayas: 'var(--accent)',
  mindanao: 'var(--series-flow)',
}

export function ChronologyView({
  d,
  profiles,
  objects,
  overrides,
  grid,
  scenarioName,
  date,
  span,
  onDate,
  onSpan,
  onSaved,
}: {
  d: Dispatch
  profiles: Profiles
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  grid: GridKey
  scenarioName: string
  date: string
  span: 'day' | 'week'
  onDate: (d: string) => void
  onSpan: (s: 'day' | 'week') => void
  onSaved: (runs: SavedRun[]) => void
}) {
  const days = profiles.days
  const [flash, setFlash] = useState<string | null>(null)
  const [reserveDeduction, setReserveDeduction] = useState(false)
  const opts = useMemo(() => {
    const o = chronoOptsFrom(objects, overrides)
    if (reserveDeduction) o.reserve_deduction = true
    return o
  }, [objects, overrides, reserveDeduction])
  const reserveMw = Math.round(
    Object.values(profiles.reserve_req_mean_mw).reduce(
      (s, per) => s + Object.values(per).reduce((a, v) => a + v, 0),
      0
    )
  )

  const windowDates = useMemo(() => {
    const idx = days.findIndex((x) => x.date === date)
    if (idx < 0) return []
    return span === 'day'
      ? [days[idx].date]
      : days.slice(Math.max(0, idx - 6), idx + 1).map((x) => x.date)
  }, [days, date, span])

  const runs = useMemo(
    () => windowDates.map((dt) => runChronology(d, profiles, dt, opts)),
    [d, profiles, windowDates, opts]
  )
  const hours: ChronoHour[] = useMemo(() => runs.flatMap((r) => r.hours), [runs])
  if (!hours.length) return null

  const marks =
    runs.length > 1
      ? runs.map((r, i) => ({ x: i * 24, label: r.summary.date.slice(5) }))
      : []
  const priceSeries = (Object.keys(GRID_COLOR) as GridKey[]).map((g) => ({
    label: cap(g),
    color: GRID_COLOR[g],
    pts: hours.map((h) => h.price[g]),
  }))
  // observed overlay: the archive's hourly LWAP for the same window, dashed
  const observed = windowDates.flatMap(
    (dt) => days.find((x) => x.date === dt)?.lwap?.[grid] ?? Array(24).fill(null)
  )
  if (observed.some((v) => v != null))
    priceSeries.push({
      label: 'observed',
      color: 'var(--series-observed)',
      pts: observed,
      dash: '4 3',
    } as (typeof priceSeries)[number])

  const meanPrice = runs.reduce((s, r) => s + r.summary.meanPrice[grid], 0) / runs.length
  const peakPrice = Math.max(...runs.map((r) => r.summary.peakPrice[grid]))
  const unserved = runs.reduce(
    (s, r) =>
      s +
      r.summary.unservedMwh.luzon +
      r.summary.unservedMwh.visayas +
      r.summary.unservedMwh.mindanao,
    0
  )
  const rentM = runs.reduce(
    (s, r) => s + r.summary.leyteRentMPhp + r.summary.mvipRentMPhp,
    0
  )
  const hasStorage = (opts.storage ?? []).length > 0
  const storageEnergy = (opts.storage ?? []).reduce((s, x) => s + x.energy_mwh, 0)
  const marginalNow = hours[19]?.marginal[grid]

  const note = (msg: string) => {
    setFlash(msg)
    window.setTimeout(() => setFlash(null), 1800)
  }
  const save = () => {
    onSaved(
      saveRun({
        id: crypto.randomUUID(),
        name: `${scenarioName} (${Object.keys(overrides).length} edits), ${date}${
          span === 'week' ? ' week' : ''
        }`,
        savedAt: new Date().toISOString(),
        scenarioName,
        overrides,
        date,
        span,
        engineVersion: ENGINE_VERSION,
        hours,
        summaries: runs.map((r) => r.summary),
      })
    )
    note('Run saved')
  }
  const exportCsv = () => {
    downloadCsv(
      `gridbill-${date}${span === 'week' ? '-week' : ''}.csv`,
      runCsv(hours, windowDates)
    )
  }
  const copyLink = () => {
    const hash = encodeShare({ overrides, scenarioName, date, span })
    window.history.replaceState(null, '', hash)
    void navigator.clipboard?.writeText(
      `${window.location.origin}${window.location.pathname}${hash}`
    )
    note('Link copied')
  }

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Observed day
          <select
            className="ribbon__select"
            value={date}
            onChange={(e) => onDate(e.target.value)}
            aria-label="Observed day to replay"
          >
            {days.map((x) => (
              <option key={x.date} value={x.date}>
                {x.date}
                {x.date === profiles.default_day ? ' (widest swing)' : ''}
                {x.date === profiles.stress_day ? ' (demand peak)' : ''}
                {x.market ? '' : ' (administered)'}
              </option>
            ))}
          </select>
        </label>
        <Segmented
          ariaLabel="Run window"
          value={span}
          onChange={(v) => onSpan(v as 'day' | 'week')}
          options={[
            { value: 'day', label: 'Day' },
            { value: 'week', label: 'Week ending' },
          ]}
        />
        <label className="chrono__reserve">
          <input
            type="checkbox"
            checked={reserveDeduction}
            onChange={(e) => setReserveDeduction(e.target.checked)}
          />
          Reserve co-clear ({num(reserveMw)} MW withheld)
        </label>
        <div className="chrono__actions">
          <button className="btn btn--ghost btn--sm" onClick={save}>
            Save run
          </button>
          <button className="btn btn--ghost btn--sm" onClick={exportCsv}>
            Export CSV
          </button>
          <button className="btn btn--ghost btn--sm" onClick={copyLink}>
            Copy link
          </button>
          {flash && <span className="chrono__flash">{flash}</span>}
        </div>
      </div>

      <div className="stat-row">
        <StatTile
          label={`Mean price, ${cap(grid)}`}
          value={php(meanPrice)}
          hint={marginalNow ? `evening margin: ${fuelLabel(marginalNow)}` : undefined}
        />
        <StatTile label="Window peak" value={php(peakPrice)} />
        <StatTile
          label="Unserved energy"
          value={num(unserved)}
          unit="MWh"
          tone={unserved > 0 ? 'danger' : 'positive'}
        />
        <StatTile
          label="Congestion rent"
          value={`₱${num(rentM, 2)}M`}
          hint="both corridors, whole window"
        />
      </div>

      <Panel
        title="Hourly clearing price"
        subtitle={`The three grids cleared together, every hour of the ${
          span === 'day' ? 'observed day' : 'week'
        }. Observed LWAP dashed where the archive has it.`}
      >
        <HourLines series={priceSeries} marks={marks} />
      </Panel>

      <Panel
        title={`Dispatch by fuel, ${cap(grid)}`}
        subtitle="Merit-order energy per hour against the demand line. Solar follows the 24-hour shape; other fuels hold their derated availability."
      >
        <DispatchArea
          fuelGen={hours.map((h) => h.fuelGen[grid])}
          demand={hours.map((h) => h.demand[grid])}
          marks={marks}
        />
      </Panel>

      {hasStorage && (
        <Panel
          title="Storage state of charge"
          subtitle="Charge-cheap, discharge-dear heuristic walked through the day; the state resets each day. A labeled heuristic, not an optimisation."
        >
          <SocChart
            soc={hours.map((h) => h.socMwh)}
            charge={hours.map((h) => h.chargeMw)}
            discharge={hours.map((h) => h.dischargeMw)}
            energyMwh={storageEnergy}
          />
        </Panel>
      )}

      <Panel
        title={`Run price duration, ${cap(grid)}`}
        subtitle="Every hour of this run sorted dear to cheap. Computed from the run you just configured, not baked."
      >
        <DurationCurve modeled={runDuration(hours, grid)} />
      </Panel>

      <p className="note">
        Replays the archive's observed days: demand is dispatched generation per hour
        (IEMOP RTD regional summaries), replayed against the edited model. Region load
        edits shift demand flat across all 24 hours, the data-center shape. Reserve
        co-clear prices each hour at demand plus the mean scheduled reserve requirement
        (IEMOP RTD reserve rows), a labeled approximation of the co-optimised market.
        Block dispatch per hour with no inter-temporal optimisation. Not PLEXOS.
      </p>
    </div>
  )
}
