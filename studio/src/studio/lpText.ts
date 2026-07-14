// Canonical LP text for the dispatch model: the byte-exact TypeScript mirror
// of pipeline/lp_model.py. Both engines serialize every coefficient through
// integer micro-units and emit the same variable and row order, so the parity
// harness can pin the sha256 of the text itself; a construction drift on
// either side fails the hash before any solver runs. Any change here must
// land in lp_model.py too, or the hash parity test fails (that is the point).

import type { Block, GridKey } from '../lib/types'

export const LP_GRID_KEYS: GridKey[] = ['luzon', 'visayas', 'mindanao']

// The sourced WESM offer price ceiling (P32/kWh, WESM Tripartite Committee
// Joint Resolution No. 2 s.2013, permanent since Dec 2015). Mirror of
// lp_dispatch.OFFER_CAP, which reads constants_ph.MARKET_ANCHORS. Shortage
// hours price here in both engines.
export const OFFER_CAP = 32
const G_SHORT: Record<GridKey, string> = { luzon: 'l', visayas: 'v', mindanao: 'm' }

// reserve is held by capacity that can actually follow dispatch instructions.
// 'offer' is the observed-book fuel: the book cannot say which MW are
// reserve-capable, so offer-mode withholding applies to the whole book, a
// stated approximation (never reached by cost-mode stacks)
const RESERVE_FUELS = new Set([
  'coal',
  'natural_gas',
  'oil',
  'geothermal',
  'hydro',
  'biomass',
  'offer',
])

export interface LpStorage {
  grid: GridKey
  power_mw: number
  energy_mwh: number
  eff: number
}

/** Integer micro-units; the only float -> text gate in the model. floor(x + 0.5),
 * the repo's shared rounding convention. */
export function micro(x: number): number {
  return Math.floor(x * 1_000_000 + 0.5)
}

/** Serialize integer micro-units as a fixed-point decimal string. */
export function mtext(k: number): string {
  const sign = k < 0 ? '-' : ''
  const a = Math.abs(k)
  const whole = Math.floor(a / 1_000_000)
  const frac = a % 1_000_000
  return `${sign}${whole}.${String(frac).padStart(6, '0')}`
}

