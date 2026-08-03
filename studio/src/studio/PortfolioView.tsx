// Portfolio and contract valuation: no free tool values a WESM generation
// position. An analyst owns generation and sells some of it on a bilateral PSA
// contract (a fixed strike price) and the rest on the WESM spot market. This
// view values that position against a saved run's hourly prices, and shows
// what the bilateral contract captured or gave up against spot, plus the spot
// exposure of the volume it does not cover.
//
// A saved run carries price per grid per hour and fuel_gen (MW per fuel per
// grid per hour), not per-unit generation. Generation here is modeled as your
// share of one fuel's dispatched MW in one grid, an approximation because the
// public run is per-fuel, not per-unit: it cannot tell you what one named
// plant produced.

import { useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { GRIDS } from '../lib/types'
import { fuelLabel, num, php } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import type { SavedRun } from './runs'
import {
  exposureDurationCurve,
  valuePortfolio,
  type ExposurePoint,
  type PortfolioSpec,
} from './portfolio'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

function fuelsInRun(run: SavedRun, grid: GridKey): string[] {
  const set = new Set<string>()
  for (const h of run.hours)
    for (const f of Object.keys(h.fuelGen[grid] ?? {})) set.add(f)
  return [...set].sort()
}

export function PortfolioView({ runsList, d }: { runsList: SavedRun[]; d: Dispatch }) {
  const [runId, setRunId] = useState('')
  const withHours = runsList.filter((r) => r.hours.length > 0)
  const run = withHours.find((r) => r.id === runId) ?? withHours[0]

  const [grid, setGrid] = useState<GridKey>('luzon')
  const [fuel, setFuel] = useState('coal')
  const [sharePct, setSharePct] = useState(10)
  const [strikePhpKwh, setStrikePhpKwh] = useState(
    () => d.assumptions.fuel_marginal_cost_php_kwh.coal ?? 6
  )
  const [contractMw, setContractMw] = useState(100)

  if (!run)
    return (
      <div className="view">
        <Panel
          title="A portfolio meets the spot price only on the megawatts its contract misses"
          subtitle="Value a generation position against a saved run's hourly prices."
        >
          <EmptyNote>
            No saved run has hourly detail yet. Open Hourly market replay, configure a
            scenario and a date range, then press Save run.
          </EmptyNote>
        </Panel>
      </div>
    )

  const fuels = fuelsInRun(run, grid)
  const activeFuel = fuels.includes(fuel) ? fuel : (fuels[0] ?? fuel)
  const spec: PortfolioSpec = {
    grid,
    fuel: activeFuel,
    sharePct,
    strikePhpKwh,
    contractMw,
  }
  const v = valuePortfolio(run.hours, spec)
  const exposure = exposureDurationCurve(run.hours, spec)
  const hasExposure = exposure.some((p) => p.uncontractedMwh > 0)

  return (
    <div className="view" data-testid="portfolio">
      <p className="scn__lede">
        Value a generation position against a saved run's hourly prices. Generation is
        your share of generation from one fuel in one grid, not a named plant's output.
        The public run tracks generation by fuel. The power supply agreement (PSA) is
        modeled as a contract for differences on a flat volume. It pays the strike price
        minus the spot price on contracted MWh, in addition to spot-market revenue.
      </p>

      <div className="scn">
        <Panel
          title="The contract decides which megawatts sell forward and which meet the spot price"
          subtitle={
            withHours.length > 1
              ? 'Pick the run, the position, and the PSA terms.'
              : `Run: ${run.name}`
          }
        >
          <div className="levers">
            {withHours.length > 1 && (
              <label className="chrono__ctl">
                Saved run
                <select
                  className="ribbon__select"
                  value={run.id}
                  onChange={(e) => setRunId(e.target.value)}
                  aria-label="Run to value"
                >
                  {withHours.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label className="chrono__ctl">
              Grid
              <select
                className="ribbon__select"
                value={grid}
                onChange={(e) => setGrid(e.target.value as GridKey)}
                aria-label="Grid"
              >
                {GRIDS.map((g) => (
                  <option key={g} value={g}>
                    {cap(g)}
                  </option>
                ))}
              </select>
            </label>
            <label className="chrono__ctl">
              Fuel
              <select
                className="ribbon__select"
                value={activeFuel}
                onChange={(e) => setFuel(e.target.value)}
                aria-label="Fuel"
              >
                {fuels.length === 0 ? (
                  <option value={activeFuel}>
                    {fuelLabel(activeFuel)}, no dispatch this run
                  </option>
                ) : (
                  fuels.map((f) => (
                    <option key={f} value={f}>
                      {fuelLabel(f)}
                    </option>
                  ))
                )}
              </select>
            </label>
            <Slider
              label="Your share of the fuel's dispatched generation"
              value={sharePct}
              min={0}
              max={100}
              step={1}
              fmt={(x) => `${x}%`}
              onChange={setSharePct}
            />
            <label className="chrono__ctl">
              PSA strike price
              <input
                type="number"
                className="lever__select"
                min={0}
                step={0.01}
                value={strikePhpKwh}
                onChange={(e) => setStrikePhpKwh(Number(e.target.value))}
                aria-label="PSA strike price, PhP per kWh"
              />
            </label>
            <label className="chrono__ctl">
              Contracted volume
              <input
                type="number"
                className="lever__select"
                min={0}
                step={1}
                value={contractMw}
                onChange={(e) => setContractMw(Number(e.target.value))}
                aria-label="Contracted volume, MW"
              />
            </label>
          </div>
        </Panel>

        <div className="scn__results">
          <div className="stat-row">
            <StatTile
              label="Generation, this position"
              value={num(v.genMwh)}
              unit="MWh"
              hint={`${cap(grid)}, ${fuelLabel(activeFuel)}, ${sharePct}% share, ${run.hours.length} hours`}
            />
            <StatTile
              label="Spot revenue"
              value={num(v.spotRevenue)}
              unit="PhP thousand"
              hint="selling all generation on the WESM spot market"
            />
            <StatTile
              label="Bilateral contract compared with WESM spot"
              value={`${v.bilateralVsWesmDeltaPhp >= 0 ? '+' : ''}${num(v.bilateralVsWesmDeltaPhp)}`}
              unit="PhP thousand"
              tone={v.bilateralVsWesmDeltaPhp >= 0 ? 'positive' : 'danger'}
              hint="what the PSA captured (+) or gave up (-) against spot, this window"
            />
            <StatTile
              label="Realized price"
              value={php(v.meanRealizedPhpKwh, 3)}
              hint={
                v.captureVsSpotPct == null
                  ? `mean spot ${php(v.meanSpotPhpKwh, 3)}`
                  : `mean spot ${php(v.meanSpotPhpKwh, 3)}, ${v.captureVsSpotPct.toFixed(1)}% of it`
              }
            />
          </div>

          <Panel
            title="Uncontracted generation is what the spot price actually reaches"
            subtitle="Generation above the contracted volume, paired with that hour's spot price, dearest spot first."
          >
            {hasExposure ? (
              <ExposureChart points={exposure} />
            ) : (
              <p className="note">
                The contracted volume covers this position's generation in every hour of
                this window. No generation is exposed to the spot market without contract
                cover.
              </p>
            )}
          </Panel>

          <p className="note">
            Generation is a flat {sharePct}% share of {fuelLabel(activeFuel)}'s hourly
            dispatched MW in {cap(grid)}, this run's actual dispatch, not a named unit's
            output. The PSA settles as a contract for differences. For each hour, the
            settlement is the strike price minus the spot price, multiplied by the lesser
            of contracted volume or generation. Contracted generation receives the fixed
            strike price, and any remaining generation sells at spot.
            {run.importedKeys && run.importedKeys.length > 0
              ? ' This run used your own CSV inputs, not the published default assumptions.'
              : ''}
          </p>
        </div>
      </div>
    </div>
  )
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  fmt,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  fmt?: (v: number) => string
  onChange: (v: number) => void
}) {
  const shown = fmt ? fmt(value) : num(value)
  return (
    <label className="lever">
      <span className="lever__label">
        {label} <b className="lever__val mono">{shown}</b>
      </span>
      <input
        type="range"
        className="lever__range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

/** Bars of uncontracted MWh, dearest spot first, colored by that hour's spot price. */
function ExposureChart({ points }: { points: ExposurePoint[] }) {
  const W = 640
  const H = 200
  const padL = 46
  const padR = 12
  const padT = 12
  const padB = 26
  const n = points.length
  const maxMwh = Math.max(...points.map((p) => p.uncontractedMwh), 1)
  const spots = points.map((p) => p.spot)
  const minSpot = Math.min(...spots)
  const maxSpot = Math.max(...spots)
  const spotSpan = maxSpot - minSpot || 1
  const barW = (W - padL - padR) / n
  const Y = (v: number) => padT + (H - padT - padB) * (1 - v / maxMwh)
  const colorFor = (spot: number) => {
    const t = Math.round((100 * (spot - minSpot)) / spotSpan)
    return `color-mix(in srgb, var(--destructive) ${t}%, var(--series-modeled))`
  }
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Uncontracted generation by hour, dearest spot price first"
    >
      <line
        x1={padL}
        y1={padT}
        x2={W - padR}
        y2={padT}
        stroke="var(--border)"
        strokeWidth={0.75}
      />
      <text x={padL - 6} y={padT + 4} textAnchor="end" className="chart__ax">
        {Math.round(maxMwh).toLocaleString()}
      </text>
      <text x={padL - 6} y={H - padB + 4} textAnchor="end" className="chart__ax">
        0
      </text>
      {points.map((p, i) => (
        <rect
          key={p.hourIndex}
          x={padL + i * barW}
          y={Y(p.uncontractedMwh)}
          width={Math.max(0.6, barW - 0.6)}
          height={Math.max(0, H - padB - Y(p.uncontractedMwh))}
          fill={colorFor(p.spot)}
        >
          <title>
            hour {p.hourIndex}: {num(p.uncontractedMwh)} MWh uncontracted at{' '}
            {php(p.spot, 2)}/kWh
          </title>
        </rect>
      ))}
      <text x={padL} y={H - 6} className="chart__ax">
        dearest spot, ₱{maxSpot.toFixed(2)}/kWh
      </text>
      <text x={W - padR} y={H - 6} textAnchor="end" className="chart__ax">
        cheapest spot, ₱{minSpot.toFixed(2)}/kWh
      </text>
    </svg>
  )
}
