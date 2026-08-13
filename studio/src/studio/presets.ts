import {
  GAS_FUEL_ID,
  GAS_PROP,
  overrideKey,
  type ClassId,
  type ObjRow,
  type Scenario,
} from './model'

export type ScenarioPresetId =
  | 'generator-outage'
  | 'corridor-derating'
  | 'dict-1500'
  | 'malampaya-reduction'
  | 'reserve-holdback'
  | 'storage-addition'

export interface ScenarioPresetDefinition {
  id: ScenarioPresetId
  name: string
  summary: string
  basis: string
  purpose: 'reference-case' | 'stress-test'
}

export const SCENARIO_PRESETS: ScenarioPresetDefinition[] = [
  {
    id: 'generator-outage',
    name: 'Dinginin Unit 1 outage',
    summary: 'Remove one 668 MW Luzon coal unit for the full run.',
    basis: 'DOE dependable capacity; the outage is an analyst assumption.',
    purpose: 'stress-test',
  },
  {
    id: 'corridor-derating',
    name: 'Leyte-Luzon 50% derating',
    summary: 'Cut the current 250 MW operating limit to 125 MW.',
    basis: 'IEMOP operating limit; the 50% derating is an analyst assumption.',
    purpose: 'stress-test',
  },
  {
    id: 'dict-1500',
    name: 'DICT 1,500 MW reference',
    summary: 'Add 1,500 MW of flat Luzon demand.',
    basis: 'DICT reference scale; this is not a project forecast.',
    purpose: 'reference-case',
  },
  {
    id: 'malampaya-reduction',
    name: 'Malampaya 50% supply',
    summary: 'Limit Luzon gas energy to half of its modeled daily maximum.',
    basis: 'DOE field context; the 50% supply level is an analyst assumption.',
    purpose: 'stress-test',
  },
  {
    id: 'reserve-holdback',
    name: 'Energy plus reserve holdback',
    summary: 'Hold recorded average reserve requirements out of energy clearing.',
    basis: 'Recorded reserve requirements with a modeled clearing approximation.',
    purpose: 'stress-test',
  },
  {
    id: 'storage-addition',
    name: 'Luzon 500 MW battery addition',
    summary: 'Add 500 MW and 2,000 MWh to the existing Luzon battery row.',
    basis: 'Four-hour battery size set as an analyst assumption.',
    purpose: 'reference-case',
  },
]

const row = (objects: Record<ClassId, ObjRow[]>, cls: ClassId, id: string): ObjRow => {
  const found = objects[cls].find((item) => item.id === id)
  if (!found) throw new Error(`The ${id} input is not available in this data build.`)
  return found
}

export function buildPreset(
  id: ScenarioPresetId,
  objects: Record<ClassId, ObjRow[]>
): Scenario {
  const definition = SCENARIO_PRESETS.find((preset) => preset.id === id)
  if (!definition) throw new Error(`Unknown scenario preset: ${id}`)

  const scenario: Scenario = {
    name: definition.name,
    overrides: {},
    purpose: definition.purpose,
    presetId: definition.id,
    sourceNotes: [definition.basis],
  }

  if (id === 'generator-outage') {
    const plant = row(objects, 'generator', 'luzon:DINGININ U1')
    scenario.overrides[overrideKey('generator', plant.id, 'capacity_mw')] = 0
    scenario.sourceNotes = [
      `DOE dependable capacity lists ${plant.label} at ${plant.props.capacity_mw} MW; the full-run outage is an analyst assumption.`,
    ]
  }
  if (id === 'corridor-derating') {
    const link = row(objects, 'interface', 'leyte_luzon_hvdc')
    const base = link.props.limit_mw as number
    scenario.overrides[overrideKey('interface', link.id, 'limit_mw')] = base / 2
  }
  if (id === 'dict-1500') {
    const luzon = row(objects, 'region', 'luzon')
    scenario.overrides[overrideKey('region', 'luzon', 'demand_mw')] =
      (luzon.props.demand_mw as number) + 1500
  }
  if (id === 'malampaya-reduction') {
    scenario.overrides[overrideKey('fuel', GAS_FUEL_ID, GAS_PROP)] = 50
  }
  if (id === 'reserve-holdback') {
    scenario.settings = { reserveHoldback: true }
  }
  if (id === 'storage-addition') {
    const storage = row(objects, 'storage', 'bess_luzon')
    scenario.overrides[overrideKey('storage', storage.id, 'power_mw')] =
      (storage.props.power_mw as number) + 500
    scenario.overrides[overrideKey('storage', storage.id, 'energy_mwh')] =
      (storage.props.energy_mwh as number) + 2000
  }
  return scenario
}
