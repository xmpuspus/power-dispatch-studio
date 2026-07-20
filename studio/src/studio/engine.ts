// Client scenario engine. Stacks are rebuilt from the baked per-fuel
// availability (merit_order[g].fuel_avail_mw) exactly as before; the coupled
// clear is a single-hour HiGHS LP (the same canonical model as the
// chronological engine, one hour deep), so snapshot prices are locational
// marginal prices from the balance duals. The pipeline stays the source of
// truth: dispatch.scenario_golden carries input/output pairs plus the LP text
// hash from the Python solve, and engine.test.ts asserts this reproduces both.

import type { Block, Dispatch, GridKey } from '../lib/types'
import { OFFER_CAP, buildDayLp } from './lpText'
import { solveLp } from './solver'

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
  lngSwitch: boolean // reprice gas from Malampaya to imported LNG (the ~2027 cliff)
  hydrology: number // multiplier on hydro availability (dry El Nino / normal / wet)
}

/** Scale a grid's hydro availability by the hydrology multiplier (dry/normal/wet). */
function scaleHydro(
  fuelAvail: Record<string, number>,
  hydrology: number
): Record<string, number> {
  if (hydrology === 1 || fuelAvail.hydro == null) return fuelAvail
  return { ...fuelAvail, hydro: round1(fuelAvail.hydro * hydrology) }
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
  // unrounded gen, for marginal-fuel and dispatch-split reads that must match
  // the Python reference exactly (rounding first can flip a block boundary)
  genRaw: Record<GridKey, number>
  // what sets each grid's price: the own-stack fuel when it explains the
  // dual, else import/export (the price arrived over a corridor)
  marginalLabel: Record<GridKey, string | null>
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

/** Marginal cost serving the g-th MW on a cost-sorted stack (mirror of
 * chrono.marginal): beyond the stack the hour is short and prices at the
 * sourced WESM offer cap. */
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
  return { cost: OFFER_CAP, fuel: 'shortage' }
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

// ---- coupled radial solve: a single-hour HiGHS LP ---------------------------

const OIL_FALLBACK = 12.0
const LABEL_EPS = 0.025
const FLOW_SAT_EPS = 0.5

/** Name what sets a snapshot price (no storage at the reference hour). */
function snapshotLabel(
  price: number,
  ownCost: number,
  ownFuel: string | null,
  unservedMarginal = false
) {
  if (unservedMarginal) return 'shortage'
  if (Math.abs(ownCost - price) <= LABEL_EPS) return ownFuel
  return price > ownCost ? 'export' : 'import'
}

/** The canonical single-hour LP text for a snapshot clear; the parity test
 * hashes this against dispatch.scenario_golden. */
export function snapshotLpText(
  demand: Record<GridKey, number>,
  stacks: Record<GridKey, Block[]>,
  caps: { leyte: number; mvip: number },
  wheel: number
): string {
  const hstacks = {
    luzon: [stacks.luzon],
    visayas: [stacks.visayas],
    mindanao: [stacks.mindanao],
  }
  const hdemand = {
    luzon: [demand.luzon],
    visayas: [demand.visayas],
    mindanao: [demand.mindanao],
  }
  let dearest = 12
  for (const g of GRID_KEYS)
    for (const b of stacks[g]) if (b.cost > dearest) dearest = b.cost
  // shortage prices at the sourced WESM offer cap; mirror of solve_snapshot_lp
  return buildDayLp(
    hstacks,
    hdemand,
    caps,
    wheel,
    [],
    null,
    Math.max(OFFER_CAP, dearest + 0.001)
  )
}

/**
 * Couple the three grids and clear them together over the two HVDC corridors:
 * the canonical LP, one hour deep, solved by HiGHS. Signed flows point south
 * (toward `to`); prices are the balance-row duals, so a saturated corridor
 * prices the downstream grid above the upstream one by the congestion rent and
 * an UNSATURATED corridor holds neighbours within the wheeling cost. Mirrors
 * pipeline/lp_dispatch.solve_snapshot_lp.
 */
export function clearCoupled(
  demand: Record<GridKey, number>,
  stacks: Record<GridKey, Block[]>,
  caps: { leyte: number; mvip: number },
  wheel: number
): CoupledResult {
  const sol = solveLp(snapshotLpText(demand, stacks, caps, wheel))
  const f1 = sol.col('f1p_0') - sol.col('f1n_0')
  const f2 = sol.col('f2p_0') - sol.col('f2n_0')

  const gen: Record<GridKey, number> = {
    luzon: demand.luzon + f1,
    visayas: demand.visayas + f2 - f1,
    mindanao: demand.mindanao - f2,
  }
  const S: Record<GridKey, string> = { luzon: 'l', visayas: 'v', mindanao: 'm' }
  const price = {} as Record<GridKey, number>
  const shortfall = {} as Record<GridKey, number>
  const marginalLabel = {} as Record<GridKey, string | null>
  for (const g of GRID_KEYS) {
    price[g] = round3(sol.dual(`bal_${S[g]}_0`))
    shortfall[g] = Math.max(0, round1(sol.col(`u_${S[g]}_0`)))
    const m = marginal(stacks[g], gen[g])
    marginalLabel[g] = snapshotLabel(price[g], m.cost, m.fuel, shortfall[g] > 1e-3)
  }
  // a zero cap is a BLOCKED corridor, not a saturated one: without the >eps
  // test this is trivially true and the rent goes negative (mirrors chrono.py)
  const sat1 = caps.leyte > FLOW_SAT_EPS && Math.abs(f1) >= caps.leyte - FLOW_SAT_EPS
  const sat2 = caps.mvip > FLOW_SAT_EPS && Math.abs(f2) >= caps.mvip - FLOW_SAT_EPS
  return {
    price,
    gen: {
      luzon: round1(gen.luzon),
      visayas: round1(gen.visayas),
      mindanao: round1(gen.mindanao),
    },
    genRaw: gen,
    marginalLabel,
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

function stackParams(d: Dispatch, coalPrice?: number, lngSwitch = false): StackParams {
  const a = d.assumptions
  const costs = a.fuel_marginal_cost_php_kwh
  // the Malampaya-to-imported-LNG switch reprices gas from the sourced Malampaya
  // cost to the sourced imported-LNG cost (Malampaya depletes around 2027).
  const effCosts =
    lngSwitch && costs.lng != null ? { ...costs, natural_gas: costs.lng } : costs
  return {
    coalCommit: a.coal_commit_php_kwh,
    coalMinFrac: a.coal_min_load_frac,
    coalPrice: coalPrice ?? a.fuel_marginal_cost_php_kwh.coal,
    costs: effCosts,
  }
}

/** Added firm/renewable blocks for the selected grid from the levers. */
function addedBlocks(
  d: Dispatch,
  lv: Levers
): { blocks: Block[]; solarDelivered: number; solarMidday: number } {
  const mo = d.merit_order[lv.grid]
  const costs = d.assumptions.fuel_marginal_cost_php_kwh
  const gasCost = lv.lngSwitch && costs.lng != null ? costs.lng : costs.natural_gas
  const blocks: Block[] = []
  // solar is derated by the availability fraction at the reference hour (~0 at the
  // evening peak): the add-solar lever barely moves adequacy, storage does.
  const solarDelivered = round1(lv.addSolar * mo.solar_avail_frac_ref)
  const solarMidday = round1(lv.addSolar * mo.solar_avail_frac_midday)
  if (solarDelivered > 0)
    blocks.push({ fuel: 'solar', cost: costs.solar ?? 0, mw: solarDelivered })
  if (lv.addGas > 0) blocks.push({ fuel: 'natural_gas', cost: gasCost, mw: lv.addGas })
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
    // the LNG switch and the hydrology multiplier are supply-side, system-wide
    // changes (gas sits only on Luzon; a dry spell affects all grids), so they apply
    // to every grid's stack. The coal price and trip are per-grid what-ifs and stay
    // scoped to the selected grid.
    stacks[g] = buildStack(
      scaleHydro(d.merit_order[g].fuel_avail_mw, lv.hydrology),
      sel ? removedSel : {},
      sel ? added : [],
      stackParams(d, sel ? lv.coalPrice : undefined, lv.lngSwitch)
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
