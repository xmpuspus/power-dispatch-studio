// A lowest-cost new-build capacity mix over the DOE demand path, shown beside
// the DOE project list. Technology costs come from NREL ATB.

import { useExpansion } from '../lib/data'
import { Panel, StatTile, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'

const fuelLabel = (f: string) => f.replace(/_/g, ' ')
const ORDER = [
  'wind',
  'solar',
  'hydro',
  'geothermal',
  'natural_gas',
  'coal',
  'oil',
  'storage',
  'biomass',
]

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
        <Panel
          title="Least-cost build compared with the DOE plan"
          subtitle="A new-build capacity mix is compared with the DOE project list."
        >
          <EmptyNote>
            The new-capacity calculation is not available in this data release.
          </EmptyNote>
        </Panel>
      </div>
    )

  const opt = d.optimized.mix_share_pct
  const doe = d.doe_pipeline.mix_share_pct
  const fuels = ORDER.filter((f) => (opt[f] ?? 0) > 0 || (doe[f] ?? 0) > 0)
  const rows: Row[] = fuels.map((f) => ({ fuel: f, opt: opt[f] ?? 0, doe: doe[f] ?? 0 }))
  const cols: Column<Row>[] = [
    { key: 'fuel', header: 'Technology', render: (r) => fuelLabel(r.fuel) },
    {
      key: 'opt',
      header: 'Least-cost build',
      align: 'right',
      mono: true,
      render: (r) => `${r.opt.toFixed(1)}%`,
    },
    {
      key: 'doe',
      header: 'DOE announced projects',
      align: 'right',
      mono: true,
      render: (r) => `${r.doe.toFixed(1)}%`,
    },
  ]

  return (
    <div className="view">
      <Panel
        title={`Lowest-cost capacity mix through ${d.horizon_year}`}
        subtitle="The lowest-cost mix of new capacity that covers DOE PDP peak demand is compared with the DOE's announced projects. This checks the plan's direction but does not replace it."
      >
        <div className="stat-row">
          <StatTile
            label="Renewable share in lowest-cost mix"
            value={`${d.optimized.re_share_pct}%`}
            hint="solar, wind, hydro, geothermal"
          />
          <StatTile
            label="Renewable share of DOE announced projects"
            value={`${d.doe_pipeline.re_share_pct}%`}
            hint="the plan"
          />
          <StatTile
            label={`${d.horizon_year} peak`}
            value={`${Math.round((d.peak_mw ?? 0) / 1000)} GW`}
            hint={`+${d.reserve_margin_pct}% reserve`}
          />
        </div>
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.fuel} />
        <p className="note">
          {d.verdict} {d.costs_note} The lowest-cost build and the DOE project list both
          have large renewable shares led by wind and solar. This cost check supports the
          plan's general direction. It is a supply-adequacy and cost check, not the DOE's
          full resource plan. The DOE model also covers loss-of-load expectation (LOLE),
          which counts periods when supply cannot meet demand, plus transmission and
          siting.
        </p>
      </Panel>
    </div>
  )
}
