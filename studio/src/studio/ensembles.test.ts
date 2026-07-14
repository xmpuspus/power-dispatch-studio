import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Dispatch, Profiles } from '../lib/types'
import { runEnsemble, type EnsembleResult } from './ensembles'

const d: Dispatch = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/dispatch.json', import.meta.url)),
    'utf8'
  )
)
const profiles: Profiles = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/profiles.json', import.meta.url)),
    'utf8'
  )
)
const date = profiles.days.filter((x) => x.market).slice(-1)[0].date

describe('scenario ensembles', () => {
  let a: EnsembleResult
  let b: EnsembleResult
  beforeAll(() => {
    a = runEnsemble(d, profiles, date, 30, 7)
    b = runEnsemble(d, profiles, date, 30, 7)
  })

  it('is reproducible for a fixed seed', () => {
    expect(a.perGrid.luzon).toEqual(b.perGrid.luzon)
    expect(a.prices.luzon).toEqual(b.prices.luzon)
  })

  it('orders the percentiles p10 <= median <= p90 on every grid', () => {
    for (const g of ['luzon', 'visayas', 'mindanao'] as const) {
      const p = a.perGrid[g]
      expect(p.p10).toBeLessThanOrEqual(p.p50 + 1e-9)
      expect(p.p50).toBeLessThanOrEqual(p.p90 + 1e-9)
    }
  })

  it('returns one price per draw per grid', () => {
    expect(a.prices.luzon).toHaveLength(30)
    expect(a.prices.visayas).toHaveLength(30)
  })
})
