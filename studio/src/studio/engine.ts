// Client scenario engine: a typed transcription of the pipeline's economic dispatch
// (pipeline/fleet_ph.stack + pipeline/coupled_dispatch.clear_coupled). NOT PLEXOS.
//
// It rebuilds each grid's merit-order stack from the baked per-fuel availability
// (merit_order[g].fuel_avail_mw), applies the scenario levers, and re-clears the
// three coupled grids the same way the Python engine does. The pipeline stays the
// source of truth: dispatch.scenario_golden carries input/output pairs from the real
// Python solve, and engine.test.ts asserts this reproduces them (parity harness).

import type { Block, Dispatch, GridKey } from '../lib/types'

export const GRID_KEYS: GridKey[] = ['luzon', 'visayas', 'mindanao']

// The two HVDC corridors as a radial path: Luzon -> Visayas -> Mindanao.
export const CORRIDOR = {
  leyte: { id: 'leyte_luzon_hvdc', from: 'luzon', to: 'visayas' },
  mvip: { id: 'mvip_hvdc', from: 'visayas', to: 'mindanao' },
} as const

export interface Levers {
  grid: GridKey
  addDC: number // flat 24/7 load added to the selected grid (MW)
  addSolar: number // installed solar added to the selected grid (MW, derated at ref hour)
  addGas: number // dispatchable gas added to the selected grid (MW)
  addCoal: number // dispatchable coal added to the selected grid (MW)
  addStorage: number // storage discharged at the peak on the selected grid (MW)
  trip: string // named unit tripped on the selected grid (matched by name)
  coalPrice: number // administered coal price for the marginal coal tranche (PhP/kWh)
  reliefMW: number // extra operating limit on the corridor feeding the selected grid (MW)
}

export interface TrippableUnit {
  name: string
  grid: string
  fuel: string
  capacity_mw: number
}

export interface CoupledResult {
  price: Record<GridKey, number>
  gen: Record<GridKey, number>
  shortfall: Record<GridKey, number>
  flowLV: number
  flowVM: number
  leyte: { flow: number; sat: boolean; rent: number }
  mvip: { flow: number; sat: boolean; rent: number }
}

// ---- stack construction (mirror of fleet_ph.stack) --------------------------

interface StackParams {
  coalCommit: number
  coalMinFrac: number
  coalPrice: number // marginal coal tranche cost (the administered-price lever)
  costs: Record<string, number>
}

/**
 * Rebuild a grid's merit-order stack from per-fuel availability, folding in any
 * removed MW (a trip or outage) BEFORE the coal commit/marginal split so the split
 * lands on the reduced fuel exactly as pipeline/fleet_ph.stack does, then appending
 * any added blocks (firm gas/coal/solar/storage). Blocks are sorted by cost.
 */
export function buildStack(
  fuelAvail: Record<string, number>,
  removed: Record<string, number>,
  added: Block[],
  p: StackParams
): Block[] {
  const blocks: Block[] = []
  for (const fuel of Object.keys(fuelAvail)) {
    const mw = (fuelAvail[fuel] ?? 0) - (removed[fuel] ?? 0)
    if (mw <= 0) continue
    if (fuel === 'coal') {
      const mustRun = round1(mw * p.coalMinFrac)
      blocks.push({ fuel: 'coal', cost: p.coalCommit, mw: mustRun })
      blocks.push({ fuel: 'coal', cost: p.coalPrice, mw: round1(mw - mustRun) })
    } else {
      blocks.push({ fuel, cost: p.costs[fuel] ?? 0, mw: round1(mw) })
    }
  }
  for (const b of added) if (b.mw > 0) blocks.push({ ...b })
  blocks.sort((a, b) => a.cost - b.cost)
  return blocks
}

/** Marginal cost serving the g-th MW on a cost-sorted stack (mirror of _marg). */
export function marginal(
  blocks: Block[],
  g: number
): { cost: number; fuel: string | null } {
  if (blocks.length === 0) return { cost: OIL_FALLBACK, fuel: null }
  if (g <= 0) return { cost: blocks[0].cost, fuel: blocks[0].fuel }
  let cum = 0
  for (const b of blocks) {
    cum += b.mw
    if (cum >= g) return { cost: b.cost, fuel: b.fuel }
  }
  const last = blocks[blocks.length - 1]
  return { cost: last.cost, fuel: last.fuel }
}

/** Single-grid clear: marginal price, availability, shortfall. */
export function clearGrid(
  blocks: Block[],
  demand: number
): { price: number; avail: number; shortfall: number; marginal: string | null } {
  const avail = blocks.reduce((s, b) => s + b.mw, 0)
  const m = marginal(blocks, demand)
  return {
    price: m.cost,
    avail: round1(avail),
    shortfall: Math.max(0, round1(demand - avail)),
    marginal: m.fuel,
  }
}

// ---- coupled radial solve (mirror of coupled_dispatch.clear_coupled) --------

const OIL_FALLBACK = 12.0

