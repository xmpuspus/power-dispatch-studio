// Chronology view: replay an observed day (or the week ending on it) hour by
// hour on the current edited model. Prices, dispatch by fuel, storage state of
// charge, and the run's own duration curve all come out of the run, live.

import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { num, php, fuelColor, fuelLabel, useOfferDay } from '../lib/data'
import { createUsageRecorder, editCountBand } from '../lib/usage'
import { Panel, Segmented, StatTile } from '../ui/kit'
import { BindingStrip, DurationCurve, DispatchArea, HourLines, SocChart } from './charts'
import { ENGINE_VERSION, runChronology, runDuration, type ChronoHour } from './chrono'
import { bindingCounts, classifyHour } from './insights'
import {
  chronoOptsFrom,
  type ClassId,
  type ObjRow,
  type Overrides,
  type ScenarioPurpose,
  type ScenarioSettings,
} from './model'
import { downloadCsv, encodeShare, runCsv, saveRun, type SavedRun } from './runs'
import { describeScenario } from './resultContext'

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
  settings,
  purpose,
  sourceNotes,
  importedKeys,
  grid,
  scenarioName,
  date,
  span,
  onDate,
  onSpan,
  selectedHour,
  onSaved,
}: {
  d: Dispatch
  profiles: Profiles
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  settings: ScenarioSettings
  purpose?: ScenarioPurpose
  sourceNotes?: string[]
  importedKeys?: string[]
  grid: GridKey
  scenarioName: string
  date: string
  span: 'day' | 'week'
  onDate: (d: string) => void
  onSpan: (s: 'day' | 'week') => void
  selectedHour: number
  onSaved: (runs: SavedRun[]) => void
}) {
  const days = profiles.days
  const [flash, setFlash] = useState<string | null>(null)
  const usage = useMemo(() => createUsageRecorder(window.localStorage), [])
  // Price from either the cost calculation or the day's published offer book.
  // (every layer the book already embodies is off; demand lever stays)
  const [engine, setEngine] = useState<'cost' | 'offers'>('cost')
  const offer = useOfferDay(engine === 'offers' ? date : null)
  const assumptions = useMemo(
    () =>
      describeScenario(objects, {
        name: scenarioName,
        overrides,
        settings,
        purpose,
        sourceNotes,
      }),
    [objects, overrides, purpose, scenarioName, settings, sourceNotes]
  )
  const suggestedName =
    scenarioName === 'Base Case' && assumptions[0]
      ? `${assumptions[0].text}, ${date}`
      : `${scenarioName}, ${date}${span === 'week' ? ' week' : ''}`
  const [runName, setRunName] = useState(suggestedName)
  useEffect(() => setRunName(suggestedName), [suggestedName])
  const opts = useMemo(() => {
    const o = chronoOptsFrom(objects, overrides, settings)
    if (engine === 'offers') {
      const only: typeof o = { demand_delta: o.demand_delta }
      if (settings.reserveHoldback) only.reserve_deduction = true
      if (offer.data) only.offer_day = offer.data
      return only
    }
    return o
  }, [objects, overrides, settings, engine, offer.data])
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

  // what the chart actually draws, regardless of the span toggle: the offer book is
  // per day, and the archive can clip the week near its start
  const effectiveSpan: 'day' | 'week' = windowDates.length > 1 ? 'week' : 'day'

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
          ? 'Loading the day’s generator offers.'
          : 'No published generator offers are available for this day. Publication lags by a few days. Pick an earlier day or stay on the cost model.'}
      </div>
    )
  if (!hours.length)
    return (
      <div className="basecase-banner">
        That day is no longer in the archive window. Pick a recorded day from the list.
        The default is the market day with the widest price range.
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
      label: 'Recorded LWAP',
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
  const selected = Math.min(Math.max(selectedHour, 0), hours.length - 1)
  const marginalNow = hours[selected]?.marginal[grid]

  const note = (msg: string) => {
    setFlash(msg)
    window.setTimeout(() => setFlash(null), 1800)
  }
  const save = () => {
    const cleanName = runName.trim()
    if (!cleanName) {
      note('Name this run before saving')
      return
    }
    onSaved(
      saveRun({
        id: crypto.randomUUID(),
        name: cleanName,
        savedAt: new Date().toISOString(),
        scenarioName,
        overrides,
        settings,
        purpose,
        assumptions,
        sourceNotes: [
          ...(sourceNotes ?? []),
          engine === 'offers'
            ? 'Published IEMOP generator offers for the selected day.'
            : 'Recorded IEMOP demand and hydro limits with modeled generation costs.',
        ],
        calculation: {
          pricingMethod: engine,
          reserveHoldback: !!settings.reserveHoldback,
        },
        importedKeys,
        date,
        span,
        engineVersion: ENGINE_VERSION,
        hours,
        summaries: runs.map((r) => r.summary),
      })
    )
    usage.track('scenario_saved', {
      span,
      editCountBand: editCountBand(
        Object.keys(overrides).length + (settings.reserveHoldback ? 1 : 0)
      ),
    })
    note('Run saved')
  }
  const exportCsv = () => {
    try {
      downloadCsv(
        `power-dispatch-${date}${span === 'week' ? '-week' : ''}.csv`,
        runCsv(hours, windowDates)
      )
    } catch {
      usage.track('export_failed', { format: 'csv' })
      note('CSV export failed')
    }
  }
  const copyLink = async () => {
    const hash = encodeShare({
      overrides,
      scenarioName,
      settings,
      purpose,
      sourceNotes,
      date,
      span,
    })
    window.history.replaceState(null, '', hash)
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable')
      await navigator.clipboard.writeText(
        `${window.location.origin}${window.location.pathname}${hash}`
      )
      note('Link copied')
    } catch {
      note('Share link ready in the address bar')
    }
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
          value={effectiveSpan}
          onChange={(v) => onSpan(v as 'day' | 'week')}
          options={[
            { value: 'day', label: 'Day' },
            {
              value: 'week',
              label: 'Week ending',
              disabled: engine === 'offers',
              title:
                engine === 'offers'
                  ? 'Recorded generator offers are published one day at a time. Switch to the cost model for a full week.'
                  : undefined,
            },
          ]}
        />
        <Segmented
          ariaLabel="Replay method"
          value={engine}
          onChange={(v) => setEngine(v as 'cost' | 'offers')}
          options={[
            { value: 'cost', label: 'Cost-model replay' },
            { value: 'offers', label: 'Offer-book replay' },
          ]}
        />
        {settings.reserveHoldback && (
          <span className="chrono__reserve">
            {num(reserveMw)} MW of recorded reserve requirements held back
          </span>
        )}
        {engine === 'cost' && hb && (
          <span
            className="chrono__reserve"
            title="Daily hydro limit from final per-resource dispatch schedules, adjusted by the current hydro settings."
          >
            recorded hydro energy limit, {num(hbTotal)} MWh
          </span>
        )}
        {engine === 'offers' && (
          <span
            className="chrono__reserve"
            title="Published generator offers include priced curves and self-scheduled capacity. Storage, water, and fleet changes are off; reserve clearing and added demand stay available."
          >
            {offer.loading
              ? 'loading generator offers'
              : offer.data
                ? "the day's book, as bid"
                : 'no published offers for this day'}
          </span>
        )}
        <label className="chrono__ctl chrono__run-name">
          Run name
          <input
            className="ribbon__select"
            value={runName}
            maxLength={100}
            onChange={(event) => setRunName(event.target.value)}
          />
        </label>
        <div className="chrono__actions">
          <button
            className="btn btn--primary btn--sm"
            onClick={save}
            disabled={!runName.trim()}
          >
            Save run
          </button>
          <button className="btn btn--ghost btn--sm" onClick={exportCsv}>
            Export CSV
          </button>
          <button className="btn btn--ghost btn--sm" onClick={() => void copyLink()}>
            Copy link
          </button>
          {flash && (
            <span className="chrono__flash" role="status">
              {flash}
            </span>
          )}
        </div>
      </div>

      <div className="chrono__method" aria-label="Calculation method">
        <strong>{engine === 'offers' ? 'Offer-book replay' : 'Cost-model replay'}</strong>
        <span>
          {engine === 'offers'
            ? 'Uses the selected day’s published generator offers. The displayed prices are recalculated, not recorded market prices.'
            : 'Uses modeled generation costs over recorded demand and hydro limits. This is a replay, not a forecast.'}
        </span>
      </div>

      <div className="stat-row">
        <StatTile
          label={`Modeled mean price, ${cap(grid)}`}
          value={php(meanPrice)}
          unit="/kWh"
          hint={marginalNow ? `hour ${selected}: ${fuelLabel(marginalNow)}` : undefined}
        />
        <StatTile label="Modeled window peak" value={php(peakPrice)} unit="/kWh" />
        <StatTile
          label="Demand not served (unserved energy)"
          value={num(unserved)}
          unit="MWh"
          tone={unserved > 0 ? 'danger' : 'positive'}
        />
        <StatTile
          label="Value of the price gap across constrained links (congestion rent)"
          value={`₱${num(rentM, 2)}M`}
          hint="both corridors, whole window"
        />
      </div>

      <Panel
        title="Modeled hourly clearing price"
        subtitle={`The three grids cleared together, every hour of the ${
          effectiveSpan === 'day' ? 'observed day' : 'week'
        }. The recorded load-weighted average price is dashed where the archive has it.`}
      >
        <HourLines series={priceSeries} marks={marks} />
      </Panel>

      <Panel
        title={`Generation by fuel and hourly demand, ${cap(grid)}`}
        subtitle="Lowest-cost-first dispatch (merit order) by hour. Solar follows its 24-hour output profile. Other fuels use their reduced available capacity."
      >
        <DispatchArea
          fuelGen={hours.map((h) => h.fuelGen[grid])}
          demand={hours.map((h) => h.demand[grid])}
          marks={marks}
        />
      </Panel>

      <Panel
        title={`Hourly price setters, ${cap(grid)}`}
        subtitle="Each hour is labeled with the price-setting fuel, an inter-grid link at its limit on the importing side, or demand that could not be served."
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
          title="Storage charging and discharging"
          subtitle="The daily optimization charges and discharges storage only when the price difference covers round-trip losses. Stored energy resets each day."
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
        subtitle="Every hour in the current run, sorted from highest to lowest price. These values come from the settings you just ran."
      >
        <DurationCurve modeled={runDuration(hours, grid)} />
      </Panel>

      <p className="note">
        Each recorded day is recalculated hour by hour with the plant, grid, and demand
        settings you ran. Demand comes from the market operator's regional summaries. A
        region load edit adds the same MW in all 24 hours. Where plant schedules are
        available, hydro generation is limited to its recorded daily energy and can move
        to the hours when it is most valuable. The reserve option holds back the
        operator's average reserve requirement before dispatch. Storage links one hour to
        the next. Regional prices include grid transfer costs and capacity limits. The
        model dispatches fuel blocks; it does not decide when individual plants start or
        stop.
      </p>
    </div>
  )
}
