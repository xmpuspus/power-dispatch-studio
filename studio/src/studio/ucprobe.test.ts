import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { MarketOps, UcProbe } from '../lib/types'
import { ucRows } from './ucprobe'

const mo: MarketOps = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/market_ops.json', import.meta.url)),
    'utf8'
  )
)

const score = (correlation: number, mae: number) => ({
  n_hours: 100,
  observed_mean_php_kwh: 7,
  modeled_mean_php_kwh: 6,
  mae_php_kwh: mae,
  bias_php_kwh: -1,
  correlation,
  high_hour_hit_rate_pct: 30,
})

describe('ucRows', () => {
  it('scores every series the probe paired, and drops the unpaired one', () => {
    const p = mo.uc_probe as UcProbe
    const r = ucRows(p)
    // Visayas has no market clearing price hours in the window, so 5 of 6
    expect(r.length).toBe(5)
    expect(r.map((x) => x.key)).not.toContain('mcp-visayas')
    for (const x of r) expect(x.hours).toBeGreaterThan(0)
  })

  it('reports the commitment run as a fall in every scored series', () => {
    const r = ucRows(mo.uc_probe as UcProbe)
    for (const x of r) expect(x.delta).toBeLessThan(0)
    expect(r.find((x) => x.key === 'lwap-luzon')?.delta).toBeCloseTo(-0.169, 6)
  })

  it('rounds the change to three decimals so the table cannot show float noise', () => {
    const p: UcProbe = {
      lp: { lwap: { luzon: score(0.3, 4) } },
      uc: { lwap: { luzon: score(0.1, 4.0001) } },
    }
    expect(ucRows(p)[0].delta).toBe(-0.2)
  })

  it('drops a series when only one engine scored it', () => {
    const p: UcProbe = {
      lp: { lwap: { luzon: score(0.3, 4) } },
      uc: { lwap: { luzon: null } },
    }
    expect(ucRows(p)).toEqual([])
  })
})
