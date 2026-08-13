// Seven consecutive recorded days solved
// on ONE linear program, so the battery state of charge carries across midnight
// instead of resetting each day. The day-by-day engine can never bank Monday's
// cheap water for Thursday's peak; this view measures what that carry is worth.
// The water stays daily-budgeted (a wet Tuesday cannot lend its river to a dry
// Friday). Reserve and the gas budget are day-mode analyses and stay off here.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { php } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { runWeek, type ChronoOpts, type WeekDaySummary } from './chrono'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const STORAGE = {
  none: { label: 'No storage', mw: 0, mwh: 0 },
  small: { label: '1 GW / 4 GWh', mw: 1000, mwh: 4000 },
  large: { label: '2 GW / 16 GWh', mw: 2000, mwh: 16000 },
} as const
type StorageKey = keyof typeof STORAGE

/** Consecutive full-coverage market days sliced into non-overlapping 7-day
 * windows, most recent first (the last window is the one the golden pins). */
function weekWindows(profiles: Profiles): string[][] {
  const full = profiles.days
    .filter(
      (d) =>
        d.market &&
        (['luzon', 'visayas', 'mindanao'] as GridKey[]).every((g) => {
          const arr = d.lwap?.[g]
          return arr?.length === 24 && arr.every((v) => v != null)
        })
    )
    .map((d) => d.date)
  const windows: string[][] = []
  for (let i = full.length - 7; i >= 0; i -= 7) windows.push(full.slice(i, i + 7))
  return windows
}

