// Cross-run analytics (roadmap item 17): a one-at-a-time lever tornado. Sweep
// each Quick lever a fixed step around a base scenario, re-clear, and rank the
// levers by how far they move the selected grid's price. Pure, so the view can
// memoize it and the test can pin the ranking.

import type { Dispatch, GridKey } from '../lib/types'
import { solveScenario, type Levers, type TrippableUnit } from './engine'

export interface TornadoBar {
  lever: string
  label: string
  step: string // human-readable perturbation, e.g. "+1500 MW"
  deltaPhpKwh: number // selected grid coupled price change vs the base
}

// the perturbation applied to each lever, and how to describe it. addDC is the
// DICT data-center wave; the supply levers are a round GW; coalPrice and
// hydrology are the administered and weather what-ifs.
type Sweep = {
  key: keyof Levers
  label: string
  apply: (lv: Levers, d: Dispatch) => void
  step: string
}

const SWEEPS: Sweep[] = [
  {
    key: 'addDC',
    label: 'Add a data center',
    step: '+1500 MW',
    apply: (lv) => {
      lv.addDC = 1500
    },
  },
  {
    key: 'addSolar',
    label: 'Add solar',
    step: '+1000 MW',
    apply: (lv) => {
      lv.addSolar = 1000
    },
  },
  {
    key: 'addGas',
    label: 'Add gas',
    step: '+1000 MW',
    apply: (lv) => {
      lv.addGas = 1000
    },
  },
  {
    key: 'addCoal',
    label: 'Add coal',
    step: '+1000 MW',
    apply: (lv) => {
      lv.addCoal = 1000
    },
  },
  {
    key: 'addStorage',
    label: 'Discharge storage',
    step: '+500 MW',
    apply: (lv) => {
      lv.addStorage = 500
    },
  },
  {
    key: 'coalPrice',
    label: 'Coal price',
    step: '+2 PhP/kWh',
    apply: (lv, d) => {
      lv.coalPrice = d.assumptions.fuel_marginal_cost_php_kwh.coal + 2
    },
  },
  {
    key: 'reliefMW',
    label: 'Relieve the corridor',
    step: '+250 MW',
    apply: (lv) => {
      lv.reliefMW = 250
    },
  },
  {
    key: 'hydrology',
    label: 'Dry hydrology',
    step: 'x0.5',
    apply: (lv) => {
      lv.hydrology = 0.5
    },
  },
  {
    key: 'lngSwitch',
    label: 'Switch gas to LNG',
    step: 'on',
    apply: (lv) => {
      lv.lngSwitch = true
    },
  },
]

/** The one-at-a-time lever tornado for a base scenario on a grid: each lever's
 * effect on the selected grid's coupled clearing price, largest swing first. */
export function leverTornado(
  d: Dispatch,
  base: Levers,
  units: TrippableUnit[]
): TornadoBar[] {
  const g: GridKey = base.grid
  const basePrice = solveScenario(d, base, units).coupled.price[g]
  const bars: TornadoBar[] = SWEEPS.map((s) => {
    const lv: Levers = { ...base }
    s.apply(lv, d)
    const price = solveScenario(d, lv, units).coupled.price[g]
    return {
      lever: s.key as string,
      label: s.label,
      step: s.step,
      deltaPhpKwh: Math.round((price - basePrice) * 1000) / 1000,
    }
  })
  return bars.sort((a, b) => Math.abs(b.deltaPhpKwh) - Math.abs(a.deltaPhpKwh))
}
