// The studio's information architecture, in one place.
//
// The old explorer sorted 39 destinations by what the model calls them
// (Objects / Solution / Analysis). A market analyst does not arrive with an
// object class in mind, they arrive with a question: what cleared tonight,
// is there headroom, where can 300 MW sit, what does it do to the bill.
// So the groups below are those questions, and every destination keeps its
// old Nav value so the panes behind them do not change.

import type { ClassId } from '../studio/model'

export type SolId =
  | 'merit'
  | 'chrono'
  | 'sweep'
  | 'distribution'
  | 'flows'
  | 'n1'
  | 'regions'
  | 'duration'
  | 'marginal'
  | 'reliability'
export type AnalysisId =
  | 'reserve'
  | 'bill'
  | 'market'
  | 'backcast'
  | 'explain'
  | 'emissions'
  | 'capture'
  | 'portfolio'
  | 'crossrun'
  | 'ensemble'
  | 'rtdoe5'
  | 'forward'
  | 'multiyear'
  | 'week'
  | 'expansion'
  | 'vintage'
  | 'nodal'
  | 'sites'
  | 'lossval'
export type PhaseId = 'lt' | 'pasa'

export type Nav =
  | { kind: 'class'; id: ClassId }
  | { kind: 'quick' }
  | { kind: 'compare' }
  | { kind: 'runs' }
  | { kind: 'sol'; id: SolId }
  | { kind: 'analysis'; id: AnalysisId }
  | { kind: 'phase'; id: PhaseId }

export type Dest = {
  /** stable slug: the deep link, the command-palette key, the test hook */
  slug: string
  label: string
  /** what the destination answers, shown under the label in search */
  hint: string
  nav: Nav
  /** re-solves from the current edits rather than reading the calibrated base */
  live?: boolean
  /** reads one grid at a time, so the region control applies */
  scoped?: boolean
  /** extra words the palette matches on */
  alias?: string
}

export type Group = {
  id: string
  /** the analyst's question, not the model's category */
  label: string
  dests: Dest[]
}