/** The canonical LP text; every argument mirrors lp_model.build_day_lp. */
export function buildDayLp(
  stacks: Record<GridKey, Block[][]>,
  demand: Record<GridKey, number[]>,
  caps: { leyte: number | number[]; mvip: number | number[] },
  wheel: number,
  storage: LpStorage[],
  reserveReq: Record<GridKey, number> | null,
  voll: number,
  hydroBudget: Partial<Record<GridKey, number | Array<number | null> | null>> | null = null,
  gasBudget: Partial<Record<GridKey, number | null>> | null = null,
  hydroDayHours: number | null = null
): string {
  const H = demand.luzon.length
  const wheelM = micro(wheel)
  const vollM = micro(voll)

  const obj: string[] = []
  const rows: string[] = []
  const bounds: string[] = []

  // dispatch variables, one per block per grid-hour, epsilon by enumeration
  let eps = 0
  for (let h = 0; h < H; h++) {
    for (const g of LP_GRID_KEYS) {
      const s = G_SHORT[g]
      stacks[g][h].forEach((b, i) => {
        eps += 1
        obj.push(` + ${mtext(micro(b.cost) + eps)} x_${s}_${h}_${i}`)
        bounds.push(` 0 <= x_${s}_${h}_${i} <= ${mtext(micro(b.mw))}`)
      })
    }
  }

  // corridor flows, split by direction, wheeling cost on each. A cap may
  // be one number for the day or a per-hour list (observed HVDC blocks
  // scale the hour's limit); a constant list emits the same text as the
  // scalar, so unaffected days pin unchanged. Mirror of lp_model.py.
  for (let h = 0; h < H; h++) {
    for (const [f, cap] of [
      ['f1', caps.leyte],
      ['f2', caps.mvip],
    ] as const) {
      const capH = Array.isArray(cap) ? cap[h] : cap
      for (const d of ['p', 'n'] as const) {
        obj.push(` + ${mtext(wheelM)} ${f}${d}_${h}`)
        bounds.push(` 0 <= ${f}${d}_${h} <= ${mtext(micro(capH))}`)
      }
    }
  }

  // storage: charge (with a per-hour epsilon so ties resolve to the earliest
  // hour), discharge, state of charge
  storage.forEach((st, k) => {
    for (let h = 0; h < H; h++) {
      obj.push(` + ${mtext(k * H + h + 1)} ch_${k}_${h}`)
      bounds.push(` 0 <= ch_${k}_${h} <= ${mtext(micro(st.power_mw))}`)
      bounds.push(` 0 <= dis_${k}_${h} <= ${mtext(micro(st.power_mw))}`)
      bounds.push(` 0 <= soc_${k}_${h} <= ${mtext(micro(st.energy_mwh))}`)
    }
  })

  // unserved load
  for (let h = 0; h < H; h++) {
    for (const g of LP_GRID_KEYS) {
      const s = G_SHORT[g]
      obj.push(` + ${mtext(vollM)} u_${s}_${h}`)
      bounds.push(` 0 <= u_${s}_${h} <= ${mtext(micro(demand[g][h]))}`)
    }
  }

  // energy balance per grid-hour; flows signed southward
  const flowTerms: Record<GridKey, [string, string][]> = {
    luzon: [
      ['f1n', '+'],
      ['f1p', '-'],
    ],
    visayas: [
      ['f1p', '+'],
      ['f1n', '-'],
      ['f2n', '+'],
      ['f2p', '-'],
    ],
    mindanao: [
      ['f2p', '+'],
      ['f2n', '-'],
    ],
  }
  for (let h = 0; h < H; h++) {
    for (const g of LP_GRID_KEYS) {
      const s = G_SHORT[g]
      const terms: string[] = stacks[g][h].map((_, i) => ` + x_${s}_${h}_${i}`)
      for (const [name, sign] of flowTerms[g]) terms.push(` ${sign} ${name}_${h}`)
      storage.forEach((st, k) => {
        if (st.grid === g) {
          terms.push(` + dis_${k}_${h}`)
          terms.push(` - ch_${k}_${h}`)
        }
      })
      terms.push(` + u_${s}_${h}`)
      rows.push(` bal_${s}_${h}:` + terms.join('') + ` = ${mtext(micro(demand[g][h]))}`)
    }
  }

  // state of charge: soc_h - soc_(h-1) - eff * ch_h + dis_h = 0
  storage.forEach((st, k) => {
    const effM = mtext(micro(st.eff))
    for (let h = 0; h < H; h++) {
      const prev = h > 0 ? ` - soc_${k}_${h - 1}` : ''
      rows.push(
        ` soc_${k}_${h}: soc_${k}_${h}${prev} - ${effM} ch_${k}_${h} + dis_${k}_${h} = 0`
      )
    }
  })

  // reserve: dispatch on reserve-capable blocks plus storage discharge must
  // leave headroom >= requirement (constant right side)
  if (reserveReq) {
    for (let h = 0; h < H; h++) {
      for (const g of LP_GRID_KEYS) {
        const s = G_SHORT[g]
        const req = reserveReq[g] ?? 0
        if (req <= 0) continue
        const terms: string[] = []
        let capM = 0
        stacks[g][h].forEach((b, i) => {
          if (RESERVE_FUELS.has(b.fuel)) {
            terms.push(` + x_${s}_${h}_${i}`)
            capM += micro(b.mw)
          }
        })
        storage.forEach((st, k) => {
          if (st.grid === g) {
            terms.push(` + dis_${k}_${h}`)
            capM += micro(st.power_mw)
          }
        })
        if (!terms.length) continue
        // a requirement beyond what the grid can hold clamps to zero headroom
        // (all capable capacity withheld) instead of an infeasible row
        const rhs = Math.max(0, capM - micro(req))
        rows.push(` res_${s}_${h}:` + terms.join('') + ` <= ${mtext(rhs)}`)
      }
    }
  }

  // hydro is energy-limited by the observed water: hydro dispatch may not
  // exceed the budget. In a native multi-day (168h) LP the water stays
  // DAILY-budgeted, so with hydroDayHours set the cap is written per day block
  // (hydroBudget[g] a per-day list); the default (whole horizon, one row,
  // scalar budget) leaves the single-day LP byte-identical
  if (hydroBudget) {
    const dh = hydroDayHours ?? H
    const ndays = Math.floor(H / dh)
    for (const g of LP_GRID_KEYS) {
      const gb = hydroBudget[g]
      if (gb == null) continue
      const s = G_SHORT[g]
      for (let dd = 0; dd < ndays; dd++) {
        const budget = Array.isArray(gb) ? gb[dd] : gb
        if (budget == null) continue
        const terms: string[] = []
        for (let h = dd * dh; h < (dd + 1) * dh; h++) {
          stacks[g][h].forEach((b, i) => {
            if (b.fuel === 'hydro') terms.push(` + x_${s}_${h}_${i}`)
          })
        }
        if (!terms.length) continue
        const name = ndays === 1 ? `hyd_${s}` : `hyd_${s}_${dd}`
        rows.push(` ${name}:` + terms.join('') + ` <= ${mtext(micro(budget))}`)
      }
    }
  }

  // gas is energy-limited by the day's fuel supply (the Malampaya budget): the
  // sum of natural-gas dispatch across the hours may not exceed the budget.
  // Same structure as the hydro water budget; off unless a scenario sets it
  if (gasBudget) {
    for (const g of LP_GRID_KEYS) {
      const budget = gasBudget[g]
      if (budget == null) continue
      const s = G_SHORT[g]
      const terms: string[] = []
      for (let h = 0; h < H; h++) {
        stacks[g][h].forEach((b, i) => {
          if (b.fuel === 'natural_gas') terms.push(` + x_${s}_${h}_${i}`)
        })
      }
      if (!terms.length) continue
      rows.push(` gas_${s}:` + terms.join('') + ` <= ${mtext(micro(budget))}`)
    }
  }

  return (
    '\\ power-dispatch-studio day LP v1\n' +
    'minimize\n obj:' +
    obj.join('') +
    '\n' +
    'subject to\n' +
    rows.join('\n') +
    '\n' +
    'bounds\n' +
    bounds.join('\n') +
    '\n' +
    'end\n'
  )
}
