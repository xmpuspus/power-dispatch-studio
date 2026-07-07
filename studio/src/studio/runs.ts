// Run management: a Run freezes a chronological solve (scenario snapshot, window,
// engine version, hourly results) so scenarios can be compared later, exported to
// CSV, or shared as a link. Runs live in localStorage; an engine bump flags older
// runs stale instead of silently re-interpreting them.

import type { GridKey } from '../lib/types'
import { ENGINE_VERSION, type ChronoHour, type ChronoSummary } from './chrono'
import type { Overrides } from './model'

export interface SavedRun {
  id: string
  name: string
  savedAt: string // ISO timestamp
  scenarioName: string
  overrides: Overrides
  date: string
  span: 'day' | 'week'
  engineVersion: number
  hours: ChronoHour[]
  summaries: ChronoSummary[]
}

const KEY = 'gridbill-studio-runs-v1'
export const MAX_RUNS = 12

export function loadRuns(): SavedRun[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as { runs?: SavedRun[] }
    return Array.isArray(parsed.runs) ? parsed.runs : []
  } catch {
    return []
  }
}

/** Persist a run; the oldest runs beyond MAX_RUNS are dropped, newest first. */
export function saveRun(run: SavedRun): SavedRun[] {
  const runs = [run, ...loadRuns()].slice(0, MAX_RUNS)
  try {
    localStorage.setItem(KEY, JSON.stringify({ runs }))
  } catch {
    // storage full: drop frozen hours from the oldest half and retry once
    const slim = runs.map((r, i) => (i > runs.length / 2 ? { ...r, hours: [] } : r))
    try {
      localStorage.setItem(KEY, JSON.stringify({ runs: slim }))
    } catch {
      /* leave persistence best-effort */
    }
  }
  return runs
}

export function deleteRun(id: string): SavedRun[] {
  const runs = loadRuns().filter((r) => r.id !== id)
  try {
    localStorage.setItem(KEY, JSON.stringify({ runs }))
  } catch {
    /* best-effort */
  }
  return runs
}

export function isStale(run: SavedRun): boolean {
  return run.engineVersion !== ENGINE_VERSION
}

// ---- CSV export -----------------------------------------------------------------

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

export function runCsv(hours: ChronoHour[], dates: string[]): string {
  const head = [
    'date',
    'hour',
    ...GRIDS.map((g) => `price_${g}_php_kwh`),
    ...GRIDS.map((g) => `demand_${g}_mw`),
    ...GRIDS.map((g) => `shortfall_${g}_mw`),
    'flow_luzon_visayas_mw',
    'flow_visayas_mindanao_mw',
    'leyte_rent_php_kwh',
    'mvip_rent_php_kwh',
    'storage_soc_mwh',
    'storage_charge_mw',
    'storage_discharge_mw',
  ]
  const rows = hours.map((h, i) => [
    dates[Math.floor(i / 24)] ?? '',
    h.hour,
    ...GRIDS.map((g) => h.price[g]),
    ...GRIDS.map((g) => h.demand[g]),
    ...GRIDS.map((g) => h.shortfall[g]),
    h.flowLV,
    h.flowVM,
    h.leyte.sat ? h.leyte.rent : 0,
    h.mvip.sat ? h.mvip.rent : 0,
    h.socMwh,
    h.chargeMw,
    h.dischargeMw,
  ])
  return [head.join(','), ...rows.map((r) => r.join(','))].join('\n')
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ---- share links: the URL is the project file ------------------------------------

export interface SharedState {
  overrides: Overrides
  scenarioName: string
  date?: string
  span?: 'day' | 'week'
}

function b64urlEncode(s: string): string {
  return btoa(unescape(encodeURIComponent(s)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

function b64urlDecode(s: string): string {
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/')
  return decodeURIComponent(escape(atob(b64)))
}

export function encodeShare(state: SharedState): string {
  return `#m=${b64urlEncode(JSON.stringify(state))}`
}

export function decodeShare(hash: string): SharedState | null {
  const m = /#m=([A-Za-z0-9_-]+)/.exec(hash)
  if (!m) return null
  try {
    const parsed = JSON.parse(b64urlDecode(m[1])) as SharedState
    if (!parsed || typeof parsed !== 'object' || typeof parsed.overrides !== 'object')
      return null
    // overrides are numeric property edits only; drop anything else
    const overrides: Overrides = {}
    for (const [k, v] of Object.entries(parsed.overrides))
      if (typeof v === 'number' && Number.isFinite(v)) overrides[k] = v
    return {
      overrides,
      scenarioName:
        typeof parsed.scenarioName === 'string' ? parsed.scenarioName : 'Shared',
      date: typeof parsed.date === 'string' ? parsed.date : undefined,
      span: parsed.span === 'week' ? 'week' : 'day',
    }
  } catch {
    return null
  }
}
