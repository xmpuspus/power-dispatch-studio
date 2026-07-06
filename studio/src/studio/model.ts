// Editable object model for the PLEXOS-style authoring surface. Objects (Fuels,
// Generators, Interfaces, Regions) carry properties you edit in a grid; a Scenario is
// a named override map; Run applies base + overrides, rebuilds the stacks, and solves
// the coupled dispatch through engine.ts (which is golden-parity to the Python).
//
// Honest block-dispatch stance: the model clears aggregate per-fuel blocks. The Fuels
// class sets the stack (cost + available MW per grid). The Generators class names the
// real units; editing a unit shifts its fuel's available capacity on its grid by the
// change (an approximation, not plant-level unit commitment) and defines the N-1 set.
// No fabricated per-plant fleet.

import type { Block, Dispatch, GridKey } from '../lib/types'
import {
  GRID_KEYS,
  buildStack,
  clearCoupled,
  clearGrid,
  type CoupledResult,
} from './engine'

export type ClassId = 'fuel' | 'generator' | 'interface' | 'region'

export interface PropSpec {
  key: string
  label: string
  unit?: string
  editable: boolean
  dp?: number
}

export interface ObjRow {
  id: string
  cls: ClassId
  label: string
  grid?: GridKey
  props: Record<string, number | string>
}

export interface SystemClass {
  id: ClassId
  label: string
  props: PropSpec[]
}

// override map: `${cls}:${id}:${propKey}` -> number
export type Overrides = Record<string, number>

export interface Scenario {
  name: string
  overrides: Overrides
}

export const CLASSES: SystemClass[] = [
  {
    id: 'generator',
    label: 'Generators',
    props: [
      { key: 'grid', label: 'Region', editable: false },
      { key: 'fuel', label: 'Fuel', editable: false },
      { key: 'capacity_mw', label: 'Max capacity', unit: 'MW', editable: true, dp: 0 },
      { key: 'marginal_cost', label: 'Fuel price', unit: '₱/kWh', editable: true, dp: 2 },
      { key: 'for_pct', label: 'Forced outage', unit: '%', editable: true, dp: 0 },
    ],
  },
  {
    id: 'fuel',
    label: 'Fuels',
    props: [
      { key: 'cost', label: 'Price', unit: '₱/kWh', editable: true, dp: 2 },
      { key: 'luzon_mw', label: 'Luzon avail', unit: 'MW', editable: true, dp: 0 },
      { key: 'visayas_mw', label: 'Visayas avail', unit: 'MW', editable: true, dp: 0 },
      { key: 'mindanao_mw', label: 'Mindanao avail', unit: 'MW', editable: true, dp: 0 },
    ],
  },
  {
    id: 'interface',
    label: 'Interfaces',
    props: [
      { key: 'from', label: 'From', editable: false },
      { key: 'to', label: 'To', editable: false },
      { key: 'limit_mw', label: 'Flow limit', unit: 'MW', editable: true, dp: 0 },
    ],
  },
  {
    id: 'region',
    label: 'Regions',
    props: [
      { key: 'demand_mw', label: 'Load (evening)', unit: 'MW', editable: true, dp: 0 },
      { key: 'peak_mw', label: 'Peak load', unit: 'MW', editable: false, dp: 0 },
    ],
  },
]

const MERIT_FUELS = [
  'solar',
  'wind',
  'hydro',
  'geothermal',
  'natural_gas',
  'biomass',
  'coal',
  'oil',
]

