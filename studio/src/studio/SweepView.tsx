// Load sweep: solve the model at each step of added flat 24/7 load on one grid
// and read the price response as a curve, not a point. The usual production-cost
// workflow runs a model list; here every step is a full coupled snapshot
// solve on the ranked scenario, cheap enough to run on every Run.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { num, php, fuelLabel } from '../lib/data'
import { Panel, StatTile, Segmented } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { blockHeadroom } from './engine'
import { HourLines } from './charts'
import {
  effNum,
  overrideKey,
  solveSnapshot,
  type ClassId,
  type ObjRow,
  type Overrides,
  type SnapshotModel,
} from './model'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
const GRID_COLOR: Record<GridKey, string> = {
  luzon: 'var(--primary)',
  visayas: 'var(--accent)',
  mindanao: 'var(--series-flow)',
}
const STEPS = 12

interface SweepStep {
  addMw: number
  s: SnapshotModel
  corridorBound: boolean
  corridorRent: number
}

/** Does a saturated corridor sit on the importing side of this grid? */
function boundIntoGrid(s: SnapshotModel, grid: GridKey): { sat: boolean; rent: number } {
  const c = s.coupled
  if (grid === 'visayas' && c.leyte.sat && c.flowLV > 0)
    return { sat: true, rent: c.leyte.rent }
  if (grid === 'luzon' && c.leyte.sat && c.flowLV < 0)
    return { sat: true, rent: c.leyte.rent }
  if (grid === 'mindanao' && c.mvip.sat && c.flowVM > 0)
    return { sat: true, rent: c.mvip.rent }
  if (grid === 'visayas' && c.mvip.sat && c.flowVM < 0)
    return { sat: true, rent: c.mvip.rent }
  return { sat: false, rent: 0 }
}

