// Chronology view: replay an observed day (or the week ending on it) hour by
// hour on the current edited model. Prices, dispatch by fuel, storage state of
// charge, and the run's own duration curve all come out of the run, live.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php, fuelColor, fuelLabel, useOfferDay } from '../lib/data'
import { Panel, Segmented, StatTile } from '../ui/kit'
import { BindingStrip, DurationCurve, DispatchArea, HourLines, SocChart } from './charts'
import { ENGINE_VERSION, runChronology, runDuration, type ChronoHour } from './chrono'
import { bindingCounts, classifyHour } from './insights'
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
  importedKeys,
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
  importedKeys?: string[]
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
  // engine: the calibrated cost model, or the day's OBSERVED offer book
  // (every layer the book already embodies is off; demand lever stays)
  const [engine, setEngine] = useState<'cost' | 'offers'>('cost')
  const offer = useOfferDay(engine === 'offers' ? date : null)
  const opts = useMemo(() => {
    const o = chronoOptsFrom(objects, overrides)
    if (engine === 'offers') {
      const only: typeof o = { demand_delta: o.demand_delta }
      if (reserveDeduction) only.reserve_deduction = true
      if (offer.data) only.offer_day = offer.data
      return only
    }
    if (reserveDeduction) o.reserve_deduction = true
    return o
  }, [objects, overrides, reserveDeduction, engine, offer.data])
  const reserveMw = Math.round(
    Object.values(profiles.reserve_req_mean_mw).reduce(
      (s, per) => s + Object.values(per).reduce((a, v) => a + v, 0),
      0
    )
  )

  const day = days.find((x) => x.date === date)
  const hb = day?.hydro_budget_mwh
  const hbTotal = hb ? (hb.luzon ?? 0) + (hb.visayas ?? 0) + (hb.mindanao ?? 0) : 0

  const windowDates = useMemo(() => {
    const idx = days.findIndex((x) => x.date === date)
    if (idx < 0) return []
    // the offer book is per day; the week window stays a cost-model view
    return span === 'day' || engine === 'offers'
      ? [days[idx].date]
      : days.slice(Math.max(0, idx - 6), idx + 1).map((x) => x.date)
  }, [days, date, span, engine])

  const offerPending = engine === 'offers' && !opts.offer_day
  const runs = useMemo(
    () =>
      offerPending ? [] : windowDates.map((dt) => runChronology(d, profiles, dt, opts)),
    [d, profiles, windowDates, opts, offerPending]
  )
  const hours: ChronoHour[] = useMemo(() => runs.flatMap((r) => r.hours), [runs])
  if (offerPending)
    return (
      <div className="basecase-banner">
        {offer.loading
          ? 'Loading the day’s offer book.'
          : 'No derived offer book for this day. Books cover the market window with a few days’ publication lag; pick an earlier day or stay on the cost model.'}
      </div>
    )
  if (!hours.length)
    return (
      <div className="basecase-banner">
        That day is no longer in the archive window. Pick an observed day from the list;
        the default is the widest-swing market day.
      </div>
    )

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
        importedKeys,
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
      `power-dispatch-${date}${span === 'week' ? '-week' : ''}.csv`,
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
        <Segmented
          ariaLabel="Dispatch engine"
          value={engine}
          onChange={(v) => setEngine(v as 'cost' | 'offers')}
          options={[
            { value: 'cost', label: 'Cost model' },
            { value: 'offers', label: 'Observed offers' },
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
        {engine === 'cost' && hb && (
          <span
            className="chrono__reserve"
            title="Observed daily hydro energy from the operator's per-resource schedules (DIPCEF); the day LP cannot dispatch more hydro than the day's water, scaled with your hydro edits and the hydrology lever."
          >
            hydro water: {num(hbTotal)} MWh observed
          </span>
        )}
        {engine === 'offers' && (
          <span
            className="chrono__reserve"
            title="The day's actual offer book (every resource's priced curve plus self-scheduled capacity as price-takers). The book already embodies unit behavior, so storage, reserve, water, and fleet edits are off; the added-load lever still applies."
          >
            {offer.loading
              ? 'loading the offer book'
              : offer.data
                ? "the day's book, as bid"
                : 'no derived book for this day'}
          </span>
        )}
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

      <Panel
        title={`What set the price, ${cap(grid)}`}
        subtitle="Per hour: the marginal fuel block, a saturated corridor on the importing side, or unserved load. The binding constraint, named."
      >
        <BindingStrip cells={hours.map((h) => classifyHour(h, grid))} />
        <div className="legend">
          {bindingCounts(hours, grid).map((b) => (
            <span className="legend__item" key={b.key}>
              <i
                style={{
                  background:
                    b.cause === 'unserved'
                      ? 'var(--destructive)'
                      : b.cause === 'corridor'
                        ? 'var(--accent)'
                        : fuelColor(b.key),
                }}
              />
              {b.label}: {b.hours}h ({num(b.share_pct, 1)}%)
            </span>
          ))}
        </div>
      </Panel>

      {hasStorage && (
        <Panel
          title="Storage state of charge"
          subtitle="Optimised by the day LP: storage cycles only when the price spread beats the round-trip loss, and idles on a flat day. The state resets each day."
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
        edits shift demand flat across all 24 hours, the data-center shape. On days the
        archive carries per-resource schedules, hydro is energy-limited to the day's
        observed water (scaled with hydro capacity edits and the hydrology lever), so the
        solver spends it in the dearest hours. The reserve toggle withholds the mean
        scheduled requirement (IEMOP RTD reserve rows) from the dispatchable stack, so
        tight hours price the withheld capacity instead of paying a synthetic demand. The
        whole day solves as one linear program (HiGHS): storage couples the hours, prices
        are the balance duals (locational marginal prices, so an importing hour can price
        at the exporter plus the wheeling cost), and shedding never beats available
        capacity. Still not full unit commitment: blocks, not units.
      </p>
    </div>
  )
}
