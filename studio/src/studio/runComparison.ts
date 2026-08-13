import type { GridKey } from '../lib/types'
import type { ActiveAssumption } from './resultContext'
import type { SavedRun } from './runs'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (value: string) => value[0].toUpperCase() + value.slice(1)

function meanOf(run: SavedRun, grid: GridKey) {
  return (
    run.summaries.reduce((sum, item) => sum + item.meanPrice[grid], 0) /
    run.summaries.length
  )
}

function unservedOf(run: SavedRun) {
  return run.summaries.reduce(
    (sum, item) =>
      sum + GRIDS.reduce((gridSum, grid) => gridSum + item.unservedMwh[grid], 0),
    0
  )
}

const assumptionList = (run: SavedRun): ActiveAssumption[] =>
  run.assumptions ??
  Object.keys(run.overrides).map((key) => ({
    key,
    text: key.replace(/:/g, ' '),
  }))

export interface RunComparisonSummary {
  assumptionChanges: string[]
  mostAffectedGrid: GridKey
  meanPriceChange: number
  unservedMwhChange: number
  boundCorridors: string[]
  text: string
}

export function compareRuns(a: SavedRun, b: SavedRun): RunComparisonSummary {
  const baseAssumptions = new Map(assumptionList(a).map((item) => [item.key, item.text]))
  const assumptionChanges = assumptionList(b)
    .filter((item) => baseAssumptions.get(item.key) !== item.text)
    .map((item) => item.text)
  const mostAffectedGrid = GRIDS.reduce((largest, grid) =>
    Math.abs(meanOf(b, grid) - meanOf(a, grid)) >
    Math.abs(meanOf(b, largest) - meanOf(a, largest))
      ? grid
      : largest
  )
  const meanPriceChange = meanOf(b, mostAffectedGrid) - meanOf(a, mostAffectedGrid)
  const unservedMwhChange = unservedOf(b) - unservedOf(a)
  const boundCorridors = [
    b.hours.some((hour) => hour.leyte.sat) ? 'Leyte-Luzon' : null,
    b.hours.some((hour) => hour.mvip.sat) ? 'MVIP' : null,
  ].filter((value): value is string => value !== null)
  const price = `${meanPriceChange >= 0 ? '+' : '-'}₱${Math.abs(meanPriceChange).toFixed(2)}/kWh`
  const energy = `${unservedMwhChange >= 0 ? '+' : '-'}${Math.abs(unservedMwhChange).toLocaleString('en-US', { maximumFractionDigits: 1 })} MWh`
  const links = boundCorridors.length
    ? boundCorridors.length === 1
      ? `${boundCorridors[0]} reached its limit.`
      : `${boundCorridors.join(' and ')} reached their limits.`
    : 'Neither corridor reached its limit.'
  const changed = assumptionChanges.length
    ? assumptionChanges.join('; ')
    : 'No active assumption changed.'
  return {
    assumptionChanges,
    mostAffectedGrid,
    meanPriceChange,
    unservedMwhChange,
    boundCorridors,
    text: `${changed} ${cap(mostAffectedGrid)} had the largest mean-price change at ${price}. Unserved energy changed by ${energy}. ${links}`,
  }
}
