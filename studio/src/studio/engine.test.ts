import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, GridKey } from '../lib/types'
import { GRID_KEYS } from './engine'
import {
  buildStack,
  clearCoupled,
  clearGrid,
  solveScenario,
  type Levers,
  type TrippableUnit,
} from './engine'

const d: Dispatch = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/dispatch.json', import.meta.url)),
    'utf8'
  )
)

function stackParams(coalPrice?: number) {
  const a = d.assumptions
  return {
    coalCommit: a.coal_commit_php_kwh,
    coalMinFrac: a.coal_min_load_frac,
    coalPrice: coalPrice ?? a.fuel_marginal_cost_php_kwh.coal,
    costs: a.fuel_marginal_cost_php_kwh,
  }
}

describe('golden parity vs the Python coupled_dispatch engine', () => {
  const g = d.scenario_golden
  const wheel = d.assumptions.wheeling_cost_php_kwh
  const tolP = g.tolerance_php_kwh
  const tolMW = g.tolerance_mw

  for (const c of g.cases) {
    it(`reproduces: ${c.label}`, () => {
      const stacks = {} as Record<GridKey, ReturnType<typeof buildStack>>
      for (const gk of GRID_KEYS) {
        stacks[gk] = buildStack(
          d.merit_order[gk].fuel_avail_mw,
          c.input.removed[gk] ?? {},
          [],
          stackParams()
        )
      }
      const res = clearCoupled(c.input.demand, stacks, c.input.caps, wheel)
      for (const gk of GRID_KEYS) {
        expect(Math.abs(res.price[gk] - c.expect.price[gk])).toBeLessThanOrEqual(tolP)
        expect(Math.abs(res.gen[gk] - c.expect.gen_mw[gk])).toBeLessThanOrEqual(tolMW)
        expect(
          Math.abs(res.shortfall[gk] - c.expect.shortfall_mw[gk])
        ).toBeLessThanOrEqual(tolMW)
      }
      expect(Math.abs(res.flowLV - c.expect.flow_lv_mw)).toBeLessThanOrEqual(tolMW)
      expect(Math.abs(res.flowVM - c.expect.flow_vm_mw)).toBeLessThanOrEqual(tolMW)
      expect(res.leyte.sat).toBe(c.expect.leyte_saturated)
      expect(Math.abs(res.leyte.rent - c.expect.leyte_rent_php_kwh)).toBeLessThanOrEqual(
        tolP
      )
      expect(res.mvip.sat).toBe(c.expect.mvip_saturated)
      expect(Math.abs(res.mvip.rent - c.expect.mvip_rent_php_kwh)).toBeLessThanOrEqual(
        tolP
      )
    })
  }
})

describe('all-levers-neutral reproduces the baked merit_order clear', () => {
  for (const gk of GRID_KEYS) {
    it(`selected grid ${gk} at baseline equals the baked stack clear`, () => {
      const stack = buildStack(d.merit_order[gk].fuel_avail_mw, {}, [], stackParams())
      const baked = clearGrid(
        d.merit_order[gk].blocks,
        d.merit_order[gk].typical_evening_demand_mw
      )
      const rebuilt = clearGrid(stack, d.merit_order[gk].typical_evening_demand_mw)
      expect(rebuilt.price).toBeCloseTo(baked.price, 3)
      // the rebuilt stack must equal the baked blocks (same fuels, MW, cost)
      const norm = (bs: typeof stack) =>
        bs.map((b) => `${b.fuel}:${b.mw.toFixed(1)}:${b.cost}`).sort()
      expect(norm(stack)).toEqual(norm(d.merit_order[gk].blocks))
    })
  }
})

const NO_LEVERS = (grid: GridKey): Levers => ({
  grid,
  addDC: 0,
  addSolar: 0,
  addGas: 0,
  addCoal: 0,
  addStorage: 0,
  trip: '',
  coalPrice: d.assumptions.fuel_marginal_cost_php_kwh.coal,
  reliefMW: 0,
  lngSwitch: false,
})

const UNITS: TrippableUnit[] = [] // trips exercised in a dedicated test below

describe('lever behavior', () => {
  it('adding a data center never lowers the clearing price', () => {
    const base = solveScenario(d, NO_LEVERS('luzon'), UNITS)
    const dc = solveScenario(d, { ...NO_LEVERS('luzon'), addDC: 2500 }, UNITS)
    expect(dc.single.price).toBeGreaterThanOrEqual(base.single.price)
  })

  it('added solar delivers ~0 MW at the evening peak but real MW at midday', () => {
    const s = solveScenario(d, { ...NO_LEVERS('luzon'), addSolar: 2000 }, UNITS)
    expect(s.solarDeliveredMW).toBeLessThan(1) // evening: solar profile ~0
    expect(s.solarMiddayMW).toBeGreaterThan(1000) // midday: the same panels deliver
  })

  it('storage discharge caps a tight-evening price where added solar cannot', () => {
    const tight = { ...NO_LEVERS('luzon'), addDC: 4000 }
    const noStore = solveScenario(d, tight, UNITS)
    const withStore = solveScenario(d, { ...tight, addStorage: 1319 }, UNITS)
    const withSolar = solveScenario(d, { ...tight, addSolar: 2000 }, UNITS)
    expect(withStore.single.price).toBeLessThanOrEqual(noStore.single.price)
    // solar at the evening peak does not move the price the way storage does
    expect(withSolar.single.price).toBeCloseTo(noStore.single.price, 3)
  })

  it('the coal-price lever moves only the marginal coal tranche', () => {
    const raised = buildStack(d.merit_order.luzon.fuel_avail_mw, {}, [], stackParams(9.0))
    const commit = raised.filter(
      (b) => b.fuel === 'coal' && b.cost === d.assumptions.coal_commit_php_kwh
    )
    const marg = raised.filter((b) => b.fuel === 'coal' && b.cost === 9.0)
    expect(commit.length).toBe(1) // committed tranche untouched at P4.14
    expect(marg.length).toBe(1) // marginal tranche re-priced to P9.00
  })

  it('the Malampaya to imported-LNG switch reprices Luzon gas upward', () => {
    const lngCost = d.assumptions.fuel_marginal_cost_php_kwh.lng
    const gasCost = d.assumptions.fuel_marginal_cost_php_kwh.natural_gas
    const before = buildStack(d.merit_order.luzon.fuel_avail_mw, {}, [], stackParams())
    const gasBefore = before.find((b) => b.fuel === 'natural_gas')
    const withLng = solveScenario(
      d,
      { ...NO_LEVERS('luzon'), addGas: 500, lngSwitch: true },
      UNITS
    )
    const gasAfter = withLng.stack.filter((b) => b.fuel === 'natural_gas')
    expect(lngCost).toBeGreaterThan(gasCost) // LNG dearer than Malampaya
    expect(gasBefore?.cost).toBe(gasCost) // baseline gas at Malampaya price
    // every gas block (base + added firm) is repriced to the LNG cost
    expect(gasAfter.every((b) => b.cost === lngCost)).toBe(true)
  })

  it('relieving the feeding corridor lowers a congested downstream price', () => {
    const congested = { ...NO_LEVERS('visayas'), addDC: 900 }
    const before = solveScenario(d, congested, UNITS)
    const after = solveScenario(d, { ...congested, reliefMW: 250 }, UNITS)
    expect(before.coupled.leyte.sat).toBe(true)
    expect(after.coupled.price.visayas).toBeLessThanOrEqual(before.coupled.price.visayas)
  })
})
