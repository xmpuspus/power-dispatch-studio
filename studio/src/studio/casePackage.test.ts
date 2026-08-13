import { describe, expect, it } from 'vitest'
import type { SavedRun } from './runs'
import {
  CASE_PACKAGE_SCHEMA,
  buildCasePackage,
  casePackageText,
  readCasePackage,
} from './casePackage'

const run: SavedRun = {
  id: 'case-1',
  name: 'DICT 1,500 MW reference, 22 July',
  savedAt: '2026-08-13T00:00:00.000Z',
  scenarioName: 'DICT 1,500 MW reference',
  overrides: { 'region:luzon:demand_mw': 14500 },
  assumptions: [
    {
      key: 'region:luzon:demand_mw',
      text: 'Luzon modeled load 14,500 MW (+1,500 MW)',
    },
  ],
  sourceNotes: [
    'DICT 1,500 MW reference scale; analyst allocation assumption, not a forecast.',
  ],
  calculation: { pricingMethod: 'cost', reserveHoldback: false },
  date: '2026-07-22',
  span: 'day',
  engineVersion: 3,
  hours: [
    {
      hour: 19,
      price: { luzon: 8, visayas: 7, mindanao: 6 },
      marginal: { luzon: 'oil', visayas: 'coal', mindanao: 'coal' },
      demand: { luzon: 14500, visayas: 2500, mindanao: 2400 },
      shortfall: { luzon: 0, visayas: 0, mindanao: 0 },
      flowLV: 125,
      flowVM: 20,
      leyte: { sat: true, rent: 1 },
      mvip: { sat: false, rent: 0 },
      fuelGen: { luzon: {}, visayas: {}, mindanao: {} },
      socMwh: 200,
      chargeMw: 0,
      dischargeMw: 100,
    },
  ],
  summaries: [
    {
      date: '2026-07-22',
      meanPrice: { luzon: 8, visayas: 7, mindanao: 6 },
      peakPrice: { luzon: 8, visayas: 7, mindanao: 6 },
      unservedMwh: { luzon: 0, visayas: 0, mindanao: 0 },
      leyteRentMPhp: 1,
      mvipRentMPhp: 0,
    },
  ],
}

describe('portable case package', () => {
  it('packages identity, assumptions, sources, results, and chart series', () => {
    const pkg = buildCasePackage(run, '2026-08-13T01:00:00.000Z')
    expect(pkg.schema).toBe(CASE_PACKAGE_SCHEMA)
    expect(pkg.run.name).toBe(run.name)
    expect(pkg.run.assumptions).toEqual(run.assumptions)
    expect(pkg.run.sourceNotes).toEqual(run.sourceNotes)
    expect(pkg.run.summaries).toHaveLength(1)
    expect(pkg.charts.hourlyPrices).toEqual([
      {
        date: '2026-07-22',
        hour: 19,
        luzon: 8,
        visayas: 7,
        mindanao: 6,
      },
    ])
    expect(pkg.charts.corridorFlows[0]).toMatchObject({
      leyteLuzonMw: 125,
      leyteLuzonBound: true,
    })
  })

  it('round-trips one case and rejects an unrelated JSON file', () => {
    expect(readCasePackage(casePackageText(run)).id).toBe('case-1')
    expect(() => readCasePackage('{"runs":[]}')).toThrow(/case package/i)
  })
})
