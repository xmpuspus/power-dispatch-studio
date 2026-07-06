import type { GridKey } from '../lib/types'
import { num, php, pct, fuelLabel } from '../lib/data'
import { Panel, StatTile, Chip } from '../ui/kit'
import { MeritStack, FlowDiagram } from './charts'
import { DataGrid, type Column } from '../ui/DataGrid'
import {
  CLASSES,
  effNum,
  overrideKey,
  type ClassId,
  type ObjRow,
  type Overrides,
  type SolvedModel,
} from './model'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

// ---- editable Properties grid (the PLEXOS authoring surface) -----------------

export function PropertiesGrid({
  cls,
  rows,
  overrides,
  onEdit,
  onRevert,
}: {
  cls: ClassId
  rows: ObjRow[]
  overrides: Overrides
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
}) {
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
                const value = effNum(overrides, cls, r.id, s.key, raw)
                return (
                  <td key={s.key} className="propgrid__num propgrid__edit">
                    <input
                      className={`propgrid__input${overridden ? ' is-set' : ''}`}
                      type="number"
                      step={s.dp === 2 ? 0.01 : 1}
                      value={value}
                      aria-label={`${r.label} ${s.label}`}
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
        subtitle="Trip each named unit and read the price move and the load shed, solved from the current model."
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
