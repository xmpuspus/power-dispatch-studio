import { describe, expect, it } from 'vitest'
import type { SavedRun } from './runs'
import { buildRunReport } from './report'
import { ENGINE_VERSION, type ChronoHour } from './chrono'

const hour = (h: number): ChronoHour => ({
  hour: h,
  price: { luzon: 6.1, visayas: 7.2, mindanao: 6.5 },
  marginal: { luzon: 'coal', visayas: 'coal', mindanao: 'coal' },
  demand: { luzon: 10000, visayas: 2000, mindanao: 2000 },
  shortfall: { luzon: 0, visayas: 0, mindanao: 0 },
  flowLV: 250,
  flowVM: 100,
  leyte: { sat: true, rent: 1.1 },
  mvip: { sat: false, rent: 0 },
  fuelGen: {
    luzon: { coal: 8000, natural_gas: 2000 },
    visayas: { coal: 2000 },
    mindanao: { coal: 2000 },
  },
  socMwh: 0,
  chargeMw: 0,
  dischargeMw: 0,
})

const run: SavedRun = {
  id: 'r1',
  name: 'DC wave, 2026-06-20',
  savedAt: '2026-07-07T00:00:00.000Z',
  scenarioName: 'DC wave',
  overrides: { 'region:luzon:demand_mw': 12000 },
  date: '2026-06-20',
  span: 'day',
  engineVersion: ENGINE_VERSION,
  hours: Array.from({ length: 24 }, (_, h) => hour(h)),
  summaries: [
    {
      date: '2026-06-20',
      meanPrice: { luzon: 6.1, visayas: 7.2, mindanao: 6.5 },
      peakPrice: { luzon: 9.1, visayas: 10.2, mindanao: 8.5 },
      unservedMwh: { luzon: 0, visayas: 0, mindanao: 0 },
      leyteRentMPhp: 6.6,
      mvipRentMPhp: 0,
    },
  ],
}

describe('buildRunReport', () => {
  const html = buildRunReport(run, {
    emissionsFactors: { coal: 0.874, natural_gas: 0.337 },
    appUrl: 'https://example.test/studio/',
  })
  it('is a self-contained document carrying the run identity', () => {
    expect(html).toContain('<!doctype html>')
    expect(html).toContain('DC wave')
    expect(html).toContain('2026-06-20')
    expect(html).toContain(`engine v${ENGINE_VERSION}`)
    expect(html).not.toContain('<script')
  })
  it('carries the scenario edits, binding tally, emissions, and disclaimer', () => {
    expect(html).toContain('region')
    expect(html).toContain('demand_mw')
    expect(html).toContain('Leyte-Luzon at limit')
    expect(html).toContain('tCO2')
    expect(html).toContain('legitimate explanations')
  })
  it('parses fleet generator edit keys whose ids contain colons', () => {
    const withGen = buildRunReport(
      {
        ...run,
        overrides: { 'generator:luzon:SPI U1:capacity_mw': 0 },
        hours: [],
      },
      {}
    )
    expect(withGen).toContain('<td>generator</td>')
    expect(withGen).toContain('<td>luzon:SPI U1</td>')
    expect(withGen).toContain('<td>capacity_mw</td>')
  })
  it('contains no em-dashes and escapes markup', () => {
    expect(html).not.toContain('—')
    const evil = buildRunReport(
      { ...run, name: '<img src=x onerror=alert(1)>', hours: [] },
      {}
    )
    expect(evil).not.toContain('<img src=x')
    expect(evil).toContain('&lt;img')
  })
})
