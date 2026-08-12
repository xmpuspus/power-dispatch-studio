import type { GridKey } from '../lib/types'
import type { ChronoHour } from '../studio/chrono'

export type MarketStripItem = {
  hour: number
  recordedPrice: number | null
  replayedPrice: number
  demandMw: number
  shortfallMw: number
  constraint: boolean
  marginal: string | null
}

export function buildMarketStrip(
  hours: ChronoHour[],
  recordedPrice: (number | null)[],
  grid: GridKey
): MarketStripItem[] {
  return hours.map((row) => ({
    hour: row.hour,
    recordedPrice: recordedPrice[row.hour] ?? null,
    replayedPrice: row.price[grid],
    demandMw: row.demand[grid],
    shortfallMw: row.shortfall[grid],
    constraint:
      grid === 'luzon'
        ? row.leyte.sat
        : grid === 'mindanao'
          ? row.mvip.sat
          : row.leyte.sat || row.mvip.sat,
    marginal: row.marginal[grid],
  }))
}
