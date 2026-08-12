import { describe, expect, it } from 'vitest'
import type { ChronoHour } from '../studio/chrono'
import { buildMarketStrip } from './marketStripData'

const hour = (h: number, price: number, demand: number): ChronoHour => ({
  hour: h,
  price: { luzon: price, visayas: 6, mindanao: 6 },
  marginal: { luzon: 'coal', visayas: 'coal', mindanao: 'coal' },
  demand: { luzon: demand, visayas: 2000, mindanao: 1800 },
  shortfall: { luzon: h === 19 ? 20 : 0, visayas: 0, mindanao: 0 },
  flowLV: 0,
  flowVM: 0,
  leyte: { sat: h === 18, rent: h === 18 ? 1 : 0 },
  mvip: { sat: false, rent: 0 },
  fuelGen: { luzon: {}, visayas: {}, mindanao: {} },
  socMwh: 0,
  chargeMw: 0,
  dischargeMw: 0,
})

describe('market-day strip', () => {
  it('aligns the recorded price with each calculated hour', () => {
    const hours = Array.from({ length: 24 }, (_, h) => hour(h, 5 + h / 10, 8000 + h))
    const recorded = Array.from({ length: 24 }, (_, h) => 6 + h / 10)
    const items = buildMarketStrip(hours, recorded, 'luzon')

    expect(items).toHaveLength(24)
    expect(items[7]).toMatchObject({
      hour: 7,
      recordedPrice: 6.7,
      replayedPrice: 5.7,
      demandMw: 8007,
      constraint: false,
      shortfallMw: 0,
    })
  })

  it('marks constrained and short hours without relying on price color', () => {
    const hours = Array.from({ length: 24 }, (_, h) => hour(h, 6, 9000))
    const prices = Array(24).fill(null)
    const items = buildMarketStrip(hours, prices, 'luzon')

    expect(items[18].constraint).toBe(true)
    expect(items[19].shortfallMw).toBe(20)
    expect(items[0].recordedPrice).toBeNull()
    expect(buildMarketStrip(hours, prices, 'visayas')[18].constraint).toBe(true)
    expect(buildMarketStrip(hours, prices, 'mindanao')[18].constraint).toBe(false)
  })
})
