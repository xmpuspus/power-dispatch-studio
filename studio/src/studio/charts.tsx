import type { Block, DurationPoint } from '../lib/types'
import { fuelColor, fuelLabel } from '../lib/data'

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
  observed = [],
}: {
  modeled: DurationPoint[]
  observed?: DurationPoint[]
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
      {observed.length > 0 && (
        <polyline
          points={path(observed)}
          fill="none"
          stroke="var(--series-observed)"
          strokeWidth={2}
        />
      )}
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

// ---- chronological run charts -------------------------------------------------

export interface LineSeries {
  label: string
  color: string
  pts: (number | null)[]
  dash?: string
}

/** Multi-series line chart over run hours, directly labeled at the line ends. */
export function HourLines({
  series,
  marks = [],
  height = 220,
}: {
  series: LineSeries[]
  marks?: { x: number; label: string }[]
  height?: number
}) {
  const W = 640
  const H = height
  const padL = 40
  const padR = 76
  const padT = 12
  const padB = 24
  const n = Math.max(...series.map((s) => s.pts.length), 2)
  const vals = series.flatMap((s) => s.pts.filter((v): v is number => v != null))
  if (!vals.length) return null
  const ymin = Math.min(...vals, 0)
  const ymax = Math.max(...vals)
  const span = ymax - ymin || 1
  const X = (i: number) => padL + ((W - padL - padR) * i) / (n - 1)
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - ymin) / span)
  const path = (pts: (number | null)[]) =>
    pts
      .map((v, i) => (v == null ? null : `${X(i).toFixed(1)},${Y(v).toFixed(1)}`))
      .filter(Boolean)
      .join(' ')
  const ticks = [ymax, (ymax + ymin) / 2, ymin]
  const lastIdx = (pts: (number | null)[]) => {
    for (let i = pts.length - 1; i >= 0; i--) if (pts[i] != null) return i
    return 0
  }
  // direct end labels, nudged apart when converging lines would overprint them
  const labels = series
    .map((s, si) => ({
      si,
      x: X(lastIdx(s.pts)) + 5,
      y: Y(s.pts[lastIdx(s.pts)] ?? ymin) + 3,
    }))
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < labels.length; i++)
    if (labels[i].y - labels[i - 1].y < 11) labels[i].y = labels[i - 1].y + 11
  const labelAt = new Map(labels.map((l) => [l.si, l]))
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Hourly series over the run window"
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
            {v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(1)}
          </text>
        </g>
      ))}
      {marks.map((m, i) => (
        <g key={`m${i}`}>
          <line
            x1={X(m.x)}
            y1={padT}
            x2={X(m.x)}
            y2={H - padB}
            stroke="var(--border-strong)"
            strokeWidth={0.75}
            strokeDasharray="2 3"
          />
          <text x={X(m.x) + 3} y={H - padB + 12 + (i % 2) * 11} className="chart__ax">
            {m.label}
          </text>
        </g>
      ))}
      {series.map((s, si) => (
        <g key={s.label}>
          <polyline
            points={path(s.pts)}
            fill="none"
            stroke={s.color}
            strokeWidth={1.8}
            strokeDasharray={s.dash}
          />
          <text
            x={labelAt.get(si)?.x ?? 0}
            y={labelAt.get(si)?.y ?? 0}
            className="chart__lbl"
            fill={s.color}
          >
            {s.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

const AREA_ORDER = [
  'solar',
  'wind',
  'hydro',
  'geothermal',
  'natural_gas',
  'biomass',
  'coal',
  'storage',
  'oil',
]

/** Stacked dispatch-by-fuel area over run hours, demand cursor line on top. */
export function DispatchArea({
  fuelGen,
  demand,
  marks = [],
}: {
  fuelGen: Record<string, number>[]
  demand: number[]
  marks?: { x: number; label: string }[]
}) {
  const W = 640
  const H = 220
  const padL = 46
  const padR = 12
  const padT = 12
  const padB = 24
  const n = fuelGen.length
  if (!n) return null
  const totals = fuelGen.map((fg) => Object.values(fg).reduce((s, v) => s + v, 0))
  const ymax = Math.max(...totals, ...demand) * 1.04 || 1
  const X = (i: number) => padL + ((W - padL - padR) * i) / (n - 1)
  const Y = (v: number) => padT + (H - padT - padB) * (1 - v / ymax)
  const fuels = AREA_ORDER.filter((f) => fuelGen.some((fg) => (fg[f] ?? 0) > 0))
  const cum = fuelGen.map(() => 0)
  const bands = fuels.map((f) => {
    const lower = [...cum]
    for (let i = 0; i < n; i++) cum[i] += fuelGen[i][f] ?? 0
    const upper = [...cum]
    const fwd = upper.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`)
    const back = lower.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).reverse()
    return { fuel: f, d: `${fwd.join(' ')} ${back.join(' ')}` }
  })
  const yticks = [ymax / 1.04, ymax / 2]
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Dispatch by fuel over the run window"
    >
      {bands.map((b) => (
        <polygon key={b.fuel} points={b.d} fill={fuelColor(b.fuel)} opacity={0.88}>
          <title>{fuelLabel(b.fuel)}</title>
        </polygon>
      ))}
      <polyline
        points={demand.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}
        fill="none"
        stroke="var(--text)"
        strokeWidth={1.4}
        strokeDasharray="3 2"
      />
      {yticks.map((v, i) => (
        <text key={i} x={padL - 6} y={Y(v) + 3} textAnchor="end" className="chart__ax">
          {Math.round(v / 1000).toLocaleString()}k
        </text>
      ))}
      {marks.map((m, i) => (
        <line
          key={`m${i}`}
          x1={X(m.x)}
          y1={padT}
          x2={X(m.x)}
          y2={H - padB}
          stroke="var(--surface)"
          strokeWidth={1}
        />
      ))}
      <text x={W - padR} y={H - 8} textAnchor="end" className="chart__ax">
        MW dispatched, demand dashed
      </text>
    </svg>
  )
}

/** Storage state of charge with the charge (down) / discharge (up) schedule. */
export function SocChart({
  soc,
  charge,
  discharge,
  energyMwh,
}: {
  soc: number[]
  charge: number[]
  discharge: number[]
  energyMwh: number
}) {
  const W = 640
  const H = 180
  const padL = 46
  const padR = 12
  const padT = 10
  const padB = 40
  const n = soc.length
  const ymax = Math.max(energyMwh, ...soc, 1)
  const X = (i: number) => padL + ((W - padL - padR) * i) / (n - 1)
  const Y = (v: number) => padT + (H - padT - padB) * (1 - v / ymax)
  const pmax = Math.max(...charge, ...discharge, 1)
  const barH = 22
  const base = H - padB + barH / 2 + 6
  const area =
    soc.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ') +
    ` ${X(n - 1).toFixed(1)},${Y(0).toFixed(1)} ${X(0).toFixed(1)},${Y(0).toFixed(1)}`
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Storage state of charge and cycle schedule"
    >
      <polygon points={area} fill="var(--series-storage)" opacity={0.25} />
      <polyline
        points={soc.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')}
        fill="none"
        stroke="var(--series-storage)"
        strokeWidth={2}
      />
      <line
        x1={padL}
        y1={Y(energyMwh)}
        x2={W - padR}
        y2={Y(energyMwh)}
        stroke="var(--border-strong)"
        strokeWidth={0.75}
        strokeDasharray="2 3"
      />
      <text x={padL - 6} y={Y(energyMwh) + 3} textAnchor="end" className="chart__ax">
        {Math.round(energyMwh).toLocaleString()}
      </text>
      <text x={padL - 6} y={Y(0) + 3} textAnchor="end" className="chart__ax">
        0
      </text>
      {soc.map((_, i) => {
        const c = charge[i]
        const dch = discharge[i]
        if (!c && !dch) return null
        const h = ((c || dch) / pmax) * (barH / 2)
        return (
          <rect
            key={i}
            x={X(i) - 3}
            y={c ? base : base - h}
            width={6}
            height={Math.max(1, h)}
            fill={c ? 'var(--series-flow)' : 'var(--accent)'}
          >
            <title>
              h{i}: {c ? `charge ${Math.round(c)} MW` : `discharge ${Math.round(dch)} MW`}
            </title>
          </rect>
        )
      })}
      <text x={padL} y={H - 2} className="chart__ax">
        state of charge MWh; charge down, discharge up
      </text>
    </svg>
  )
}

/** Hourly percentile band (p10 to p90 shaded, median line) with an optional
 * dashed comparison series, e.g. the base model's median. */
export function BandChart({
  band,
  compare,
  compareLabel = 'base median',
}: {
  band: { p10: number; p50: number; p90: number }[]
  compare?: number[]
  compareLabel?: string
}) {
  const W = 640
  const H = 220
  const padL = 40
  const padR = 76
  const padT = 12
  const padB = 24
  const n = band.length
  if (!n) return null
  const vals = band.flatMap((b) => [b.p10, b.p90]).concat(compare ?? [])
  const ymin = Math.min(...vals)
  const ymax = Math.max(...vals)
  const span = ymax - ymin || 1
  const X = (i: number) => padL + ((W - padL - padR) * i) / (n - 1)
  const Y = (v: number) => padT + (H - padT - padB) * (1 - (v - ymin) / span)
  const line = (pts: number[]) =>
    pts.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(' ')
  const area =
    band.map((b, i) => `${X(i).toFixed(1)},${Y(b.p90).toFixed(1)}`).join(' ') +
    ' ' +
    band
      .map((b, i) => `${X(i).toFixed(1)},${Y(b.p10).toFixed(1)}`)
      .reverse()
      .join(' ')
  const ticks = [ymax, (ymax + ymin) / 2, ymin]
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Hourly price percentile band across replayed days"
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
            {v.toFixed(1)}
          </text>
        </g>
      ))}
      <polygon points={area} fill="var(--series-modeled)" opacity={0.16} />
      <polyline
        points={line(band.map((b) => b.p50))}
        fill="none"
        stroke="var(--series-modeled)"
        strokeWidth={2}
      />
      {compare && compare.length === n && (
        <polyline
          points={line(compare)}
          fill="none"
          stroke="var(--series-observed)"
          strokeWidth={1.6}
          strokeDasharray="4 3"
        />
      )}
      <text
        x={X(n - 1) + 5}
        y={Y(band[n - 1].p50) + 3}
        className="chart__lbl"
        fill="var(--series-modeled)"
      >
        median
      </text>
      {compare && compare.length === n && (
        <text
          x={X(n - 1) + 5}
          y={Y(compare[n - 1]) + 14}
          className="chart__lbl"
          fill="var(--series-observed)"
        >
          {compareLabel}
        </text>
      )}
      <text x={padL} y={H - 8} className="chart__ax">
        h0
      </text>
      <text x={W - padR} y={H - 8} textAnchor="end" className="chart__ax">
        h23; band = 10th to 90th percentile across days
      </text>
    </svg>
  )
}

/** One cell per hour, colored by what set the price: the binding-constraint strip. */
export function BindingStrip({
  cells,
}: {
  cells: { cause: 'unserved' | 'corridor' | 'fuel'; detail: string }[]
}) {
  const n = cells.length
  if (!n) return null
  const W = 640
  const H = 46
  const gap = n > 48 ? 0.5 : 1.5
  const w = (W - gap * (n - 1)) / n
  const fill = (c: { cause: string; detail: string }) =>
    c.cause === 'unserved'
      ? 'var(--destructive)'
      : c.cause === 'corridor'
        ? 'var(--accent)'
        : fuelColor(c.detail)
  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="What set the price each hour"
    >
      {cells.map((c, i) => (
        <rect
          key={i}
          x={i * (w + gap)}
          y={6}
          width={w}
          height={26}
          rx={1.5}
          fill={fill(c)}
          opacity={0.92}
        >
          <title>
            h{i % 24}:{' '}
            {c.cause === 'fuel' ? `${fuelLabel(c.detail)} on the margin` : c.detail}
          </title>
        </rect>
      ))}
      <text x={0} y={H - 3} className="chart__ax">
        one cell per hour
      </text>
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
