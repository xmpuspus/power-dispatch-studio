// The 5-minute as-bid replay shows intraday price changes that the
// hourly engine smooths away. Each sample day's offer book was cleared to that
// grid's own dispatched generation at 5-minute resolution (pipeline/
// rtdoe5_replay.py). This view covers the captured sample days.

import { useEffect, useMemo } from 'react'
import type { GridKey } from '../lib/types'
import { php, useMarketAnchors, useRtdoe5 } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
export function Rtdoe5View({
  grid,
  date,
  onDate,
}: {
  grid: GridKey
  date: string | null
  onDate: (date: string) => void
}) {
  const r5 = useRtdoe5()
  const anchors = useMarketAnchors()
  const days = r5.data?.days ?? []
  const day = days.find((d) => d.date === date) ?? days[days.length - 1]
  const offerCap = anchors.data?.wesm_offer_cap_php_kwh
  useEffect(() => {
    if (day && day.date !== date) onDate(day.date)
  }, [day, date, onDate])

  const stats = useMemo(() => {
    if (!day) return null
    const s = day.series[grid].filter((v): v is number => v != null)
    if (!s.length) return null
    const atCap = offerCap == null ? null : s.filter((v) => v >= offerCap - 0.01).length
    return {
      min: Math.min(...s),
      max: Math.max(...s),
      mean: s.reduce((a, b) => a + b, 0) / s.length,
      atCapPct: atCap == null ? null : Math.round((100 * atCap) / s.length),
      n: s.length,
    }
  }, [day, grid, offerCap])

  if (!r5.data?.available || !day)
    return (
      <div className="view">
        <Panel
          title="5-minute offer replay"
          subtitle="Intraday price volatility on the sample days."
        >
          <EmptyNote>
            No 5-minute sample days are available in this data release.
          </EmptyNote>
        </Panel>
      </div>
    )

  // SVG polyline of the 5-minute series plus the hourly-mean step overlay
  const W = 900
  const H = 260
  const padL = 44
  const padB = 24
  const padT = 10
  const series = day.series[grid]
  const hourly = day.hourly[grid]
  const lo = stats ? Math.min(stats.min, 0) : 0
  const hi = stats ? Math.max(stats.max, 1) : 1
  const X = (i: number) => padL + (i / (series.length - 1)) * (W - padL - 8)
  const Y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB)
  const linePts = series
    .map((v, i) => (v == null ? null : `${X(i).toFixed(1)},${Y(v).toFixed(1)}`))
    .filter(Boolean)
    .join(' ')
  const hourlyPts = hourly
    .map((v, h) =>
      v == null ? null : `${X((h + 0.5) * 12).toFixed(1)},${Y(v).toFixed(1)}`
    )
    .filter(Boolean)
    .join(' ')

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Sample day
          <select
            className="ribbon__select"
            value={day.date}
            onChange={(e) => onDate(e.target.value)}
            aria-label="Sample day"
          >
            {days.map((d) => (
              <option key={d.date} value={d.date}>
                {d.date}
              </option>
            ))}
          </select>
        </label>
      </div>

      <Panel
        title={`5-minute offer replay, ${cap(grid)}, ${day.date}`}
        subtitle="Each 5-minute set of generator offers is cleared against generation in that grid. The step line shows the hourly average used by the hourly replay."
      >
        {stats && (
          <div className="stat-row">
            <StatTile
              label="Intraday range"
              value={`${php(stats.max - stats.min)}/kWh`}
              hint="min to max"
            />
            <StatTile
              label="Peak 5-min"
              value={`${php(stats.max)}/kWh`}
              hint="dearest interval"
            />
            {stats.atCapPct != null && (
              <StatTile
                label="At the published offer cap"
                value={`${stats.atCapPct}%`}
                hint={`${php(offerCap ?? 0)}/kWh cap`}
              />
            )}
          </div>
        )}
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="r5chart"
          role="img"
          aria-label={`5-minute ${grid} price series for ${day.date}`}
        >
          <line x1={padL} y1={Y(lo)} x2={W - 8} y2={Y(lo)} className="chart__ax" />
          <text x={padL - 6} y={Y(hi)} textAnchor="end" className="chart__ax">
            ₱{hi.toFixed(0)}
          </text>
          <text x={padL - 6} y={Y(lo)} textAnchor="end" className="chart__ax">
            ₱{lo.toFixed(0)}
          </text>
          <polyline points={linePts} className="r5chart__fine" />
          <polyline points={hourlyPts} className="r5chart__hourly" />
          <text x={padL} y={H - 6} className="chart__ax">
            00:00
          </text>
          <text x={W - 8} y={H - 6} textAnchor="end" className="chart__ax">
            24:00
          </text>
        </svg>
        <p className="note">
          A 5-minute replay of published generator bids on a sample day. Each grid is
          calculated separately. The intraday swings and intervals that hit the offer cap
          are what the hourly replay averages away. Sample days only: the full 5-minute
          books live only inside IEMOP's rolling window, so these are the ones the archive
          captured.
        </p>
      </Panel>
    </div>
  )
}
