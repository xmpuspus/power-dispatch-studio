import { describe, expect, it } from 'vitest'
import type { GridKey } from '../lib/types'
import type { ChronoHour, ChronoSummary } from './chrono'
import { compareRuns } from './runComparison'
import type { SavedRun } from './runs'

const grids = <T>(luzon: T, visayas: T, mindanao: T): Record<GridKey, T> => ({
  luzon,
  visayas,
  mindanao,
})

function makeRun(id: string, price: number, shortfall: number, bound: boolean): SavedRun {
  const summary: ChronoSummary = {
    date: '2026-07-22',
    meanPrice: grids(6, price, 6),
    peakPrice: grids(7, price + 2, 7),
    unservedMwh: grids(0, shortfall, 0),
    leyteRentMPhp: bound ? 4.2 : 0,
    mvipRentMPhp: 0,
  }
  const hour: ChronoHour = {
    hour: 19,
    price: summary.meanPrice,
    marginal: grids('coal', bound ? 'unserved load' : 'coal', 'coal'),
    demand: grids(12_000, 2_500, 2_400),
    shortfall: summary.unservedMwh,
    flowLV: bound ? 125 : 10,
    flowVM: 0,
    leyte: { sat: bound, rent: bound ? 2 : 0 },
    mvip: { sat: false, rent: 0 },
    fuelGen: grids({}, {}, {}),
    socMwh: 0,
    chargeMw: 0,
    dischargeMw: 0,
  }
  return {
    id,
    name: id === 'base' ? 'Base replay' : 'Visayas stress test',
    savedAt: id === 'base' ? '2026-08-12T00:00:00Z' : '2026-08-13T00:00:00Z',
    scenarioName: id === 'base' ? 'Base Case' : 'Visayas +4,000 MW stress test',
    overrides: id === 'base' ? {} : { 'region:visayas:demand_mw': 6500 },
    assumptions:
      id === 'base'
        ? []
        : [
            {
              key: 'region:visayas:demand_mw',
              text: 'Visayas modeled load 6,500 MW (+4,000 MW)',
            },
          ],
    date: '2026-07-22',
    span: 'day',
    engineVersion: 3,
    hours: [hour],
    summaries: [summary],
  }
}

describe('run comparison summary', () => {
  it('states the change, most affected grid, price move, unserved energy, and binding link', () => {
    const summary = compareRuns(
      makeRun('base', 6, 0, false),
      makeRun('stress', 32, 1000, true)
    )
    expect(summary.assumptionChanges).toContain(
      'Visayas modeled load 6,500 MW (+4,000 MW)'
    )
    expect(summary.mostAffectedGrid).toBe('visayas')
    expect(summary.meanPriceChange).toBe(26)
    expect(summary.unservedMwhChange).toBe(1000)
    expect(summary.boundCorridors).toEqual(['Leyte-Luzon'])
    expect(summary.text).toContain('Visayas')
    expect(summary.text).toContain('+₱26.00/kWh')
    expect(summary.text).toContain('1,000 MWh')
    expect(summary.text).toContain('Leyte-Luzon reached its limit')
  })

  it('uses plural wording when both corridors bind', () => {
    const changed = makeRun('stress', 32, 1000, true)
    changed.hours[0].mvip.sat = true

    expect(compareRuns(makeRun('base', 6, 0, false), changed).text).toContain(
      'Leyte-Luzon and MVIP reached their limits'
    )
  })
})
