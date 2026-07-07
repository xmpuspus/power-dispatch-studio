import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { GRID_KEYS } from './engine'
import { runChronology, runDuration, type ChronoOpts } from './chrono'

const read = (rel: string) =>
  JSON.parse(readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8'))
const d: Dispatch = read('../../public/data/dispatch.json')
const profiles: Profiles = read('../../public/data/profiles.json')

describe('chronological golden parity vs the Python chrono engine', () => {
  const g = profiles.chrono_golden
  it('golden fixtures are baked', () => {
    expect(g.available).toBe(true)
    expect(g.cases?.length).toBeGreaterThanOrEqual(5)
  })
  const tolP = g.tolerance_php_kwh ?? 0.02
  const tolMW = g.tolerance_mw ?? 1.0

  for (const c of g.cases ?? []) {
    it(`reproduces: ${c.label}`, () => {
      const { date, ...opts } = c.input
      const res = runChronology(d, profiles, date, opts as ChronoOpts)
      for (let h = 0; h < 24; h++) {
        for (const gk of GRID_KEYS)
          expect(
            Math.abs(res.hours[h].price[gk] - c.expect.price[gk][h]),
            `${gk} price h${h}`
          ).toBeLessThanOrEqual(tolP)
        expect(
          Math.abs(res.hours[h].flowLV - c.expect.flow_lv[h]),
          `flowLV h${h}`
        ).toBeLessThanOrEqual(tolMW)
        expect(
          Math.abs(res.hours[h].flowVM - c.expect.flow_vm[h]),
          `flowVM h${h}`
        ).toBeLessThanOrEqual(tolMW)
        expect(
          Math.abs(res.hours[h].socMwh - c.expect.soc_mwh[h]),
          `soc h${h}`
        ).toBeLessThanOrEqual(tolMW)
        expect(
          Math.abs(res.hours[h].shortfall.luzon - c.expect.shortfall_luzon[h]),
          `shortfall h${h}`
        ).toBeLessThanOrEqual(tolMW)
      }
      for (const gk of GRID_KEYS) {
        expect(
          Math.abs(res.summary.meanPrice[gk] - c.expect.summary.mean_price[gk])
        ).toBeLessThanOrEqual(tolP)
        expect(
          Math.abs(res.summary.unservedMwh[gk] - c.expect.summary.unserved_mwh[gk])
        ).toBeLessThanOrEqual(tolMW)
      }
      expect(
        Math.abs(res.summary.leyteRentMPhp - c.expect.summary.leyte_rent_m_php)
      ).toBeLessThanOrEqual(0.01)
      expect(
        Math.abs(res.summary.mvipRentMPhp - c.expect.summary.mvip_rent_m_php)
      ).toBeLessThanOrEqual(0.01)
    })
  }
})

describe('chronological behavior', () => {
  const date = profiles.default_day as string

  it('a flat DC load raises demand in every hour, never lowering any price', () => {
    const base = runChronology(d, profiles, date)
    const dc = runChronology(d, profiles, date, { demand_delta: { luzon: 1500 } })
    for (let h = 0; h < 24; h++) {
      expect(dc.hours[h].demand.luzon - base.hours[h].demand.luzon).toBeCloseTo(1500, 0)
      expect(dc.hours[h].price.luzon).toBeGreaterThanOrEqual(base.hours[h].price.luzon)
    }
  })

  it('added solar generates midday, not at the evening peak', () => {
    const solar = runChronology(d, profiles, date, {
      solar_delta_mw: { luzon: 2000 },
    })
    const gen = (h: number) => solar.hours[h].fuelGen.luzon.solar ?? 0
    expect(gen(12)).toBeGreaterThan(1000)
    expect(gen(19)).toBeLessThan(1)
  })

  it('storage never discharges more than it stored, and ends the day empty', () => {
    const res = runChronology(d, profiles, date, {
      storage: [{ grid: 'luzon', power_mw: 1000, energy_mwh: 2000 }],
    })
    let soc = 0
    for (const h of res.hours) {
      soc += h.chargeMw * profiles.storage_round_trip_eff - h.dischargeMw
      expect(h.socMwh).toBeGreaterThanOrEqual(-1e-6)
      expect(h.socMwh).toBeLessThanOrEqual(2000 + 1e-6)
    }
    expect(res.hours[23].socMwh).toBe(0)
    expect(Math.abs(soc)).toBeLessThanOrEqual(0.5)
  })

  it('the reserve deduction prices at demand plus the scheduled requirement', () => {
    const base = runChronology(d, profiles, date)
    const withRes = runChronology(d, profiles, date, { reserve_deduction: true })
    for (let h = 0; h < 24; h++) {
      expect(withRes.hours[h].demand.luzon).toBeGreaterThan(base.hours[h].demand.luzon)
      expect(withRes.hours[h].price.luzon).toBeGreaterThanOrEqual(
        base.hours[h].price.luzon
      )
    }
  })

  it('runDuration sorts the run prices high to low across the window', () => {
    const res = runChronology(d, profiles, date)
    const dur = runDuration(res.hours, 'luzon')
    expect(dur).toHaveLength(24)
    for (let i = 1; i < dur.length; i++)
      expect(dur[i].price).toBeLessThanOrEqual(dur[i - 1].price)
    expect(dur[0].pct).toBe(0)
    expect(dur[dur.length - 1].pct).toBe(100)
  })

  it('every profile day replays without shortfall surprises on the base model', () => {
    // structural smoke over a sample of days: prices finite, no NaN
    const days = profiles.days.filter((x) => x.market).slice(0, 5)
    for (const day of days) {
      const res = runChronology(d, profiles, day.date)
      for (const h of res.hours)
        for (const gk of GRID_KEYS as GridKey[]) {
          expect(Number.isFinite(h.price[gk])).toBe(true)
          expect(h.price[gk]).toBeGreaterThan(0)
        }
    }
  })
})