export const GROUPS: Group[] = [
  {
    id: 'tonight',
    label: "Tonight's market",
    dests: [
      {
        slug: 'chronology',
        label: 'Chronology',
        hint: 'Every hour of one observed day, three grids cleared together',
        nav: { kind: 'sol', id: 'chrono' },
        live: true,
        scoped: true,
        alias: 'hourly clearing price day week short-term',
      },
      {
        slug: 'explain-a-day',
        label: 'Explain a day',
        hint: 'What set the price on a chosen day, hour by hour',
        nav: { kind: 'analysis', id: 'explain' },
        scoped: true,
        alias: 'driver why price spike',
      },
      {
        slug: 'five-minute-replay',
        label: '5-minute replay',
        hint: "The operator's own 5-minute dispatch intervals, replayed",
        nav: { kind: 'analysis', id: 'rtdoe5' },
        scoped: true,
        alias: 'rtd rtdoe interval real time',
      },
      {
        slug: 'merit-order',
        label: 'Merit order',
        hint: 'The stack that clears, cheapest unit to the marginal one',
        nav: { kind: 'sol', id: 'merit' },
        live: true,
        scoped: true,
        alias: 'supply curve stack dispatch',
      },
      {
        slug: 'marginal-units',
        label: 'Marginal units',
        hint: 'Which plant sets the price, and how often',
        nav: { kind: 'sol', id: 'marginal' },
        scoped: true,
        alias: 'price setter frequency',
      },
      {
        slug: 'native-week',
        label: 'Native week',
        hint: '168 hours solved as one program, storage carried across midnight',
        nav: { kind: 'analysis', id: 'week' },
        scoped: true,
        alias: '168 hour weekly lp',
      },
    ],
  },
  {
    id: 'headroom',
    label: 'Is there headroom',
    dests: [
      {
        slug: 'reliability',
        label: 'Reliability',
        hint: 'Loss-of-load probability from forced-outage Monte Carlo',
        nav: { kind: 'sol', id: 'reliability' },
        live: true,
        alias: 'lolp monte carlo outage risk',
      },
      {
        slug: 'adequacy',
        label: 'Adequacy',
        hint: 'Whether supply covers demand across the outage schedule',
        nav: { kind: 'phase', id: 'pasa' },
        alias: 'pasa margin outlook',
      },
      {
        slug: 'n-1',
        label: 'N-1 contingency',
        hint: 'What the margin does when the largest unit trips',
        nav: { kind: 'sol', id: 'n1' },
        live: true,
        scoped: true,
        alias: 'trip sual contingency largest unit',
      },
      {
        slug: 'load-sweep',
        label: 'Load sweep',
        hint: 'Price against demand, swept across the whole range',
        nav: { kind: 'sol', id: 'sweep' },
        live: true,
        scoped: true,
        alias: 'demand curve sensitivity',
      },
      {
        slug: 'window-band',
        label: 'Window band',
        hint: 'The price band the archive window actually produced',
        nav: { kind: 'sol', id: 'distribution' },
        live: true,
        scoped: true,
        alias: 'distribution spread percentile',
      },
      {
        slug: 'price-duration',
        label: 'Price duration',
        hint: 'Hours at or above each price, sorted',
        nav: { kind: 'sol', id: 'duration' },
        scoped: true,
        alias: 'duration curve exceedance',
      },
    ],
  },
  {
    id: 'siting',
    label: 'Where it can sit',
    dests: [
      {
        slug: 'siting',
        label: 'Siting a new load',
        hint: 'What a named site can draw, hour by hour, over its own lines',
        nav: { kind: 'analysis', id: 'sites' },
        scoped: true,
        alias: 'data center site pax silica connect headroom',
      },
      {
        slug: 'coupled-flows',
        label: 'Coupled flows',
        hint: 'What moves over the HVDC links, and when they bind',
        nav: { kind: 'sol', id: 'flows' },
        live: true,
        alias: 'hvdc corridor interconnector leyte',
      },
      {
        slug: 'nodal-prices',
        label: 'Nodal prices',
        hint: 'Locational deviation from the regional price, per bus',
        nav: { kind: 'analysis', id: 'nodal' },
        scoped: true,
        alias: 'lmp bus dipcef locational',
      },
      {
        slug: 'regional-split',
        label: 'Regional split',
        hint: 'How the solved dispatch divides across the three grids',
        nav: { kind: 'sol', id: 'regions' },
        live: true,
        alias: 'luzon visayas mindanao regions',
      },
    ],
  },
  {
    id: 'prices',
    label: 'Prices and bills',
    dests: [
      {
        slug: 'bill-impact',
        label: 'Bill impact',
        hint: 'What a WESM move does to a Meralco household bill',
        nav: { kind: 'analysis', id: 'bill' },
        alias: 'meralco household generation charge pass through retail',
      },
      {
        slug: 'capture-prices',
        label: 'Capture prices',
        hint: 'What each fuel earns against the average, by shape',
        nav: { kind: 'analysis', id: 'capture' },
        scoped: true,
        alias: 'capture rate solar cannibalisation revenue',
      },
      {
        slug: 'forward-prices',
        label: 'Forward prices',
        hint: 'The forward band the archive window supports',
        nav: { kind: 'analysis', id: 'forward' },
        scoped: true,
        alias: 'futures band forecast curve',
      },
      {
        slug: 'market-power',
        label: 'Market power',
        hint: 'How concentrated the clearing stack is, and who cannot be replaced',
        nav: { kind: 'analysis', id: 'market' },
        alias: 'hhi concentration supplier residual supply index rsi',
      },
      {
        slug: 'reserve-market',
        label: 'Reserve market',
        hint: 'What co-clearing reserves costs the energy price',
        nav: { kind: 'analysis', id: 'reserve' },
        scoped: true,
        alias: 'ancillary services co-clear regulating',
      },
      {
        slug: 'emissions',
        label: 'Emissions',
        hint: 'Tonnes per hour from the solved stack, and what a carbon price moves',
        nav: { kind: 'analysis', id: 'emissions' },
        alias: 'carbon co2 intensity',
      },
    ],
  },
  {
    id: 'buildout',
    label: 'The build-out',
    dests: [
      {
        slug: 'long-term',
        label: 'Long-term',
        hint: 'Capacity the long horizon needs, against the announced pipeline',
        nav: { kind: 'phase', id: 'lt' },
        alias: 'lt plan capacity expansion horizon',
      },
      {
        slug: 'expansion-mix',
        label: 'Expansion mix',
        hint: 'Which technology the least-cost build picks, and why',
        nav: { kind: 'analysis', id: 'expansion' },
        alias: 'build new entry technology screening',
      },
      {
        slug: 'multi-year-path',
        label: 'Multi-year path',
        hint: 'The price and margin path across years, not one day',
        nav: { kind: 'analysis', id: 'multiyear' },
        alias: 'trajectory 2028 2030 path',
      },
      {
        slug: 'portfolio',
        label: 'Portfolio',
        hint: 'What one owner holds, and what it earns',
        nav: { kind: 'analysis', id: 'portfolio' },
        alias: 'owner company fleet revenue',
      },
    ],
  },
  {
    id: 'scenarios',
    label: 'My scenarios',
    dests: [
      {
        slug: 'quick-scenario',
        label: 'Quick scenario',
        hint: 'Drag a lever, the three grids re-clear live, no Run needed',
        nav: { kind: 'quick' },
        live: true,
        alias: 'lever slider what if simulate add data center storage',
      },
      {
        slug: 'compare',
        label: 'Compare scenarios',
        hint: 'Two scenarios side by side, property by property',
        nav: { kind: 'compare' },
        live: true,
        alias: 'diff side by side versus',
      },
      {
        slug: 'saved-runs',
        label: 'Saved runs',
        hint: 'Runs kept in this browser, ready to restore',
        nav: { kind: 'runs' },
        alias: 'history restore bookmark',
      },
      {
        slug: 'cross-run',
        label: 'Cross-run',
        hint: 'One measure tracked across every saved run',
        nav: { kind: 'analysis', id: 'crossrun' },
        alias: 'across runs comparison trend',
      },
      {
        slug: 'ensembles',
        label: 'Ensembles',
        hint: 'Many draws of the same scenario, and the spread they give',
        nav: { kind: 'analysis', id: 'ensemble' },
        alias: 'sampling uncertainty draws band',
      },
    ],
  },
  {
    id: 'trust',
    label: 'Is the model right',
    dests: [
      {
        slug: 'backcast',
        label: 'Backcast',
        hint: 'Every market day replayed against the observed price',
        nav: { kind: 'analysis', id: 'backcast' },
        scoped: true,
        alias: 'validation mae bias correlation calibration proof',
      },
      {
        slug: 'loss-validation',
        label: 'Loss validation',
        hint: 'Whether the loss surface reproduces the observed nodal spread',
        nav: { kind: 'analysis', id: 'lossval' },
        alias: 'losses surface nodal check',
      },
      {
        slug: 'assumptions',
        label: 'Assumptions',
        hint: 'Every constant, its source, and the date it was read',
        nav: { kind: 'analysis', id: 'vintage' },
        alias: 'vintage sources provenance constants methodology',
      },
    ],
  },
  {
    id: 'inputs',
    label: 'Model inputs',
    dests: [
      {
        slug: 'generators',
        label: 'Generators',
        hint: 'Every sourced unit: capacity, fuel price, forced outage',
        nav: { kind: 'class', id: 'generator' },
        alias: 'plants units fleet capacity',
      },
      {
        slug: 'fuels',
        label: 'Fuels',
        hint: 'Fuel prices and how much of each is available per grid',
        nav: { kind: 'class', id: 'fuel' },
        alias: 'coal gas hydro price availability',
      },
      {
        slug: 'interfaces',
        label: 'Interfaces',
        hint: 'The corridor flow limits the solve must respect',
        nav: { kind: 'class', id: 'interface' },
        alias: 'links limits hvdc transfer',
      },
      {
        slug: 'regions',
        label: 'Regions',
        hint: 'Evening load and peak for each of the three grids',
        nav: { kind: 'class', id: 'region' },
        alias: 'demand load peak',
      },
      {
        slug: 'storage',
        label: 'Storage',
        hint: 'Battery power and energy on each grid',
        nav: { kind: 'class', id: 'storage' },
        alias: 'battery bess discharge',
      },
    ],
  },
]

