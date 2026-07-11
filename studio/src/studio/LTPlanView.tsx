// LT Plan: the DOE's committed and indicative build pipeline as sourced
// candidates. No expansion optimizer runs here; the DOE's own lists carry the
// MW, the fuel, and the proponents' target dates, and Apply materialises a
// horizon into the scenario as ordinary fuel-availability edits you can see,
// revert, and Run like any other property change.

import { useMemo, useState } from 'react'
import type { GridKey, TdpCorridor } from '../lib/types'
import { num, php, fuelLabel, useProjects, useDemandPath } from '../lib/data'
import { Panel, StatTile, Chip, Segmented, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { addsAtHorizon, type GridFuelAdd } from './insights'
import type { ClassId, ObjRow } from './model'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const YEARS = [2026, 2027, 2028, 2029, 2030, 2032, 2035]

export function LTPlanView({
  objects,
  onEdit,
}: {
  objects: Record<ClassId, ObjRow[]>
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
}) {
  const pj = useProjects()
  const [year, setYear] = useState(2028)
  const [scope, setScope] = useState<'committed' | 'both'>('committed')
  const rows = useMemo(() => pj.data?.rows ?? [], [pj.data])
  const { adds, unscheduledMw } = useMemo(
    () => addsAtHorizon(rows, year, scope === 'both'),
    [rows, year, scope]
  )
  if (pj.loading) return <EmptyNote>Loading the DOE project lists.</EmptyNote>
  if (pj.error || !pj.data?.available)
    return <EmptyNote>LT Plan layer not baked. Run make data.</EmptyNote>
  const p = pj.data

  const perGrid = (g: GridKey) =>
    Math.round(adds.filter((a) => a.grid === g).reduce((s, a) => s + a.mw, 0))

  // Apply is idempotent: each affected property is set to BASE plus the
  // horizon's additions, so clicking twice (or re-applying after moving the
  // slider) never stacks. It overwrites a manual edit on the same fuel-grid
  // cell; the properties grid shows the change and the revert.
  const applyBuilds = () => {
    for (const a of adds) {
      const fuelRow = objects.fuel.find((f) => f.id === a.fuel)
      if (!fuelRow) continue
      const key = `${a.grid}_mw`
      const base = fuelRow.props[key] as number
      onEdit('fuel', a.fuel, key, Math.round((base + a.mw) * 10) / 10)
    }
  }
  const applyCorridor = (c: TdpCorridor) => {
    if (!c.iface || !c.adds_mw) return
    const row = objects.interface.find((i) => i.id === c.iface)
    if (!row) return
    const base = row.props.limit_mw as number
    onEdit('interface', c.iface, 'limit_mw', base + c.adds_mw)
  }

  const addCols: Column<GridFuelAdd>[] = [
    { key: 'grid', header: 'Grid', render: (r) => cap(r.grid) },
    { key: 'fuel', header: 'Fuel', render: (r) => fuelLabel(r.fuel) },
    {
      key: 'mw',
      header: `MW by ${year}`,
      align: 'right',
      mono: true,
      render: (r) => `+${num(r.mw)}`,
    },
  ]
  const corridorCols: Column<TdpCorridor>[] = [
    { key: 'name', header: 'Corridor project', render: (c) => c.name },
    {
      key: 'adds',
      header: 'Transfer MW',
      align: 'right',
      mono: true,
      render: (c) => (c.adds_mw ? `+${num(c.adds_mw)}` : 'not stated'),
    },
    { key: 'target', header: 'Target', render: (c) => c.target },
    {
      key: 'cost',
      header: 'Cost',
      align: 'right',
      mono: true,
      render: (c) => (c.cost_mphp ? `${php(c.cost_mphp / 1000, 1)}B` : '-'),
    },
    {
      key: 'apply',
      header: '',
      render: (c) =>
        c.iface && c.adds_mw ? (
          <button className="btn btn--ghost btn--sm" onClick={() => applyCorridor(c)}>
            Apply to scenario
          </button>
        ) : (
          <Chip tone="default">outside model topology</Chip>
        ),
    },
  ]

  const committedTotal = (g: GridKey) =>
    (p.totals?.committed?.[g] as { gen_mw: number } | undefined)?.gen_mw

  return (
    <div className="view">
      <DemandPathPanel />
      <p className="scn__lede">
        The DOE tracks every private-sector power project by grid, fuel, MW, and the
        proponent's target date: committed (permitted and financed) and indicative
        (earlier-stage, far larger). Pick a horizon, read what the pipeline claims to
        deliver by then, and Apply writes it into the scenario as fuel-availability edits.
        Dates are the proponents' declarations, not this site's forecast.
      </p>

      <div className="chrono__controls">
        <label className="chrono__ctl">
          Horizon
          <select
            className="ribbon__select"
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            aria-label="Build horizon year"
          >
            {YEARS.map((y) => (
              <option key={y} value={y}>
                by {y}
              </option>
            ))}
          </select>
        </label>
        <Segmented
          ariaLabel="Project status scope"
          value={scope}
          onChange={(v) => setScope(v)}
          options={[
            { value: 'committed', label: 'Committed only' },
            { value: 'both', label: 'Committed + indicative' },
          ]}
        />
        <div className="chrono__actions">
          <button
            className="btn btn--run btn--sm"
            onClick={applyBuilds}
            disabled={!adds.length}
          >
            Apply builds to scenario
          </button>
        </div>
      </div>

      <div className="stat-row">
        {GRIDS.map((g) => (
          <StatTile
            key={g}
            label={`${cap(g)} by ${year}`}
            value={`+${num(perGrid(g))}`}
            unit="MW"
            hint={`committed list total ${num(committedTotal(g))} MW`}
          />
        ))}
        <StatTile
          label="No stated date"
          value={num(unscheduledMw)}
          unit="MW"
          hint="TBD rows, never counted in a horizon"
        />
      </div>

      <Panel
        title="What the pipeline adds, by grid and fuel"
        subtitle={`Every ${scope === 'both' ? 'committed and indicative' : 'committed'} project with a target commercial operation on or before ${year}, summed. As of ${p.as_of}.`}
        right={<Source href={p.editions?.committed?.luzon?.src} label="DOE list" />}
      >
        <DataGrid
          columns={addCols}
          rows={adds}
          getKey={(r) => `${r.grid}:${r.fuel}`}
          empty="Nothing in the pipeline lands by this horizon."
        />
        <p className="note">
          {p.note} {p.ess_note}
        </p>
      </Panel>

      <Panel
        title="Transmission pipeline (NGCP TDP 2025-2050)"
        subtitle="Corridor projects from the operator's transmission development plan. Only upgrades to the model's two corridors can apply; the rest are listed for the record."
        right={<Source href={p.src_tdp} label="TDP" />}
      >
        <DataGrid
          columns={corridorCols}
          rows={p.corridors ?? []}
          getKey={(c) => c.name}
        />
        <p className="note">
          Transfer MW is stated only where the TDP itself states a transfer capacity;
          conductor thermal ratings are not transfer limits and are not imputed. Dates
          assume the regulator approves on NGCP's planning schedule.
        </p>
      </Panel>

      <p className="note">
        Apply writes ordinary property edits tagged to the active scenario: System &gt;
        Fuels shows each changed cell with its revert, and Run re-solves. The DOE
        committed total for {year >= 2028 ? 'the 2028 horizon' : 'this horizon'} can be
        read against the announced data-center wave in the Load sweep view.
      </p>
    </div>
  )
}

type MRow = {
  year: number
  luzon?: number
  visayas?: number
  mindanao?: number
  ph?: number
}

/** The DOE PDP 2023-2050 peak-demand forecast, the demand trajectory the
 * supply pipeline below has to serve. A labeled DOE forecast, not this site's
 * projection. */
function DemandPathPanel() {
  const dp = useDemandPath()
  if (dp.loading || !dp.data?.available) return null
  const d = dp.data
  const years = d.years ?? []
  const idx = (y: number) => years.indexOf(y)
  const ph = d.philippines_mw ?? []
  const pg = d.per_grid_mw
  const fmt = (v?: number) => (v == null ? 'n/a' : num(v))
  const rows: MRow[] = [2025, 2030, 2040, 2050]
    .filter((y) => idx(y) >= 0)
    .map((y) => ({
      year: y,
      luzon: pg?.luzon?.[idx(y)],
      visayas: pg?.visayas?.[idx(y)],
      mindanao: pg?.mindanao?.[idx(y)],
      ph: ph[idx(y)],
    }))
  const cols: Column<MRow>[] = [
    { key: 'year', header: 'Year', render: (r) => String(r.year) },
    {
      key: 'luzon',
      header: 'Luzon',
      align: 'right',
      mono: true,
      render: (r) => fmt(r.luzon),
    },
    {
      key: 'visayas',
      header: 'Visayas',
      align: 'right',
      mono: true,
      render: (r) => fmt(r.visayas),
    },
    {
      key: 'mindanao',
      header: 'Mindanao',
      align: 'right',
      mono: true,
      render: (r) => fmt(r.mindanao),
    },
    {
      key: 'ph',
      header: 'Philippines',
      align: 'right',
      mono: true,
      render: (r) => fmt(r.ph),
    },
  ]
  return (
    <Panel
      title="System peak demand path (DOE forecast)"
      subtitle={`The ${d.plan} peak-demand forecast, per grid in MW, that the build pipeline below has to serve. A labeled ${d.owner} forecast (the plan's Table 28), not this site's projection; national peak grows about ${d.cagr_2025_2050_pct} percent a year to ${fmt(ph[idx(2050)])} MW by 2050. The data-center anchors sit on top of this baseline growth.`}
      right={<Source href={d.src} label="DOE PDP" />}
    >
      <div className="stat-row">
        <StatTile
          label="National peak, 2025"
          value={fmt(ph[idx(2025)])}
          unit="MW"
          hint={`${d.owner} PDP forecast`}
        />
        <StatTile
          label="2030"
          value={fmt(ph[idx(2030)])}
          unit="MW"
          hint="reference scenario"
        />
        <StatTile
          label="2040"
          value={fmt(ph[idx(2040)])}
          unit="MW"
          hint="reference scenario"
        />
        <StatTile
          label="2050"
          value={fmt(ph[idx(2050)])}
          unit="MW"
          hint="end of horizon"
        />
      </div>
      <DataGrid columns={cols} rows={rows} getKey={(r) => String(r.year)} />
      <p className="note">{d.note}</p>
    </Panel>
  )
}
