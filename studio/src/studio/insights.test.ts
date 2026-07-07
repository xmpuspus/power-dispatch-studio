import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, ProjectRow, Profiles } from '../lib/types'
import { runChronology, type ChronoHour } from './chrono'
import {
  addsAtHorizon,
  bindingCounts,
  classifyHour,
  emissionsByFuel,
  hourlyBand,
  percentile,
  pooledDuration,
  runEmissionsT,
  windowStats,
} from './insights'

const load = <T>(name: string): T =>
  JSON.parse(
    readFileSync(
      fileURLToPath(new URL(`../../public/data/${name}`, import.meta.url)),
      'utf8'
    )
  )
const d = load<Dispatch>('dispatch.json')
const profiles = load<Profiles>('profiles.json')
const factors = load<{ factor_map: Record<string, number> }>('emissions.json').factor_map

const hour = (over: Partial<ChronoHour>): ChronoHour => ({
  hour: 0,
  price: { luzon: 6, visayas: 6, mindanao: 6 },
  marginal: { luzon: 'coal', visayas: 'coal', mindanao: 'coal' },
  demand: { luzon: 10000, visayas: 2000, mindanao: 2000 },
  shortfall: { luzon: 0, visayas: 0, mindanao: 0 },
  flowLV: 0,
  flowVM: 0,
  leyte: { sat: false, rent: 0 },
  mvip: { sat: false, rent: 0 },
  fuelGen: {
    luzon: { coal: 5000, natural_gas: 2000, hydro: 1000 },
    visayas: { coal: 1500, geothermal: 500 },
    mindanao: { coal: 1500, hydro: 500 },
  },
  socMwh: 0,
  chargeMw: 0,
  dischargeMw: 0,
  ...over,
})

describe('percentile', () => {
  it('interpolates and clamps', () => {
    expect(percentile([1, 2, 3, 4, 5], 50)).toBe(3)
    expect(percentile([1, 2, 3, 4, 5], 0)).toBe(1)
    expect(percentile([1, 2, 3, 4, 5], 100)).toBe(5)
    expect(percentile([1, 2], 50)).toBeCloseTo(1.5, 9)
    expect(Number.isNaN(percentile([], 50))).toBe(true)
  })
})

describe('classifyHour names the binding constraint', () => {
  it('unserved load beats everything', () => {
    const h = hour({ shortfall: { luzon: 100, visayas: 0, mindanao: 0 } })
    expect(classifyHour(h, 'luzon').cause).toBe('unserved')
  })
  it('a saturated corridor binds only the importing side', () => {
    const h = hour({ flowLV: 250, leyte: { sat: true, rent: 3 } })
    expect(classifyHour(h, 'visayas')).toEqual({
      cause: 'corridor',
      detail: 'Leyte-Luzon at limit',
    })
    // Luzon exports on this flow sign: its price is set by its own stack
    expect(classifyHour(h, 'luzon').cause).toBe('fuel')
  })
  it('otherwise the marginal fuel sets the price', () => {
    const h = hour({ marginal: { luzon: 'oil', visayas: 'coal', mindanao: 'coal' } })
    expect(classifyHour(h, 'luzon')).toEqual({ cause: 'fuel', detail: 'oil' })
  })
  it('counts tally to the window length', () => {
    const hours = [
      hour({}),
      hour({ marginal: { luzon: 'oil', visayas: 'coal', mindanao: 'coal' } }),
    ]
    const counts = bindingCounts(hours, 'luzon')
    expect(counts.reduce((s, c) => s + c.hours, 0)).toBe(2)
  })
})

describe('window distribution over real replayed days', () => {
  const dates = profiles.days
    .filter((x) => x.market)
    .slice(0, 5)
    .map((x) => x.date)
  const runs = dates.map((dt) => runChronology(d, profiles, dt, {}))
  it('band is ordered p10 <= p50 <= p90 for every hour', () => {
    const band = hourlyBand(runs, 'luzon')
    expect(band).toHaveLength(24)
    for (const b of band) {
      expect(b.p10).toBeLessThanOrEqual(b.p50 + 1e-9)
      expect(b.p50).toBeLessThanOrEqual(b.p90 + 1e-9)
    }
  })
  it('window stats bracket the daily means and name the dearest day', () => {
    const s = windowStats(runs, 'luzon')
    expect(s.days).toBe(dates.length)
    expect(s.p10).toBeLessThanOrEqual(s.p50)
    expect(s.p50).toBeLessThanOrEqual(s.p90)
    expect(dates).toContain(s.maxDate)
  })
  it('pooled duration is monotone dear to cheap over all hours', () => {
    const dur = pooledDuration(runs, 'luzon')
    expect(dur).toHaveLength(24 * dates.length)
    for (let i = 1; i < dur.length; i++)
      expect(dur[i].price).toBeLessThanOrEqual(dur[i - 1].price + 1e-9)
  })
})

describe('emissions math', () => {
  it('prices dispatched energy at the sourced factors, zero for storage', () => {
    const hours = [hour({})]
    const t = runEmissionsT(hours, factors)
    const expected =
      8000 * factors.coal +
      2000 * factors.natural_gas +
      1500 * factors.hydro +
      500 * factors.geothermal
    expect(t).toBe(Math.round(expected))
    expect(factors.storage).toBe(0)
    expect(factors.hydro).toBe(0)
  })
  it('per-fuel breakdown sums to the total within per-row rounding', () => {
    const hours = [hour({}), hour({})]
    const rows = emissionsByFuel(hours, factors)
    const total = rows.reduce((s, r) => s + r.tco2, 0)
    expect(Math.abs(total - runEmissionsT(hours, factors))).toBeLessThanOrEqual(
      rows.length
    )
  })
})

describe('LT Plan horizon math', () => {
  const rows: ProjectRow[] = [
    {
      grid: 'luzon',
      status: 'committed',
      fuel: 'coal',
      mw: 100,
      target: 'Dec-26',
      target_year: 2026,
    },
    {
      grid: 'luzon',
      status: 'committed',
      fuel: 'solar',
      mw: 50,
      target: 'Jun-29',
      target_year: 2029,
    },
    {
      grid: 'luzon',
      status: 'committed',
      fuel: 'storage',
      mw: 40,
      target: 'Dec-26',
      target_year: 2026,
    },
    {
      grid: 'luzon',
      status: 'committed',
      fuel: 'wind',
      mw: 30,
      target: 'TBD',
      target_year: null,
    },
    {
      grid: 'visayas',
      status: 'indicative',
      fuel: 'wind',
      mw: 2000,
      target: 'Jun-33',
      target_year: 2033,
    },
  ]
  it('respects the horizon, the status scope, the ESS split, and TBD', () => {
    const c28 = addsAtHorizon(rows, 2028, false)
    expect(c28.adds).toEqual([{ grid: 'luzon', fuel: 'coal', mw: 100 }])
    expect(c28.unscheduledMw).toBe(30)
    const c29 = addsAtHorizon(rows, 2029, false)
    expect(c29.adds.map((a) => a.fuel).sort()).toEqual(['coal', 'solar'])
    const both35 = addsAtHorizon(rows, 2035, true)
    expect(both35.adds.find((a) => a.fuel === 'wind' && a.grid === 'visayas')?.mw).toBe(
      2000
    )
  })
})
