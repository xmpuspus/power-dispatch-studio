// Run report: one self-contained HTML file for a frozen run, readable years
// after the browser storage that held the run is gone. Tables and sources
// only; its values come from the frozen hourly results.

import type { GridKey } from '../lib/types'
import type { SavedRun } from './runs'
import { bindingCounts, capturePrices } from './insights'

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

const CLASS_LABEL: Record<string, string> = {
  region: 'Grid',
  generator: 'Power plant',
  fuel: 'Fuel',
  interface: 'Grid link',
  storage: 'Storage',
}

const PROPERTY_LABEL: Record<string, string> = {
  demand_mw: 'Demand (MW)',
  capacity_mw: 'Available capacity (MW)',
  marginal_cost: 'Generation cost (P/kWh)',
  cost: 'Fuel cost (P/kWh)',
  limit_mw: 'Transfer limit (MW)',
}

const classLabel = (v: string) => CLASS_LABEL[v] ?? v.replace(/_/g, ' ')
const propertyLabel = (v: string) => PROPERTY_LABEL[v] ?? v.replace(/_/g, ' ')
const objectLabel = (v: string) => v.replace(':', ' / ')

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
      return `<tr><td>${esc(classLabel(cls))}</td><td>${esc(objectLabel(id))}</td><td>${esc(propertyLabel(prop))}</td><td class="n">${v}</td></tr>`
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
    : '<p class="note">Hourly detail is no longer stored for this run, so the per-hour tables are unavailable.</p>'

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
<table><thead><tr><th>Fuel</th><th class="n">MWh</th><th class="n">Metric tonnes CO2 (tCO2)</th></tr></thead><tbody>
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

  let userSupplied = ''
  const imported = run.importedKeys ?? []
  if (imported.length) {
    const rows = imported
      .map((k) => {
        const cls = k.slice(0, k.indexOf(':'))
        const prop = k.slice(k.lastIndexOf(':') + 1)
        const id = k.slice(cls.length + 1, k.length - prop.length - 1)
        return `<tr><td>${esc(classLabel(cls))}</td><td>${esc(objectLabel(id))}</td><td>${esc(propertyLabel(prop))}</td><td class="n">${run.overrides[k]}</td></tr>`
      })
      .join('')
    userSupplied = `<h2>User-supplied inputs (${imported.length})</h2>
<table><thead><tr><th>Type</th><th>Plant, grid, or link</th><th>Setting</th><th class="n">Value</th></tr></thead><tbody>${rows}</tbody></table>
<p class="note">These values were imported from the analyst's own CSV in the browser and never uploaded. They are the analyst's inputs, not the generated public data.</p>`
  }

  let capture = ''
  if (run.hours.length) {
    const rows = capturePrices(run.hours)
    if (rows.length)
      capture = `<h2>Capture prices per technology</h2>
<table><thead><tr><th>Fuel</th><th>Grid</th><th class="n">Generation MWh</th><th class="n">Capture price ₱/kWh</th><th class="n">Capture rate</th></tr></thead><tbody>
${rows
  .map(
    (r) =>
      `<tr><td>${esc(r.fuel.replace(/_/g, ' '))}</td><td>${esc(cap(r.grid))}</td>` +
      `<td class="n">${num(r.gen_mwh)}</td><td class="n">${r.capture_price_php_kwh.toFixed(3)}</td>` +
      `<td class="n">${r.capture_rate === null ? 'n/a' : r.capture_rate.toFixed(3)}</td></tr>`
  )
  .join('')}
</tbody></table>
<p class="note">Generation-weighted capture price per technology: sum(generation times price) divided by generation, on each grid's own price. The capture rate is that divided by the run's time-average price. It is a revenue measure used for project analysis and Green Energy Auction (GEA) bids. Solar and wind earn less than the flat average when they clear mostly in low-price hours.</p>`
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
  )}${dates.length > 1 ? ` to ${esc(dates[dates.length - 1])}` : ''} · calculation version ${run.engineVersion} · saved ${esc(
    run.savedAt.slice(0, 16).replace('T', ' ')
  )} UTC</p>

<h2>Scenario edits (${edits.length})</h2>
${
  edits.length
    ? `<table><thead><tr><th>Type</th><th>Plant, grid, or link</th><th>Setting</th><th class="n">Value</th></tr></thead><tbody>${editRows}</tbody></table>`
    : '<p class="note">Base case: no setting changes.</p>'
}

<h2>Daily summary</h2>
<table><thead><tr><th>Date</th>${GRIDS.map((g) => `<th class="n">Mean ${cap(g)}</th>`).join('')}${GRIDS.map(
    (g) => `<th class="n">Peak ${cap(g)}</th>`
  ).join('')}<th class="n">Unserved MWh</th><th class="n">Rent MP</th></tr></thead>
<tbody>${sumRows}</tbody></table>

${userSupplied}
${bindingBlocks}
${capture}
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
    : '<p class="note">Hourly detail is no longer stored for this run.</p>'
}

<h2>Model and data</h2>
<p class="note">This report recalculates recorded IEMOP market days with a cost-based
dispatch model. It represents Luzon, Visayas, and Mindanao and the two
high-voltage direct-current links between them. Demand is the operator's recorded
hourly dispatched generation. Storage can move energy between hours, and reserve
requirements reduce the capacity available for energy. Regional prices reflect the
cost of the last generation block needed, grid transfer costs, and binding transfer
limits. This is a scenario calculation, not a forecast. The methodology page explains
the model limits, data sources, and historical price comparison for the site that produced this
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