export function SweepView({
  d,
  objects,
  overrides,
  grid,
}: {
  d: Dispatch
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
  grid: GridKey
}) {
  const [maxMw, setMaxMw] = useState<'500' | '1500' | '3000'>('1500')
  const steps = useMemo<SweepStep[]>(() => {
    const max = Number(maxMw)
    const baseDemand = effNum(
      overrides,
      'region',
      grid,
      'demand_mw',
      objects.region.find((r) => r.id === grid)?.props.demand_mw as number
    )
    const out: SweepStep[] = []
    for (let i = 0; i <= STEPS; i++) {
      const addMw = Math.round((max * i) / STEPS)
      const ov = {
        ...overrides,
        [overrideKey('region', grid, 'demand_mw')]: baseDemand + addMw,
      }
      const s = solveSnapshot(d, objects, ov)
      const b = boundIntoGrid(s, grid)
      out.push({ addMw, s, corridorBound: b.sat, corridorRent: b.rent })
    }
    return out
  }, [d, objects, overrides, grid, maxMw])

  const first = steps[0]
  const last = steps[steps.length - 1]
  const baseFuel = first.s.marginalFuel[grid]
  // how far the price holds: the room left in the block already setting it.
  // A flat sweep is this number being larger than the range, not a dead card.
  const headroom = blockHeadroom(first.s.stacks[grid], first.s.demand[grid])
  const flip = steps.find((st) => st.s.marginalFuel[grid] !== baseFuel)
  const bind = steps.find((st) => st.corridorBound && !first.corridorBound)
  const short = steps.find((st) => st.s.coupled.shortfall[grid] > 0)

  const series = (Object.keys(GRID_COLOR) as GridKey[]).map((g) => ({
    label: cap(g),
    color: GRID_COLOR[g],
    pts: steps.map((st) => st.s.coupled.price[g]),
  }))
  const marks: { x: number; label: string }[] = []
  if (bind)
    marks.push({ x: steps.indexOf(bind), label: `corridor binds +${num(bind.addMw)}` })
  if (flip)
    marks.push({
      x: steps.indexOf(flip),
      label: `${fuelLabel(flip.s.marginalFuel[grid] ?? 'none')} margin +${num(flip.addMw)}`,
    })
  if (short)
    marks.push({ x: steps.indexOf(short), label: `unserved +${num(short.addMw)}` })

  const cols: Column<SweepStep>[] = [
    {
      key: 'mw',
      header: 'Added MW',
      align: 'right',
      mono: true,
      render: (r) => `+${num(r.addMw)}`,
    },
    {
      key: 'price',
      header: `Price, ${cap(grid)} (₱/kWh)`,
      align: 'right',
      mono: true,
      render: (r) => php(r.s.coupled.price[grid]),
    },
    {
      key: 'marg',
      header: 'Price-setting fuel (marginal fuel)',
      render: (r) => fuelLabel(r.s.marginalFuel[grid] ?? 'none'),
    },
    {
      key: 'corr',
      header: 'Import corridor',
      render: (r) =>
        r.corridorBound
          ? `at limit, price difference ${php(r.corridorRent)}/kWh`
          : 'below limit',
    },
    {
      key: 'head',
      header: 'Headroom MW',
      align: 'right',
      mono: true,
      render: (r) => num(r.s.avail[grid] - r.s.demand[grid]),
    },
    {
      key: 'shed',
      header: 'Unserved MW',
      align: 'right',
      mono: true,
      render: (r) => num(r.s.coupled.shortfall[grid]),
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <Segmented
          ariaLabel="Sweep range"
          value={maxMw}
          onChange={(v) => setMaxMw(v)}
          options={[
            { value: '500', label: 'to +500 MW' },
            { value: '1500', label: 'to +1,500 MW' },
            { value: '3000', label: 'to +3,000 MW' },
          ]}
        />
      </div>

      <div className="stat-row">
        <StatTile
          label="Price at +0"
          value={php(first.s.coupled.price[grid])}
          unit="/kWh"
          hint={fuelLabel(baseFuel ?? 'none')}
        />
        <StatTile
          label={`Price at +${num(last.addMw)} MW`}
          value={php(last.s.coupled.price[grid])}
          unit="/kWh"
          hint={fuelLabel(last.s.marginalFuel[grid] ?? 'none')}
          tone={
            last.s.coupled.price[grid] > first.s.coupled.price[grid] + 0.005
              ? 'accent'
              : 'default'
          }
        />
        <StatTile
          label="Spare capacity"
          value={`${num(first.s.avail[grid] - first.s.demand[grid])} to ${num(
            last.s.avail[grid] - last.s.demand[grid]
          )}`}
          unit="MW"
          hint="available minus load at the reference hour"
          tone={last.s.avail[grid] - last.s.demand[grid] < 1000 ? 'danger' : 'accent'}
        />
        <StatTile
          label="Price holds for another"
          value={num(headroom)}
          unit="MW"
          hint={`room left in the ${fuelLabel(baseFuel ?? 'none')} block that sets the price`}
          tone={headroom < Number(maxMw) ? 'accent' : 'default'}
        />
        <StatTile
          label="Import corridor binds at"
          value={
            bind
              ? `+${num(bind.addMw)}`
              : first.corridorBound
                ? 'already bound'
                : 'not in range'
          }
          unit={bind ? 'MW' : undefined}
          tone={bind || first.corridorBound ? 'danger' : 'positive'}
        />
        <StatTile
          label="Unserved load from"
          value={short ? `+${num(short.addMw)}` : 'not in range'}
          unit={short ? 'MW' : undefined}
          tone={short ? 'danger' : 'positive'}
        />
      </div>

      <Panel
        title={`Clearing price as added demand increases, ${cap(grid)}`}
        subtitle={`Flat 24/7 demand is added to the selected scenario in ${STEPS} steps of ${num(Number(maxMw) / STEPS)} MW. All three grids clear together again at each step.`}
      >
        <HourLines series={series} marks={marks} />
      </Panel>

      <Panel
        title="Spare capacity as demand increases"
        subtitle="Each step solves the evening reference hour. A single hour has no daily water limit, so hydro can offer its full available capacity here. Hourly market replay solves whole days and applies the daily water limit."
      >
        <DataGrid columns={cols} rows={steps} getKey={(r) => String(r.addMw)} />
        <p className="note">
          DICT forecasts 1,500 MW of data-center demand by 2028, and Meralco has committed
          1,000 MW for 10 data centers. Both figures describe future demand, not recorded
          demand. The demand steps show which fuel sets the price, when the importing link
          reaches its limit, and when available supply runs out. A flat price with falling
          spare capacity is still a meaningful result. On a broad coal-price step, each MW
          of new demand can reduce spare capacity by one MW before the price changes. The
          Power-shortfall risk view shows the resulting loss-of-load probability (LOLP).
        </p>
      </Panel>
    </div>
  )
}
