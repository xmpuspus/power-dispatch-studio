import { useMemo } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { num, php, pct, fuelLabel } from '../lib/data'
import { Panel, StatTile, Chip, EmptyNote } from '../ui/kit'
import { MeritStack, FlowDiagram } from './charts'
import { DataGrid, type Column } from '../ui/DataGrid'
import {
  CLASSES,
  effNum,
  overrideKey,
  solveModel,
  type ClassId,
  type ObjRow,
  type Overrides,
  type Scenario,
  type SolvedModel,
} from './model'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

// ---- editable Properties grid (the object authoring surface) -----------------

export function PropertiesGrid({
  cls,
  rows,
  overrides,
  importedKeys,
  onEdit,
  onRevert,
}: {
  cls: ClassId
  rows: ObjRow[]
  overrides: Overrides
  importedKeys?: string[]
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
}) {
  const imported = new Set(importedKeys ?? [])
  const specs = CLASSES.find((c) => c.id === cls)?.props ?? []
  return (
    <div className="propgrid-wrap">
      <table className="propgrid">
        <thead>
          <tr>
            <th className="propgrid__obj">Object</th>
            {specs.map((s) => (
              <th key={s.key} className={s.editable ? 'propgrid__num' : ''}>
                {s.label}
                {s.unit && <span className="propgrid__unit"> {s.unit}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="propgrid__obj">{r.label}</td>
              {specs.map((s) => {
                const raw = r.props[s.key]
                if (!s.editable || typeof raw !== 'number') {
                  return (
                    <td
                      key={s.key}
                      className={typeof raw === 'number' ? 'propgrid__num' : ''}
                    >
                      {typeof raw === 'number' ? num(raw, s.dp ?? 0) : String(raw ?? '')}
                    </td>
                  )
                }
                const k = overrideKey(cls, r.id, s.key)
                const overridden = k in overrides
                const isImported = imported.has(k)
                const value = effNum(overrides, cls, r.id, s.key, raw)
                return (
                  <td key={s.key} className="propgrid__num propgrid__edit">
                    <input
                      className={`propgrid__input${overridden ? ' is-set' : ''}${isImported ? ' is-imported' : ''}`}
                      type="number"
                      step={s.dp === 2 ? 0.01 : 1}
                      value={value}
                      aria-label={`${r.label} ${s.label}${isImported ? ', user-supplied' : ''}`}
                      title={
                        isImported
                          ? 'user-supplied value from your CSV import'
                          : undefined
                      }
                      onChange={(e) => onEdit(cls, r.id, s.key, Number(e.target.value))}
                    />
                    {overridden && (
                      <button
                        className="propgrid__revert"
                        title={`Revert to base (${num(raw, s.dp ?? 0)})`}
                        aria-label="Revert to base value"
                        onClick={() => onRevert(cls, r.id, s.key)}
                      >
                        ×
                      </button>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---- Solution views that read the solved model (recomputed on Run) -----------

export function SolvedMeritView({ s, grid }: { s: SolvedModel; grid: GridKey }) {
  const price = s.coupled.price[grid]
  const marg = s.marginalFuel[grid]
  return (
    <div className="view">
      <div className="stat-row">
        <StatTile
          label="Clearing price"
          value={php(price)}
          hint={marg ? fuelLabel(marg) : 'unserved'}
        />
        <StatTile label="Available" value={num(s.avail[grid])} unit="MW" />
        <StatTile label="Load (evening)" value={num(s.demand[grid])} unit="MW" />
        <StatTile
          label="Reserve margin"
          value={pct(s.reserveMarginPct[grid] / 100, 1)}
          hint="available vs peak"
          tone={s.reserveMarginPct[grid] < 10 ? 'danger' : 'default'}
        />
      </div>
      <Panel
        title="Merit-order supply stack"
        subtitle={`${cap(grid)}, solved from the current model. Blocks by marginal cost against the load cursor.`}
      >
        <MeritStack blocks={s.stacks[grid]} demand={s.demand[grid]} />
      </Panel>
    </div>
  )
}

export function SolvedFlowsView({ s }: { s: SolvedModel }) {
  const prices: Record<string, number | null> = {
    luzon: s.coupled.price.luzon,
    visayas: s.coupled.price.visayas,
    mindanao: s.coupled.price.mindanao,
  }
  const corridors = [
    {
      from: 'luzon',
      to: 'visayas',
      flow_mw: s.coupled.leyte.flow,
      saturated: s.coupled.leyte.sat,
      rent: s.coupled.leyte.rent,
    },
    {
      from: 'visayas',
      to: 'mindanao',
      flow_mw: s.coupled.mvip.flow,
      saturated: s.coupled.mvip.sat,
      rent: s.coupled.mvip.rent,
    },
  ]
  return (
    <div className="view">
      <Panel
        title="Coupled inter-island dispatch"
        subtitle="The three grids cleared together over the HVDC links, from the current model."
      >
        <FlowDiagram prices={prices} corridors={corridors} />
        <div className="stat-row">
          {(['leyte', 'mvip'] as const).map((c) => (
            <StatTile
              key={c}
              label={c === 'leyte' ? 'Leyte-Luzon' : 'MVIP'}
              value={`${num(Math.abs(s.coupled[c].flow))} MW`}
              hint={s.coupled[c].sat ? `bound, rent ${php(s.coupled[c].rent)}` : 'open'}
              tone={s.coupled[c].sat ? 'danger' : 'default'}
            />
          ))}
        </div>
      </Panel>
    </div>
  )
}

export function SolvedN1View({ s, grid }: { s: SolvedModel; grid: GridKey }) {
  const rows = s.n1.filter((n) => n.grid === grid)
  const cols: Column<(typeof rows)[number]>[] = [
    { key: 'unit', header: 'Unit', render: (r) => r.unit },
    {
      key: 'cap',
      header: 'MW',
      align: 'right',
      mono: true,
      render: (r) => num(r.capacity_mw),
    },
    {
      key: 'price',
      header: 'Price move',
      align: 'right',
      mono: true,
      render: (r) => `${php(r.base_price, 0)} → ${php(r.tripped_price, 0)}`,
    },
    {
      key: 'shed',
      header: 'Shed',
      align: 'right',
      mono: true,
      render: (r) => num(r.shortfall_mw),
    },
  ]
  return (
    <div className="view">
      <Panel
        title={`N-1 contingency on ${cap(grid)}`}
        subtitle="Trip each named plant and read the price move and the load shed, solved from the current model. Multi-unit stations (Sual, Ilijan, Masinloc) lose all their units, so their move exceeds a single-unit N-1."
      >
        <DataGrid
          columns={cols}
          rows={rows}
          getKey={(r) => r.unit}
          empty="No named units on this grid."
        />
      </Panel>
    </div>
  )
}

export function SolvedRegionsView({ s }: { s: SolvedModel }) {
  const grids: GridKey[] = ['luzon', 'visayas', 'mindanao']
  const cols: Column<GridKey>[] = [
    { key: 'g', header: 'Region', render: (g) => cap(g) },
    {
      key: 'price',
      header: 'Clearing price',
      align: 'right',
      mono: true,
      render: (g) => php(s.coupled.price[g]),
    },
    {
      key: 'load',
      header: 'Load MW',
      align: 'right',
      mono: true,
      render: (g) => num(s.demand[g]),
    },
    {
      key: 'avail',
      header: 'Available MW',
      align: 'right',
      mono: true,
      render: (g) => num(s.avail[g]),
    },
    {
      key: 'rm',
      header: 'Reserve margin',
      align: 'right',
      mono: true,
      render: (g) => pct(s.reserveMarginPct[g] / 100, 1),
    },
  ]
  return (
    <div className="view">
      <Panel title="Regions" subtitle="Solved clearing price and adequacy by grid.">
        <DataGrid columns={cols} rows={grids} getKey={(g) => g} />
        <p className="note">
          Shortfall shown as a negative reserve margin. Prices come from the coupled solve
          of the current model; the Analysis views read the calibrated base case.
        </p>
      </Panel>
    </div>
  )
}

export function SolvedReliabilityView({ s }: { s: SolvedModel }) {
  const grids: GridKey[] = ['luzon', 'visayas', 'mindanao']
  return (
    <div className="view">
      <Panel
        title="Probabilistic reliability"
        subtitle={`${num(s.reliability.luzon.draws)} Monte Carlo draws on the current model. Each trips the named units at their forced-outage rate against a sampled evening load.`}
      >
        <div className="stat-row">
          {grids.map((g) => (
            <StatTile
              key={g}
              label={`LOLP ${cap(g)}`}
              value={pct(s.reliability[g].lolp_pct / 100, 2)}
              hint={`E[shed] ${num(s.reliability[g].expected_shortfall_mw)} MW`}
              tone={s.reliability[g].lolp_pct > 1 ? 'danger' : 'positive'}
            />
          ))}
        </div>
        <div className="stat-row">
          {grids.map((g) => (
            <StatTile
              key={g}
              label={`1-in-100 shed, ${cap(g)}`}
              value={num(s.reliability[g].shortfall_p99_mw)}
              unit="MW"
              tone={s.reliability[g].shortfall_p99_mw > 0 ? 'danger' : 'default'}
            />
          ))}
        </div>
        <p className="note">
          Loss-of-load probability is the share of tight evenings that go short. Only the
          named units carry an outage rate; the rest of the fleet holds at its
          deterministic availability, so the draws add outage variance, not a lower mean.
          Edit a unit's forced outage or capacity, or a region's load, and Run to move it.
          The 20,000-draw pipeline distribution and the storage buy-back are shown below
          as base-case reference.
        </p>
      </Panel>
    </div>
  )
}

// Memberships: the relations each object belongs to (a Generator to its
// Region and Fuel; an Interface to its two Regions; a Region and a Fuel to their
// member Generators). Read-only, derived from the object model.
export function MembershipsView({
  cls,
  objects,
}: {
  cls: ClassId
  objects: Record<ClassId, ObjRow[]>
}) {
  const rows: { obj: string; rels: { label: string; value: string }[] }[] = []
  if (cls === 'generator') {
    for (const g of objects.generator)
      rows.push({
        obj: g.label,
        rels: [
          { label: 'Region', value: String(g.props.grid) },
          { label: 'Fuel', value: fuelLabel(String(g.props.fuel)) },
        ],
      })
  } else if (cls === 'interface') {
    for (const i of objects.interface)
      rows.push({
        obj: i.label,
        rels: [
          { label: 'From', value: String(i.props.from) },
          { label: 'To', value: String(i.props.to) },
        ],
      })
  } else if (cls === 'region') {
    for (const r of objects.region) {
      const inRegion = objects.generator.filter((g) => g.grid === r.id)
      const links = objects.interface.filter(
        (i) =>
          String(i.props.from).toLowerCase() === r.id ||
          String(i.props.to).toLowerCase() === r.id
      )
      rows.push({
        obj: r.label,
        rels: [
          {
            label: `Generators (${inRegion.length})`,
            value: inRegion.map((g) => g.label).join(', ') || 'none',
          },
          { label: 'Interfaces', value: links.map((i) => i.label).join(', ') || 'none' },
        ],
      })
    }
  } else if (cls === 'storage') {
    for (const s of objects.storage)
      rows.push({
        obj: s.label,
        rels: [
          { label: 'Region', value: String(s.props.grid) },
          {
            label: 'Participates in',
            value: 'Chronology runs (optimised by the LP; cycles when the spread pays)',
          },
        ],
      })
  } else {
    for (const f of objects.fuel) {
      const users = objects.generator.filter((g) => String(g.props.fuel) === f.id)
      rows.push({
        obj: f.label,
        rels: [
          {
            label: `Generators (${users.length})`,
            value: users.map((g) => g.label).join(', ') || 'none named',
          },
        ],
      })
    }
  }
  return (
    <div className="memberships">
      {rows.map((r) => (
        <div className="memberships__row" key={r.obj}>
          <div className="memberships__obj">{r.obj}</div>
          <div className="memberships__rels">
            {r.rels.map((rel) => (
              <div className="memberships__rel" key={rel.label}>
                <Chip tone="default">{rel.label}</Chip>
                <span>{rel.value}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// Solve every scenario and compare the headline metrics side by side. The Base Case
// column is the reference; a cell that differs from it is highlighted.
export function CompareView({
  d,
  objects,
  scenarios,
}: {
  d: Dispatch
  objects: Record<ClassId, ObjRow[]>
  scenarios: Scenario[]
}) {
  const solved = useMemo(
    () => scenarios.map((s) => solveModel(d, objects, s.overrides)),
    [d, objects, scenarios]
  )
  const metrics: {
    label: string
    fmt: (s: SolvedModel) => string
    raw: (s: SolvedModel) => number
  }[] = [
    {
      label: 'Luzon price',
      fmt: (s) => php(s.coupled.price.luzon),
      raw: (s) => s.coupled.price.luzon,
    },
    {
      label: 'Visayas price',
      fmt: (s) => php(s.coupled.price.visayas),
      raw: (s) => s.coupled.price.visayas,
    },
    {
      label: 'Mindanao price',
      fmt: (s) => php(s.coupled.price.mindanao),
      raw: (s) => s.coupled.price.mindanao,
    },
    {
      label: 'Leyte-Luzon flow',
      fmt: (s) => `${num(Math.abs(s.coupled.leyte.flow))} MW`,
      raw: (s) => s.coupled.leyte.flow,
    },
    {
      label: 'Leyte-Luzon rent',
      fmt: (s) => php(s.coupled.leyte.rent),
      raw: (s) => s.coupled.leyte.rent,
    },
    {
      label: 'Luzon reserve margin',
      fmt: (s) => pct(s.reserveMarginPct.luzon / 100, 1),
      raw: (s) => s.reserveMarginPct.luzon,
    },
    {
      label: 'Luzon LOLP',
      fmt: (s) => pct(s.reliability.luzon.lolp_pct / 100, 2),
      raw: (s) => s.reliability.luzon.lolp_pct,
    },
    {
      label: 'Visayas reserve margin',
      fmt: (s) => pct(s.reserveMarginPct.visayas / 100, 1),
      raw: (s) => s.reserveMarginPct.visayas,
    },
  ]
  return (
    <div className="view">
      <Panel
        title="Compare scenarios"
        subtitle="Every scenario solved side by side. The Base Case is the reference; a changed cell is highlighted."
      >
        {scenarios.length < 2 && (
          <EmptyNote>
            Only the Base Case so far. Edit some properties, add a scenario with + New in
            the ribbon, and they line up here.
          </EmptyNote>
        )}
        <div className="propgrid-wrap">
          <table className="propgrid compare">
            <thead>
              <tr>
                <th className="propgrid__obj">Metric</th>
                {scenarios.map((s, i) => (
                  <th key={i} className="propgrid__num">
                    {s.name}
                    <span className="propgrid__unit">
                      {' '}
                      ({Object.keys(s.overrides).length})
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => {
                const baseRaw = m.raw(solved[0])
                return (
                  <tr key={m.label}>
                    <td className="propgrid__obj">{m.label}</td>
                    {solved.map((s, i) => {
                      const diff = i > 0 && Math.abs(m.raw(s) - baseRaw) > 1e-6
                      return (
                        <td
                          key={i}
                          className={`propgrid__num${diff ? ' compare__diff' : ''}`}
                        >
                          {m.fmt(s)}
                        </td>
                      )
                    })}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

export function ObjectsList({ rows }: { rows: ObjRow[] }) {
  return (
    <div className="objlist">
      {rows.map((r) => (
        <div className="objlist__row" key={r.id}>
          <Chip tone="default">{r.cls}</Chip>
          <span>{r.label}</span>
          {r.grid && <span className="objlist__grid mono">{cap(r.grid)}</span>}
        </div>
      ))}
    </div>
  )
}
