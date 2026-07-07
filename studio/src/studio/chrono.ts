// Chronological dispatch engine: replay an observed day hour by hour on the
// (optionally edited) model. NOT PLEXOS: block dispatch per hour, no
// inter-temporal optimisation; storage cycles on a labeled two-pass heuristic.
//
// This file is the TypeScript side of a parity pair with pipeline/chrono.py.
// profiles.chrono_golden carries input/output pairs computed by the Python
// engine; chrono.test.ts asserts this file reproduces them. Any change here
// must land in chrono.py too, or the parity test fails (that is the point).

import type { Block, Dispatch, GridKey } from '../lib/types'
import type { Profiles } from '../lib/types'
import { GRID_KEYS, buildStack, clearCoupled, marginal } from './engine'

// bump when the run outputs change meaning; saved runs from an older engine
// are flagged stale in the Runs view
export const ENGINE_VERSION = 1

export interface ChronoOpts {
  demand_delta?: Partial<Record<GridKey, number>>
  solar_delta_mw?: Partial<Record<GridKey, number>>
  fuel_avail_delta?: Partial<Record<GridKey, Record<string, number>>>
  fuel_cost?: Record<string, number>
  hydrology?: number
  caps?: { leyte?: number; mvip?: number }
  storage?: { grid: GridKey; power_mw: number; energy_mwh: number }[]
  reserve_deduction?: boolean
}

export interface ChronoHour {
  hour: number
  price: Record<GridKey, number>
  marginal: Record<GridKey, string | null>
  demand: Record<GridKey, number>
  shortfall: Record<GridKey, number>
  flowLV: number
  flowVM: number
  leyte: { sat: boolean; rent: number }
  mvip: { sat: boolean; rent: number }
  fuelGen: Record<GridKey, Record<string, number>>
  socMwh: number
  chargeMw: number
  dischargeMw: number
}

export interface ChronoSummary {
  date: string
  meanPrice: Record<GridKey, number>
  peakPrice: Record<GridKey, number>
  unservedMwh: Record<GridKey, number>
  leyteRentMPhp: number
  mvipRentMPhp: number
}

export interface ChronoResult {
  hours: ChronoHour[]
  summary: ChronoSummary
}

const EPS_SOC = 1e-9
const HOURS = Array.from({ length: 24 }, (_, h) => h)

function round1(x: number): number {
  return Math.round(x * 10) / 10
}
function round3(x: number): number {
  return Math.round(x * 1000) / 1000
}
// storage schedule values round DOWN so a cycle can never discharge more than
// it stored or charge past the energy cap (Math.round could round up past both)
function floor1(x: number): number {
  return Math.floor(x * 10) / 10
}
function fuelDispatch(blocks: Block[], served: number): Record<string, number> {
  const out: Record<string, number> = {}
  let remaining = served
  for (const b of blocks) {
    if (remaining <= 0) break
    const take = Math.min(b.mw, remaining)
    out[b.fuel] = round1((out[b.fuel] ?? 0) + take)
    remaining -= take
  }
  return out
}