function rootDecr(
  phi: (x: number) => number,
  lo: number,
  hi: number,
  target: number
): number {
  for (let i = 0; i < 40 && hi - lo > 0.25; i++) {
    const m = (lo + hi) / 2
    if (phi(m) > target) lo = m
    else hi = m
  }
  return (lo + hi) / 2
}

function optFlow(
  phi: (x: number) => number,
  lo: number,
  hi: number,
  wheel: number
): number {
  if (hi <= lo) return lo
  const zero = Math.min(Math.max(0, lo), hi)
  const p0 = phi(zero)
  if (p0 > wheel) return phi(hi) >= wheel ? hi : rootDecr(phi, zero, hi, wheel)
  if (p0 < -wheel) return phi(lo) <= -wheel ? lo : rootDecr(phi, lo, zero, -wheel)
  return zero
}

/**
 * Couple the three grids and clear them together over the two HVDC corridors.
 * demand/stacks keyed by grid; caps {leyte, mvip} in MW. Signed flows point south
 * (toward `to`); a saturated corridor prices the downstream grid above the upstream
 * one by the congestion rent. Same coordinate-descent solve as the Python engine.
 */
export function clearCoupled(
  demand: Record<GridKey, number>,
  stacks: Record<GridKey, Block[]>,
  caps: { leyte: number; mvip: number },
  wheel: number
): CoupledResult {
  const dL = demand.luzon
  const dV = demand.visayas
  const dM = demand.mindanao
  const bL = stacks.luzon
  const bV = stacks.visayas
  const bM = stacks.mindanao
  const c1 = caps.leyte
  const c2 = caps.mvip
  const mcL = (f1: number) => marginal(bL, dL + f1).cost
  const mcV = (f1: number, f2: number) => marginal(bV, dV + f2 - f1).cost
  const mcM = (f2: number) => marginal(bM, dM - f2).cost

  let f1 = 0
  let f2 = 0
  for (let i = 0; i < 60; i++) {
    const lo = Math.max(-c1, -dL)
    const hi = Math.min(c1, dV + f2)
    const nf1 = optFlow((x) => mcV(x, f2) - mcL(x), lo, hi, wheel)
    const lo2 = Math.max(-c2, nf1 - dV)
    const hi2 = Math.min(c2, dM)
    const nf2 = optFlow((x) => mcM(x) - mcV(nf1, x), lo2, hi2, wheel)
    if (Math.abs(nf1 - f1) + Math.abs(nf2 - f2) < 0.25) {
      f1 = nf1
      f2 = nf2
      break
    }
    f1 = nf1
    f2 = nf2
  }

  const gen: Record<GridKey, number> = {
    luzon: dL + f1,
    visayas: dV + f2 - f1,
    mindanao: dM - f2,
  }
  const avail: Record<GridKey, number> = {
    luzon: bL.reduce((s, b) => s + b.mw, 0),
    visayas: bV.reduce((s, b) => s + b.mw, 0),
    mindanao: bM.reduce((s, b) => s + b.mw, 0),
  }
  const price: Record<GridKey, number> = {
    luzon: round3(marginal(bL, gen.luzon).cost),
    visayas: round3(marginal(bV, gen.visayas).cost),
    mindanao: round3(marginal(bM, gen.mindanao).cost),
  }
  const shortfall: Record<GridKey, number> = {
    luzon: Math.max(0, round1(gen.luzon - avail.luzon)),
    visayas: Math.max(0, round1(gen.visayas - avail.visayas)),
    mindanao: Math.max(0, round1(gen.mindanao - avail.mindanao)),
  }
  const eps = 0.5
  const sat1 = Math.abs(f1) >= c1 - eps
  const sat2 = Math.abs(f2) >= c2 - eps
  return {
    price,
    gen: {
      luzon: round1(gen.luzon),
      visayas: round1(gen.visayas),
      mindanao: round1(gen.mindanao),
    },
    shortfall,
    flowLV: round1(f1),
    flowVM: round1(f2),
    leyte: {
      flow: round1(f1),
      sat: sat1,
      rent: sat1
        ? round3(f1 > 0 ? price.visayas - price.luzon : price.luzon - price.visayas)
        : 0,
    },
    mvip: {
      flow: round1(f2),
      sat: sat2,
      rent: sat2
        ? round3(f2 > 0 ? price.mindanao - price.visayas : price.visayas - price.mindanao)
        : 0,
    },
  }
}

// ---- scenario assembly ------------------------------------------------------

export interface ScenarioOut {
  single: { price: number; avail: number; shortfall: number; marginal: string | null }
  base: { price: number; marginal: string | null }
  coupled: CoupledResult
  feed: 'leyte' | 'mvip' | null // which corridor feeds the selected grid (null for Luzon)
  demand: Record<GridKey, number>
  stack: Block[] // the selected grid's scenario merit-order stack (for the chart)
  demandSel: number // the selected grid's demand after the add-DC lever
  solarDeliveredMW: number // solar MW the add-solar lever actually delivers at the ref hour
  solarMiddayMW: number // what the same solar would deliver at midday (the caveat)
}

