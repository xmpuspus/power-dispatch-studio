// The loss-surface validation (pipeline/loss_surface.py): does network
// physics rank the market's own per-node price deviations? Because WESM's
// within-region nodal structure is a loss surface (the congestion column
// is zero), marginal loss factors from the OSM-geometry backbone are a
// testable prediction of the observed per-node deviations. One panel per
// grid, the same numbers the figure in the README draws, recomputed
// nightly. Validation, not a model output: the verdict per grid is stated,
// failing grids included.

import { useLossSurface } from '../lib/data'
import type { LossGridWindow } from '../lib/types'
import { Panel, StatTile, EmptyNote } from '../ui/kit'

const GRIDS = ['luzon', 'visayas', 'mindanao'] as const
const GOOD = '#1a7f48'
const CRIT = '#b3261e'
const REGION: Record<string, string> = {
  luzon: '#4e79a7',
  visayas: '#e2664b',
  mindanao: '#1a7f48',
}

function fmtAxis(v: number): string {
  return Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2)
}

function Scatter({
  pts,
  w,
  color,
  validated,
}: {
  pts: [number, number][]
  w: LossGridWindow
  color: string
  validated: boolean
}) {
  const W = 300
  const H = 220
  const padL = 34
  const padB = 34
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  const xlo = Math.min(...xs)
  const xhi = Math.max(...xs)
  const ylo = Math.min(...ys, 0)
  const yhi = Math.max(...ys, 0)
  const xMid = (xlo + xhi) / 2
  const yMid = (ylo + yhi) / 2
  const X = (v: number) => padL + ((v - xlo) / (xhi - xlo || 1)) * (W - padL - 8)
  const Y = (v: number) => 8 + (1 - (v - ylo) / (yhi - ylo || 1)) * (H - 8 - padB)
  const edge = validated ? GOOD : CRIT
  const fitY = (x: number) => w.affine_slope * x + w.affine_intercept_php_kwh
  const yTitleY = (8 + (H - padB)) / 2
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="lossfit" role="img" aria-label="scatter">
      <line x1={padL} y1={Y(0)} x2={W - 8} y2={Y(0)} className="chart__ax" />
      {pts.map((p, i) => (
        <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={2.6} fill={color} opacity={0.45} />
      ))}
      <line
        x1={X(xlo)}
        y1={Y(fitY(xlo))}
        x2={X(xhi)}
        y2={Y(fitY(xhi))}
        stroke="var(--text)"
        strokeWidth={1.6}
      />
      <text x={X(xlo)} y={H - padB + 12} className="chart__ax" textAnchor="start">
        {fmtAxis(xlo)}
      </text>
      <text x={X(xMid)} y={H - padB + 12} className="chart__ax" textAnchor="middle">
        {fmtAxis(xMid)}
      </text>
      <text x={X(xhi)} y={H - padB + 12} className="chart__ax" textAnchor="end">
        {fmtAxis(xhi)}
      </text>
      <text x={padL} y={H - 8} className="chart__ax">
        modeled loss factor
      </text>
      <text x={padL - 4} y={Y(yhi) + 3} className="chart__ax" textAnchor="end">
        {fmtAxis(yhi)}
      </text>
      <text x={padL - 4} y={Y(yMid) + 3} className="chart__ax" textAnchor="end">
        {fmtAxis(yMid)}
      </text>
      <text x={padL - 4} y={Y(ylo) + 3} className="chart__ax" textAnchor="end">
        {fmtAxis(ylo)}
      </text>
      <text
        x={10}
        y={yTitleY}
        className="chart__ax"
        textAnchor="middle"
        transform={`rotate(-90 10 ${yTitleY})`}
      >
        observed deviation, ₱/kWh
      </text>
      <rect
        x={padL + 2}
        y={10}
        width={116}
        height={20}
        rx={4}
        fill="var(--surface)"
        stroke={edge}
        strokeWidth={1}
        opacity={0.92}
      />
      <text x={padL + 8} y={24} fontSize={11} fill="var(--text)">
        Spearman {w.spearman >= 0 ? '+' : ''}
        {w.spearman.toFixed(2)}
      </text>
    </svg>
  )
}

export function LossValidationView() {
  const ls = useLossSurface()
  const d = ls.data

  if (!d?.available || !d.window || !d.scatter)
    return (
      <div className="view">
        <Panel
          title="Loss-surface validation"
          subtitle="Network physics against the market's own per-node prices."
        >
          <EmptyNote>Not baked yet. Run pipeline/loss_surface.py, then rebake.</EmptyNote>
        </Panel>
      </div>
    )

  return (
    <div className="view">
      <Panel
        title="Does network physics track the market's own per-node prices?"
        subtitle={`Marginal loss factors from the OpenStreetMap grid against WESM's published per-node deviations, over ${d.clean_days} clean market days. Recomputed nightly.`}
      >
        <div className="stat-row">
          {GRIDS.map((g) => {
            const w = d.window![g]
            const validated = (d.validated_grids ?? []).includes(g)
            if (!w) return null
            return (
              <StatTile
                key={g}
                label={g[0].toUpperCase() + g.slice(1)}
                value={`${w.spearman >= 0 ? '+' : ''}${w.spearman.toFixed(2)}`}
                hint={`${validated ? 'validated' : 'fails'} · ${w.n_nodes} nodes, ${
                  w.n_bus
                } independent bus · 95% CI [${w.spearman_ci95[0].toFixed(2)}, ${w.spearman_ci95[1].toFixed(2)}]`}
              />
            )
          })}
        </div>
        <div className="lossgrid">
          {GRIDS.map((g) => {
            const w = d.window![g]
            const pts = d.scatter![g]
            if (!w || !pts) return null
            const validated = (d.validated_grids ?? []).includes(g)
            return (
              <div key={g} className="losspanel">
                <div
                  className="losspanel__title"
                  style={{ color: validated ? GOOD : CRIT }}
                >
                  {g[0].toUpperCase() + g.slice(1)}
                  <span className="losspanel__err">
                    R² {w.r2.toFixed(2)} · error {w.mae_after_affine_php_kwh.toFixed(2)}{' '}
                    ₱/kWh
                  </span>
                </div>
                <Scatter pts={pts} w={w} color={REGION[g]} validated={validated} />
              </div>
            )
          })}
        </div>
        <p className="note">
          Each panel's axes are a per-grid affine reference, not comparable across panels.
        </p>
        <p className="note">{d.finding}</p>
        <p className="note">
          The claim is the Spearman rank correlation: does the network model order the
          nodes the way the market's own settlement does? The line is the fitted affine
          convention (the loss reference is an affine choice, so slope and intercept are
          fitted and reported, not hidden), and the error is the mean gap from that line
          per node. Resistances are class-typical values scaled by real routed length,
          labeled estimates like the reactances. Grids that fail the test are shown
          failing, not dropped.
        </p>
      </Panel>
    </div>
  )
}
