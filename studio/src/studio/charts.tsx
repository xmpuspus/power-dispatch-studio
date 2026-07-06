import type { Block, DurationPoint } from '../lib/types'
import { fuelLabel } from '../lib/data'

const FUEL_VAR: Record<string, string> = {
  coal: 'var(--fuel-coal)',
  oil: 'var(--fuel-oil)',
  natural_gas: 'var(--fuel-gas)',
  hydro: 'var(--fuel-hydro)',
  geothermal: 'var(--fuel-geothermal)',
  solar: 'var(--fuel-solar)',
  wind: 'var(--series-flow)',
  biomass: 'var(--positive)',
  storage: 'var(--series-storage)',
  firm: 'var(--primary)',
  import: 'var(--series-flow)',
}
const fuelColor = (f: string) => FUEL_VAR[f] ?? 'var(--text-faint)'

/** Merit-order supply stack: blocks by marginal cost, with the demand cursor. */
export function MeritStack({ blocks, demand }: { blocks: Block[]; demand: number }) {
  const sorted = [...blocks].sort((a, b) => a.cost - b.cost)
  const total = sorted.reduce((s, b) => s + b.mw, 0)
  const scale = Math.max(total, demand) * 1.02 || 1
  const W = 640
  const H = 62
  let x = 0
  const dx = (demand / scale) * W
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Merit-order supply stack"
    >
      {sorted.map((b, i) => {
        const w = (b.mw / scale) * W
        const seg = (
          <rect
            key={i}
            x={x}
            y={10}
            width={Math.max(0, w)}
            height={30}
            fill={fuelColor(b.fuel)}
            opacity={0.92}
          >
            <title>
              {fuelLabel(b.fuel)}: {Math.round(b.mw)} MW at ₱{b.cost.toFixed(2)}/kWh
            </title>
          </rect>
        )
        x += w
        return seg
      })}
      <line
        x1={dx}
        y1={4}
        x2={dx}
        y2={48}
        stroke="var(--text)"
        strokeWidth={1.6}
        strokeDasharray="3 2"
      />
      <text x={Math.min(dx + 4, W - 96)} y={58} className="chart__lbl">
        demand {Math.round(demand).toLocaleString()} MW
      </text>
    </svg>
  )
}

/** Price-duration overlay: modeled (flat plateau) vs observed (fat tails). */
export function DurationCurve({
  modeled,
  observed,
}: {
  modeled: DurationPoint[]
  observed: DurationPoint[]
}) {
  const W = 640
  const H = 240
  const padL = 40
  const padR = 12
  const padT = 14
  const padB = 26
  const all = [...modeled, ...observed].map((d) => d.price)
  const ymin = Math.min(...all)
  const ymax = Math.max(...all)
  const span = ymax - ymin || 1
  const X = (p: number) => padL + ((W - padL - padR) * p) / 100
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - ymin) / span)
  const path = (pts: DurationPoint[]) =>
    pts.map((d) => `${X(d.pct).toFixed(1)},${Y(d.price).toFixed(1)}`).join(' ')
  const ticks = [ymax, (ymax + ymin) / 2, 0, ymin].filter(
    (v, i, a) => a.indexOf(v) === i && v >= ymin && v <= ymax
  )
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Price-duration curve, modeled versus observed"
    >
      {ticks.map((v, i) => (
        <g key={i}>
          <line
            x1={padL}
            y1={Y(v)}
            x2={W - padR}
            y2={Y(v)}
            stroke="var(--border)"
            strokeWidth={0.75}
          />
          <text x={padL - 6} y={Y(v) + 3} textAnchor="end" className="chart__ax">
            ₱{v.toFixed(0)}
          </text>
        </g>
      ))}
      <polyline
        points={path(observed)}
        fill="none"
        stroke="var(--series-observed)"
        strokeWidth={2}
      />
      <polyline
        points={path(modeled)}
        fill="none"
        stroke="var(--series-modeled)"
        strokeWidth={2}
      />
      <text x={padL} y={H - 8} className="chart__ax">
        0%
      </text>
      <text x={W - padR} y={H - 8} textAnchor="end" className="chart__ax">
        100% of the market window
      </text>
    </svg>
  )
}

