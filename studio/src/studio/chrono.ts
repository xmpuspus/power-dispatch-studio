// Chronological dispatch engine: replay an observed day on the (optionally
// edited) model, solved as ONE linear program over the 24 coupled hours by
// HiGHS (the same solver build PLEXOS-class tools embed, compiled to wasm).
// Storage is true inter-temporal optimisation (it cycles only when the price
// spread beats the round-trip loss), the reserve toggle is a real
// withheld-capacity constraint, and prices are the balance duals: locational
// marginal prices, wheel-shading included.
//
// This file is the TypeScript side of a parity pair with
// pipeline/lp_dispatch.py. Both sides build the byte-identical LP text
// (lpText.ts / lp_model.py; profiles.chrono_golden pins its sha256) and must
// reproduce the same outputs. Any change here must land there too, or the
// parity test fails (that is the point).

import type { Block, Dispatch, GridKey } from '../lib/types'
import type { Profiles } from '../lib/types'
import { GRID_KEYS, buildStack, marginal } from './engine'
import { OFFER_CAP, buildDayLp, type LpStorage } from './lpText'
import { solveLp } from './solver'

// bump when the run outputs change meaning; saved runs from an older engine
// are flagged stale in the Runs view. v3: energy-limited hydro.
export const ENGINE_VERSION = 3

export const LABEL_EPS = 0.025
const STORE_EPS = 1e-3
const FLOW_SAT_EPS = 0.5

export interface ChronoOpts {
  demand_delta?: Partial<Record<GridKey, number>>
  solar_delta_mw?: Partial<Record<GridKey, number>>
  fuel_avail_delta?: Partial<Record<GridKey, Record<string, number>>>
  fuel_cost?: Record<string, number>
  hydrology?: number
  caps?: { leyte?: number; mvip?: number }
  storage?: { grid: GridKey; power_mw: number; energy_mwh: number }[]
  reserve_deduction?: boolean
  // a day-level gas fuel-energy budget (the Malampaya supply cliff), {grid: MWh}
  gas_budget?: Partial<Record<GridKey, number>>
  // OFFER MODE: the day's derived offer book (web/data/offers/); replaces
  // the cost-proxy stacks, disables every layer the book already embodies
  // (storage, reserve, water, outage deviations, fleet levers); only the
  // demand lever stays. Mirror of lp_dispatch._assemble.
  offer_day?: OfferDay
}

