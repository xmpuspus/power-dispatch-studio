import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, GridKey } from '../lib/types'
import { baseObjects, overrideKey, solveModel, type Overrides } from './model'

const d: Dispatch = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/dispatch.json', import.meta.url)),
    'utf8'
  )
)
const gens: { name: string; grid: string; fuel: string; capacity_mw: number }[] =
  JSON.parse(
    readFileSync(
      fileURLToPath(new URL('../../public/data/generators.geojson', import.meta.url)),
      'utf8'
    )
  ).features.map(
    (f: {
      properties: { name: string; grid: string; fuel: string; capacity_mw: number }
    }) => f.properties
  )

const OBJ = baseObjects(d, gens)
const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

describe('solveModel base case reproduces the baked solution', () => {
  it('no overrides clears every grid on the coal margin (~P6), no flow', () => {
    const s = solveModel(d, OBJ, {})
    for (const g of GRIDS) expect(s.coupled.price[g]).toBeCloseTo(6, 1)
    expect(Math.abs(s.coupled.flowLV)).toBeLessThan(1)
  })

  it('base fuel availability matches the baked merit_order for Luzon', () => {
    const s = solveModel(d, OBJ, {})
    const baked = Object.values(d.merit_order.luzon.fuel_avail_mw).reduce(
      (a, b) => a + b,
      0
    )
    expect(s.avail.luzon).toBeGreaterThan(baked * 0.9)
  })
})

describe('property edits move the solution the right way', () => {
  it('raising a region load never lowers its clearing price', () => {
    const base = solveModel(d, OBJ, {})
    const ov: Overrides = {
      [overrideKey('region', 'luzon', 'demand_mw')]:
        (OBJ.region.find((r) => r.id === 'luzon')!.props.demand_mw as number) + 4000,
    }
    const hi = solveModel(d, OBJ, ov)
    // evening load sets the clearing price; the reserve margin is avail vs the annual
    // peak, so it is unaffected by an evening-load edit (that is the honest coupling)
    expect(hi.coupled.price.luzon).toBeGreaterThan(base.coupled.price.luzon)
  })

  it('cutting fuel availability erodes the reserve margin', () => {
    const base = solveModel(d, OBJ, {})
    const ov: Overrides = {
      [overrideKey('fuel', 'coal', 'luzon_mw')]:
        (OBJ.fuel.find((f) => f.id === 'coal')!.props.luzon_mw as number) - 3000,
    }
    const cut = solveModel(d, OBJ, ov)
    expect(cut.reserveMarginPct.luzon).toBeLessThan(base.reserveMarginPct.luzon)
  })

  it('editing the coal fuel price raises the marginal coal cost in the stack', () => {
    const ov: Overrides = { [overrideKey('fuel', 'coal', 'cost')]: 9 }
    const s = solveModel(d, OBJ, ov)
    const coalMarg = s.stacks.luzon
      .filter((b) => b.fuel === 'coal')
      .some((b) => b.cost === 9)
    expect(coalMarg).toBe(true)
  })

  it('cutting a named unit capacity reduces its grid available supply', () => {
    const sual = OBJ.generator.find((g) => g.id.toLowerCase().includes('sual'))
    if (!sual) return
    const base = solveModel(d, OBJ, {})
    const ov: Overrides = {
      [overrideKey('generator', sual.id, 'capacity_mw')]: 200,
    }
    const cut = solveModel(d, OBJ, ov)
    expect(cut.avail.luzon).toBeLessThan(base.avail.luzon)
  })

  it('relieving an interface limit lowers a congested downstream price', () => {
    const ov0: Overrides = {
      [overrideKey('region', 'visayas', 'demand_mw')]:
        (OBJ.region.find((r) => r.id === 'visayas')!.props.demand_mw as number) + 900,
    }
    const congested = solveModel(d, OBJ, ov0)
    expect(congested.coupled.leyte.sat).toBe(true)
    const ov1: Overrides = {
      ...ov0,
      [overrideKey('interface', 'leyte_luzon_hvdc', 'limit_mw')]: 500,
    }
    const relieved = solveModel(d, OBJ, ov1)
    expect(relieved.coupled.price.visayas).toBeLessThanOrEqual(
      congested.coupled.price.visayas
    )
  })

  it('N-1 solves a tripped price for every named unit', () => {
    const s = solveModel(d, OBJ, {})
    expect(s.n1.length).toBe(OBJ.generator.length)
    for (const row of s.n1)
      expect(row.tripped_price).toBeGreaterThanOrEqual(row.base_price - 1e-9)
  })
})
