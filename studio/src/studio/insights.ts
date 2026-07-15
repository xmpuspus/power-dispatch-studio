// Derived analytics over solved results: what set the price each hour, percentile
// bands across replayed days, and per-run CO2 when emission factors are baked.
// Pure functions over engine outputs; nothing here touches the parity engines.

import type { GridKey, ProjectRow } from '../lib/types'
import type { ChronoHour, ChronoResult } from './chrono'

// ---- binding-constraint classification -------------------------------------------

export interface HourBinding {
  cause: 'unserved' | 'corridor' | 'fuel'
  // the marginal fuel for 'fuel', the feeding corridor for 'corridor'
  detail: string
}

/** Which constraint set this grid's price in this hour: unserved load, a saturated
 * corridor on the importing side, or the marginal fuel block. */
export function classifyHour(h: ChronoHour, grid: GridKey): HourBinding {
  if (h.shortfall[grid] > 0) return { cause: 'unserved', detail: 'unserved load' }
  const importsLeyte =
    (grid === 'visayas' && h.leyte.sat && h.flowLV > 0) ||
    (grid === 'luzon' && h.leyte.sat && h.flowLV < 0)
  if (importsLeyte) return { cause: 'corridor', detail: 'Leyte-Luzon at limit' }
  const importsMvip =
    (grid === 'mindanao' && h.mvip.sat && h.flowVM > 0) ||
    (grid === 'visayas' && h.mvip.sat && h.flowVM < 0)
  if (importsMvip) return { cause: 'corridor', detail: 'MVIP at limit' }
  return { cause: 'fuel', detail: h.marginal[grid] ?? 'none' }
}

export interface BindingCount {
  key: string
  cause: HourBinding['cause']
  label: string
  hours: number
  share_pct: number
}

/** Tally of price-setting causes over a run window, largest first. */
export function bindingCounts(hours: ChronoHour[], grid: GridKey): BindingCount[] {
  const tally = new Map<string, { cause: HourBinding['cause']; n: number }>()
  for (const h of hours) {
    const b = classifyHour(h, grid)
    const key = b.detail
    const cur = tally.get(key)
    if (cur) cur.n += 1
    else tally.set(key, { cause: b.cause, n: 1 })
  }
  const n = hours.length || 1
  return [...tally.entries()]
    .map(([key, v]) => ({
      key,
      cause: v.cause,
      label: key.replace(/_/g, ' '),
      hours: v.n,
      share_pct: Math.round((1000 * v.n) / n) / 10,
    }))
    .sort((a, b) => b.hours - a.hours)
}

// ---- percentile bands across replayed days ----------------------------------------

/** Linear-interpolated percentile of an unsorted sample; p in [0, 100]. */
export function percentile(values: number[], p: number): number {
  if (!values.length) return NaN
  const s = [...values].sort((a, b) => a - b)
  const idx = (Math.min(100, Math.max(0, p)) / 100) * (s.length - 1)
  const lo = Math.floor(idx)
  const hi = Math.ceil(idx)
  return lo === hi ? s[lo] : s[lo] + (s[hi] - s[lo]) * (idx - lo)
}

export interface HourBand {
  p10: number
  p50: number
  p90: number
}

/** Per-hour price percentiles across a set of replayed days, one grid. */
export function hourlyBand(runs: ChronoResult[], grid: GridKey): HourBand[] {
  const H = 24
  const out: HourBand[] = []
  for (let h = 0; h < H; h++) {
    const sample = runs.map((r) => r.hours[h].price[grid])
    out.push({
      p10: percentile(sample, 10),
      p50: percentile(sample, 50),
      p90: percentile(sample, 90),
    })
  }
  return out
}

export interface WindowStats {
  days: number
  p10: number
  p50: number
  p90: number
  max: number
  maxDate: string
}

/** Distribution of the DAILY MEAN price across replayed days, one grid. */
export function windowStats(runs: ChronoResult[], grid: GridKey): WindowStats {
  const means = runs.map((r) => r.summary.meanPrice[grid])
  let maxDate = ''
  let max = -Infinity
  for (const r of runs)
    if (r.summary.meanPrice[grid] > max) {
      max = r.summary.meanPrice[grid]
      maxDate = r.summary.date
    }
  return {
    days: runs.length,
    p10: percentile(means, 10),
    p50: percentile(means, 50),
    p90: percentile(means, 90),
    max,
    maxDate,
  }
}

/** Every hourly price of every replayed day, sorted dear to cheap, as duration
 * points (pct of window). The scenario's own price-duration curve. */
export function pooledDuration(
  runs: ChronoResult[],
  grid: GridKey
): { pct: number; price: number }[] {
  const s = runs.flatMap((r) => r.hours.map((h) => h.price[grid]))
  s.sort((a, b) => b - a)
  const n = s.length
  return s.map((price, i) => ({ pct: n > 1 ? (100 * i) / (n - 1) : 0, price }))
}

// ---- LT Plan horizon math ----------------------------------------------------------

export interface GridFuelAdd {
  grid: GridKey
  fuel: string
  mw: number
}

