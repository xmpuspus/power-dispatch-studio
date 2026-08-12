// The one scenario file, read and written by the browser.
//
// The command line already took {"date", "opts"} and the studio kept its edits
// in a URL hash, so a scenario dragged out of a slider could not re-run in
// Python. This module maps between the two: chronoOptsFrom already produces the
// engine's option map, and fromScenarioFile turns that map back into the object
// edits the studio displays.
//
// The same schema module in src/power_dispatch/schema.py validates the file on
// the Python side, and tests/fixtures/scenario_example.json is the one fixture
// both round-trip tests read.

import type { GridKey } from '../lib/types'
import { GRID_KEYS } from './engine'
import {
  chronoOptsFrom,
  overrideKey,
  type ClassId,
  type ObjRow,
  type Overrides,
} from './model'
import type { ChronoOpts } from './chrono'

export const SCENARIO_SCHEMA = 'pds-scenario/1'

export interface ScenarioFile {
  schema: string
  name?: string
  date: string
  opts: ChronoOpts
  meta?: Record<string, unknown>
}

export interface LoadResult {
  name: string
  date: string
  overrides: Overrides
  /** what the file asked for and the studio's object model cannot hold */
  warnings: string[]
}

type Objects = Record<ClassId, ObjRow[]>

const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

/** Build the file from the current scenario. `opts` is the engine's own map. */
export function toScenarioFile(
  name: string,
  date: string,
  objects: Objects,
  overrides: Overrides,
  meta?: Record<string, unknown>
): ScenarioFile {
  const opts = chronoOptsFrom(objects, overrides)
  // the offer book is a whole day of data, never a scenario setting
  delete (opts as { offer_day?: unknown }).offer_day
  // name each battery. Two rows can sit on one grid, so a file that carries
  // only {grid, power_mw, energy_mwh} cannot say which row it meant, and a
  // round trip through the studio would move a value onto the wrong battery.
  if (opts.storage?.length) {
    const left = objects.storage.slice()
    opts.storage = opts.storage.map((s) => {
      const i = left.findIndex(
        (r) =>
          r.grid === s.grid &&
          effOf(overrides, r, 'power_mw') === s.power_mw &&
          effOf(overrides, r, 'energy_mwh') === s.energy_mwh
      )
      const row = i >= 0 ? left.splice(i, 1)[0] : undefined
      return row ? { id: row.id, ...s } : s
    })
  }
  return {
    schema: SCENARIO_SCHEMA,
    name,
    date,
    opts,
    meta: {
      written_by: 'Power Dispatch Studio',
      ...meta,
    },
  }
}

export function scenarioFileText(f: ScenarioFile): string {
  return JSON.stringify(f, null, 2)
}

/** The value a property carries right now: the override, else the base. */
function effOf(ov: Overrides, row: ObjRow, prop: string): number {
  const k = overrideKey(row.cls, row.id, prop)
  const base = row.props[prop]
  return k in ov ? ov[k] : num(base) ? base : 0
}

function baseOf(rows: ObjRow[], id: string, prop: string): number | null {
  const r = rows.find((x) => x.id === id)
  const v = r?.props[prop]
  return num(v) ? v : null
}

/**
 * Turn a scenario file back into object edits.
 *
 * Every option that maps onto an editable property becomes an absolute value on
 * that property, because that is what the studio's tables hold. An option the
 * object model cannot express comes back as a warning rather than a silent drop:
 * a reader who loads a file has to know which half of it took effect.
 */
