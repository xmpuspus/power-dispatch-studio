// Portfolio and contract valuation: value a generation position against a saved
// run's hourly prices, and split what a bilateral PSA contract captured (or gave
// up) from the uncontracted spot exposure.
//
// A saved run carries PRICE per grid per hour and fuel_gen (MW per fuel per
// grid per hour), not per-unit generation. An analyst's position is defined as
// a share of one fuel's dispatched MW in one grid: {grid, fuel, sharePct}. This
// is a stated approximation, "your share of the fuel's dispatched generation",
// because the public run is per-fuel, not per-unit; it cannot tell you what one
// named plant produced.
//
// The PSA (bilateral power supply agreement) is modeled as a contract for
// differences on a flat volume: the analyst is paid (strike - spot) times the
// contracted MWh, on top of selling everything at spot. That nets out to
// selling the contracted slice at the fixed strike and the rest at spot.

import type { GridKey } from '../lib/types'
import type { ChronoHour } from './chrono'

export interface PortfolioSpec {
  grid: GridKey
  fuel: string
  sharePct: number
  strikePhpKwh: number
  contractMw: number
}

export interface PortfolioValuation {
  genMwh: number
  // PhP thousand: genMwh (MWh) times price (PhP/kWh) is 1,000x PhP
  spotRevenue: number
  cfdSettlement: number
  portfolioRevenue: number
  // the headline: what the bilateral captured over WESM (== cfdSettlement)
  bilateralVsWesmDeltaPhp: number
  // mean realized price as a share of the generation-weighted mean spot price;
  // null when generation is zero or spot averaged to zero
  captureVsSpotPct: number | null
  meanSpotPhpKwh: number
  meanRealizedPhpKwh: number
}

export interface ExposurePoint {
  hourIndex: number
  uncontractedMwh: number
  spot: number
}

const round1 = (x: number): number => Math.round(x * 10) / 10
const round3 = (x: number): number => Math.round(x * 1000) / 1000

function genMwhAt(h: ChronoHour, spec: PortfolioSpec): number {
  const fuelMw = h.fuelGen[spec.grid]?.[spec.fuel] ?? 0
  return fuelMw * (spec.sharePct / 100)
}

/** Value a generation position against a saved run's hours: spot revenue for
 * all generation, the PSA settlement on the contracted slice, and the blended
 * result. Pure. */
export function valuePortfolio(
  hours: ChronoHour[],
  spec: PortfolioSpec
): PortfolioValuation {
  let genMwh = 0
  let spotRevenue = 0
  let cfdSettlement = 0
  for (const h of hours) {
    const gen = genMwhAt(h, spec)
    const price = h.price[spec.grid]
    genMwh += gen
    spotRevenue += gen * price
    const contracted = Math.min(spec.contractMw, gen)
    cfdSettlement += (spec.strikePhpKwh - price) * contracted
  }
  const portfolioRevenue = spotRevenue + cfdSettlement
  // generation-weighted: what the position would have earned selling
  // everything at spot, the same convention insights.capturePrices uses
  const meanSpotPhpKwh = genMwh > 0 ? spotRevenue / genMwh : 0
  const meanRealizedPhpKwh = genMwh > 0 ? portfolioRevenue / genMwh : 0
  const captureVsSpotPct =
    genMwh > 0 && meanSpotPhpKwh !== 0
      ? round1((meanRealizedPhpKwh / meanSpotPhpKwh) * 100)
      : null
  return {
    genMwh: round1(genMwh),
    spotRevenue: Math.round(spotRevenue),
    cfdSettlement: Math.round(cfdSettlement),
    portfolioRevenue: Math.round(portfolioRevenue),
    bilateralVsWesmDeltaPhp: Math.round(cfdSettlement),
    captureVsSpotPct,
    meanSpotPhpKwh: round3(meanSpotPhpKwh),
    meanRealizedPhpKwh: round3(meanRealizedPhpKwh),
  }
}

/** The uncontracted MWh each hour (generation above the contracted volume),
 * paired with that hour's spot price, sorted dearest spot first: an exposure
 * duration curve. Pure. */
export function exposureDurationCurve(
  hours: ChronoHour[],
  spec: PortfolioSpec
): ExposurePoint[] {
  return hours
    .map((h, i) => ({
      hourIndex: i,
      uncontractedMwh: round1(Math.max(0, genMwhAt(h, spec) - spec.contractMw)),
      spot: h.price[spec.grid],
    }))
    .sort((a, b) => b.spot - a.spot)
}
