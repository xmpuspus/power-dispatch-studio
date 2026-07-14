import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Dispatch, Profiles } from '../lib/types'
import { forwardPath, pdpGrowth, type PdpPath, type YearBand } from './forward'

const read = (f: string) =>
  JSON.parse(readFileSync(fileURLToPath(new URL(`../../public/data/${f}`, import.meta.url)), 'utf8'))
const d: Dispatch = read('dispatch.json')
const profiles: Profiles = read('profiles.json')
const dp = read('demand_path.json')
const pdp: PdpPath = { years: dp.years, per_grid_mw: dp.per_grid_mw }

describe('PDP growth', () => {
  it('is zero at the base year and rising after it', () => {
    expect(pdpGrowth(pdp, 2026, 2026).luzon).toBe(0)
    expect(pdpGrowth(pdp, 2026, 2030).luzon!).toBeGreaterThan(0)
  })
})

describe('forward path', () => {
  let bands: YearBand[]
  beforeAll(() => {
    bands = forwardPath(d, profiles, pdp, 2026, [2026, 2028, 2030], 15, 11)
  })
  it('returns one band per requested year', () => {
    expect(bands.map((b) => b.year)).toEqual([2026, 2028, 2030])
  })
  it('orders p10 <= median <= p90 on every grid and year', () => {
    for (const b of bands)
      for (const g of ['luzon', 'visayas', 'mindanao'] as const) {
        expect(b.perGrid[g].p10).toBeLessThanOrEqual(b.perGrid[g].p50 + 1e-9)
        expect(b.perGrid[g].p50).toBeLessThanOrEqual(b.perGrid[g].p90 + 1e-9)
      }
  })
  it('is reproducible for a fixed seed', () => {
    const again = forwardPath(d, profiles, pdp, 2026, [2026, 2028, 2030], 15, 11)
    expect(again).toEqual(bands)
  })
})