/** Base objects (no overrides) derived from the baked model + named generators. */
export function baseObjects(
  d: Dispatch,
  gens: { name: string; grid: string; fuel: string; capacity_mw: number }[]
): Record<ClassId, ObjRow[]> {
  const costs = d.assumptions.fuel_marginal_cost_php_kwh
  const generators: ObjRow[] = gens.map((g) => ({
    id: g.name,
    cls: 'generator',
    label: g.name,
    grid: g.grid.toLowerCase() as GridKey,
    props: {
      grid: cap(g.grid),
      fuel: g.fuel,
      capacity_mw: g.capacity_mw,
      marginal_cost: costs[g.fuel] ?? 0,
      for_pct: forcedOutagePct(g.fuel),
    },
  }))
  const fuels: ObjRow[] = MERIT_FUELS.map((f) => ({
    id: f,
    cls: 'fuel',
    label: f.replace(/_/g, ' '),
    props: {
      cost: costs[f] ?? 0,
      luzon_mw: d.merit_order.luzon.fuel_avail_mw[f] ?? 0,
      visayas_mw: d.merit_order.visayas.fuel_avail_mw[f] ?? 0,
      mindanao_mw: d.merit_order.mindanao.fuel_avail_mw[f] ?? 0,
    },
  }))
  const interfaces: ObjRow[] = d.coupling.corridors.map((c) => ({
    id: c.id,
    cls: 'interface',
    label: c.name,
    props: {
      from: c.id === 'leyte_luzon_hvdc' ? 'Luzon' : 'Visayas',
      to: c.id === 'leyte_luzon_hvdc' ? 'Visayas' : 'Mindanao',
      limit_mw: c.limit_mw,
    },
  }))
  const regions: ObjRow[] = GRID_KEYS.map((g) => ({
    id: g,
    cls: 'region',
    label: cap(g),
    grid: g,
    props: {
      demand_mw: d.merit_order[g].typical_evening_demand_mw,
      peak_mw: d.merit_order[g].peak_demand_mw,
    },
  }))
  return { generator: generators, fuel: fuels, interface: interfaces, region: regions }
}

export function overrideKey(cls: ClassId, id: string, prop: string): string {
  return `${cls}:${id}:${prop}`
}

/** Effective numeric value of a property: override if present, else the base. */
export function effNum(
  ov: Overrides,
  cls: ClassId,
  id: string,
  prop: string,
  base: number
): number {
  const k = overrideKey(cls, id, prop)
  return k in ov ? ov[k] : base
}

export interface N1Solved {
  unit: string
  grid: GridKey
  capacity_mw: number
  base_price: number
  tripped_price: number
  shortfall_mw: number
}

export interface McResult {
  lolp_pct: number
  expected_shortfall_mw: number
  shortfall_p99_mw: number
  draws: number
}

export interface SolvedModel {
  coupled: CoupledResult
  stacks: Record<GridKey, Block[]>
  demand: Record<GridKey, number>
  avail: Record<GridKey, number>
  reserveMarginPct: Record<GridKey, number>
  n1: N1Solved[]
  marginalFuel: Record<GridKey, string | null>
  reliability: Record<GridKey, McResult>
}

const MC_DRAWS = 4000
const MC_SEED = 42

