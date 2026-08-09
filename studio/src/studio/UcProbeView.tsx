// The mixed-integer unit-commitment test, published rather than hidden.
// A licensed production-cost tool commits each thermal unit with a
// minimum-stable level and a start cost. This project ran that variant against
// the same recorded days and the price match got worse in every measured pair,
// so the linear model stays the default. pipeline/uc_probe.py writes the rows.

import { useMarketOps } from '../lib/data'
import type { GridKey, UcProbe } from '../lib/types'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const METRIC: Record<string, string> = {
  lwap: 'load-weighted average price (LWAP)',
  mcp: 'market clearing price (MCP)',
}

export interface Row {
  key: string
  pair: string
  hours: number
  lp: number
  uc: number
  delta: number
  maeLp: number
  maeUc: number
}

/** One row per scored series. A series with no paired hours drops out. */
export function ucRows(p: UcProbe): Row[] {
  const out: Row[] = []
  for (const metric of ['lwap', 'mcp']) {
    for (const g of GRIDS) {
      const lp = p.lp?.[metric]?.[g]
      const uc = p.uc?.[metric]?.[g]
      if (!lp || !uc) continue
      out.push({
        key: `${metric}-${g}`,
        pair: `${cap(g)} ${METRIC[metric]}`,
        hours: lp.n_hours,
        lp: lp.correlation,
        uc: uc.correlation,
        delta: Math.round((uc.correlation - lp.correlation) * 1000) / 1000,
        maeLp: lp.mae_php_kwh,
        maeUc: uc.mae_php_kwh,
      })
    }
  }
  return out
}

const sign = (v: number) => (v > 0 ? `+${v.toFixed(3)}` : v.toFixed(3))

export function UcProbeView() {
  const mo = useMarketOps()
  const p = mo.data?.uc_probe
  if (mo.loading) return <EmptyNote>Loading the commitment test.</EmptyNote>
  if (!p || p.available === false || !p.lp)
    return <EmptyNote>No commitment test in this data build.</EmptyNote>

  const r = ucRows(p)
  if (!r.length) return <EmptyNote>The commitment test scored no paired hours.</EmptyNote>
  const worst = r.reduce((a, b) => (b.delta < a.delta ? b : a))
  const maeShift = r.reduce((s, x) => s + Math.abs(x.maeUc - x.maeLp), 0) / r.length

  const cols: Column<Row>[] = [
    { key: 'pair', header: 'Recorded price series', render: (x) => x.pair },
    {
      key: 'hours',
      header: 'Paired hours',
      align: 'right',
      mono: true,
      render: (x) => x.hours.toLocaleString('en-US'),
    },
    {
      key: 'lp',
      header: 'Linear model',
      align: 'right',
      mono: true,
      render: (x) => x.lp.toFixed(3),
    },
    {
      key: 'uc',
      header: 'With commitment',
      align: 'right',
      mono: true,
      render: (x) => x.uc.toFixed(3),
    },
    {
      key: 'delta',
      header: 'Change',
      align: 'right',
      mono: true,
      render: (x) => sign(x.delta),
    },
    {
      key: 'mae',
      header: 'Average error, PhP/kWh',
      align: 'right',
      mono: true,
      render: (x) => `${x.maeLp.toFixed(2)} to ${x.maeUc.toFixed(2)}`,
    },
  ]

  const stable = Object.entries(p.min_stable_generic ?? {})
  const stableCols: Column<[string, number]>[] = [
    { key: 'fuel', header: 'Fuel', render: (x) => x[0].replace(/_/g, ' ') },
    {
      key: 'frac',
      header: 'Share of the committed block that must keep running',
      align: 'right',
      mono: true,
      render: (x) => `${Math.round(x[1] * 100)}%`,
    },
  ]

  return (
    <div className="view">
      <Panel
        title={`Committing each thermal block lowered the price correlation in all ${r.length} recorded series`}
        subtitle={
          'Correlation between the modeled hourly price and the recorded price, ' +
          'with and without mixed-integer commitment, over the same days. ' +
          'Higher is better. LWAP is the load-weighted average price, and MCP is the market clearing price.'
        }
      >
        <DataGrid columns={cols} rows={r} getKey={(x) => x.key} />
        <div className="stat-row">
          <StatTile
            label="Largest fall"
            value={sign(worst.delta)}
            hint={`${worst.pair}, from ${worst.lp.toFixed(3)} to ${worst.uc.toFixed(3)}`}
            tone="danger"
          />
          <StatTile
            label="Mean change in average error"
            value={`P${maeShift.toFixed(3)}`}
            unit="/kWh"
            hint="The error barely moves, and only the correlation falls"
          />
          <StatTile
            label="Engine the studio runs"
            value={p.engine_default === 'lp' ? 'Linear' : String(p.engine_default)}
            hint="The measurement chose it, and no preference did"
          />
        </div>
        <p className="note">
          The probe writes this verdict into the data build: {p.verdict}. LP is the linear
          program this studio solves in your browser.
        </p>
      </Panel>

      <Panel
        title="The test used generic minimum-stable levels, because no Philippine unit registry publishes them"
        subtitle="Share of a committed block that must keep running, applied at the fuel-block level."
      >
        <DataGrid
          columns={stableCols}
          rows={stable}
          getKey={(x) => x[0]}
          empty="This build states no minimum-stable levels."
        />
        <p className="note">{p.min_stable_label}</p>
        <p className="note">
          A fuel-block floor is coarser than a per-unit floor. That coarseness is the most
          likely reason the commitment run scores worse, and a per-unit registry is what a
          sharper test needs. Written by {p.generated_by}.
        </p>
      </Panel>
    </div>
  )
}