export const ALL_DESTS: Dest[] = GROUPS.flatMap((g) => g.dests)

const BY_SLUG = new Map(ALL_DESTS.map((d) => [d.slug, d]))

export function destBySlug(slug: string): Dest | undefined {
  return BY_SLUG.get(slug)
}

export function destOf(nav: Nav): Dest | undefined {
  return ALL_DESTS.find((d) => sameNav(d.nav, nav))
}

export function groupOf(nav: Nav): Group | undefined {
  return GROUPS.find((g) => g.dests.some((d) => sameNav(d.nav, nav)))
}

export function sameNav(a: Nav, b: Nav): boolean {
  if (a.kind !== b.kind) return false
  return 'id' in a && 'id' in b ? a.id === b.id : true
}

/** The phase the status bar reports. Only two navs carry their own phase. */
export function phaseOf(nav: Nav): string {
  if (nav.kind === 'phase') return nav.id === 'lt' ? 'Long-term' : 'Adequacy'
  return 'Short-term'
}

// --- deep links -------------------------------------------------------------
// A scenario share already owns `#m=<payload>`; the view slug rides beside it
// as `v=<slug>` so both survive the same link. Any of the 39 destinations is
// now addressable, which is what makes "look at the Visayas backcast" sendable.

export function readHashView(hash: string): { slug?: string; grid?: string } {
  const v = /[#&]v=([a-z0-9-]+)/i.exec(hash)
  const g = /[#&]g=(luzon|visayas|mindanao)/i.exec(hash)
  return { slug: v?.[1], grid: g?.[1]?.toLowerCase() }
}

export function writeHashView(slug: string, grid?: string) {
  const cur = window.location.hash
  const keep = cur.replace(/^#/, '').split('&')
  const rest = keep.filter((p) => p && !/^v=/.test(p) && !/^g=/.test(p))
  const parts = [`v=${slug}`, ...(grid ? [`g=${grid}`] : []), ...rest]
  const next = `#${parts.join('&')}`
  if (next === cur) return
  // a new view is a place the reader can go Back from; a region switch inside
  // the same view is not, or Back would walk one grid at a time
  const moved = readHashView(cur).slug !== slug
  if (moved) window.history.pushState(null, '', next)
  else window.history.replaceState(null, '', next)
}

/** Rank destinations against a palette query. Empty query keeps source order. */
export function searchDests(q: string): Dest[] {
  const t = q.trim().toLowerCase()
  if (!t) return ALL_DESTS
  const scored: Array<[number, Dest]> = []
  for (const d of ALL_DESTS) {
    const label = d.label.toLowerCase()
    const hay = `${label} ${d.hint.toLowerCase()} ${d.alias ?? ''}`
    let score = 0
    if (label.startsWith(t)) score = 100
    else if (label.includes(t)) score = 70
    else if (hay.includes(t)) score = 40
    else if (t.split(/\s+/).every((w) => hay.includes(w))) score = 20
    if (score) scored.push([score, d])
  }
  return scored
    .sort((a, b) => b[0] - a[0] || a[1].label.localeCompare(b[1].label))
    .map((x) => x[1])
}
