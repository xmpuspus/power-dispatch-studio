import type { EvidenceKind } from '../shell/workflows'
import {
  GAS_FUEL_ID,
  GAS_PROP,
  carbonPriceOf,
  type ClassId,
  type ObjRow,
  type Scenario,
} from './model'

export interface ActiveAssumption {
  key: string
  text: string
}

export interface ResultContext {
  label: string
  summary: string
  assumptions: ActiveAssumption[]
}

const num = (value: number, maximumFractionDigits = 2) =>
  value.toLocaleString('en-US', { maximumFractionDigits })

function parseKey(key: string) {
  const first = key.indexOf(':')
  const last = key.lastIndexOf(':')
  return {
    cls: key.slice(0, first) as ClassId,
    id: key.slice(first + 1, last),
    prop: key.slice(last + 1),
  }
}

function deltaText(value: number, base: number, unit: string) {
  const delta = value - base
  if (Math.abs(delta) < 1e-9) return ''
  return ` (${delta > 0 ? '+' : ''}${num(delta)} ${unit})`
}

export function describeScenario(
  objects: Record<ClassId, ObjRow[]>,
  scenario: Scenario
): ActiveAssumption[] {
  const assumptions: ActiveAssumption[] = []
  for (const [key, value] of Object.entries(scenario.overrides)) {
    const { cls, id, prop } = parseKey(key)
    if (cls === 'fuel' && id === GAS_FUEL_ID && prop === GAS_PROP) {
      assumptions.push({ key, text: `Malampaya gas supply ${num(value, 0)}%` })
      continue
    }
    if (cls === 'fuel' && id === '__carbon__') {
      assumptions.push({
        key,
        text: `Policy carbon price ₱${num(carbonPriceOf(scenario.overrides), 0)}/tCO2`,
      })
      continue
    }
    const item = objects[cls]?.find((candidate) => candidate.id === id)
    const base = item?.props[prop]
    if (!item || typeof base !== 'number') {
      assumptions.push({
        key,
        text: `${id.replace(/_/g, ' ')} ${prop.replace(/_/g, ' ')} ${num(value)}`,
      })
      continue
    }
    if (cls === 'region' && prop === 'demand_mw') {
      assumptions.push({
        key,
        text: `${item.label} modeled load ${num(value, 0)} MW${deltaText(value, base, 'MW')}`,
      })
      continue
    }
    if (cls === 'generator' && prop === 'capacity_mw') {
      assumptions.push({
        key,
        text: `${item.label} available capacity ${num(value, 0)} MW${deltaText(value, base, 'MW')}`,
      })
      continue
    }
    if (cls === 'interface' && prop === 'limit_mw') {
      assumptions.push({
        key,
        text: `${item.label} operating limit ${num(value, 0)} MW${deltaText(value, base, 'MW')}`,
      })
      continue
    }
    if (cls === 'storage' && prop === 'power_mw') {
      assumptions.push({
        key,
        text: `${item.label} power ${num(value, 0)} MW${deltaText(value, base, 'MW')}`,
      })
      continue
    }
    if (cls === 'storage' && prop === 'energy_mwh') {
      assumptions.push({
        key,
        text: `${item.label} energy ${num(value, 0)} MWh${deltaText(value, base, 'MWh')}`,
      })
      continue
    }
    const unit = prop.endsWith('_mw') ? 'MW' : prop === 'cost' ? '₱/kWh' : ''
    assumptions.push({
      key,
      text: `${item.label} ${prop.replace(/_/g, ' ')} ${num(value)}${unit ? ` ${unit}` : ''}${deltaText(value, base, unit)}`,
    })
  }
  if (scenario.settings?.reserveHoldback) {
    assumptions.push({
      key: 'setting:reserve-holdback',
      text: 'Reserve requirements held back from energy clearing',
    })
  }
  return assumptions
}

export function buildResultContext({
  evidenceKind,
  scenario,
  objects,
  dirty,
  date,
}: {
  evidenceKind: EvidenceKind
  scenario: Scenario
  objects: Record<ClassId, ObjRow[]>
  dirty: boolean
  date?: string | null
}): ResultContext {
  const assumptions = describeScenario(objects, scenario)
  if (dirty) {
    return {
      label: 'Preview, not calculated',
      summary: `Pending settings for ${scenario.name}. Press Run before using these results.`,
      assumptions,
    }
  }
  const suffix = date ? ` for ${date}` : ''
  if (evidenceKind === 'recorded') {
    return {
      label: 'Recorded market data',
      summary: `Published IEMOP values${suffix}. No dispatch calculation changes these values.`,
      assumptions: [],
    }
  }
  if (evidenceKind === 'derived') {
    return {
      label: 'Calculated from records',
      summary: `A statistic calculated from published market records${suffix}.`,
      assumptions: [],
    }
  }
  if (evidenceKind === 'replayed') {
    return {
      label: 'Cost-model replay',
      summary: `A dispatch calculation over recorded system conditions${suffix}. This is not a forecast.`,
      assumptions,
    }
  }
  if (evidenceKind === 'scenario') {
    const label =
      scenario.purpose === 'stress-test'
        ? 'Stress-test result'
        : scenario.purpose === 'reference-case'
          ? 'Reference-case result'
          : 'Scenario result'
    return {
      label,
      summary: `${scenario.name}${suffix}. Modeled result, not a recorded price or forecast.`,
      assumptions,
    }
  }
  if (evidenceKind === 'assumed') {
    return {
      label: 'Model input',
      summary: `Editable inputs for ${scenario.name}. Values do not change results until Run.`,
      assumptions,
    }
  }
  return {
    label: 'Recorded data with model replay',
    summary: `Recorded system conditions shown beside calculated results${suffix}. Modeled prices are not recorded prices or forecasts.`,
    assumptions,
  }
}
