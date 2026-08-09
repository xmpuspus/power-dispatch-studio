// Settle a contract book against the modeled spot price.
//
// The TypeScript twin of src/power_dispatch/contracts.py, and the two carry the
// same arithmetic on purpose: a supplier who marks a scenario in the browser and
// then re-runs it in a notebook has to read the same pesos. contracts.test.ts
// checks the browser against worked numbers, and tests/test_contracts.py checks
// Python against the same ones.

import type { GridKey } from '../lib/types'
import type { ChronoHour } from './chrono'

export const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

export interface Contract {
  name?: string
  grid: GridKey
  mw: number
  strike_php_kwh: number
  /** buy fixes what the holder pays, sell fixes what the holder receives */
  side?: 'buy' | 'sell'
  /** hours the contract covers, 0 to 23. Absent means the whole day */
  hours?: number[]
}

export interface SettledContract {
  name: string
  grid: GridKey
  mw: number
  strike: number
  side: 'buy' | 'sell'
  hoursCovered: number
  mwh: number
  spotValue: number
  strikeValue: number
  position: number
  meanSpot: number
}

export interface OpenRow {
  grid: GridKey
  loadMw: number
  openMwh: number
  openCost: number
  coveredPct: number
}

export interface Settlement {
  contracts: SettledContract[]
  position: number
  open: OpenRow[]
  openCost: number
}

/** Every problem with a book, as messages a person can act on. */
export function validateBook(book: Contract[]): string[] {
  const e: string[] = []
  book.forEach((c, i) => {
    if (!GRIDS.includes(c.grid)) e.push(`Contract ${i + 1} needs a grid.`)
    if (!Number.isFinite(c.mw) || c.mw < 0)
      e.push(`Contract ${i + 1} needs volume in MW, and it cannot be negative.`)
    if (!Number.isFinite(c.strike_php_kwh))
      e.push(`Contract ${i + 1} needs a strike price in PhP/kWh.`)
    if (c.hours && c.hours.some((h) => h < 0 || h > 23))
      e.push(`Contract ${i + 1} names an hour outside 0 to 23.`)
  })
  return e
}

/**
 * Mark a book against one solved day.
 *
 * One MW held for one hour is one MWh, and a price in PhP/kWh is a thousand
 * pesos per MWh, so one contract-hour is worth mw * 1000 * price.
 */
export function settle(
  hours: ChronoHour[],
  book: Contract[],
  loadMw: Partial<Record<GridKey, number>> = {}
): Settlement {
  const n = hours.length
  const rows: SettledContract[] = book.map((c) => {
    const cover = (c.hours ?? Array.from({ length: n }, (_, i) => i)).filter((h) => h < n)
    const side = c.side ?? 'buy'
    const sign = side === 'buy' ? 1 : -1
    const spot = cover.reduce((s, h) => s + hours[h].price[c.grid] * c.mw * 1000, 0)
    const strike = c.strike_php_kwh * c.mw * 1000 * cover.length
    return {
      name: c.name || `${c.grid} ${c.mw} MW at P${c.strike_php_kwh}`,
      grid: c.grid,
      mw: c.mw,
      strike: c.strike_php_kwh,
      side,
      hoursCovered: cover.length,
      mwh: c.mw * cover.length,
      spotValue: spot,
      strikeValue: strike,
      position: sign * (spot - strike),
      meanSpot: cover.length
        ? cover.reduce((s, h) => s + hours[h].price[c.grid], 0) / cover.length
        : 0,
    }
  })

  // only a buy contract covers a load. A sell contract is a separate position.
  const covered: Record<string, number[]> = {}
  for (const g of GRIDS) covered[g] = new Array(n).fill(0)
  book.forEach((c) => {
    if ((c.side ?? 'buy') !== 'buy') return
    for (const h of c.hours ?? Array.from({ length: n }, (_, i) => i))
      if (h < n) covered[c.grid][h] += c.mw
  })

  const open: OpenRow[] = []
  for (const g of GRIDS) {
    const mw = loadMw[g]
    if (!mw) continue
    let mwh = 0
    let cost = 0
    for (let h = 0; h < n; h++) {
      const gap = Math.max(0, mw - covered[g][h])
      mwh += gap
      cost += gap * 1000 * hours[h].price[g]
    }
    open.push({
      grid: g,
      loadMw: mw,
      openMwh: mwh,
      openCost: cost,
      coveredPct: n ? 100 * (1 - mwh / (mw * n)) : 0,
    })
  }

  return {
    contracts: rows,
    position: rows.reduce((s, r) => s + r.position, 0),
    open,
    openCost: open.reduce((s, r) => s + r.openCost, 0),
  }
}

export interface PositionChange {
  base: Settlement
  scenario: Settlement
  positionChange: number
  openCostChange: number
  netChange: number
}

/** What one scenario does to the position, which is the question people ask. */
export function comparePosition(
  baseHours: ChronoHour[],
  scenarioHours: ChronoHour[],
  book: Contract[],
  loadMw: Partial<Record<GridKey, number>> = {}
): PositionChange {
  const base = settle(baseHours, book, loadMw)
  const scenario = settle(scenarioHours, book, loadMw)
  const positionChange = scenario.position - base.position
  const openCostChange = scenario.openCost - base.openCost
  return {
    base,
    scenario,
    positionChange,
    openCostChange,
    netChange: positionChange - openCostChange,
  }
}

/** A starting book, so the view opens on something a reader can change. */
export const SAMPLE_BOOK: Contract[] = [
  {
    name: 'Power supply agreement',
    grid: 'luzon',
    mw: 250,
    strike_php_kwh: 6.4,
    side: 'buy',
  },
  {
    name: 'Evening peak block',
    grid: 'luzon',
    mw: 100,
    strike_php_kwh: 9.0,
    side: 'buy',
    hours: [18, 19, 20, 21],
  },
]
