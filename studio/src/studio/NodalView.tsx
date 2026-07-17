// Observed per-node price deviations (pipeline/nodal_obs.py): which WESM
// nodes persistently price above or below their regional SMP, from the
// derived DIPCEF nodal dailies, clean market days only. Purely observed;
// the modeled nodal counterfactual stays a labeled probe (methodology).

import { useMemo, useState } from 'react'
import type { GridKey } from '../lib/types'
import { useNodalObs } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const sgn = (v: number) => `${v > 0 ? '+' : ''}₱${v.toFixed(2)}`

export function NodalView({ grid }: { grid: GridKey }) {
  const obs = useNodalObs()
  const [q, setQ] = useState('')
  const d = obs.data
  const pg = d?.per_grid?.[grid]

  const rows = useMemo(() => {
    if (!d?.nodes) return []
    const mine = d.nodes.filter((n) => n.grid === grid)
    const needle = q.trim().toUpperCase()
    const hit = needle ? mine.filter((n) => n.res.includes(needle)) : mine
    return [...hit].sort((a, b) => b.dev - a.dev)
  }, [d, grid, q])

  if (!d?.available || !pg || !d.window)
    return (
      <div className="view">
        <Panel
          title="Nodal prices, observed"
          subtitle="Per-node deviations from the regional price."
        >
          <EmptyNote>
            No nodal dailies baked yet. Run pipeline/nodal_prices.py --derive, then
            rebake.
          </EmptyNote>
        </Panel>
      </div>
    )

  const shown = rows.slice(0, 25)
  return (
    <div className="view">
      <Panel
        title={`Persistent locational deviations, ${cap(grid)}`}
        subtitle={`Mean deviation of each node's price from the ${cap(grid)} regional SMP over the window's ${d.window.clean_days} clean market days (DIPCEF final; administered PSM/SEC days excluded).`}
      >
        <div className="stat-row">
          <StatTile
            label="Nodes priced"
            value={String(pg.n_nodes)}
            hint={`of ${d.n_nodes} across the three grids`}
          />
          <StatTile
            label="5th to 95th percentile"
            value={`${pg.p5.toFixed(2)} to +${pg.p95.toFixed(2)}`}
            hint="pesos per kWh vs the regional price"
          />
          <StatTile
            label="Widest premium"
            value={sgn(pg.top[0]?.dev ?? 0)}
            hint={pg.top[0]?.res ?? ''}
          />
          <StatTile
            label="Widest discount"
            value={sgn(pg.bottom[0]?.dev ?? 0)}
            hint={pg.bottom[0]?.res ?? ''}
          />
        </div>
        <p className="note">
          Observed deviations, not congestion premiums: WESM's published nodal congestion
          component is zero on every sampled day, so within-region separation formally
          rides the loss column and intra-regional congestion is handled through
          administered actions (price substitution, security limits, constrained-on
          payments). The map's Prices mode draws the {d.n_placed} nodes that resolve to a
          mapped station; this table lists every node.
        </p>
      </Panel>

      <Panel
        title="Every node in the grid"
        subtitle="Sorted premium first. Search by resource code (plants end _Gxx, loads _Lxx, delivery points _T1L1)."
      >
        <input
          className="ribbon__select"
          type="search"
          placeholder="Filter nodes, e.g. SUAL or _L"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Filter nodes"
        />
        <table className="propgrid">
          <thead>
            <tr>
              <th>Node</th>
              <th className="num">vs regional ₱/kWh</th>
              <th className="num">clean days</th>
              <th className="num">mean MW</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((n) => (
              <tr key={n.res}>
                <td>{n.res}</td>
                <td className="num">{sgn(n.dev)}</td>
                <td className="num">{n.days}</td>
                <td className="num">{n.mw ? n.mw.toFixed(0) : '0'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > shown.length && (
          <p className="note">
            Showing 25 of {rows.length} matching nodes; narrow the filter for the rest.
            The full table ships in nodal_obs.json.
          </p>
        )}
        <p className="note">
          Window {d.window.first} to {d.window.last}: {d.window.days_derived} derived
          days, {d.window.clean_days} clean ({d.window.clean_criterion}). A modeled
          counterfactual ("what would a data center at node X pay?") stays a labeled probe
          until more of the fleet resolves onto network buses; see the methodology's nodal
          section.
        </p>
      </Panel>
    </div>
  )
}
