// Forward price scenarios (roadmap item 1): the reason a PH analyst opens PLEXOS.
// Builds a forward price DISTRIBUTION per future year by sampling the observed
// day library, applying the DOE PDP peak-demand growth for that year, and
// drawing joint operating states (hydrology, fuel price, a forced outage)
// through the same day model the studio solves. Never a point forecast: a
// scenario ensemble on observed days, carrying the one-regime label because the
// library spans a single post-suspension quarter.

import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { runChronology } from './chrono'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

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

export interface PdpPath {
  years: number[]
  per_grid_mw: Record<GridKey, number[]>
}

export interface YearBand {
  year: number
  demandGrowthMw: Partial<Record<GridKey, number>>
  perGrid: Record<GridKey, { p10: number; p50: number; p90: number }>
}

function pct(sorted: number[], p: number): number {
  if (!sorted.length) return 0
  const i = Math.min(
    sorted.length - 1,
    Math.max(0, Math.round((p / 100) * (sorted.length - 1)))
  )
  return sorted[i]
}

/** The additive per-grid demand growth (MW) from the base year to a target
 * year, straight off the DOE PDP peak-demand path. */
export function pdpGrowth(
  pdp: PdpPath,
  baseYear: number,
  year: number
): Partial<Record<GridKey, number>> {
  const bi = pdp.years.indexOf(baseYear)
  const yi = pdp.years.indexOf(year)
  if (bi < 0 || yi < 0) return {}
  const out: Partial<Record<GridKey, number>> = {}
  for (const g of GRIDS) {
    const arr = pdp.per_grid_mw[g]
    if (arr) out[g] = Math.round(arr[yi] - arr[bi])
  }
  return out
}

export interface PolicyScenario {
  label: string
  gasBudgetLuzonMwh?: number // Malampaya cliff: a firm gas fuel budget, or none
  carbonPhpPerTco2?: number // carbon price lever, added to each fuel's cost
}

export interface TrajectoryPoint {
  year: number
  median: Record<GridKey, number>
}

const GAS_TCO2 = 0.337 // natural gas emission factor tCO2/MWh (emissions.py)
const COAL_TCO2 = 0.874
const OIL_TCO2 = 0.533

/** A multi-year MEDIAN price trajectory per policy scenario to a long horizon:
 * the same PDP-growth draws as forwardPath, but the median line only, and each
 * scenario also carries a gas fuel budget (the Malampaya cliff) and a carbon
 * price (both fed through the day model). The NDC-pathway and long-PSA view.
 * Composes items 1, 14 (gas budget) and 15 (carbon). Seeded and pure. */
export function multiYearTrajectory(
  d: Dispatch,
  profiles: Profiles,
  pdp: PdpPath,
  baseYear: number,
  years: number[],
  scenario: PolicyScenario,
  drawsPerYear: number,
  seed: number
): TrajectoryPoint[] {
  const marketDays = profiles.days.filter((x) => x.market).map((x) => x.date)
  const c = d.assumptions.fuel_marginal_cost_php_kwh
  const carbon = scenario.carbonPhpPerTco2 ?? 0
  const points: TrajectoryPoint[] = []
  let call = 0
  for (const year of years) {
    const growth = pdpGrowth(pdp, baseYear, year)
    const acc: Record<GridKey, number[]> = { luzon: [], visayas: [], mindanao: [] }
    for (let i = 0; i < drawsPerYear; i++) {
      const r = mulberry32(seed + call++ * 2654435761)
      const date = marketDays[Math.floor(r() * marketDays.length)] ?? marketDays[0]
      const demand: Partial<Record<GridKey, number>> = {}
      for (const g of GRIDS) demand[g] = (growth[g] ?? 0) + Math.round((r() - 0.5) * 400)
      const opts: {
        demand_delta: Partial<Record<GridKey, number>>
        hydrology: number
        fuel_cost: Record<string, number>
        gas_budget?: Partial<Record<GridKey, number>>
      } = {
        demand_delta: demand,
        hydrology: 0.7 + r() * 0.4,
        fuel_cost: {
          coal: c.coal + carbon * (COAL_TCO2 / 1000),
          natural_gas: c.natural_gas + carbon * (GAS_TCO2 / 1000),
          oil: c.oil + carbon * (OIL_TCO2 / 1000),
        },
      }
      if (scenario.gasBudgetLuzonMwh != null)
        opts.gas_budget = { luzon: scenario.gasBudgetLuzonMwh }
      const res = runChronology(d, profiles, date, opts)
      for (const g of GRIDS) acc[g].push(res.summary.meanPrice[g])
    }
    const median = {} as Record<GridKey, number>
    for (const g of GRIDS) {
      const s = [...acc[g]].sort((a, b) => a - b)
      median[g] = Math.round(s[Math.floor(s.length / 2)] * 1000) / 1000
    }
    points.push({ year, median })
  }
  return points
}

/** A forward price band per year: for each year, drawsPerYear scenarios, each a
 * random observed day plus the PDP growth plus joint operating draws, cleared
 * through the day model. Seeded and pure. */
export function forwardPath(
  d: Dispatch,
  profiles: Profiles,
  pdp: PdpPath,
  baseYear: number,
  years: number[],
  drawsPerYear: number,
  seed: number
): YearBand[] {
  const marketDays = profiles.days.filter((x) => x.market).map((x) => x.date)
  const coalBase = d.assumptions.fuel_marginal_cost_php_kwh.coal
  const bands: YearBand[] = []
  let call = 0
  for (const year of years) {
    const growth = pdpGrowth(pdp, baseYear, year)
    const acc: Record<GridKey, number[]> = { luzon: [], visayas: [], mindanao: [] }
    for (let i = 0; i < drawsPerYear; i++) {
      const r = mulberry32(seed + call++ * 2654435761)
      const date = marketDays[Math.floor(r() * marketDays.length)] ?? marketDays[0]
      const demand: Partial<Record<GridKey, number>> = {}
      for (const g of GRIDS) demand[g] = (growth[g] ?? 0) + Math.round((r() - 0.5) * 400)
      const opts = {
        demand_delta: demand,
        hydrology: 0.6 + r() * 0.55,
        fuel_cost: { coal: coalBase + (r() - 0.5) * 4 },
        fuel_avail_delta: { luzon: { coal: -Math.round(r() * 700) } },
      }
      const res = runChronology(d, profiles, date, opts)
      for (const g of GRIDS) acc[g].push(res.summary.meanPrice[g])
    }
    const perGrid = {} as Record<GridKey, { p10: number; p50: number; p90: number }>
    for (const g of GRIDS) {
      const s = [...acc[g]].sort((a, b) => a - b)
      perGrid[g] = {
        p10: Math.round(pct(s, 10) * 1000) / 1000,
        p50: Math.round(pct(s, 50) * 1000) / 1000,
        p90: Math.round(pct(s, 90) * 1000) / 1000,
      }
    }
    bands.push({ year, demandGrowthMw: growth, perGrid })
  }
  return bands
}
