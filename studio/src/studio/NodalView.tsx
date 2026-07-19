// Observed per-node price deviations (pipeline/nodal_obs.py): which WESM
// nodes persistently price above or below their regional SMP, from the
// derived DIPCEF nodal dailies, clean market days only. Purely observed;
// the modeled nodal counterfactual stays a labeled probe (methodology).

import { useMemo, useState } from 'react'
import type { GridKey } from '../lib/types'
import { useLossSurface, useNodalObs } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const sgn = (v: number) => `${v > 0 ? '+' : ''}₱${v.toFixed(2)}`

type SortKey = 'dev' | 'dev_pk' | 'dev_md' | 'days' | 'mw'

export function NodalView({ grid }: { grid: GridKey }) {
  const obs = useNodalObs()
  const ls = useLossSurface()
  const [q, setQ] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('dev')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const d = obs.data
  const pg = d?.per_grid?.[grid]
  const failing = (ls.data?.failing_grids ?? []).includes(grid)
  const mwShare = d?.resolution?.per_grid_mw_share?.[grid]

  const rows = useMemo(() => {
    if (!d?.nodes) return []
    const mine = d.nodes.filter((n) => n.grid === grid)
    const needle = q.trim().toUpperCase()
    const hit = needle ? mine.filter((n) => n.res.includes(needle)) : mine
    const dir = sortDir === 'asc' ? 1 : -1
    return [...hit].sort((a, b) => (a[sortKey] - b[sortKey]) * dir)
  }, [d, grid, q, sortKey, sortDir])

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(key)
      setSortDir('desc')
    }
  }
  const arrow = (key: SortKey) =>
    key === sortKey ? (sortDir === 'asc' ? ' (asc)' : ' (desc)') : ''

  const banner = failing
    ? `${cap(grid)} fails the loss-surface validation: a stable negative rank ` +
      'correlation across the clean sample days, sign reversal not yet diagnosed.' +
      (mwShare != null
        ? ` Only ${(mwShare * 100).toFixed(1)}% of ${cap(grid)}'s scheduled MW resolves to a mapped node.`
        : '') +
      ' Read these deviations with low confidence.'
    : null
  const congestionStat = d?.congestion
    ? `nonzero on ${d.congestion.days_nonzero} of ${d.congestion.days_sampled} sampled days, up to ₱${d.congestion.max_php_kwh.toFixed(2)}/kWh`
    : null
  const methodologyNote =
    'Observed deviations, not congestion premiums: the published DIPCEF congestion ' +
    'component is zero through the WESM suspension window and small and ' +
    'intermittent after real-time pricing resumed' +
    (congestionStat ? ` (${congestionStat})` : '') +
    ", so within-region separation mostly rides the loss column. The map's Prices " +
    `mode draws the ${d?.n_placed ?? 0} nodes that resolve to a mapped site ` +
    '(stations and plant sites exactly, locality centroids at city precision); ' +
    'this table lists every node.'

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
        {banner && <div className="basecase-banner">{banner}</div>}
        <div className="stat-row">
          <StatTile
            label="Nodes priced"
            value={String(pg.n_nodes)}
            hint={`of ${d.n_nodes} across the three grids, window has ${d.window.clean_days} clean days`}
          />
          <StatTile
            label="5th to 95th percentile"
            value={`${pg.p5.toFixed(2)} to +${pg.p95.toFixed(2)}`}
            hint="pesos per kWh vs the regional price"
          />
          <StatTile
            label="Widest premium"
            value={sgn(pg.top[0]?.dev ?? 0)}
            hint={
              pg.top[0]
                ? `${pg.top[0].res} · mean of ${pg.top[0].days} days · peak ${sgn(pg.top[0].dev_pk)}, mid ${sgn(pg.top[0].dev_md)}`
                : ''
            }
          />
          <StatTile
            label="Widest discount"
            value={sgn(pg.bottom[0]?.dev ?? 0)}
            hint={
              pg.bottom[0]
                ? `${pg.bottom[0].res} · mean of ${pg.bottom[0].days} days · peak ${sgn(pg.bottom[0].dev_pk)}, mid ${sgn(pg.bottom[0].dev_md)}`
                : ''
            }
          />
        </div>
        <p className="note">{methodologyNote}</p>
        <p className="note">
          Directional screen, not a capture price. Each figure is a mean over a small
          sample of clean days; the peak and mid-hour columns below show how much a node's
          price moves within a day. Do not use this number to size a PPA or bid.
        </p>
      </Panel>

      <Panel
        title="Every node in the grid"
        subtitle="Search by resource code, or click a column to sort (plants end _Gxx, loads _Lxx, delivery points _T1L1)."
      >
        <input
          className="ribbon__select"
          type="search"
          placeholder="Filter nodes, e.g. SUAL or _L"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Filter nodes"
        />
        <div className="propgrid-wrap">
          <table className="propgrid">
            <thead>
              <tr>
                <th>Node</th>
                <th className="propgrid__num sortable" onClick={() => sortBy('dev')}>
                  vs regional ₱/kWh{arrow('dev')}
                </th>
                <th className="propgrid__num sortable" onClick={() => sortBy('dev_pk')}>
                  peak ₱/kWh{arrow('dev_pk')}
                </th>
                <th className="propgrid__num sortable" onClick={() => sortBy('dev_md')}>
                  mid ₱/kWh{arrow('dev_md')}
                </th>
                <th className="propgrid__num sortable" onClick={() => sortBy('days')}>
                  clean days{arrow('days')}
                </th>
                <th className="propgrid__num sortable" onClick={() => sortBy('mw')}>
                  mean MW{arrow('mw')}
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((n) => (
                <tr key={n.res}>
                  <td>{n.res}</td>
                  <td className="propgrid__num">{sgn(n.dev)}</td>
                  <td className="propgrid__num">{sgn(n.dev_pk)}</td>
                  <td className="propgrid__num">{sgn(n.dev_md)}</td>
                  <td className="propgrid__num">{n.days}</td>
                  <td className="propgrid__num">{n.mw ? n.mw.toFixed(0) : '0'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length > shown.length && (
          <p className="note">
            Showing 25 of {rows.length} matching nodes; sort or narrow the filter for the
            rest. The full table ships in nodal_obs.json.
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
