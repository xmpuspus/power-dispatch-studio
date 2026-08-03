// Observed per-node price deviations (pipeline/nodal_obs.py): which WESM
// nodes persistently price above or below their regional SMP, from the
// derived DIPCEF nodal dailies, clean market days only. Purely observed;
// the modeled nodal counterfactual stays a labeled probe (methodology).

import { useMemo, useState } from 'react'
import type { GridKey } from '../lib/types'
import { useLossSurface, useNodalObs } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { ScrollBox } from '../ui/ScrollBox'

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
    "Recorded price differences are not the same as congestion premiums. The operator's final " +
    'per-resource prices include a congestion component that is zero through ' +
    'the WESM suspension window and small and ' +
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
          title="A connection point's price leaves the regional price by the losses and limits on the way there"
          subtitle="Each value is the difference from the island grid's regional price."
        >
          <EmptyNote>
            Daily prices at individual grid connection points are not available in this
            data release.
          </EmptyNote>
        </Panel>
      </div>
    )

  const shown = rows.slice(0, 25)
  return (
    <div className="view">
      <Panel
        title={`Average price difference at each ${cap(grid)} grid connection point`}
        subtitle={`Each value is the mean difference from the ${cap(grid)} regional system marginal price over ${d.window.clean_days} market days. Final per-resource prices are used. Days with administered pricing are excluded.`}
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
          These averages show the direction of local price differences but are not capture
          prices. The peak and midday columns show how each node changes within a day. The
          sample covers only the listed market days, so do not use these values to size a
          power purchase agreement (PPA) or bid.
        </p>
      </Panel>

      <Panel
        title="Every connection point carries its own gap from the regional price"
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
        <ScrollBox className="propgrid-wrap">
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
        </ScrollBox>
        {rows.length > shown.length && (
          <p className="note">
            Showing 25 of {rows.length} matching nodes. Sort or narrow the filter to see
            the rest. The full table is available in nodal_obs.json.
          </p>
        )}
        <p className="note">
          The window runs from {d.window.first} to {d.window.last} and includes{' '}
          {d.window.days_derived} recorded days. Of those, {d.window.clean_days} meet the
          market-day rule ({d.window.clean_criterion}). A modeled data-center price at one
          node remains an exploratory estimate until more power plants are matched to
          network buses. See the nodal section of the methodology.
        </p>
      </Panel>
    </div>
  )
}
