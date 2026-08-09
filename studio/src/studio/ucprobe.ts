// Scoring rows for the mixed-integer commitment test, kept apart from the view
// so the component file exports only a component.

import type { GridKey, UcProbe } from '../lib/types'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)
export const METRIC: Record<string, string> = {
  lwap: 'load-weighted average price (LWAP)',
  mcp: 'market clearing price (MCP)',
}

export interface Row {
  key: string
  pair: string
  hours: number
  lp: number
  uc: number
  delta: number
  maeLp: number
  maeUc: number
}

/** One row per scored series. A series with no paired hours drops out. */
export function ucRows(p: UcProbe): Row[] {
  const out: Row[] = []
  for (const metric of ['lwap', 'mcp']) {
    for (const g of GRIDS) {
      const lp = p.lp?.[metric]?.[g]
      const uc = p.uc?.[metric]?.[g]
      if (!lp || !uc) continue
      out.push({
        key: `${metric}-${g}`,
        pair: `${cap(g)} ${METRIC[metric]}`,
        hours: lp.n_hours,
        lp: lp.correlation,
        uc: uc.correlation,
        delta: Math.round((uc.correlation - lp.correlation) * 1000) / 1000,
        maeLp: lp.mae_php_kwh,
        maeUc: uc.mae_php_kwh,
      })
    }
  }
  return out
}
