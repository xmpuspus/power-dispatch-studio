// The analyst's day-explainer: pick any past market day and read what set its
// evening peak. The observed price is decomposed into fundamentals (the cost
// model), the offer premium (the offer-book replay minus the cost model), and
// the residual the calibrated view still misses, with the named equipment that
// actually bound the grid that day and the day's stress context. Everything is
// computed live from the same engines the rest of the studio runs, and the
// whole decomposition exports to CSV.

import { useMemo, useState } from 'react'
import type { GridKey, Profiles, Dispatch, DriverDay } from '../lib/types'
import { num, php, fuelLabel, useDrivers, useOfferDay, downloadCsv } from '../lib/data'
import { Panel, StatTile, Chip } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { HourLines } from './charts'
import { runChronology, type ChronoResult } from './chrono'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const EVE = [17, 18, 19, 20, 21] // the evening peak window, matching the backcast
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

const mean = (xs: (number | null | undefined)[]): number | null => {
  const v = xs.filter((x): x is number => x != null && !Number.isNaN(x))
  return v.length ? v.reduce((s, x) => s + x, 0) / v.length : null
}

// the fuel on the margin in the most evening hours, cost or offer engine
function dominantMarginal(run: ChronoResult | null, g: GridKey): string | null {
  if (!run) return null
  const counts: Record<string, number> = {}
  for (const h of EVE) {
    const m = run.hours[h]?.marginal[g]
    if (m) counts[m] = (counts[m] ?? 0) + 1
  }
  const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]
  return top ? top[0] : null
}

interface Decomp {
  grid: GridKey
  observed: number | null
  cost: number | null
  offer: number | null
  premium: number | null
  residual: number | null
}

