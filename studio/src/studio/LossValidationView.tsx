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
  const pad = 30
  const xs = pts.map((p) => p[0])
  const ys = pts.map((p) => p[1])
  const xlo = Math.min(...xs)
  const xhi = Math.max(...xs)
  const ylo = Math.min(...ys, 0)
  const yhi = Math.max(...ys, 0)
  const X = (v: number) => pad + ((v - xlo) / (xhi - xlo || 1)) * (W - pad - 8)
  const Y = (v: number) => 8 + (1 - (v - ylo) / (yhi - ylo || 1)) * (H - 8 - pad)
  const edge = validated ? GOOD : CRIT
  const fitY = (x: number) => w.affine_slope * x + w.affine_intercept_php_kwh
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="lossfit" role="img" aria-label="scatter">
      <line x1={pad} y1={Y(0)} x2={W - 8} y2={Y(0)} className="chart__ax" />
      {pts.map((p, i) => (
        <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={2.6} fill={color} opacity={0.45} />
      ))}
      <line
        x1={X(xlo)}
        y1={Y(fitY(xlo))}
        x2={X(xhi)}
        y2={Y(fitY(xhi))}
        stroke="#12335c"
        strokeWidth={1.6}
      />
      <text x={pad} y={H - 8} className="chart__ax">
        modeled loss factor
      </text>
      <rect
        x={pad + 2}
        y={10}
        width={116}
        height={20}
        rx={4}
        fill="#fff"
        stroke={edge}
        strokeWidth={1}
        opacity={0.92}
      />
      <text x={pad + 8} y={24} fontSize={11} fill="#12335c">
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
                hint={
                  validated
                    ? `validated · ${w.n_nodes} nodes`
                    : `fails · ${w.n_nodes} nodes`
                }
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
                    error {w.mae_after_affine_php_kwh.toFixed(2)} ₱/kWh
                  </span>
                </div>
                <Scatter pts={pts} w={w} color={REGION[g]} validated={validated} />
              </div>
            )
          })}
        </div>
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
