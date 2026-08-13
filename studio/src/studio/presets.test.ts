import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, Fleet, Profiles } from '../lib/types'
import { baseObjects, overrideKey } from './model'
import { SCENARIO_PRESETS, buildPreset } from './presets'

const load = <T>(rel: string): T =>
  JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'))

const dispatch = load<Dispatch>('../../public/data/dispatch.json')
const profiles = load<Profiles>('../../public/data/profiles.json')
const fleet = load<Fleet>('../../public/data/fleet.json')
const objects = baseObjects(dispatch, [], profiles.storage_defaults ?? [], fleet.plants)

describe('analyst task presets', () => {
  it('offers the six approved starting cases in a stable order', () => {
    expect(SCENARIO_PRESETS.map((preset) => preset.id)).toEqual([
      'generator-outage',
      'corridor-derating',
      'dict-1500',
      'malampaya-reduction',
      'reserve-holdback',
      'storage-addition',
    ])
  })

  it('trips one sourced 668 MW Dinginin unit', () => {
    const scenario = buildPreset('generator-outage', objects)
    expect(scenario.name).toBe('Dinginin Unit 1 outage')
    expect(
      scenario.overrides[overrideKey('generator', 'luzon:DINGININ U1', 'capacity_mw')]
    ).toBe(0)
    expect(scenario.sourceNotes?.join(' ')).toContain('DOE')
    expect(scenario.sourceNotes?.join(' ')).toContain('668 MW')
  })

  it('halves the current Leyte-Luzon operating limit', () => {
    const scenario = buildPreset('corridor-derating', objects)
    expect(
      scenario.overrides[overrideKey('interface', 'leyte_luzon_hvdc', 'limit_mw')]
    ).toBe(125)
    expect(scenario.name).toBe('Leyte-Luzon 50% derating')
  })

  it('adds the 1,500 MW DICT reference scale to Luzon demand', () => {
    const base = objects.region.find((row) => row.id === 'luzon')!.props
      .demand_mw as number
    const scenario = buildPreset('dict-1500', objects)
    expect(scenario.overrides[overrideKey('region', 'luzon', 'demand_mw')]).toBe(
      base + 1500
    )
    expect(scenario.sourceNotes?.join(' ')).toContain('reference')
    expect(scenario.sourceNotes?.join(' ')).toContain('not a project forecast')
  })

  it('sets Malampaya supply to 50 percent', () => {
    const scenario = buildPreset('malampaya-reduction', objects)
    expect(
      scenario.overrides[overrideKey('fuel', '__gas_supply__', 'malampaya_supply_pct')]
    ).toBe(50)
  })

  it('keeps reserve holdback as a run setting, not a numeric object edit', () => {
    const scenario = buildPreset('reserve-holdback', objects)
    expect(scenario.overrides).toEqual({})
    expect(scenario.settings?.reserveHoldback).toBe(true)
  })

  it('adds a 500 MW four-hour battery to the existing Luzon BESS row', () => {
    const base = objects.storage.find((row) => row.id === 'bess_luzon')!
    const scenario = buildPreset('storage-addition', objects)
    expect(scenario.overrides[overrideKey('storage', 'bess_luzon', 'power_mw')]).toBe(
      (base.props.power_mw as number) + 500
    )
    expect(scenario.overrides[overrideKey('storage', 'bess_luzon', 'energy_mwh')]).toBe(
      (base.props.energy_mwh as number) + 2000
    )
  })
})
