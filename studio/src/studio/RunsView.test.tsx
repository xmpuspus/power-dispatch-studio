import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { GridKey } from '../lib/types'
import { RunsView } from './RunsView'
import type { ChronoHour, ChronoSummary } from './chrono'
import type { SavedRun } from './runs'

const grids = <T,>(luzon: T, visayas: T, mindanao: T): Record<GridKey, T> => ({
  luzon,
  visayas,
  mindanao,
})

const run = (id: string, visayasPrice: number): SavedRun => {
  const hour: ChronoHour = {
    hour: 19,
    price: grids(6, visayasPrice, 6),
    marginal: grids('coal', visayasPrice > 6 ? 'unserved load' : 'coal', 'coal'),
    demand: grids(12_000, 2_500, 2_400),
    shortfall: grids(0, visayasPrice > 6 ? 1_000 : 0, 0),
    flowLV: 0,
    flowVM: 0,
    leyte: { sat: false, rent: 0 },
    mvip: { sat: false, rent: 0 },
    fuelGen: grids({ coal: 12_000 }, { coal: 1_500 }, { coal: 2_400 }),
    socMwh: 0,
    chargeMw: 0,
    dischargeMw: 0,
  }
  const summary: ChronoSummary = {
    date: '2026-07-22',
    meanPrice: hour.price,
    peakPrice: hour.price,
    unservedMwh: hour.shortfall,
    leyteRentMPhp: 0,
    mvipRentMPhp: 0,
  }
  return {
    id,
    name: id === 'base' ? 'Base Case' : 'Visayas stress test',
    savedAt: '2026-08-13T10:00:00.000Z',
    scenarioName: id === 'base' ? 'Base Case' : 'Visayas stress test',
    overrides: id === 'base' ? {} : { 'region:visayas:demand_mw': 6_345 },
    date: '2026-07-22',
    span: 'day',
    engineVersion: 3,
    hours: [hour],
    summaries: [summary],
  }
}

describe('RunsView', () => {
  it('charts the grid with the largest mean-price change by default', () => {
    const html = renderToStaticMarkup(
      <RunsView
        runs={[run('base', 6), run('stress', 32)]}
        onRunsChange={() => undefined}
        onRestore={() => undefined}
        onOpenReplay={() => undefined}
      />
    )

    expect(html).toContain('Hourly price chart')
    expect(html).toContain('A: Visayas')
    expect(html).toContain('B: Visayas')
    expect(html).not.toContain('A: Luzon')
  })
})
