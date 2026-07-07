// Run report: one self-contained HTML file for a frozen run, readable years
// after the browser storage that held the run is gone. Tables and provenance
// only; every number in it comes from the frozen hourly results.

import type { GridKey } from '../lib/types'
import type { SavedRun } from './runs'
import { bindingCounts } from './insights'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const php = (v: number, dp = 2) => `P${v.toFixed(dp)}`
const num = (v: number) => Math.round(v).toLocaleString('en-US')

const CSS = `
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#1a2233;
margin:2rem auto;max-width:60rem;padding:0 1rem}
h1{font-size:1.4rem;margin:0}h2{font-size:1.05rem;margin:1.8rem 0 .4rem}
.sub{color:#5a6478;margin:.2rem 0 1.2rem}
table{border-collapse:collapse;width:100%;margin:.4rem 0}
th,td{border:1px solid #d8dde6;padding:.32rem .55rem;text-align:left;font-size:.86rem}
th{background:#f2f4f8}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.note{color:#5a6478;font-size:.85rem}
code{background:#f2f4f8;padding:.1rem .3rem;border-radius:3px}
`

export interface ReportExtras {
  emissionsFactors?: Record<string, number> | null
  emissionsSrc?: string | null
  appUrl?: string
}

/** Build the self-contained HTML report for a saved run. */
export function buildRunReport(run: SavedRun, extras: ReportExtras = {}): string {
  const dates = run.summaries.map((s) => s.date)
  const edits = Object.entries(run.overrides)
  const editRows = edits
    .map(([k, v]) => {
      // key is `${cls}:${id}:${prop}` where id itself may contain ':' (fleet
      // generator ids are `${grid}:${name}`), so take the outer segments only
      const cls = k.slice(0, k.indexOf(':'))
      const prop = k.slice(k.lastIndexOf(':') + 1)
      const id = k.slice(cls.length + 1, k.length - prop.length - 1)
      return `<tr><td>${esc(cls)}</td><td>${esc(id)}</td><td>${esc(prop)}</td><td class="n">${v}</td></tr>`
    })
    .join('')

  const sumRows = run.summaries
    .map(
      (s) =>
        `<tr><td>${esc(s.date)}</td>` +
        GRIDS.map((g) => `<td class="n">${php(s.meanPrice[g])}</td>`).join('') +
        GRIDS.map((g) => `<td class="n">${php(s.peakPrice[g])}</td>`).join('') +
        `<td class="n">${num(GRIDS.reduce((a, g) => a + s.unservedMwh[g], 0))}</td>` +
        `<td class="n">${(s.leyteRentMPhp + s.mvipRentMPhp).toFixed(2)}</td></tr>`
    )
    .join('')

  const bindingBlocks = run.hours.length
    ? GRIDS.map((g) => {
        const rows = bindingCounts(run.hours, g)
          .map(
            (b) =>
              `<tr><td>${esc(b.label)}</td><td>${esc(b.cause)}</td>` +
              `<td class="n">${b.hours}</td><td class="n">${b.share_pct.toFixed(1)}%</td></tr>`
          )
          .join('')
        return `<h2>What set the price on ${cap(g)}</h2>
<table><thead><tr><th>Constraint</th><th>Kind</th><th class="n">Hours</th><th class="n">Share</th></tr></thead>
<tbody>${rows}</tbody></table>`
      }).join('\n')
    : '<p class="note">Hourly detail was evicted from storage; per-hour tables are unavailable for this run.</p>'

  let emissions = ''
  const factors = extras.emissionsFactors
  if (factors && run.hours.length) {
    const energy = new Map<string, number>()
    for (const h of run.hours)
      for (const g of GRIDS)
        for (const [fuel, mw] of Object.entries(h.fuelGen[g]))
          energy.set(fuel, (energy.get(fuel) ?? 0) + mw)
    const rows = [...energy.entries()]
      .map(([fuel, mwh]) => ({ fuel, mwh, t: mwh * (factors[fuel] ?? 0) }))
      .sort((a, b) => b.t - a.t)
    const total = rows.reduce((s, r) => s + r.t, 0)
    emissions = `<h2>CO2, all grids</h2>
<table><thead><tr><th>Fuel</th><th class="n">MWh</th><th class="n">tCO2</th></tr></thead><tbody>
${rows
  .map(
    (r) =>
      `<tr><td>${esc(r.fuel.replace(/_/g, ' '))}</td><td class="n">${num(r.mwh)}</td><td class="n">${num(r.t)}</td></tr>`
  )
  .join('')}
<tr><th>Total</th><th class="n">${num(rows.reduce((s, r) => s + r.mwh, 0))}</th><th class="n">${num(total)}</th></tr>
</tbody></table>
<p class="note">Operational emission factors per technology, each with a primary source${
      extras.emissionsSrc ? ` (${esc(extras.emissionsSrc)})` : ''
    }; lifecycle emissions are out of scope. Storage discharge carries no factor of its own; its charging energy is counted at the generating fuel.</p>`
  }

  const hourRows = run.hours
    .map(
      (h, i) =>
        `<tr><td>${esc(dates[Math.floor(i / 24)] ?? '')}</td><td class="n">${h.hour}</td>` +
        GRIDS.map((g) => `<td class="n">${h.price[g].toFixed(2)}</td>`).join('') +
        `<td class="n">${h.flowLV.toFixed(0)}</td><td class="n">${h.flowVM.toFixed(0)}</td>` +
        `<td class="n">${GRIDS.reduce((a, g) => a + h.shortfall[g], 0).toFixed(0)}</td></tr>`
    )
    .join('')

  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(run.name)}: run report</title><style>${CSS}</style></head>
