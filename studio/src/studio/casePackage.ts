import type { GridKey } from '../lib/types'
import { isSavedRun, type SavedRun } from './runs'

export const CASE_PACKAGE_SCHEMA = 'power-dispatch-case/v1'

interface PricePoint {
  date: string
  hour: number
  luzon: number
  visayas: number
  mindanao: number
}

interface FlowPoint {
  date: string
  hour: number
  leyteLuzonMw: number
  visayasMindanaoMw: number
  leyteLuzonBound: boolean
  mvipBound: boolean
}

export interface CasePackage {
  schema: typeof CASE_PACKAGE_SCHEMA
  exportedAt: string
  run: SavedRun
  charts: {
    hourlyPrices: PricePoint[]
    corridorFlows: FlowPoint[]
  }
}

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

const dateForHour = (run: SavedRun, index: number) =>
  run.summaries[Math.floor(index / 24)]?.date ?? run.date

export function buildCasePackage(
  run: SavedRun,
  exportedAt = new Date().toISOString()
): CasePackage {
  return {
    schema: CASE_PACKAGE_SCHEMA,
    exportedAt,
    run,
    charts: {
      hourlyPrices: run.hours.map((hour, index) => ({
        date: dateForHour(run, index),
        hour: hour.hour,
        ...Object.fromEntries(GRIDS.map((grid) => [grid, hour.price[grid]])),
      })) as PricePoint[],
      corridorFlows: run.hours.map((hour, index) => ({
        date: dateForHour(run, index),
        hour: hour.hour,
        leyteLuzonMw: hour.flowLV,
        visayasMindanaoMw: hour.flowVM,
        leyteLuzonBound: hour.leyte.sat,
        mvipBound: hour.mvip.sat,
      })),
    },
  }
}

export function casePackageText(run: SavedRun): string {
  return JSON.stringify(buildCasePackage(run), null, 2)
}

export function readCasePackage(text: string): SavedRun {
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error('That file is not valid JSON.')
  }
  const record = parsed as { schema?: unknown; run?: unknown } | null
  if (record?.schema !== CASE_PACKAGE_SCHEMA)
    throw new Error('That file is not a Power Dispatch Studio case package.')
  if (!isSavedRun(record.run)) throw new Error('The case package has no valid run.')
  return record.run
}