// small seeded PRNG so a Run gives a stable loss-of-load probability, not a jittery
// one; a standard-normal draw by Box-Muller for the load sample.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
function gaussian(rng: () => number): number {
  const u = Math.max(1e-9, rng())
  const v = rng()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

/**
 * Client Monte Carlo loss-of-load, on the EDITED model. Each draw trips the named
 * units at their (edited) forced-outage rate, samples an evening load from the baked
 * distribution centred on the (edited) region load, and takes the shortfall against
 * available capacity. Same idea as the pipeline's snapshot draws, run live so the
 * reliability responds to edits (add capacity, lower LOLP; add load or cut a unit,
 * raise it). Only the named units carry an outage rate; the rest holds deterministic.
 */
function reliabilityMC(
  grid: GridKey,
  fuelAvail: Record<string, number>,
  gens: { fuel: string; cap: number; forFrac: number }[],
  loadMean: number,
  loadStd: number
): McResult {
  const totalAvail = Object.values(fuelAvail).reduce((s, v) => s + v, 0)
  const rng = mulberry32(MC_SEED + grid.length)
  const shortfalls: number[] = []
  let losses = 0
  for (let i = 0; i < MC_DRAWS; i++) {
    let out = 0
    for (const g of gens) if (rng() < g.forFrac) out += g.cap
    const avail = Math.max(0, totalAvail - out)
    const load = loadMean + loadStd * gaussian(rng)
    const sf = Math.max(0, load - avail)
    shortfalls.push(sf)
    if (sf > 0.5) losses++
  }
  shortfalls.sort((x, y) => x - y)
  const p99 = shortfalls[Math.min(shortfalls.length - 1, Math.floor(0.99 * MC_DRAWS))]
  const mean = shortfalls.reduce((s, v) => s + v, 0) / MC_DRAWS
  return {
    lolp_pct: Math.round((1000 * losses) / MC_DRAWS) / 10,
    expected_shortfall_mw: Math.round(mean * 10) / 10,
    shortfall_p99_mw: Math.round(p99),
    draws: MC_DRAWS,
  }
}

/** Apply base + overrides, rebuild the stacks, and solve the coupled dispatch. */
export function solveModel(
  d: Dispatch,
  objects: Record<ClassId, ObjRow[]>,
  ov: Overrides
): SolvedModel {
  const a = d.assumptions
  const wheel = a.wheeling_cost_php_kwh

  // effective fuel costs (Fuels grid)
  const costs: Record<string, number> = { ...a.fuel_marginal_cost_php_kwh }
  for (const f of objects.fuel)
    costs[f.id] = effNum(ov, 'fuel', f.id, 'cost', f.props.cost as number)

  // effective per-grid fuel availability: Fuels grid MW, then each generator's
  // capacity delta applied to its fuel and grid (a labeled approximation).
  const fuelAvail: Record<GridKey, Record<string, number>> = {
    luzon: {},
    visayas: {},
    mindanao: {},
  }
  for (const f of objects.fuel) {
    fuelAvail.luzon[f.id] = effNum(
      ov,
      'fuel',
      f.id,
      'luzon_mw',
      f.props.luzon_mw as number
    )
    fuelAvail.visayas[f.id] = effNum(
      ov,
      'fuel',
      f.id,
      'visayas_mw',
      f.props.visayas_mw as number
    )
    fuelAvail.mindanao[f.id] = effNum(
      ov,
      'fuel',
      f.id,
      'mindanao_mw',
      f.props.mindanao_mw as number
    )
  }
  for (const g of objects.generator) {
    const baseCap = g.props.capacity_mw as number
    const eff = effNum(ov, 'generator', g.id, 'capacity_mw', baseCap)
    const delta = eff - baseCap
    if (delta !== 0 && g.grid && g.props.fuel) {
      const fuel = g.props.fuel as string
      fuelAvail[g.grid][fuel] = Math.max(0, (fuelAvail[g.grid][fuel] ?? 0) + delta)
    }
  }

  const demand: Record<GridKey, number> = {
    luzon: effNum(
      ov,
      'region',
      'luzon',
      'demand_mw',
      objForId(objects.region, 'luzon').props.demand_mw as number
    ),
    visayas: effNum(
      ov,
      'region',
      'visayas',
      'demand_mw',
      objForId(objects.region, 'visayas').props.demand_mw as number
    ),
    mindanao: effNum(
      ov,
      'region',
      'mindanao',
      'demand_mw',
      objForId(objects.region, 'mindanao').props.demand_mw as number
    ),
  }

  const caps = {
    leyte: effNum(
      ov,
      'interface',
      'leyte_luzon_hvdc',
      'limit_mw',
      ifaceLimit(objects.interface, 'leyte_luzon_hvdc')
    ),
    mvip: effNum(
      ov,
      'interface',
      'mvip_hvdc',
      'limit_mw',
      ifaceLimit(objects.interface, 'mvip_hvdc')
    ),
  }

  const sp = {
    coalCommit: a.coal_commit_php_kwh,
    coalMinFrac: a.coal_min_load_frac,
    coalPrice: costs.coal,
    costs,
  }
  const stacks: Record<GridKey, Block[]> = {
    luzon: buildStack(fuelAvail.luzon, {}, [], sp),
    visayas: buildStack(fuelAvail.visayas, {}, [], sp),
    mindanao: buildStack(fuelAvail.mindanao, {}, [], sp),
  }
  const coupled = clearCoupled(demand, stacks, caps, wheel)
  const avail: Record<GridKey, number> = {
    luzon: sum(stacks.luzon),
    visayas: sum(stacks.visayas),
    mindanao: sum(stacks.mindanao),
  }
  const reserveMarginPct: Record<GridKey, number> = {
    luzon: margin(avail.luzon, objForId(objects.region, 'luzon').props.peak_mw as number),
    visayas: margin(
      avail.visayas,
      objForId(objects.region, 'visayas').props.peak_mw as number
    ),
    mindanao: margin(
      avail.mindanao,
      objForId(objects.region, 'mindanao').props.peak_mw as number
    ),
  }
  const marginalFuel: Record<GridKey, string | null> = {
    luzon: marginalOf(stacks.luzon, demand.luzon),
    visayas: marginalOf(stacks.visayas, demand.visayas),
    mindanao: marginalOf(stacks.mindanao, demand.mindanao),
  }

  // N-1: trip each named unit at its grid's demand, read the price move + shortfall
  const n1: N1Solved[] = objects.generator.map((g) => {
    const grid = g.grid as GridKey
    const eff = effNum(
      ov,
      'generator',
      g.id,
      'capacity_mw',
      g.props.capacity_mw as number
    )
    const fuel = g.props.fuel as string
    const base = clearGrid(stacks[grid], demand[grid])
    const trippedAvail = {
      ...fuelAvail[grid],
      [fuel]: Math.max(0, (fuelAvail[grid][fuel] ?? 0) - eff),
    }
    const trippedStack = buildStack(trippedAvail, {}, [], sp)
    const tripped = clearGrid(trippedStack, demand[grid])
    return {
      unit: g.id,
      grid,
      capacity_mw: eff,
      base_price: base.price,
      tripped_price: tripped.price,
      shortfall_mw: tripped.shortfall,
    }
  })

  // live loss-of-load per grid, from the edited model
  const loadDist = d.reliability_mc.load_dist
  const gensBy = (grid: GridKey) =>
    objects.generator
      .filter((g) => g.grid === grid)
      .map((g) => ({
        fuel: g.props.fuel as string,
        cap: effNum(ov, 'generator', g.id, 'capacity_mw', g.props.capacity_mw as number),
        forFrac:
          effNum(ov, 'generator', g.id, 'for_pct', g.props.for_pct as number) / 100,
      }))
  const reliability: Record<GridKey, McResult> = {
    luzon: reliabilityMC(
      'luzon',
      fuelAvail.luzon,
      gensBy('luzon'),
      demand.luzon,
      loadDist.luzon.std
    ),
    visayas: reliabilityMC(
      'visayas',
      fuelAvail.visayas,
      gensBy('visayas'),
      demand.visayas,
      loadDist.visayas.std
    ),
    mindanao: reliabilityMC(
      'mindanao',
      fuelAvail.mindanao,
      gensBy('mindanao'),
      demand.mindanao,
      loadDist.mindanao.std
    ),
  }

  return {
    coupled,
    stacks,
    demand,
    avail,
    reserveMarginPct,
    n1,
    marginalFuel,
    reliability,
  }
}

function objForId(rows: ObjRow[], id: string): ObjRow {
  return rows.find((r) => r.id === id) ?? rows[0]
}
function ifaceLimit(rows: ObjRow[], id: string): number {
  const r = rows.find((x) => x.id === id)
  return (r?.props.limit_mw as number) ?? (id === 'leyte_luzon_hvdc' ? 250 : 450)
}
function sum(blocks: Block[]): number {
  return Math.round(blocks.reduce((s, b) => s + b.mw, 0) * 10) / 10
}
function margin(avail: number, peak: number): number {
  return peak > 0 ? Math.round(((avail - peak) / peak) * 1000) / 10 : 0
}
function marginalOf(blocks: Block[], demand: number): string | null {
  const sorted = [...blocks].sort((x, y) => x.cost - y.cost)
  let cum = 0
  for (const b of sorted) {
    cum += b.mw
    if (cum >= demand) return b.fuel
  }
  return sorted.length ? sorted[sorted.length - 1].fuel : null
}
function forcedOutagePct(fuel: string): number {
  const rate: Record<string, number> = {
    coal: 10,
    natural_gas: 5,
    oil: 10,
    geothermal: 8,
    hydro: 4,
    biomass: 8,
  }
  return rate[fuel] ?? 0
}
function cap(s: string): string {
  return s[0].toUpperCase() + s.slice(1).toLowerCase()
}