/** Replay one observed day, hour by hour. Mirrors pipeline/chrono.run_chronology. */
export function runChronology(
  d: Dispatch,
  profiles: Profiles,
  date: string,
  opts: ChronoOpts = {}
): ChronoResult {
  const day = profiles.days.find((x) => x.date === date)
  if (!day) throw new Error(`no profile day ${date}`)
  const a = d.assumptions
  const wheel = a.wheeling_cost_php_kwh
  const costs: Record<string, number> = {
    ...a.fuel_marginal_cost_php_kwh,
    ...(opts.fuel_cost ?? {}),
  }
  const params = {
    coalCommit: a.coal_commit_php_kwh,
    coalMinFrac: a.coal_min_load_frac,
    coalPrice: costs.coal,
    costs,
  }
  const hyd = opts.hydrology ?? 1
  const solarProfile = profiles.solar_profile
  const caps = { leyte: 250, mvip: 450 }
  for (const c of d.coupling.corridors) {
    if (c.id === 'leyte_luzon_hvdc') caps.leyte = c.limit_mw
    else caps.mvip = c.limit_mw
  }
  if (opts.caps?.leyte != null) caps.leyte = opts.caps.leyte
  if (opts.caps?.mvip != null) caps.mvip = opts.caps.mvip

  const fuelBase = {} as Record<GridKey, Record<string, number>>
  const solarInst = {} as Record<GridKey, number>
  for (const g of GRID_KEYS) {
    const mo = d.merit_order[g]
    const fa: Record<string, number> = { ...mo.fuel_avail_mw }
    if (hyd !== 1 && fa.hydro != null) fa.hydro = round1(fa.hydro * hyd)
    for (const [fuel, delta] of Object.entries(opts.fuel_avail_delta?.[g] ?? {}))
      fa[fuel] = Math.max(0, round1((fa[fuel] ?? 0) + delta))
    fuelBase[g] = fa
    solarInst[g] = mo.solar_installed_mw + (opts.solar_delta_mw?.[g] ?? 0)
  }

  const reserveAdd = { luzon: 0, visayas: 0, mindanao: 0 } as Record<GridKey, number>
  if (opts.reserve_deduction) {
    for (const g of GRID_KEYS) {
      const req = profiles.reserve_req_mean_mw[g] ?? {}
      reserveAdd[g] = round1(Object.values(req).reduce((s, v) => s + v, 0))
    }
  }

  const fuelAvailAt = (g: GridKey, h: number): Record<string, number> => {
    const fa = { ...fuelBase[g] }
    fa.solar = round1(Math.max(0, solarInst[g]) * solarProfile[h])
    return fa
  }
  const demandAt = (h: number): Record<GridKey, number> => ({
    luzon: day.demand.luzon[h] + (opts.demand_delta?.luzon ?? 0) + reserveAdd.luzon,
    visayas:
      day.demand.visayas[h] + (opts.demand_delta?.visayas ?? 0) + reserveAdd.visayas,
    mindanao:
      day.demand.mindanao[h] + (opts.demand_delta?.mindanao ?? 0) + reserveAdd.mindanao,
  })

  interface HourClear {
    res: ReturnType<typeof clearCoupled>
    dem: Record<GridKey, number>
    stacks: Record<GridKey, Block[]>
  }
  const clearHour = (
    h: number,
    extraDemand?: Partial<Record<GridKey, number>>,
    added?: Partial<Record<GridKey, Block[]>>
  ): HourClear => {
    const dem = demandAt(h)
    if (extraDemand) for (const g of GRID_KEYS) dem[g] = dem[g] + (extraDemand[g] ?? 0)
    const stacks = {} as Record<GridKey, Block[]>
    for (const g of GRID_KEYS)
      stacks[g] = buildStack(fuelAvailAt(g, h), {}, added?.[g] ?? [], params)
    return { res: clearCoupled(dem, stacks, caps, wheel), dem, stacks }
  }

  // pass 1: no storage, gives the price shape the heuristic reads
  const pass1 = HOURS.map((h) => clearHour(h))

  // storage policy: rank the day's hours by (pass-1 price, demand, hour) on the
  // store's grid; charge in the cheapest hours, discharge in the dearest, walked
  // chronologically through the SoC state. Demand breaks the ties a flat cost
  // plateau leaves. A labeled heuristic, not an optimisation.
  const eff = profiles.storage_round_trip_eff
  const offer = d.storage.discharge_offer_php_kwh
  interface Store {
    grid: GridKey
    charge: number[]
    discharge: number[]
    soc: number[]
  }
  const stores: Store[] = []
  for (const s of opts.storage ?? []) {
    const { grid: g, power_mw: power, energy_mwh: energy } = s
    if (power <= 0 || energy <= 0) continue
    const order = [...HOURS].sort(
      (x, y) =>
        pass1[x].res.price[g] - pass1[y].res.price[g] ||
        pass1[x].dem[g] - pass1[y].dem[g] ||
        x - y
    )
    const nCharge = Math.min(24, Math.ceil(energy / (power * eff)))
    const nDis = Math.min(24 - nCharge, Math.ceil(energy / power))
    const chargeSet = new Set(order.slice(0, nCharge))
    const disSet = new Set(
      order.slice(order.length - nDis).filter((h) => !chargeSet.has(h))
    )
    let soc = 0
    const charge = HOURS.map(() => 0)
    const discharge = HOURS.map(() => 0)
    const socSeries = HOURS.map(() => 0)
    for (const h of HOURS) {
      if (chargeSet.has(h) && soc < energy - EPS_SOC) {
        charge[h] = floor1(Math.min(power, (energy - soc) / eff))
        soc += charge[h] * eff
      } else if (disSet.has(h) && soc > EPS_SOC) {
        discharge[h] = floor1(Math.min(power, soc))
        soc -= discharge[h]
      }
      socSeries[h] = round1(soc)
    }
    stores.push({ grid: g, charge, discharge, soc: socSeries })
  }

  // pass 2: charge as extra demand, discharge as a storage block
  const hours: ChronoHour[] = HOURS.map((h) => {
    let hc = pass1[h]
    if (stores.length) {
      const extra: Partial<Record<GridKey, number>> = {}
      const added: Partial<Record<GridKey, Block[]>> = {}
      for (const s of stores) {
        extra[s.grid] = (extra[s.grid] ?? 0) + s.charge[h]
        if (s.discharge[h] > 0) {
          ;(added[s.grid] ??= []).push({
            fuel: 'storage',
            cost: offer,
            mw: s.discharge[h],
          })
        }
      }
      hc = clearHour(h, extra, added)
    }
    const { res, dem, stacks } = hc
    const fuelGen = {} as Record<GridKey, Record<string, number>>
    for (const g of GRID_KEYS) {
      const avail = stacks[g].reduce((s, b) => s + b.mw, 0)
      fuelGen[g] = fuelDispatch(stacks[g], Math.min(res.genRaw[g], avail))
    }
    const marg = {} as Record<GridKey, string | null>
    for (const g of GRID_KEYS) marg[g] = marginal(stacks[g], res.genRaw[g]).fuel
    return {
      hour: h,
      price: res.price,
      marginal: marg,
      demand: {
        luzon: round1(dem.luzon),
        visayas: round1(dem.visayas),
        mindanao: round1(dem.mindanao),
      },
      shortfall: res.shortfall,
      flowLV: res.flowLV,
      flowVM: res.flowVM,
      leyte: { sat: res.leyte.sat, rent: res.leyte.rent },
      mvip: { sat: res.mvip.sat, rent: res.mvip.rent },
      fuelGen,
      socMwh: round1(stores.reduce((s, st) => s + st.soc[h], 0)),
      chargeMw: round1(stores.reduce((s, st) => s + st.charge[h], 0)),
      dischargeMw: round1(stores.reduce((s, st) => s + st.discharge[h], 0)),
    }
  })

  const rentM = (key: 'leyte' | 'mvip', flowKey: 'flowLV' | 'flowVM') =>
    round3(
      hours.reduce(
        (s, o) => s + (o[key].sat ? (Math.abs(o[flowKey]) * o[key].rent) / 1000 : 0),
        0
      )
    )
  const per = (f: (g: GridKey) => number) =>
    ({ luzon: f('luzon'), visayas: f('visayas'), mindanao: f('mindanao') }) as Record<
      GridKey,
      number
    >
  return {
    hours,
    summary: {
      date,
      meanPrice: per((g) => round3(hours.reduce((s, o) => s + o.price[g], 0) / 24)),
      peakPrice: per((g) => Math.max(...hours.map((o) => o.price[g]))),
      unservedMwh: per((g) => round1(hours.reduce((s, o) => s + o.shortfall[g], 0))),
      leyteRentMPhp: rentM('leyte', 'flowLV'),
      mvipRentMPhp: rentM('mvip', 'flowVM'),
    },
  }
}

/** Duration points (pct of window, price high to low) from a run's hourly prices. */
export function runDuration(
  hours: ChronoHour[],
  grid: GridKey
): { pct: number; price: number }[] {
  const s = hours.map((h) => h.price[grid]).sort((a, b) => b - a)
  const n = s.length
  return s.map((price, i) => ({ pct: n > 1 ? (100 * i) / (n - 1) : 0, price }))
}