/** Sum the DOE build pipeline into per-grid per-fuel MW landing on or before a
 * horizon year. Rows with no stated date go to the unscheduled bucket, never
 * into a horizon; ESS rows stay out (the DOE tracks them separately). */
export function addsAtHorizon(
  rows: ProjectRow[],
  year: number,
  includeIndicative: boolean
): { adds: GridFuelAdd[]; unscheduledMw: number } {
  const sums = new Map<string, number>()
  let unscheduled = 0
  for (const r of rows) {
    if (r.status === 'indicative' && !includeIndicative) continue
    if (r.fuel === 'storage') continue
    if (r.target_year == null) {
      unscheduled += r.mw
      continue
    }
    if (r.target_year > year) continue
    const k = `${r.grid}:${r.fuel}`
    sums.set(k, (sums.get(k) ?? 0) + r.mw)
  }
  const adds: GridFuelAdd[] = [...sums.entries()]
    .map(([k, mw]) => {
      const [grid, fuel] = k.split(':')
      return { grid: grid as GridKey, fuel, mw: Math.round(mw * 10) / 10 }
    })
    .sort((a, b) => b.mw - a.mw)
  return { adds, unscheduledMw: Math.round(unscheduled) }
}

// ---- emissions (factors are baked constants with sources; see emissions.json) -----

/** Window CO2 in tonnes for one grid (or all grids) from dispatched energy per
 * fuel. Hourly MW over one hour is MWh; storage discharge carries no factor of
 * its own (its charging energy was already counted at the generating fuel). */
export function runEmissionsT(
  hours: ChronoHour[],
  factors: Record<string, number>,
  grid?: GridKey
): number {
  const grids: GridKey[] = grid ? [grid] : ['luzon', 'visayas', 'mindanao']
  let t = 0
  for (const h of hours)
    for (const g of grids)
      for (const [fuel, mw] of Object.entries(h.fuelGen[g]))
        t += mw * (factors[fuel] ?? 0)
  return Math.round(t)
}

/** Per-fuel CO2 tonnes over a window, all grids, largest first. */
export function emissionsByFuel(
  hours: ChronoHour[],
  factors: Record<string, number>
): { fuel: string; tco2: number; mwh: number }[] {
  const energy = new Map<string, number>()
  for (const h of hours)
    for (const g of ['luzon', 'visayas', 'mindanao'] as GridKey[])
      for (const [fuel, mw] of Object.entries(h.fuelGen[g]))
        energy.set(fuel, (energy.get(fuel) ?? 0) + mw)
  return [...energy.entries()]
    .map(([fuel, mwh]) => ({
      fuel,
      mwh: Math.round(mwh),
      tco2: Math.round(mwh * (factors[fuel] ?? 0)),
    }))
    .sort((a, b) => b.tco2 - a.tco2 || b.mwh - a.mwh)
}

// ---- capture prices: generation-weighted average price per technology -----------

export interface CaptureRow {
  fuel: string
  grid: GridKey
  gen_mwh: number
  capture_price_php_kwh: number
  // capture price divided by the run's time-average price on the same grid;
  // null when that average is zero (nothing to divide by)
  capture_rate: number | null
}

/** Generation-weighted capture price per fuel per grid over a run's hours:
 * sum(generation x price) / sum(generation), each grid's own price. The
 * revenue signal a GEA or project analyst needs: a flat PPA misses the
 * merit-order effect solar and wind create for themselves as they clear. */
export function capturePrices(hours: ChronoHour[]): CaptureRow[] {
  const grids: GridKey[] = ['luzon', 'visayas', 'mindanao']
  const genPriceSum = new Map<string, number>()
  const genSum = new Map<string, number>()
  const priceSum: Record<GridKey, number> = { luzon: 0, visayas: 0, mindanao: 0 }
  for (const h of hours) {
    for (const g of grids) {
      priceSum[g] += h.price[g]
      for (const [fuel, mw] of Object.entries(h.fuelGen[g])) {
        const k = `${fuel}|${g}`
        genPriceSum.set(k, (genPriceSum.get(k) ?? 0) + mw * h.price[g])
        genSum.set(k, (genSum.get(k) ?? 0) + mw)
      }
    }
  }
  const n = hours.length || 1
  const avgPrice: Record<GridKey, number> = {
    luzon: priceSum.luzon / n,
    visayas: priceSum.visayas / n,
    mindanao: priceSum.mindanao / n,
  }
  const rows: CaptureRow[] = []
  for (const [k, gen] of genSum) {
    if (gen <= 0) continue
    const [fuel, grid] = k.split('|') as [string, GridKey]
    const capturePrice = (genPriceSum.get(k) ?? 0) / gen
    const ap = avgPrice[grid]
    rows.push({
      fuel,
      grid,
      gen_mwh: Math.round(gen),
      capture_price_php_kwh: Math.round(capturePrice * 1000) / 1000,
      capture_rate: ap > 0 ? Math.round((capturePrice / ap) * 1000) / 1000 : null,
    })
  }
  return rows.sort((a, b) => b.gen_mwh - a.gen_mwh)
}