export function fromScenarioFile(raw: unknown, objects: Objects): LoadResult {
  const warnings: string[] = []
  const overrides: Overrides = {}
  const f = raw as Partial<ScenarioFile>
  if (!f || typeof f !== 'object') throw new Error('That file is not a scenario.')
  if (f.schema && f.schema !== SCENARIO_SCHEMA)
    warnings.push(
      `File says schema ${f.schema}, and this build reads ${SCENARIO_SCHEMA}.`
    )
  if (typeof f.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(f.date))
    throw new Error('That file has no date shaped YYYY-MM-DD.')
  const opts = (f.opts ?? {}) as ChronoOpts

  for (const g of GRID_KEYS) {
    const d = opts.demand_delta?.[g]
    if (d == null) continue
    if (Array.isArray(d)) {
      warnings.push(
        `${g} demand carries an hourly shape. The studio holds one flat number, so it took the mean.`
      )
    }
    const flat = Array.isArray(d) ? d.reduce((s, v) => s + v, 0) / d.length : d
    const base = baseOf(objects.region, g, 'demand_mw')
    if (base != null) overrides[overrideKey('region', g, 'demand_mw')] = base + flat
  }

  for (const [fuel, cost] of Object.entries(opts.fuel_cost ?? {})) {
    if (baseOf(objects.fuel, fuel, 'cost') == null) {
      warnings.push(`No fuel named ${fuel} in this build, so its price was skipped.`)
      continue
    }
    overrides[overrideKey('fuel', fuel, 'cost')] = cost
  }

  for (const g of GRID_KEYS) {
    for (const [fuel, delta] of Object.entries(opts.fuel_avail_delta?.[g] ?? {})) {
      const prop = `${g}_mw`
      const base = baseOf(objects.fuel, fuel, prop)
      if (base == null) {
        warnings.push(`No fuel named ${fuel} in this build, so its ${g} MW was skipped.`)
        continue
      }
      overrides[overrideKey('fuel', fuel, prop)] = base + delta
    }
    const solar = opts.solar_delta_mw?.[g]
    if (solar != null) {
      const base = baseOf(objects.fuel, 'solar', `${g}_mw`)
      if (base != null) overrides[overrideKey('fuel', 'solar', `${g}_mw`)] = base + solar
      else
        warnings.push(`This build has no solar row, so the ${g} solar edit was skipped.`)
    }
  }

  const CAPS: Record<string, string> = {
    leyte: 'leyte_luzon_hvdc',
    mvip: 'mvip_hvdc',
  }
  for (const [key, id] of Object.entries(CAPS)) {
    const v = opts.caps?.[key as 'leyte' | 'mvip']
    if (v == null) continue
    if (Array.isArray(v)) {
      warnings.push(
        `The ${key} link carries an hourly limit, and the studio holds one number.`
      )
      continue
    }
    if (baseOf(objects.interface, id, 'limit_mw') == null) {
      warnings.push(`No link named ${id} in this build.`)
      continue
    }
    overrides[overrideKey('interface', id, 'limit_mw')] = v
  }

  // the file's list IS the run's storage, so a row it never names goes to zero.
  // Anything else means loading a scenario leaves a battery from the previous
  // one running, which is the kind of edit nobody notices until the price moves.
  if (opts.storage) {
    const left = objects.storage.slice()
    const touched = new Set<string>()
    for (const s of opts.storage) {
      const named = s as {
        id?: string
        grid: GridKey
        power_mw: number
        energy_mwh: number
      }
      let i = named.id ? left.findIndex((r) => r.id === named.id) : -1
      if (i < 0) i = left.findIndex((r) => r.grid === named.grid)
      if (i < 0) {
        warnings.push(`No storage row on ${named.grid}, so that battery was skipped.`)
        continue
      }
      const row = left.splice(i, 1)[0]
      touched.add(row.id)
      overrides[overrideKey('storage', row.id, 'power_mw')] = named.power_mw
      overrides[overrideKey('storage', row.id, 'energy_mwh')] = named.energy_mwh
    }
    for (const row of left) {
      overrides[overrideKey('storage', row.id, 'power_mw')] = 0
      overrides[overrideKey('storage', row.id, 'energy_mwh')] = 0
    }
    if (left.length)
      warnings.push(
        `${left.length} battery the file does not name went to zero: ${left
          .map((r) => r.label)
          .join(', ')}.`
      )
    void touched
  }

  // options the engine honors and the object tables do not hold
  if (opts.hydrology != null && opts.hydrology !== 1)
    warnings.push(
      `Hydrology ${opts.hydrology} is a run setting, not a table value. Set it in Scenario builder.`
    )
  if (opts.reserve_deduction)
    warnings.push('Reserve withholding is a run setting. Turn it on in the reserve view.')
  if (opts.gas_budget)
    warnings.push('The gas budget comes from the Malampaya lever, so it was not loaded.')

  return {
    name: typeof f.name === 'string' && f.name ? f.name : 'Loaded scenario',
    date: f.date,
    overrides,
    warnings,
  }
}