/** Horizontal share bars: which block sets the price how often. */
export function ShareBars({ rows }: { rows: { block: string; share_pct: number }[] }) {
  const max = Math.max(...rows.map((r) => r.share_pct), 1)
  return (
    <div className="sharebars">
      {rows.map((r) => (
        <div className="sharebars__row" key={r.block}>
          <span className="sharebars__label">{fuelLabel(r.block)}</span>
          <span className="sharebars__track">
            <span
              className="sharebars__fill"
              style={{
                width: `${(r.share_pct / max) * 100}%`,
                background: fuelColor(r.block.split(' ')[0]),
              }}
            />
          </span>
          <span className="sharebars__val mono">{r.share_pct.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  )
}

/** Radial 3-grid flow diagram: Luzon -> Visayas -> Mindanao over the HVDC links. */
export function FlowDiagram({
  prices,
  corridors,
}: {
  prices: Record<string, number | null>
  corridors: {
    from: string
    to: string
    flow_mw?: number | null
    saturated?: boolean
    rent?: number
  }[]
}) {
  const nodes: Record<string, { x: number; label: string }> = {
    luzon: { x: 90, label: 'Luzon' },
    visayas: { x: 320, label: 'Visayas' },
    mindanao: { x: 550, label: 'Mindanao' },
  }
  const W = 640
  const y = 60
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} 130`}
      role="img"
      aria-label="Inter-island coupled flow diagram"
    >
      {corridors.map((c, i) => {
        const a = nodes[c.from]
        const b = nodes[c.to]
        if (!a || !b) return null
        const mid = (a.x + b.x) / 2
        return (
          <g key={i}>
            <line
              x1={a.x + 46}
              y1={y}
              x2={b.x - 46}
              y2={y}
              stroke={c.saturated ? 'var(--destructive)' : 'var(--border-strong)'}
              strokeWidth={c.saturated ? 4 : 2}
            />
            <text x={mid} y={y - 12} textAnchor="middle" className="chart__ax">
              {Math.abs(c.flow_mw ?? 0).toFixed(0)} MW{c.saturated ? ' · bound' : ''}
            </text>
            {c.saturated && c.rent ? (
              <text x={mid} y={y + 22} textAnchor="middle" className="chart__rent mono">
                rent ₱{c.rent.toFixed(2)}
              </text>
            ) : null}
          </g>
        )
      })}
      {Object.entries(nodes).map(([k, n]) => (
        <g key={k}>
          <circle
            cx={n.x}
            cy={y}
            r={44}
            fill="var(--surface-3)"
            stroke="var(--border-strong)"
            strokeWidth={1.5}
          />
          <text x={n.x} y={y - 6} textAnchor="middle" className="chart__node">
            {n.label}
          </text>
          <text x={n.x} y={y + 14} textAnchor="middle" className="chart__nodeval mono">
            ₱{(prices[k] ?? 0).toFixed(2)}
          </text>
        </g>
      ))}
    </svg>
  )
}

/** Paired bars comparing a metric before/after a scenario (e.g. LOLP with vs without). */
export function CompareBars({
  items,
  unit = '%',
  dp = 2,
}: {
  items: { label: string; a: number; b: number; aLabel: string; bLabel: string }[]
  unit?: string
  dp?: number
}) {
  const max = Math.max(...items.flatMap((i) => [i.a, i.b]), 0.0001)
  return (
    <div className="cmpbars">
      {items.map((it) => (
        <div className="cmpbars__group" key={it.label}>
          <div className="cmpbars__title">{it.label}</div>
          {(['a', 'b'] as const).map((k) => (
            <div className="cmpbars__row" key={k}>
              <span className="cmpbars__key">{k === 'a' ? it.aLabel : it.bLabel}</span>
              <span className="cmpbars__track">
                <span
                  className={`cmpbars__fill cmpbars__fill--${k}`}
                  style={{ width: `${(it[k] / max) * 100}%` }}
                />
              </span>
              <span className="cmpbars__val mono">
                {it[k].toFixed(dp)}
                {unit}
              </span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
