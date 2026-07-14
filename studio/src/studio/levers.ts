import type { Dispatch, GridKey } from '../lib/types'
import type { Levers } from './engine'

/** The base Quick-scenario levers for a grid: no edits, the sourced fleet at
 * the observed coal price. Shared by the Scenario view and the cross-run
 * tornado so both sweep from the same base. */
export function initLevers(d: Dispatch, grid: GridKey): Levers {
  return {
    grid,
    addDC: 0,
    addSolar: 0,
    addGas: 0,
    addCoal: 0,
    addStorage: 0,
    trip: '',
    coalPrice: d.assumptions.fuel_marginal_cost_php_kwh.coal,
    reliefMW: 0,
    lngSwitch: false,
    hydrology: 1,
  }
}
