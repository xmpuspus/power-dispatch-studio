import { describe, expect, it } from 'vitest'
import type { GridKey } from '../lib/types'
import type { ChronoHour } from './chrono'
import { comparePosition, settle, validateBook, type Contract } from './contracts'

/** A solved day at one price on every grid, so the arithmetic stays visible. */
const flat = (price: number, n = 24): ChronoHour[] =>
  Array.from({ length: n }, (_, h) => ({
    hour: h,
    price: { luzon: price, visayas: price, mindanao: price },
    marginal: { luzon: 'coal', visayas: 'coal', mindanao: 'coal' },
    demand: { luzon: 10000, visayas: 2000, mindanao: 2000 },
    shortfall: { luzon: 0, visayas: 0, mindanao: 0 },
    flowLV: 0,
    flowVM: 0,
    leyte: { sat: false, rent: 0 },
    mvip: { sat: false, rent: 0 },
    fuelGen: { luzon: {}, visayas: {}, mindanao: {} },
    socMwh: 0,
    chargeMw: 0,
    dischargeMw: 0,
  })) as ChronoHour[]

const buy: Contract[] = [
  { grid: 'luzon' as GridKey, mw: 100, strike_php_kwh: 5, side: 'buy' },
]

// The Python test in tests/test_contracts.py checks these same numbers, so the
// two sides of the tool cannot report a different position for the same book.
describe('settle', () => {
  it('values one peso above strike on 100 MW for a day at P2.4M', () => {
    expect(settle(flat(6), buy).position).toBe(2_400_000)
  })

  it('runs the other way below strike', () => {
    expect(settle(flat(4), buy).position).toBe(-2_400_000)
  })

  it('flips the sign for a sell contract', () => {
    const sell: Contract[] = [{ ...buy[0], side: 'sell' }]
    expect(settle(flat(6), sell).position).toBe(-2_400_000)
  })

  it('covers only the hours a block names', () => {
    const peak: Contract[] = [{ ...buy[0], hours: [18, 19, 20, 21] }]
    const s = settle(flat(6), peak)
    expect(s.contracts[0].hoursCovered).toBe(4)
    expect(s.position).toBe(400_000)
  })

  it('prices the open position at spot and reports the cover', () => {
    const s = settle(flat(6), buy, { luzon: 400 })
    expect(s.open[0].openMwh).toBe(300 * 24)
    expect(s.open[0].coveredPct).toBeCloseTo(25, 6)
    expect(s.openCost).toBe(300 * 1000 * 24 * 6)
  })

  it('never lets a sell contract cover a load', () => {
    const sell: Contract[] = [{ ...buy[0], side: 'sell' }]
    expect(settle(flat(6), sell, { luzon: 100 }).open[0].openMwh).toBe(2400)
  })
})

describe('comparePosition', () => {
  it('reports the contract gain, the open cost, and the net', () => {
    const c = comparePosition(flat(5), flat(6), buy, { luzon: 400 })
    expect(c.positionChange).toBe(2_400_000)
    expect(c.openCostChange).toBe(300 * 1000 * 24 * 1)
    expect(c.netChange).toBe(c.positionChange - c.openCostChange)
  })

  it('moves nothing when the price does not move', () => {
    expect(comparePosition(flat(6), flat(6), buy).positionChange).toBe(0)
  })
})

describe('validateBook', () => {
  it('names a bad grid, a negative volume, and an hour past 23', () => {
    const bad = [
      { grid: 'lozon', mw: 100, strike_php_kwh: 5 },
      { grid: 'luzon', mw: -50, strike_php_kwh: 5 },
      { grid: 'luzon', mw: 100, strike_php_kwh: 5, hours: [25] },
    ] as unknown as Contract[]
    const msgs = validateBook(bad).join(' ')
    expect(msgs).toContain('Contract 1 needs a grid')
    expect(msgs).toContain('cannot be negative')
    expect(msgs).toContain('outside 0 to 23')
  })

  it('passes a good book', () => {
    expect(validateBook(buy)).toEqual([])
  })
})

// The same golden price series the Python suite settles, from the case
// chrono_golden pins for "both Sual units out all day". Both sides read the
// same numbers and must reach the same pesos, so a settlement that drifts on
// one engine fails there instead of quietly disagreeing with the other.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

describe('the browser reaches the same pesos as Python', () => {
  it('settles the golden Sual day to the position its own prices imply', () => {
    const profiles = JSON.parse(
      readFileSync(
        fileURLToPath(new URL('../../public/data/profiles.json', import.meta.url)),
        'utf8'
      )
    )
    const g = profiles.chrono_golden.cases.find(
      (c: { label: string }) => c.label === 'both Sual units out all day'
    )
    const hours = Array.from({ length: 24 }, (_, h) => ({
      hour: h,
      price: {
        luzon: g.expect.price.luzon[h],
        visayas: g.expect.price.visayas[h],
        mindanao: g.expect.price.mindanao[h],
      },
    })) as ChronoHour[]
    const book: Contract[] = [
      { name: 'PSA with the DU', grid: 'luzon', mw: 250, strike_php_kwh: 6.4 },
      {
        name: 'Evening peak block',
        grid: 'luzon',
        mw: 100,
        strike_php_kwh: 9.0,
        hours: [18, 19, 20, 21],
      },
    ]
    const s = settle(hours, book, { luzon: 400 })

    // These were hand-written pesos, 600,500 and 19,800,300. The golden case
    // takes its hydro budget from the rolling archive window, so a fixed
    // historical day re-solves every night. On 2026-08-10 the window grew from
    // 77 days to 83, hydro set the Luzon price in 6 hours where coal had, and
    // the two figures moved 25x. The Python twin of this test carries the same
    // fix, because both engines change together.
    //
    // Derive them from the case's own prices instead, the long way round.
    // Comparing settle() against a recording of settle() would prove nothing.
    const MWH_PESOS = 1000
    const OWN_LOAD_MW = 400
    const luz: number[] = g.expect.price.luzon
    const coveredMw = Array.from({ length: 24 }, () => 0)
    let wantPosition = 0
    for (const c of book) {
      const cover = c.hours ?? Array.from({ length: 24 }, (_, h) => h)
      for (const h of cover) {
        wantPosition += (luz[h] - c.strike_php_kwh) * c.mw * MWH_PESOS
        coveredMw[h] += c.mw
      }
    }
    // The open position is the load the book leaves uncovered, hour by hour,
    // never the whole 400 MW: 250 MW runs all day, 100 MW more covers 18 to 21.
    const wantOpen = luz.reduce(
      (sum, price, h) =>
        sum + Math.max(0, OWN_LOAD_MW - coveredMw[h]) * MWH_PESOS * price,
      0
    )

    expect(s.position).toBeCloseTo(wantPosition, 2)
    expect(s.openCost).toBeCloseTo(wantOpen, 2)
    // A price move has to reach the position, or the checks above pass on zeros.
    expect(Math.abs(s.position)).toBeGreaterThan(1)
    expect(s.openCost).toBeGreaterThan(1)
  })
})