export function DayExplainerView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const drivers = useDrivers()

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
  const day = marketDays.find((x) => x.date === date) ?? marketDays[marketDays.length - 1]

  const offerDay = useOfferDay(day?.date ?? null)
  const costRun = useMemo(
    () => (day ? runChronology(d, profiles, day.date, {}) : null),
    [d, profiles, day]
  )
  const offerRun = useMemo(
    () =>
      day && offerDay.data
        ? runChronology(d, profiles, day.date, { offer_day: offerDay.data })
        : null,
    [d, profiles, day, offerDay.data]
  )

  const decomp = (g: GridKey): Decomp => {
    const observed = mean(EVE.map((h) => day?.lwap?.[g]?.[h]))
    const cost = costRun ? mean(EVE.map((h) => costRun.hours[h]?.price[g])) : null
    const offer = offerRun ? mean(EVE.map((h) => offerRun.hours[h]?.price[g])) : null
    const premium = offer != null && cost != null ? offer - cost : null
    const residual = observed != null && offer != null ? observed - offer : null
    return { grid: g, observed, cost, offer, premium, residual }
  }

  if (!day)
    return (
      <div className="view">
        <Panel title="Explain a day" subtitle="Decompose any market day's evening peak.">
          <p className="note">No full-coverage market day in the archive window yet.</p>
        </Panel>
      </div>
    )

  const here = decomp(grid)
  const costFuel = dominantMarginal(costRun, grid)
  const offerFuel = dominantMarginal(offerRun, grid)
  const driversDay: DriverDay | undefined = drivers.data?.days.find(
    (x) => x.date === date
  )
  const equip = driversDay?.binding?.top_equipment ?? []
  const curtail = driversDay?.curtailed_mwh?.[grid]
  const alerts = driversDay?.n_alert_advisories
  const reserveMax = driversDay?.reserve_price_max

  const exportRows = GRIDS.map((g) => {
    const x = decomp(g)
    const f = (v: number | null) => (v == null ? '' : v.toFixed(2))
    return {
      date,
      grid: g,
      observed_evening_php_kwh: f(x.observed),
      cost_model_php_kwh: f(x.cost),
      offer_replay_php_kwh: f(x.offer),
      offer_premium_php_kwh: f(x.premium),
      residual_observed_minus_offer_php_kwh: f(x.residual),
    }
  })

  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Grid', render: (g) => cap(g) },
    {
      key: 'obs',
      header: 'Observed peak',
      align: 'right',
      mono: true,
      render: (g) => php(decomp(g).observed),
    },
    {
      key: 'cost',
      header: 'Cost model',
      align: 'right',
      mono: true,
      render: (g) => php(decomp(g).cost),
    },
    {
      key: 'prem',
      header: 'Offer premium',
      align: 'right',
      mono: true,
      render: (g) => {
        const p = decomp(g).premium
        return p == null ? '-' : `${p >= 0 ? '+' : ''}${php(p)}`
      },
    },
    {
      key: 'offer',
      header: 'Offer replay',
      align: 'right',
      mono: true,
      render: (g) => php(decomp(g).offer),
    },
    {
      key: 'res',
      header: 'Residual',
      align: 'right',
      mono: true,
      render: (g) => {
        const r = decomp(g).residual
        return r == null ? '-' : `${r >= 0 ? '+' : ''}${php(r)}`
      },
    },
  ]

  const equipCols: Column<{ name: string; rows: number }>[] = [
    { key: 'name', header: 'Equipment', render: (e) => e.name },
    {
      key: 'rows',
      header: 'RTD intervals bound',
      align: 'right',
      mono: true,
      render: (e) => num(e.rows),
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Market day
          <select
            className="ribbon__select"
            value={day.date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Explain day"
          >
            {marketDays.map((x) => (
              <option key={x.date} value={x.date}>
                {x.date}
              </option>
            ))}
          </select>
        </label>
        <span className="note">
          The observed evening peak (hours 17 to 21), split into what the fundamentals
          explain and what offer behaviour adds.
        </span>
      </div>

      <div className="stat-row">
        <StatTile
          label={`Observed peak, ${cap(grid)}`}
          value={php(here.observed)}
          hint={`hours 17 to 21, ${date}`}
        />
        <StatTile
          label="Fundamentals (cost model)"
          value={php(here.cost)}
          hint={costFuel ? `priced on ${fuelLabel(costFuel)}` : 'merit-order stack'}
        />
        <StatTile
          label="Offer premium"
          value={
            here.premium == null
              ? '-'
              : `${here.premium >= 0 ? '+' : ''}${php(here.premium)}`
          }
          hint="offer replay minus cost model"
          tone={here.premium != null && here.premium > 1 ? 'danger' : 'default'}
        />
        <StatTile
          label="Offer replay (calibrated)"
          value={php(here.offer)}
          hint={
            offerRun
              ? offerFuel
                ? `priced on ${fuelLabel(offerFuel)}`
                : "the operator's book"
              : offerDay.loading
                ? 'loading the book'
                : 'no offer book this day'
          }
        />
      </div>

      <Panel
        title={`How the evening peak was set, ${cap(grid)} on ${date}`}
        subtitle="Observed against the cost model (fundamentals) and the offer-book replay (fundamentals plus offer behaviour), hour by hour."
        right={
          <button
            className="btn btn--ghost btn--sm"
            onClick={() => downloadCsv(exportRows, `day-explainer_${date}.csv`)}
          >
            Export CSV
          </button>
        }
      >
        {costRun ? (
          <HourLines
            series={[
              {
                label: 'observed',
                color: 'var(--series-observed)',
                pts: day.lwap![grid]!,
                dash: '4 3',
              },
              {
                label: 'cost model',
                color: 'var(--series-modeled)',
                pts: costRun.hours.map((h) => h.price[grid]),
              },
              ...(offerRun
                ? [
                    {
                      label: 'offer replay',
                      color: 'var(--series-offer)',
                      pts: offerRun.hours.map((h) => h.price[grid]),
                    },
                  ]
                : []),
            ]}
          />
        ) : (
          <p className="note">Replaying the day.</p>
        )}
        <DataGrid columns={cols} rows={GRIDS} getKey={(g) => g} />
        <p className="note">
          Offer premium is the offer replay minus the cost model: the part of the evening
          price that offer behaviour, scarcity, and caps add on top of the merit-order
          fundamentals. Residual is what the calibrated offer replay still misses against
          the tape.
          {offerRun
            ? ''
            : ' No derived offer book for this day (books lag publication a few days), so the premium is blank; pick an earlier day.'}
        </p>
      </Panel>

      <Panel
        title={`What bound the grid on ${date}`}
        subtitle="The named equipment the operator's real-time dispatch held at a limit that day, from the archive."
      >
        <div className="chip-row">
          {curtail != null && curtail > 0 ? (
            <Chip tone="danger">{num(curtail)} MWh curtailed</Chip>
          ) : null}
          {alerts != null && alerts > 0 ? (
            <Chip tone="danger">{num(alerts)} alert advisories</Chip>
          ) : null}
          {reserveMax != null ? (
            <Chip tone="default">reserve peaked at {php(reserveMax)}</Chip>
          ) : null}
          {driversDay?.spread != null ? (
            <Chip tone="default">island spread {php(driversDay.spread)}</Chip>
          ) : null}
        </div>
        {equip.length ? (
          <DataGrid columns={equipCols} rows={equip.slice(0, 8)} getKey={(e) => e.name} />
        ) : (
          <p className="note">
            {drivers.loading
              ? 'Loading the day-by-day archive feed.'
              : 'No named binding equipment recorded for this day in the archive.'}
          </p>
        )}
      </Panel>
    </div>
  )
}
