// Expansion mix (roadmap item 12): a least-cost greenfield capacity build over
// the DOE PDP demand path, next to the DOE's own pipeline. The point is not to
// replace the plan but to check it: a least-cost optimizer with generic NREL ATB
// costs should land renewable-heavy the way the DOE plan does, and it does.

import { useExpansion } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'

const fuelLabel = (f: string) => f.replace(/_/g, ' ')
const ORDER = ['wind', 'solar', 'hydro', 'geothermal', 'natural_gas', 'coal', 'oil', 'storage', 'biomass']

interface Row {
  fuel: string
  opt: number
  doe: number
}

export function ExpansionView() {
  const e = useExpansion()
  const d = e.data
  if (!d?.available || !d.optimized || !d.doe_pipeline)
    return (
      <div className="view">
        <Panel title="Expansion mix" subtitle="Least-cost greenfield build vs the DOE plan.">
          <EmptyNote>No expansion result baked yet. Run pipeline/expansion.py and rebake.</EmptyNote>
        </Panel>
      </div>
    )

  const opt = d.optimized.mix_share_pct
  const doe = d.doe_pipeline.mix_share_pct
  const fuels = ORDER.filter((f) => (opt[f] ?? 0) > 0 || (doe[f] ?? 0) > 0)
  const rows: Row[] = fuels.map((f) => ({ fuel: f, opt: opt[f] ?? 0, doe: doe[f] ?? 0 }))
  const cols: Column<Row>[] = [
    { key: 'fuel', header: 'Technology', render: (r) => fuelLabel(r.fuel) },
    { key: 'opt', header: 'Least-cost build', align: 'right', mono: true, render: (r) => `${r.opt.toFixed(1)}%` },
    { key: 'doe', header: 'DOE pipeline', align: 'right', mono: true, render: (r) => `${r.doe.toFixed(1)}%` },
  ]

  return (
    <div className="view">
      <Panel
        title={`Expansion mix to ${d.horizon_year}`}
        subtitle="A least-cost greenfield capacity build over the DOE PDP peak demand, beside the DOE's own pipeline. Check the plan, not replace it."
      >
        <div className="stat-row">
          <StatTile label="Least-cost RE share" value={`${d.optimized.re_share_pct}%`} hint="solar, wind, hydro, geo" />
          <StatTile label="DOE pipeline RE share" value={`${d.doe_pipeline.re_share_pct}%`} hint="the plan" />
          <StatTile label={`${d.horizon_year} peak`} value={`${Math.round((d.peak_mw ?? 0) / 1000)} GW`} hint={`+${d.reserve_margin_pct}% reserve`} />
        </div>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.fuel} />
        <p className="note">
          {d.verdict} {d.costs_note} The least-cost build and the DOE pipeline are both
          renewable-heavy, wind and solar led, so the plan's direction survives a cost test
          it was never shown. This is an adequacy-and-cost screen, not the DOE's full
          resource plan: LOLE detail, transmission, and siting stay with the DOE model.
        </p>
      </Panel>
    </div>
  )
}
