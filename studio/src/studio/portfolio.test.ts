import { describe, expect, it } from 'vitest'
import type { ChronoHour } from './chrono'
import { exposureDurationCurve, valuePortfolio, type PortfolioSpec } from './portfolio'

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
  fuelGen: { luzon: {}, visayas: {}, mindanao: {} },
  socMwh: 0,
  chargeMw: 0,
  dischargeMw: 0,
  ...over,
})

describe('valuePortfolio', () => {
  it('scales generation by share, prices it at spot, and settles the PSA slice against a hand-computed fixture', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 1000 }, visayas: {}, mindanao: {} },
        price: { luzon: 5, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 2000 }, visayas: {}, mindanao: {} },
        price: { luzon: 8, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 500 }, visayas: {}, mindanao: {} },
        price: { luzon: 3, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 10,
      strikePhpKwh: 6,
      contractMw: 150,
    }
    const v = valuePortfolio(hours, spec)
    // gen: 100, 200, 50 MWh (10% of 1000, 2000, 500)
    expect(v.genMwh).toBe(350)
    // spot revenue: 100*5 + 200*8 + 50*3 = 500 + 1600 + 150
    expect(v.spotRevenue).toBe(2250)
    // contracted: min(150,100)=100, min(150,200)=150, min(150,50)=50
    // cfd: (6-5)*100 + (6-8)*150 + (6-3)*50 = 100 - 300 + 150
    expect(v.cfdSettlement).toBe(-50)
    expect(v.bilateralVsWesmDeltaPhp).toBe(v.cfdSettlement)
    expect(v.portfolioRevenue).toBe(2200)
    expect(v.meanSpotPhpKwh).toBeCloseTo(2250 / 350, 3)
    expect(v.meanRealizedPhpKwh).toBeCloseTo(2200 / 350, 3)
    // 2200/350 divided by 2250/350 is exactly 2200/2250
    expect(v.captureVsSpotPct).toBeCloseTo((2200 / 2250) * 100, 1)
  })

  it('the PSA beats spot when the strike sits above the observed price', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 200 }, visayas: {}, mindanao: {} },
        price: { luzon: 4, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 50,
      strikePhpKwh: 8,
      contractMw: 80,
    }
    const v = valuePortfolio(hours, spec)
    // gen 100 MWh, spot revenue 400, cfd (8-4)*80 = 320
    expect(v.spotRevenue).toBe(400)
    expect(v.cfdSettlement).toBe(320)
    expect(v.cfdSettlement).toBeGreaterThan(0)
    expect(v.portfolioRevenue).toBeGreaterThan(v.spotRevenue)
    expect(v.portfolioRevenue).toBe(720)
  })

  it('caps the contracted volume at generation when the contract exceeds it', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 1000 }, visayas: {}, mindanao: {} },
        price: { luzon: 5, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 2000 }, visayas: {}, mindanao: {} },
        price: { luzon: 8, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 500 }, visayas: {}, mindanao: {} },
        price: { luzon: 3, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 100,
      strikePhpKwh: 7,
      contractMw: 999999,
    }
    const v = valuePortfolio(hours, spec)
    // gen equals the full fuel dispatch each hour: 1000, 2000, 500
    expect(v.genMwh).toBe(3500)
    expect(v.spotRevenue).toBe(22500)
    // contracted is capped at generation, not the contract volume:
    // (7-5)*1000 + (7-8)*2000 + (7-3)*500 = 2000 - 2000 + 2000
    expect(v.cfdSettlement).toBe(2000)
    expect(v.portfolioRevenue).toBe(24500)
  })

  it('an hour with no dispatch from the chosen fuel contributes zero generation', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 1000 }, visayas: {}, mindanao: {} },
        price: { luzon: 5, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { natural_gas: 500 }, visayas: {}, mindanao: {} },
        price: { luzon: 9, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 10,
      strikePhpKwh: 6,
      contractMw: 50,
    }
    const v = valuePortfolio(hours, spec)
    expect(v.genMwh).toBe(100)
    expect(v.spotRevenue).toBe(500)
    // contracted: min(50,100)=50, min(50,0)=0; cfd = (6-5)*50 + (6-9)*0
    expect(v.cfdSettlement).toBe(50)
    expect(v.portfolioRevenue).toBe(550)
  })
})

describe('exposureDurationCurve', () => {
  it('pairs the uncontracted MWh with spot price and sorts dearest spot first', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 100 }, visayas: {}, mindanao: {} },
        price: { luzon: 3, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 400 }, visayas: {}, mindanao: {} },
        price: { luzon: 9, visayas: 6, mindanao: 6 },
      }),
      hour({
        fuelGen: { luzon: { coal: 300 }, visayas: {}, mindanao: {} },
        price: { luzon: 6, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 50,
      strikePhpKwh: 6,
      contractMw: 120,
    }
    const curve = exposureDurationCurve(hours, spec)
    expect(curve).toEqual([
      { hourIndex: 1, uncontractedMwh: 80, spot: 9 },
      { hourIndex: 2, uncontractedMwh: 30, spot: 6 },
      { hourIndex: 0, uncontractedMwh: 0, spot: 3 },
    ])
  })

  it('never reports negative exposure when the contract exceeds generation', () => {
    const hours = [
      hour({
        fuelGen: { luzon: { coal: 100 }, visayas: {}, mindanao: {} },
        price: { luzon: 5, visayas: 6, mindanao: 6 },
      }),
    ]
    const spec: PortfolioSpec = {
      grid: 'luzon',
      fuel: 'coal',
      sharePct: 50,
      strikePhpKwh: 6,
      contractMw: 999,
    }
    const curve = exposureDurationCurve(hours, spec)
    expect(curve[0].uncontractedMwh).toBe(0)
  })
})