function stackParams(d: Dispatch, coalPrice?: number): StackParams {
  const a = d.assumptions
  return {
    coalCommit: a.coal_commit_php_kwh,
    coalMinFrac: a.coal_min_load_frac,
    coalPrice: coalPrice ?? a.fuel_marginal_cost_php_kwh.coal,
    costs: a.fuel_marginal_cost_php_kwh,
  }
}

/** Added firm/renewable blocks for the selected grid from the levers. */
function addedBlocks(
  d: Dispatch,
  lv: Levers
): { blocks: Block[]; solarDelivered: number; solarMidday: number } {
  const mo = d.merit_order[lv.grid]
  const costs = d.assumptions.fuel_marginal_cost_php_kwh
  const blocks: Block[] = []
  // solar is derated by the availability fraction at the reference hour (~0 at the
  // evening peak): the add-solar lever barely moves adequacy, storage does.
  const solarDelivered = round1(lv.addSolar * mo.solar_avail_frac_ref)
  const solarMidday = round1(lv.addSolar * mo.solar_avail_frac_midday)
  if (solarDelivered > 0)
    blocks.push({ fuel: 'solar', cost: costs.solar ?? 0, mw: solarDelivered })
  if (lv.addGas > 0)
    blocks.push({ fuel: 'natural_gas', cost: costs.natural_gas, mw: lv.addGas })
  if (lv.addCoal > 0) blocks.push({ fuel: 'coal', cost: lv.coalPrice, mw: lv.addCoal })
  if (lv.addStorage > 0) {
    const disc = d.storage?.discharge_offer_php_kwh ?? 5.17
    blocks.push({ fuel: 'storage', cost: disc, mw: lv.addStorage })
  }
  return { blocks, solarDelivered, solarMidday }
}

/** Removed MW per fuel on the selected grid from a named-unit trip. */
function removedForTrip(lv: Levers, units: TrippableUnit[]): Record<string, number> {
  const removed: Record<string, number> = {}
  if (lv.trip) {
    const u = units.find((x) => x.name === lv.trip && x.grid.toLowerCase() === lv.grid)
    if (u) removed[u.fuel] = (removed[u.fuel] ?? 0) + u.capacity_mw
  }
  return removed
}

/**
 * Solve the full scenario: the selected grid gets the levers; the other two grids
 * clear at baseline. Returns the single-grid clear, the base (no-lever) price, the
 * coupled solve, and the solar-caveat figures.
 */
export function solveScenario(
  d: Dispatch,
  lv: Levers,
  units: TrippableUnit[]
): ScenarioOut {
  const wheel = d.assumptions.wheeling_cost_php_kwh
  const removedSel = removedForTrip(lv, units)
  const { blocks: added, solarDelivered, solarMidday } = addedBlocks(d, lv)

  const demand: Record<GridKey, number> = {
    luzon: d.merit_order.luzon.typical_evening_demand_mw,
    visayas: d.merit_order.visayas.typical_evening_demand_mw,
    mindanao: d.merit_order.mindanao.typical_evening_demand_mw,
  }
  demand[lv.grid] += lv.addDC

  const stacks: Record<GridKey, Block[]> = {} as Record<GridKey, Block[]>
  for (const g of GRID_KEYS) {
    const sel = g === lv.grid
    stacks[g] = buildStack(
      d.merit_order[g].fuel_avail_mw,
      sel ? removedSel : {},
      sel ? added : [],
      stackParams(d, sel ? lv.coalPrice : undefined)
    )
  }

  // base (no levers) single-grid clear for the selected grid, for the delta readout
  const baseStack = buildStack(
    d.merit_order[lv.grid].fuel_avail_mw,
    {},
    [],
    stackParams(d)
  )
  const base = clearGrid(baseStack, d.merit_order[lv.grid].typical_evening_demand_mw)

  // the relief lever raises the operating limit of the corridor feeding the grid
  const feed: 'leyte' | 'mvip' | null =
    lv.grid === 'luzon' ? null : lv.grid === 'mindanao' ? 'mvip' : 'leyte'
  const caps = {
    leyte: baseCap(d, 'leyte') + (feed === 'leyte' ? lv.reliefMW : 0),
    mvip: baseCap(d, 'mvip') + (feed === 'mvip' ? lv.reliefMW : 0),
  }

  const single = clearGrid(stacks[lv.grid], demand[lv.grid])
  const coupled = clearCoupled(demand, stacks, caps, wheel)
  return {
    single,
    base: { price: base.price, marginal: base.marginal },
    coupled,
    feed,
    demand,
    stack: stacks[lv.grid],
    demandSel: demand[lv.grid],
    solarDeliveredMW: solarDelivered,
    solarMiddayMW: solarMidday,
  }
}

function baseCap(d: Dispatch, which: 'leyte' | 'mvip'): number {
  const id = which === 'leyte' ? CORRIDOR.leyte.id : CORRIDOR.mvip.id
  const c = d.coupling.corridors.find((x) => x.id === id)
  return c?.limit_mw ?? (which === 'leyte' ? 250 : 450)
}

function round1(x: number): number {
  return Math.round(x * 10) / 10
}
function round3(x: number): number {
  return Math.round(x * 1000) / 1000
}