<body>
<h1>Power Dispatch Studio run report</h1>
<p class="sub">${esc(run.name)} · scenario "${esc(run.scenarioName)}" · window ${esc(
    dates[0] ?? run.date
  )}${dates.length > 1 ? ` to ${esc(dates[dates.length - 1])}` : ''} · engine v${run.engineVersion} · saved ${esc(
    run.savedAt.slice(0, 16).replace('T', ' ')
  )} UTC</p>

<h2>Scenario edits (${edits.length})</h2>
${
  edits.length
    ? `<table><thead><tr><th>Class</th><th>Object</th><th>Property</th><th class="n">Value</th></tr></thead><tbody>${editRows}</tbody></table>`
    : '<p class="note">Base case: no property edits.</p>'
}

<h2>Daily summary</h2>
<table><thead><tr><th>Date</th>${GRIDS.map((g) => `<th class="n">Mean ${cap(g)}</th>`).join('')}${GRIDS.map(
    (g) => `<th class="n">Peak ${cap(g)}</th>`
  ).join('')}<th class="n">Unserved MWh</th><th class="n">Rent MP</th></tr></thead>
<tbody>${sumRows}</tbody></table>

${bindingBlocks}
${emissions}

<h2>Hourly results</h2>
${
  run.hours.length
    ? `<details><summary>${run.hours.length} hours (click to expand)</summary>
<table><thead><tr><th>Date</th><th class="n">h</th>${GRIDS.map(
        (g) => `<th class="n">${cap(g)} P/kWh</th>`
      ).join(
        ''
      )}<th class="n">Flow L-V MW</th><th class="n">Flow V-M MW</th><th class="n">Unserved MW</th></tr></thead>
<tbody>${hourRows}</tbody></table></details>`
    : '<p class="note">Hourly detail was evicted from storage.</p>'
}

<h2>Provenance</h2>
<p class="note">Chronological replay of observed IEMOP market days on a merit-order
model, three zonal grids coupled over two HVDC corridors, solved as one linear
program per day by HiGHS (storage inter-temporal, reserves as withheld capacity,
prices from the balance duals). Demand is the archive's dispatched generation per
hour. Not PLEXOS, and not a forecast. Model scope, data provenance, and the backcast
accuracy statement live in the methodology page of the site that produced this
report${extras.appUrl ? `: <code>${esc(extras.appUrl)}</code>` : '.'}</p>
<p class="note">Statistical indicators derived from public data. Patterns may have
legitimate explanations.</p>
</body></html>`
}

export function downloadReport(filename: string, html: string): void {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