export interface OfferDay {
  date: string
  // per grid, 24 entries of [cost PhP/kWh, mw] block lists (or null)
  hours: Record<GridKey, ([number, number][] | null)[]>
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

const HOURS = Array.from({ length: 24 }, (_, h) => h)

function round1(x: number): number {
  return Math.round(x * 10) / 10
}
function round3(x: number): number {
  return Math.round(x * 1000) / 1000
}

/** Name what sets an LMP; mirror of lp_dispatch.price_label, pinned by the
 * goldens. On an importing grid the dual can sit at the exporter's cost plus
 * the wheel, on an exporter the importer's cost minus it, and with storage
 * strictly between its bounds at the arbitrage value. */
export function priceLabel(
  price: number,
  ownCost: number,
  ownFuel: string | null,
  storageMarginal: boolean,
  hydroMarginal = false,
  unservedMarginal = false
): string | null {
  // a shed hour is a shortage no matter what block its penalty happens to
  // coincide with (an edited cost can sit above the offer cap)
  if (unservedMarginal) return 'shortage'
  if (Math.abs(ownCost - price) <= LABEL_EPS) return ownFuel
  if (storageMarginal) return 'storage'
  if (hydroMarginal) return 'hydro'
  return price > ownCost ? 'export' : 'import'
}

interface Assembled {
  stacks: Record<GridKey, Block[][]>
  demand: Record<GridKey, number[]>
  caps: { leyte: number | number[]; mvip: number | number[] }
  wheel: number
  storage: LpStorage[]
  reserveReq: Record<GridKey, number> | null
  voll: number
  hydroBudget: Partial<Record<GridKey, number | null>> | null
  gasBudget: Partial<Record<GridKey, number | null>> | null
}

/** Input assembly, shared by the run and the parity hash test. Mirrors
 * lp_dispatch._assemble exactly. */
export function assembleDay(
  d: Dispatch,
  profiles: Profiles,
  date: string,
  opts: ChronoOpts = {}
): Assembled {
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
  // observed HVDC blocks (NSO advisories, inferred): the hour's corridor
  // limit scales by the fraction of the hour the link was unblocked;
  // levers apply to the base limit first. Mirror of lp_dispatch._assemble.
  const scaledCaps: { leyte: number | number[]; mvip: number | number[] } = {
    ...caps,
  }
  for (const key of ['leyte', 'mvip'] as const) {
    const frac = day.corridor_caps?.[key]
    if (frac) scaledCaps[key] = HOURS.map((h) => round1(caps[key] * frac[h]))
  }

  // OFFER MODE: the book replaces the cost proxy; only the demand lever
  // stays. Mirror of lp_dispatch._assemble's offer branch.
  if (opts.offer_day) {
    const oStacks = { luzon: [], visayas: [], mindanao: [] } as Record<GridKey, Block[][]>
    const oDemand = { luzon: [], visayas: [], mindanao: [] } as Record<GridKey, number[]>
    let dearest = 12
    for (const h of HOURS) {
      for (const g of GRID_KEYS) {
        const blocks = (opts.offer_day.hours[g][h] ?? []).map(([p, mw]) => ({
          fuel: 'offer',
          cost: p,
          mw,
        }))
        blocks.sort((a, b) => a.cost - b.cost)
        for (const b of blocks) if (b.cost > dearest) dearest = b.cost
        oStacks[g].push(blocks)
        oDemand[g].push(day.demand[g][h] + (opts.demand_delta?.[g] ?? 0))
      }
    }
    // the reserve toggle stays available on the book (withheld from the
    // whole book, a stated approximation); mirror of the Python branch
    let oReserve: Record<GridKey, number> | null = null
    if (opts.reserve_deduction) {
      oReserve = { luzon: 0, visayas: 0, mindanao: 0 }
      for (const g of GRID_KEYS) {
        const dayReq = day.reserve_req_mw?.[g]
        const req =
          dayReq && Object.keys(dayReq).length > 0
            ? dayReq
            : (profiles.reserve_req_mean_mw[g] ?? {})
        oReserve[g] = round1(Object.values(req).reduce((s, v) => s + v, 0))
      }
    }
    return {
      stacks: oStacks,
      demand: oDemand,
      caps: scaledCaps,
      wheel,
      storage: [],
      reserveReq: oReserve,
      voll: Math.max(OFFER_CAP, dearest + 0.001),
      hydroBudget: null,
      gasBudget: opts.gas_budget ?? null,
    }
  }

  const fuelBase = {} as Record<GridKey, Record<string, number>>
  const solarInst = {} as Record<GridKey, number>
  const outDev = day.out_dev_mw ?? {}
  for (const g of GRID_KEYS) {
    const mo = d.merit_order[g]
    const fa: Record<string, number> = { ...mo.fuel_avail_mw }
    if (hyd !== 1 && fa.hydro != null) fa.hydro = round1(fa.hydro * hyd)
    // the day's scheduled-outage deviation from the window mean (the static
    // derate already carries the mean; hydro rides its water budget instead)
    // comes off before any what-if lever; mirror of lp_dispatch._assemble
    for (const [fuel, dev] of Object.entries(outDev[g] ?? {}))
      if (fa[fuel] != null) fa[fuel] = Math.max(0, round1(fa[fuel] - dev))
    for (const [fuel, delta] of Object.entries(opts.fuel_avail_delta?.[g] ?? {}))
      fa[fuel] = Math.max(0, round1((fa[fuel] ?? 0) + delta))
    fuelBase[g] = fa
    solarInst[g] = mo.solar_installed_mw + (opts.solar_delta_mw?.[g] ?? 0)
  }

  const stacks = { luzon: [], visayas: [], mindanao: [] } as Record<GridKey, Block[][]>
  const demand = { luzon: [], visayas: [], mindanao: [] } as Record<GridKey, number[]>
  for (const h of HOURS) {
    for (const g of GRID_KEYS) {
      const fa = { ...fuelBase[g] }
      fa.solar = round1(Math.max(0, solarInst[g]) * solarProfile[h])
      stacks[g].push(buildStack(fa, {}, [], params))
      demand[g].push(day.demand[g][h] + (opts.demand_delta?.[g] ?? 0))
    }
  }

  const eff = profiles.storage_round_trip_eff
  const storage: LpStorage[] = (opts.storage ?? [])
    .filter((s) => s.power_mw > 0 && s.energy_mwh > 0)
    .map((s) => ({
      grid: s.grid,
      power_mw: s.power_mw,
      energy_mwh: s.energy_mwh,
      eff,
    }))

  let reserveReq: Record<GridKey, number> | null = null
  if (opts.reserve_deduction) {
    reserveReq = { luzon: 0, visayas: 0, mindanao: 0 }
    for (const g of GRID_KEYS) {
      // the DAY's scheduled requirement when the archive carries it, with
      // the window mean as a PER-GRID fallback; mirror of
      // lp_dispatch._assemble (an empty per-grid dict also falls back)
      const dayReq = day.reserve_req_mw?.[g]
      const req =
        dayReq && Object.keys(dayReq).length > 0
          ? dayReq
          : (profiles.reserve_req_mean_mw[g] ?? {})
      reserveReq[g] = round1(Object.values(req).reduce((s, v) => s + v, 0))
    }
  }

  // the day's observed hydro energy, scaled with hydro capacity so the
  // hydrology lever and capacity edits stay coherent (half the water at
  // half the plant; more plant, proportionally more energy)
  let hydroBudget: Partial<Record<GridKey, number | null>> | null = null
  const dayBudget = day.hydro_budget_mwh
  if (dayBudget) {
    hydroBudget = {}
    for (const g of GRID_KEYS) {
      const baseHydro = d.merit_order[g].fuel_avail_mw.hydro ?? 0
      const effHydro = fuelBase[g].hydro ?? 0
      const budget = dayBudget[g]
      hydroBudget[g] =
        budget == null || baseHydro <= 0 ? null : budget * (effHydro / baseHydro)
    }
  }

  // unserved load prices at the sourced WESM offer cap (P32/kWh); the max
  // guard keeps shedding strictly dearer than any block an edit could push
  // above the cap
  let dearest = 12
  for (const g of GRID_KEYS)
    for (const hb of stacks[g]) for (const b of hb) if (b.cost > dearest) dearest = b.cost
  const voll = Math.max(OFFER_CAP, dearest + 0.001)

  return {
    stacks,
    demand,
    caps: scaledCaps,
    wheel,
    storage,
    reserveReq,
    voll,
    hydroBudget,
    gasBudget: opts.gas_budget ?? null,
  }
}

/** The canonical LP text for a day run; the parity test hashes this. */
export function buildChronoLpText(
  d: Dispatch,
  profiles: Profiles,
  date: string,
  opts: ChronoOpts = {}
): string {
  const m = assembleDay(d, profiles, date, opts)
  return buildDayLp(
    m.stacks,
    m.demand,
    m.caps,
    m.wheel,
    m.storage,
    m.reserveReq,
    m.voll,
    m.hydroBudget,
    m.gasBudget
  )
}

/** Replay one observed day on the LP. Mirrors lp_dispatch.run_chronology_lp. */
export function runChronology(
  d: Dispatch,
  profiles: Profiles,
  date: string,
  opts: ChronoOpts = {}
): ChronoResult {
  const m = assembleDay(d, profiles, date, opts)
  const sol = solveLp(
    buildDayLp(
      m.stacks,
      m.demand,
      m.caps,
      m.wheel,
      m.storage,
      m.reserveReq,
      m.voll,
      m.hydroBudget,
      m.gasBudget
    )
  )
  const S: Record<GridKey, string> = { luzon: 'l', visayas: 'v', mindanao: 'm' }

  const hours: ChronoHour[] = HOURS.map((h) => {
    const f1 = sol.col(`f1p_${h}`) - sol.col(`f1n_${h}`)
    const f2 = sol.col(`f2p_${h}`) - sol.col(`f2n_${h}`)
    const price = {} as Record<GridKey, number>
    const shed = {} as Record<GridKey, number>
    const fuelGen = {} as Record<GridKey, Record<string, number>>
    for (const g of GRID_KEYS) {
      price[g] = round3(sol.dual(`bal_${S[g]}_${h}`))
      shed[g] = Math.max(0, round1(sol.col(`u_${S[g]}_${h}`)))
      const per: Record<string, number> = {}
      m.stacks[g][h].forEach((b, i) => {
        const x = sol.col(`x_${S[g]}_${h}_${i}`)
        if (x > 1e-6) per[b.fuel] = (per[b.fuel] ?? 0) + x
      })
      fuelGen[g] = Object.fromEntries(Object.entries(per).map(([f, v]) => [f, round1(v)]))
    }
    const charge = { luzon: 0, visayas: 0, mindanao: 0 } as Record<GridKey, number>
    const dis = { luzon: 0, visayas: 0, mindanao: 0 } as Record<GridKey, number>
    let socTotal = 0
    const storeMarg = { luzon: false, visayas: false, mindanao: false } as Record<
      GridKey,
      boolean
    >
    m.storage.forEach((st, k) => {
      const dk = sol.col(`dis_${k}_${h}`)
      charge[st.grid] += sol.col(`ch_${k}_${h}`)
      dis[st.grid] += dk
      socTotal += sol.col(`soc_${k}_${h}`)
      if (dk > STORE_EPS && dk < st.power_mw - STORE_EPS) storeMarg[st.grid] = true
    })
    for (const g of GRID_KEYS)
      if (dis[g] > 1e-6) fuelGen[g].storage = round1((fuelGen[g].storage ?? 0) + dis[g])

    const dem = {} as Record<GridKey, number>
    for (const g of GRID_KEYS) dem[g] = m.demand[g][h] + charge[g]
    const gen: Record<GridKey, number> = {
      luzon: dem.luzon + f1 - shed.luzon,
      visayas: dem.visayas + f2 - f1 - shed.visayas,
      mindanao: dem.mindanao - f2 - shed.mindanao,
    }
    const marg = {} as Record<GridKey, string | null>
    for (const g of GRID_KEYS) {
      // the day's water binding leaves hydro strictly interior while the
      // budget row carries a shadow price: hydro sets the LMP
      let hydMarg = false
      if (Math.abs(sol.dual(`hyd_${S[g]}`)) > 1e-6) {
        m.stacks[g][h].forEach((b, i) => {
          if (b.fuel === 'hydro') {
            const x = sol.col(`x_${S[g]}_${h}_${i}`)
            if (x > STORE_EPS && x < b.mw - STORE_EPS) hydMarg = true
          }
        })
      }
      // snap the own-stack read to 0.1 MW: the two solver builds can
      // disagree by 1e-9 at a block boundary, and offer books pack blocks
      // tightly enough for that to flip the label; mirror of lp_dispatch
      const mres = marginal(m.stacks[g][h], round1(gen[g]))
      marg[g] = priceLabel(
        price[g],
        mres.cost,
        mres.fuel,
        storeMarg[g],
        hydMarg,
        shed[g] > STORE_EPS
      )
    }
    const cap1 = Array.isArray(m.caps.leyte) ? m.caps.leyte[h] : m.caps.leyte
    const cap2 = Array.isArray(m.caps.mvip) ? m.caps.mvip[h] : m.caps.mvip
    const sat1 = Math.abs(f1) >= cap1 - FLOW_SAT_EPS
    const sat2 = Math.abs(f2) >= cap2 - FLOW_SAT_EPS
    return {
      hour: h,
      price,
      marginal: marg,
      demand: {
        luzon: round1(dem.luzon),
        visayas: round1(dem.visayas),
        mindanao: round1(dem.mindanao),
      },
      shortfall: shed,
      flowLV: round1(f1),
      flowVM: round1(f2),
      leyte: {
        sat: sat1,
        rent: sat1
          ? round3(f1 > 0 ? price.visayas - price.luzon : price.luzon - price.visayas)
          : 0,
      },
      mvip: {
        sat: sat2,
        rent: sat2
          ? round3(
              f2 > 0 ? price.mindanao - price.visayas : price.visayas - price.mindanao
            )
          : 0,
      },
      fuelGen,
      socMwh: round1(socTotal),
      chargeMw: round1(Object.values(charge).reduce((s, v) => s + v, 0)),
      dischargeMw: round1(Object.values(dis).reduce((s, v) => s + v, 0)),
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

export interface WeekDaySummary {
  date: string
  meanPrice: Record<GridKey, number>
  peakPrice: Record<GridKey, number>
  startSocMwh: number
  endSocMwh: number
}

export interface WeekResult {
  hours: (ChronoHour & { day: number })[]
  days: WeekDaySummary[]
  summary: {
    dates: string[]
    physicalCost: number
    meanPrice: Record<GridKey, number>
    peakPrice: Record<GridKey, number>
    unservedMwh: Record<GridKey, number>
    leyteRentMPhp: number
    mvipRentMPhp: number
    socSwingMwh: number
  }
  objective: number
}

interface AssembledWeek {
  stacks: Record<GridKey, Block[][]>
  demand: Record<GridKey, number[]>
  caps: { leyte: number[]; mvip: number[] }
  wheel: number
  storage: LpStorage[]
  voll: number
  hydroBudget: Partial<Record<GridKey, Array<number | null> | null>> | null
  H: number
  text: string
}

/** Concatenate seven assembled days into one 168-hour model, water kept
 * daily-budgeted. Mirror of lp_dispatch.run_week_lp's assembly. */
function assembleWeek(
  d: Dispatch,
  profiles: Profiles,
  dates: string[],
  opts: ChronoOpts
): AssembledWeek {
  const days = dates.map((date) => assembleDay(d, profiles, date, opts))
  const H = days.length * 24
  const expand = (c: number | number[]) => (Array.isArray(c) ? [...c] : Array(24).fill(c))
  const stacks = {} as Record<GridKey, Block[][]>
  const demand = {} as Record<GridKey, number[]>
  for (const g of GRID_KEYS) {
    stacks[g] = days.flatMap((m) => m.stacks[g])
    demand[g] = days.flatMap((m) => m.demand[g])
  }
  const caps = {
    leyte: days.flatMap((m) => expand(m.caps.leyte)),
    mvip: days.flatMap((m) => expand(m.caps.mvip)),
  }
  const wheel = days[0].wheel
  const storage = days[0].storage
  const voll = Math.max(...days.map((m) => m.voll))
  // per-day water: hydroBudget[g] becomes an nd-long list, one cap per day,
  // skipping grids that carry no budget on any day
  let hydroBudget: Partial<Record<GridKey, Array<number | null> | null>> | null = {}
  let anyHydro = false
  for (const g of GRID_KEYS) {
    const perDay = days.map((m) => (m.hydroBudget ?? {})[g] ?? null)
    const has = perDay.some((v) => v != null)
    hydroBudget[g] = has ? perDay : null
    if (has) anyHydro = true
  }
  if (!anyHydro) hydroBudget = null
  const text = buildDayLp(
    stacks,
    demand,
    caps,
    wheel,
    storage,
    null,
    voll,
    hydroBudget,
    null,
    24
  )
  return { stacks, demand, caps, wheel, storage, voll, hydroBudget, H, text }
}

/** The canonical 168-hour week LP text; the week golden hashes this. */
export function buildWeekLpText(
  d: Dispatch,
  profiles: Profiles,
  dates: string[],
  opts: ChronoOpts = {}
): string {
  return assembleWeek(d, profiles, dates, opts).text
}

/** A native seven-day chronology on ONE 168-hour LP: storage carries across
 * midnight instead of resetting each day, while the water stays daily-budgeted
 * (hydroDayHours=24). Reserve and gas are day-mode analyses and stay off here.
 * Mirror of lp_dispatch.run_week_lp; the week golden pins buildWeekLpText's sha. */
export function runWeek(
  d: Dispatch,
  profiles: Profiles,
  dates: string[],
  opts: ChronoOpts = {}
): WeekResult {
  const { stacks, demand, caps, wheel, storage, voll, H, text } = assembleWeek(
    d,
    profiles,
    dates,
    opts
  )
  const S: Record<GridKey, string> = { luzon: 'l', visayas: 'v', mindanao: 'm' }
  const sol = solveLp(text)

  const hours = Array.from({ length: H }, (_, h) => {
    const dd = Math.floor(h / 24)
    const f1 = sol.col(`f1p_${h}`) - sol.col(`f1n_${h}`)
    const f2 = sol.col(`f2p_${h}`) - sol.col(`f2n_${h}`)
    const price = {} as Record<GridKey, number>
    const shed = {} as Record<GridKey, number>
    const fuelGen = {} as Record<GridKey, Record<string, number>>
    for (const g of GRID_KEYS) {
      price[g] = round3(sol.dual(`bal_${S[g]}_${h}`))
      shed[g] = Math.max(0, round1(sol.col(`u_${S[g]}_${h}`)))
      const per: Record<string, number> = {}
      stacks[g][h].forEach((b, i) => {
        const x = sol.col(`x_${S[g]}_${h}_${i}`)
        if (x > 1e-6) per[b.fuel] = (per[b.fuel] ?? 0) + x
      })
      fuelGen[g] = Object.fromEntries(Object.entries(per).map(([f, v]) => [f, round1(v)]))
    }
    const charge = { luzon: 0, visayas: 0, mindanao: 0 } as Record<GridKey, number>
    const dis = { luzon: 0, visayas: 0, mindanao: 0 } as Record<GridKey, number>
    let socTotal = 0
    const storeMarg = { luzon: false, visayas: false, mindanao: false } as Record<
      GridKey,
      boolean
    >
    storage.forEach((st, k) => {
      const dk = sol.col(`dis_${k}_${h}`)
      charge[st.grid] += sol.col(`ch_${k}_${h}`)
      dis[st.grid] += dk
      socTotal += sol.col(`soc_${k}_${h}`)
      if (dk > STORE_EPS && dk < st.power_mw - STORE_EPS) storeMarg[st.grid] = true
    })
    for (const g of GRID_KEYS)
      if (dis[g] > 1e-6) fuelGen[g].storage = round1((fuelGen[g].storage ?? 0) + dis[g])
    const dem = {} as Record<GridKey, number>
    for (const g of GRID_KEYS) dem[g] = demand[g][h] + charge[g]
    const gen: Record<GridKey, number> = {
      luzon: dem.luzon + f1 - shed.luzon,
      visayas: dem.visayas + f2 - f1 - shed.visayas,
      mindanao: dem.mindanao - f2 - shed.mindanao,
    }
    const marg = {} as Record<GridKey, string | null>
    for (const g of GRID_KEYS) {
      let hydMarg = false
      if (Math.abs(sol.dual(`hyd_${S[g]}_${dd}`)) > 1e-6) {
        stacks[g][h].forEach((b, i) => {
          if (b.fuel === 'hydro') {
            const x = sol.col(`x_${S[g]}_${h}_${i}`)
            if (x > STORE_EPS && x < b.mw - STORE_EPS) hydMarg = true
          }
        })
      }
      const mres = marginal(stacks[g][h], round1(gen[g]))
      marg[g] = priceLabel(
        price[g],
        mres.cost,
        mres.fuel,
        storeMarg[g],
        hydMarg,
        shed[g] > STORE_EPS
      )
    }
    const cap1 = caps.leyte[h]
    const cap2 = caps.mvip[h]
    const sat1 = Math.abs(f1) >= cap1 - FLOW_SAT_EPS
    const sat2 = Math.abs(f2) >= cap2 - FLOW_SAT_EPS
    return {
      hour: h,
      day: dd,
      price,
      marginal: marg,
      demand: {
        luzon: round1(dem.luzon),
        visayas: round1(dem.visayas),
        mindanao: round1(dem.mindanao),
      },
      shortfall: shed,
      flowLV: round1(f1),
      flowVM: round1(f2),
      leyte: {
        sat: sat1,
        rent: sat1
          ? round3(f1 > 0 ? price.visayas - price.luzon : price.luzon - price.visayas)
          : 0,
      },
      mvip: {
        sat: sat2,
        rent: sat2
          ? round3(
              f2 > 0 ? price.mindanao - price.visayas : price.visayas - price.mindanao
            )
          : 0,
      },
      fuelGen,
      socMwh: round1(socTotal),
      chargeMw: round1(Object.values(charge).reduce((s, v) => s + v, 0)),
      dischargeMw: round1(Object.values(dis).reduce((s, v) => s + v, 0)),
    }
  })

  const per = (f: (g: GridKey) => number) =>
    ({ luzon: f('luzon'), visayas: f('visayas'), mindanao: f('mindanao') }) as Record<
      GridKey,
      number
    >
  const daySummaries: WeekDaySummary[] = dates.map((date, dd) => {
    const block = hours.filter((o) => o.day === dd)
    return {
      date,
      meanPrice: per((g) => round3(block.reduce((s, o) => s + o.price[g], 0) / 24)),
      peakPrice: per((g) => Math.max(...block.map((o) => o.price[g]))),
      startSocMwh: round1(block[0].socMwh),
      endSocMwh: round1(block[block.length - 1].socMwh),
    }
  })
  const rentM = (key: 'leyte' | 'mvip', flowKey: 'flowLV' | 'flowVM') =>
    round3(
      hours.reduce(
        (s, o) => s + (o[key].sat ? (Math.abs(o[flowKey]) * o[key].rent) / 1000 : 0),
        0
      )
    )

  // physical system cost EXCLUDING the uniqueness epsilons; the comparable
  // number for the inter-day saving (mirror of lp_dispatch.run_week_lp)
  let phys = 0
  for (let h = 0; h < H; h++) {
    for (const g of GRID_KEYS) {
      stacks[g][h].forEach((b, i) => {
        phys += sol.col(`x_${S[g]}_${h}_${i}`) * b.cost
      })
      phys += voll * sol.col(`u_${S[g]}_${h}`)
    }
    phys +=
      wheel *
      (sol.col(`f1p_${h}`) +
        sol.col(`f1n_${h}`) +
        sol.col(`f2p_${h}`) +
        sol.col(`f2n_${h}`))
  }

  return {
    hours,
    days: daySummaries,
    summary: {
      dates,
      physicalCost: round1(phys),
      meanPrice: per((g) => round3(hours.reduce((s, o) => s + o.price[g], 0) / H)),
      peakPrice: per((g) => Math.max(...hours.map((o) => o.price[g]))),
      unservedMwh: per((g) => round1(hours.reduce((s, o) => s + o.shortfall[g], 0))),
      leyteRentMPhp: rentM('leyte', 'flowLV'),
      mvipRentMPhp: rentM('mvip', 'flowVM'),
      socSwingMwh: round1(Math.max(0, ...hours.map((o) => o.socMwh))),
    },
    objective: sol.objective,
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
