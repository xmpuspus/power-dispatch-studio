import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, Profiles } from '../lib/types'
import { baseObjects, chronoOptsFrom, overrideKey } from './model'
import {
  SCENARIO_SCHEMA,
  fromScenarioFile,
  scenarioFileText,
  toScenarioFile,
} from './scenarioFile'

const load = <T>(rel: string): T =>
  JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'))

const d = load<Dispatch>('../../public/data/dispatch.json')
const profiles = load<Profiles>('../../public/data/profiles.json')
// the one fixture the Python round trip reads too, so the two cannot drift
const fixture = load<Record<string, unknown>>(
  '../../../tests/fixtures/scenario_example.json'
)

const objects = baseObjects(d, [], profiles.storage_defaults ?? [], [])

describe('the scenario file', () => {
  it('reads the shared fixture and lands the edits the studio can hold', () => {
    const r = fromScenarioFile(fixture, objects)
    expect(r.date).toBe('2026-06-17')
    expect(r.name).toContain('DICT')
    // demand: base plus 1500
    const base = objects.region.find((x) => x.id === 'luzon')!.props.demand_mw as number
    expect(r.overrides[overrideKey('region', 'luzon', 'demand_mw')]).toBe(base + 1500)
    // one Sual unit out of the Luzon coal availability
    const coal = objects.fuel.find((x) => x.id === 'coal')!.props.luzon_mw as number
    expect(r.overrides[overrideKey('fuel', 'coal', 'luzon_mw')]).toBe(coal - 647)
    // an absolute price, not a delta
    expect(r.overrides[overrideKey('fuel', 'natural_gas', 'cost')]).toBe(9.5)
  })

  it('warns about the settings the object tables cannot hold', () => {
    const r = fromScenarioFile(fixture, objects)
    const joined = r.warnings.join(' ')
    expect(joined).toContain('Hydrology')
    expect(joined).toContain('Reserve withholding')
  })

  it('round-trips the options the studio owns', () => {
    const r = fromScenarioFile(fixture, objects)
    const back = toScenarioFile('round trip', r.date, objects, r.overrides)
    const want = (fixture as { opts: Record<string, unknown> }).opts
    expect(back.opts.demand_delta).toEqual(want.demand_delta)
    expect(back.opts.fuel_cost).toEqual(want.fuel_cost)
    expect(back.opts.fuel_avail_delta).toEqual(want.fuel_avail_delta)
    expect(back.opts.solar_delta_mw).toEqual(want.solar_delta_mw)
    expect(back.opts.caps).toEqual(want.caps)
    expect(back.opts.storage).toEqual(want.storage)
  })

  it('stamps the schema and writes text a person can read', () => {
    const f = toScenarioFile('empty', '2026-06-17', objects, {})
    expect(f.schema).toBe(SCENARIO_SCHEMA)
    const text = scenarioFileText(f)
    expect(text.split('\n').length).toBeGreaterThan(3)
    expect(JSON.parse(text).schema).toBe(SCENARIO_SCHEMA)
  })

  it('refuses a file with no date, and names the reason', () => {
    expect(() =>
      fromScenarioFile({ schema: SCENARIO_SCHEMA, opts: {} }, objects)
    ).toThrow(/date/)
  })

  it('flags a schema from another build instead of guessing', () => {
    const r = fromScenarioFile({ ...fixture, schema: 'pds-scenario/9' }, objects)
    expect(r.warnings.join(' ')).toContain('pds-scenario/9')
  })

  it('takes the mean of an hourly demand shape and says so', () => {
    const hours = Array.from({ length: 24 }, (_, h) => (h < 12 ? 0 : 2000))
    const r = fromScenarioFile(
      {
        schema: SCENARIO_SCHEMA,
        date: '2026-06-17',
        opts: { demand_delta: { luzon: hours } },
      },
      objects
    )
    const base = objects.region.find((x) => x.id === 'luzon')!.props.demand_mw as number
    expect(r.overrides[overrideKey('region', 'luzon', 'demand_mw')]).toBe(base + 1000)
    expect(r.warnings.join(' ')).toContain('hourly shape')
  })

  it('produces the same options the solver already reads', () => {
    const r = fromScenarioFile(fixture, objects)
    const direct = chronoOptsFrom(objects, r.overrides)
    const strip = (o: typeof direct) => ({
      ...o,
      storage: o.storage?.map(({ ...rest }) => {
        delete (rest as { id?: string }).id
        return rest
      }),
    })
    const viaFile = toScenarioFile('x', r.date, objects, r.overrides).opts
    // the file adds one key the solver never reads: which battery each row is
    expect(strip(viaFile)).toEqual(strip(direct))
    const first = viaFile.storage?.[0] as { id?: string } | undefined
    expect(first?.id).toBe('bess_luzon')
  })
})
