import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Dispatch } from '../lib/types'
import { leverTornado, type TornadoBar } from './crossrun'
import type { Levers } from './engine'

const d: Dispatch = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/dispatch.json', import.meta.url)),
    'utf8'
  )
)

const base: Levers = {
  grid: 'luzon',
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

describe('lever tornado', () => {
  // the global setup (vitest.setup.ts) loads the wasm solver in beforeAll, so
  // the sweep has to run after that, not at import time
  let bars: TornadoBar[]
  beforeAll(() => {
    bars = leverTornado(d, base, [])
  })

  it('covers every Quick lever once', () => {
    expect(bars.map((b) => b.lever).sort()).toEqual(
      [
        'addCoal',
        'addDC',
        'addGas',
        'addSolar',
        'addStorage',
        'coalPrice',
        'hydrology',
        'lngSwitch',
        'reliefMW',
      ].sort()
    )
  })

  it('is ranked by absolute price swing, largest first', () => {
    for (let i = 1; i < bars.length; i++)
      expect(Math.abs(bars[i - 1].deltaPhpKwh)).toBeGreaterThanOrEqual(
        Math.abs(bars[i].deltaPhpKwh) - 1e-9
      )
  })

  it('adding data-center load does not lower the price', () => {
    const dc = bars.find((b) => b.lever === 'addDC')!
    expect(dc.deltaPhpKwh).toBeGreaterThanOrEqual(-1e-9)
  })

  it('adding coal supply does not raise the price', () => {
    const coal = bars.find((b) => b.lever === 'addCoal')!
    expect(coal.deltaPhpKwh).toBeLessThanOrEqual(1e-9)
  })
})
