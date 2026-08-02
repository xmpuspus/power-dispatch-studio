// Assumption vintage: the data foundation an analyst needs to trust the
// tool before trusting a number out of it. Every row here is a generated value
// with its source or basis, nothing invented. Single-user, single-browser
// tool: no accounts, no server-side state, every value is a file this
// browser fetched from the same data build used by the rest of the studio.

import { useMeta, useEmissions, useMarketAnchors, num, php, pct } from '../lib/data'
import { Panel, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { ENGINE_VERSION } from './chrono'
import type { Dispatch } from '../lib/types'

interface ConstRow {
  label: string
  value: string
  source: string
  href?: string
}

export function VintageView({ d }: { d: Dispatch }) {
  const meta = useMeta()
  const em = useEmissions()
  const anchors = useMarketAnchors()

  if (meta.loading) return <EmptyNote>Loading the data record.</EmptyNote>
  if (meta.error || !meta.data)
    return (
      <EmptyNote>Data record not found. {meta.error ?? 'meta.json missing'}.</EmptyNote>
    )

  const a = d.assumptions
  const hy = a.hydrology
  const offerCap = anchors.data?.wesm_offer_cap_php_kwh
  const offerCapSrc = anchors.data?.src_offer_cap

  const constRows: ConstRow[] = [
    ...Object.entries(a.fuel_marginal_cost_php_kwh).map(([fuel, v]) => ({
      label: `Fuel marginal cost, ${fuel.replace(/_/g, ' ')}`,
      value: `${php(v)}/kWh`,
      source: a.note,
    })),
    {
      label: 'Coal commit price (must-run tranche)',
      value: `${php(a.coal_commit_php_kwh)}/kWh`,
      source: a.note,
    },
    {
      label: 'Coal minimum load fraction',
      value: pct(a.coal_min_load_frac),
      source: a.note,
    },
    {
      label: 'Wheeling cost',
      value: `${php(a.wheeling_cost_php_kwh)}/kWh`,
      source: a.note,
    },
    ...(offerCap != null
      ? [
          {
            label: 'WESM offer cap',
            value: `${php(offerCap)}/kWh`,
            source: 'WESM Tripartite Committee price ceiling, permanent since Dec 2015',
            href: offerCapSrc,
          },
        ]
      : []),
    {
      label: 'Hydrology, normal multiplier',
      value: num(hy.normal_multiplier, 2),
      source: hy.note,
    },
    {
      label: 'Hydrology, dry multiplier (El Nino)',
      value: num(hy.dry_multiplier, 3),
      source: hy.dry_label,
      href: hy.src_dry,
    },
    {
      label: 'Hydrology, wet multiplier',
      value: num(hy.wet_multiplier, 2),
      source: hy.note,
    },
  ]

  const constCols: Column<ConstRow>[] = [
    { key: 'label', header: 'Constant', render: (r) => r.label },
    { key: 'value', header: 'Value', align: 'right', mono: true, render: (r) => r.value },
    {
      key: 'src',
      header: 'Source / basis',
      render: (r) => (r.href ? <Source href={r.href} label={r.source} /> : r.source),
    },
  ]

  const datasetRows = Object.entries(meta.data.datasets ?? {}).sort((a2, b2) =>
    a2[0].localeCompare(b2[0])
  )
  const datasetCols: Column<[string, number]>[] = [
    { key: 'ds', header: 'Dataset', mono: true, render: ([ds]) => ds },
    {
      key: 'days',
      header: 'Days archived',
      align: 'right',
      mono: true,
      render: ([, days]) => num(days),
    },
  ]

  const generatedAt = meta.data.built_utc
    ? meta.data.built_utc.slice(0, 19).replace('T', ' ') + ' UTC'
    : 'unknown'

  const factorCols: Column<{
    fuel: string
    tco2_per_mwh: number | null
    basis: string
    src: string
  }>[] = [
    { key: 'fuel', header: 'Technology', render: (f) => f.fuel.replace(/_/g, ' ') },
    {
      key: 'v',
      header: 'Metric tonnes CO2 per MWh (tCO2/MWh)',
      align: 'right',
      mono: true,
      render: (f) => (f.tco2_per_mwh == null ? 'excluded' : f.tco2_per_mwh.toFixed(3)),
    },
    { key: 'basis', header: 'Basis', render: (f) => f.basis },
    { key: 'src', header: '', render: (f) => <Source href={f.src} label="source" /> },
  ]

  return (
    <div className="view">
      <p className="scn__lede">
        This is a single-user tool with no accounts or server-side state. The browser
        loads every value below from the same data release used by the rest of the studio.
        Each row shows its source or calculation basis.
      </p>

      <Panel
        title="Data release date and archive coverage"
        subtitle="The generation date and the number of archived days from each source."
      >
        <div className="kvs">
          <div className="kv">
            <span>Generated</span>
            <span className="mono">{generatedAt}</span>
          </div>
          <div className="kv">
            <span>Calculation version</span>
            <span className="mono">v{ENGINE_VERSION}</span>
          </div>
        </div>
        {datasetRows.length > 0 && (
          <DataGrid columns={datasetCols} rows={datasetRows} getKey={([ds]) => ds} />
        )}
      </Panel>

      <Panel
        title="Fixed assumptions used by the dispatch calculation"
        subtitle="Fuel costs, committed-coal settings, inter-grid transfer cost, the WESM offer cap, and water-availability adjustments."
      >
        <DataGrid columns={constCols} rows={constRows} getKey={(r) => r.label} />
      </Panel>

      <Panel
        title="Operational emission factors and their sources"
        subtitle={
          em.data?.unit ?? 'Operational (combustion) emission factors per technology.'
        }
      >
        {em.loading && <EmptyNote>Loading the emission factors.</EmptyNote>}
        {!em.loading && (!em.data?.available || !em.data.factors) && (
          <EmptyNote>Emission factors are not available.</EmptyNote>
        )}
        {em.data?.factors && (
          <>
            <DataGrid
              columns={factorCols}
              rows={em.data.factors}
              getKey={(f) => f.fuel}
            />
            <p className="note">{em.data.note}</p>
            {em.data.ngef && (
              <p className="note">
                DOE grid factor (cross-check, not an input): Luzon-Visayas{' '}
                {em.data.ngef.luzon_visayas_tco2_per_mwh.toFixed(3)} metric tonnes CO2 per
                MWh, Mindanao {em.data.ngef.mindanao_tco2_per_mwh.toFixed(3)} metric
                tonnes CO2 per MWh ({em.data.ngef.vintage}).{' '}
                <Source href={em.data.ngef.src} label="source" />
              </p>
            )}
          </>
        )}
      </Panel>
    </div>
  )
}
