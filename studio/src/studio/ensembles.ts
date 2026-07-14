// Scenario ensembles (roadmap item 5): a seeded Monte Carlo of joint draws
// (data-center load growth, hydrology, fuel price, a forced outage) pushed
// through the SAME day chronology the studio already solves, surfacing a price
// distribution per grid instead of a single point. Seeded, so a re-run gives
// the identical ensemble, and synchronous like the window band (the 66-day band
// already proves the solve budget is there).

import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { runChronology } from './chrono'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

/** Deterministic PRNG (mulberry32): the same seed gives the same draws, so an
 * ensemble is reproducible and testable. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export interface DrawRanges {
  demandGrowthMw: number // max data-center load added to Luzon (uniform 0..this)
  hydrologyLo: number // hydrology multiplier drawn uniform [lo, hi]
  hydrologyHi: number
  coalPriceSpread: number // coal price drawn uniform base +/- this (PhP/kWh)
  outageMw: number // a forced coal outage on Luzon drawn uniform 0..this
}

export const DEFAULT_RANGES: DrawRanges = {
  demandGrowthMw: 1500, // the DICT 1.5 GW wave as the upper draw
  hydrologyLo: 0.6,
  hydrologyHi: 1.15,
  coalPriceSpread: 2,
  outageMw: 700, // about one large coal unit
}

export interface GridDist {
  p10: number
  p50: number
  p90: number
  mean: number
}

export interface EnsembleResult {
  nDraws: number
  seed: number
  date: string
  perGrid: Record<GridKey, GridDist>
  prices: Record<GridKey, number[]> // sorted ascending, for a histogram/CDF
}

function pct(sorted: number[], p: number): number {
  if (!sorted.length) return 0
  const i = Math.min(
    sorted.length - 1,
    Math.max(0, Math.round((p / 100) * (sorted.length - 1)))
  )
  return sorted[i]
}

/** Run nDraws joint-draw chronologies on one observed day and return the price
 * distribution per grid. Pure given (d, profiles, date, nDraws, seed). */
export function runEnsemble(
  d: Dispatch,
  profiles: Profiles,
  date: string,
  nDraws: number,
  seed: number,
  ranges: DrawRanges = DEFAULT_RANGES
): EnsembleResult {
  const coalBase = d.assumptions.fuel_marginal_cost_php_kwh.coal
  const acc: Record<GridKey, number[]> = { luzon: [], visayas: [], mindanao: [] }
  for (let i = 0; i < nDraws; i++) {
    const r = mulberry32(seed + i * 2654435761)
    const opts = {
      demand_delta: { luzon: Math.round(r() * ranges.demandGrowthMw) },
      hydrology: ranges.hydrologyLo + r() * (ranges.hydrologyHi - ranges.hydrologyLo),
      fuel_cost: { coal: coalBase + (r() - 0.5) * 2 * ranges.coalPriceSpread },
      fuel_avail_delta: { luzon: { coal: -Math.round(r() * ranges.outageMw) } },
    }
    const res = runChronology(d, profiles, date, opts)
    for (const g of GRIDS) acc[g].push(res.summary.meanPrice[g])
  }
  const perGrid = {} as Record<GridKey, GridDist>
  const prices = {} as Record<GridKey, number[]>
  for (const g of GRIDS) {
    const sorted = [...acc[g]].sort((a, b) => a - b)
    prices[g] = sorted
    perGrid[g] = {
      p10: Math.round(pct(sorted, 10) * 1000) / 1000,
      p50: Math.round(pct(sorted, 50) * 1000) / 1000,
      p90: Math.round(pct(sorted, 90) * 1000) / 1000,
      mean:
        Math.round((sorted.reduce((s, x) => s + x, 0) / (sorted.length || 1)) * 1000) /
        1000,
    }
  }
  return { nDraws, seed, date, perGrid, prices }
}