export function WeekView({
  d,
  profiles,
  grid,
}: {
  d: Dispatch
  profiles: Profiles
  grid: GridKey
}) {
  const windows = useMemo(() => weekWindows(profiles), [profiles])
  const [wIdx, setWIdx] = useState(0)
  const [storeKey, setStoreKey] = useState<StorageKey>('none')
  const [dcWave, setDcWave] = useState(false)

  const result = useMemo(() => {
    if (!windows.length) return null
    const dates = windows[Math.min(wIdx, windows.length - 1)]
    const st = STORAGE[storeKey]
    const opts: ChronoOpts = {}
    if (st.mw > 0) opts.storage = [{ grid: 'luzon', power_mw: st.mw, energy_mwh: st.mwh }]
    if (dcWave) {
      opts.solar_delta_mw = { luzon: 8000 }
      opts.demand_delta = { luzon: 2500 }
    }
    const week = runWeek(d, profiles, dates, opts)
    // day-by-day baseline: each date solved on its own empty-start battery, the
    // same epsilon-free physical cost the week reports. A single-date week is an
    // independent 24h solve, so this is exactly the seven-independent-day total.
    const dayByDay = dates.reduce(
      (s, dt) => s + runWeek(d, profiles, [dt], opts).summary.physicalCost,
      0
    )
    const saving = Math.max(0, dayByDay - week.summary.physicalCost)
    const carry = Math.max(0, ...week.days.map((x) => x.endSocMwh))
    return { week, dayByDay, saving, carry, dates }
  }, [windows, wIdx, storeKey, dcWave, d, profiles])

  if (!result)
    return (
      <div className="view">
        <Panel
          title="Continuous seven-day storage replay"
          subtitle="A 168-hour optimization carries stored energy across midnight."
        >
          <EmptyNote>
            The observed library has fewer than seven full-coverage days, so a week cannot
            be assembled.
          </EmptyNote>
        </Panel>
      </div>
    )

  const { week, dayByDay, saving, carry, dates } = result
  const pct = dayByDay > 0 ? (100 * saving) / dayByDay : 0
  const storageSelected = STORAGE[storeKey].mw > 0
  const storageDispatched = week.hours.some(
    (hour) => hour.socMwh > 0.001 || hour.chargeMw > 0.001 || hour.dischargeMw > 0.001
  )

  // SoC trace across the 168 hours, midnight gridlines between days
  const W = 820
  const H = 200
  const padL = 46
  const padB = 24
  const padT = 10
  const socMax = Math.max(1, ...week.hours.map((o) => o.socMwh))
  const X = (h: number) => padL + (h / 167) * (W - padL - 12)
  const Y = (v: number) => padT + (1 - v / socMax) * (H - padT - padB)
  const soc = week.hours
    .map((o, h) => `${X(h).toFixed(1)},${Y(o.socMwh).toFixed(1)}`)
    .join(' ')

  const cols: Column<WeekDaySummary>[] = [
    { key: 'date', header: 'Day', render: (r) => r.date },
    {
      key: 'mean',
      header: `${cap(grid)} mean (₱/kWh)`,
      align: 'right',
      mono: true,
      render: (r) => php(r.meanPrice[grid]),
    },
    {
      key: 'start',
      header: 'Start SoC',
      align: 'right',
      mono: true,
      render: (r) => `${r.startSocMwh.toLocaleString('en-US')} MWh`,
    },
    {
      key: 'end',
      header: 'Carry to next day',
      align: 'right',
      mono: true,
      render: (r) => `${r.endSocMwh.toLocaleString('en-US')} MWh`,
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Week window
          <select
            className="ribbon__select"
            value={wIdx}
            onChange={(e) => setWIdx(Number(e.target.value))}
            aria-label="Week window"
          >
            {windows.map((w, i) => (
              <option key={w[0]} value={i}>
                {w[0]} to {w[6]}
              </option>
            ))}
          </select>
        </label>
        <label className="chrono__ctl">
          Battery size
          <select
            className="ribbon__select"
            value={storeKey}
            onChange={(e) => setStoreKey(e.target.value as StorageKey)}
            aria-label="Storage"
          >
            {(Object.keys(STORAGE) as StorageKey[]).map((k) => (
              <option key={k} value={k}>
                {STORAGE[k].label}
              </option>
            ))}
          </select>
        </label>
        <label className="chrono__reserve">
          <input
            type="checkbox"
            checked={dcWave}
            onChange={(e) => setDcWave(e.target.checked)}
          />
          Added-demand case (8 GW solar + 2.5 GW load)
        </label>
      </div>

      <Panel
        title={`Value of carrying stored energy between days, ${dates[0]} to ${dates[6]}`}
        subtitle="One 168-hour optimization carries battery energy across midnight and is compared with the same seven days solved separately."
      >
        {!storageSelected ? (
          <EmptyNote>
            Choose a battery size to calculate inter-day storage value.
          </EmptyNote>
        ) : (
          <>
            <div className="stat-row">
              <StatTile
                label="Inter-day saving"
                value={`₱${(saving / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 })}k`}
                hint={`${pct.toFixed(3)}% of weekly system cost`}
                tone={saving > 1 ? 'positive' : 'default'}
              />
              <StatTile
                label="Peak charge held"
                value={`${week.summary.socSwingMwh.toLocaleString('en-US')} MWh`}
                hint="deepest state of charge"
              />
              <StatTile
                label="Carried across midnight"
                value={`${carry.toLocaleString('en-US', { maximumFractionDigits: 0 })} MWh`}
                hint="most a day hands the next"
                tone={carry > 1 ? 'accent' : 'default'}
              />
            </div>
            {storageDispatched ? (
              <>
                <svg
                  viewBox={`0 0 ${W} ${H}`}
                  className="fwdchart"
                  role="img"
                  aria-label="Storage state of charge across the week"
                >
                  <line x1={padL} y1={Y(0)} x2={W - 12} y2={Y(0)} className="chart__ax" />
                  <text x={padL - 6} y={Y(socMax)} textAnchor="end" className="chart__ax">
                    {socMax.toFixed(0)}
                  </text>
                  <text x={padL - 6} y={Y(0)} textAnchor="end" className="chart__ax">
                    0
                  </text>
                  {dates.map((dt, i) => (
                    <g key={dt}>
                      <line
                        x1={X(i * 24)}
                        y1={padT}
                        x2={X(i * 24)}
                        y2={H - padB}
                        className="chart__grid"
                      />
                      <text x={X(i * 24) + 2} y={H - 8} className="chart__ax">
                        {dt.slice(5)}
                      </text>
                    </g>
                  ))}
                  <polyline points={soc} className="fwdchart__median" />
                </svg>
                <DataGrid columns={cols} rows={week.days} getKey={(r) => r.date} />
              </>
            ) : (
              <div className="chart-summary">
                <strong className="chart-summary__value">No storage dispatch</strong>
                <span className="chart-summary__detail">
                  The selected battery did not charge or discharge during this week.
                </span>
              </div>
            )}
          </>
        )}
        <p className="note">
          {!storageSelected
            ? 'Select a battery size above. The run will compare one 168-hour solve with the same seven days solved separately.'
            : !storageDispatched
              ? 'Hourly modeled price differences did not cover the battery losses, so carrying energy across midnight had no value in this case. Use the added-demand case to test a wider midday-to-evening price spread.'
              : 'Daily water limits remain separate, so hydro energy cannot move from one day to another. Reserve and gas limits are day-level analyses and are not used in the week calculation. The browser and Python historical replay use the same optimization model.'}
        </p>
      </Panel>
    </div>
  )
}
