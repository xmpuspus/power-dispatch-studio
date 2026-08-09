// The studio groups its 42 views by the questions users ask about the market.
// Each destination keeps its existing Nav value so the view routing stays stable.

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
  | 'commitment'
  | 'futureyear'
  | 'contracts'
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
    label: "How today's market clears",
    dests: [
      {
        slug: 'chronology',
        label: 'Hourly market replay',
        hint: 'Every hour of one recorded day, three grids cleared together',
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
        label: 'Lowest-cost-first dispatch (merit order)',
        hint: 'Which plants run, from the cheapest through the price-setting unit',
        nav: { kind: 'sol', id: 'merit' },
        live: true,
        scoped: true,
        alias: 'supply curve stack dispatch',
      },
      {
        slug: 'marginal-units',
        label: 'Marginal units',
        hint: 'The price-setting plant and its frequency',
        nav: { kind: 'sol', id: 'marginal' },
        scoped: true,
        alias: 'price setter frequency',
      },
      {
        slug: 'native-week',
        label: 'Inter-day storage (168 hours)',
        hint: '168 hours solved as one program, storage carried across midnight',
        nav: { kind: 'analysis', id: 'week' },
        scoped: true,
        alias: '168 hour weekly lp',
      },
    ],
  },
  {
    id: 'headroom',
    label: 'Can supply cover demand',
    dests: [
      {
        slug: 'reliability',
        label: 'Power-shortfall risk',
        hint: 'Chance of a shortfall (LOLP) across simulated random plant outages',
        nav: { kind: 'sol', id: 'reliability' },
        live: true,
        alias: 'lolp monte carlo outage risk',
      },
      {
        slug: 'adequacy',
        label: 'Supply after scheduled outages',
        hint: 'Whether supply covers demand across the outage schedule',
        nav: { kind: 'phase', id: 'pasa' },
        alias: 'pasa margin outlook',
      },
      {
        slug: 'n-1',
        label: 'Loss of one major unit (N-1)',
        hint: 'What the price does when any one unit trips at the evening peak',
        nav: { kind: 'sol', id: 'n1' },
        live: true,
        scoped: true,
        alias: 'trip sual contingency largest unit',
      },
      {
        slug: 'load-sweep',
        label: 'Price as demand grows',
        hint: 'Price against demand, swept across the whole range',
        nav: { kind: 'sol', id: 'sweep' },
        live: true,
        scoped: true,
        alias: 'demand curve sensitivity',
      },
      {
        slug: 'window-band',
        label: 'Price range across recorded days',
        hint: 'The price band the model produces when it replays every recorded day',
        nav: { kind: 'sol', id: 'distribution' },
        live: true,
        scoped: true,
        alias: 'distribution spread percentile',
      },
      {
        slug: 'price-duration',
        label: 'Hours above each price',
        hint: 'Hours at or above each price, sorted',
        nav: { kind: 'sol', id: 'duration' },
        scoped: true,
        alias: 'duration curve exceedance',
      },
    ],
  },
  {
    id: 'siting',
    label: 'Where new demand can connect',
    dests: [
      {
        slug: 'siting',
        label: 'Siting a new load',
        hint: 'Hourly load a named site can draw through its own lines',
        nav: { kind: 'analysis', id: 'sites' },
        scoped: true,
        alias: 'data center site pax silica connect headroom',
      },
      {
        slug: 'coupled-flows',
        label: 'Power between island grids',
        hint: 'What moves over the high-voltage direct-current links and when a link reaches its limit',
        nav: { kind: 'sol', id: 'flows' },
        live: true,
        alias: 'hvdc corridor interconnector leyte',
      },
      {
        slug: 'nodal-prices',
        label: 'Prices at grid connection points (nodal prices)',
        hint: 'How each connection point differs from its regional price',
        nav: { kind: 'analysis', id: 'nodal' },
        scoped: true,
        alias: 'lmp bus dipcef locational',
      },
      {
        slug: 'regional-split',
        label: 'Generation by island grid',
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
        hint: 'How a spot-price change in WESM affects a Meralco household bill',
        nav: { kind: 'analysis', id: 'bill' },
        alias: 'meralco household generation charge pass through retail',
      },
      {
        slug: 'contract-position',
        label: 'Your contract position',
        hint: 'What a scenario does to a book of contracts, in pesos',
        nav: { kind: 'analysis', id: 'contracts' },
        alias: 'ppa psa hedge settlement position exposure retail supplier book strike',
      },
      {
        slug: 'capture-prices',
        label: 'Average price earned by each technology (capture price)',
        hint: 'What each technology earns compared with the market average',
        nav: { kind: 'analysis', id: 'capture' },
        scoped: true,
        alias: 'capture rate solar cannibalisation revenue',
      },
      {
        slug: 'forward-prices',
        label: 'Possible future price range',
        hint: 'The forward band the archive window supports',
        nav: { kind: 'analysis', id: 'forward' },
        scoped: true,
        alias: 'futures band forecast curve',
      },
      {
        slug: 'market-power',
        label: 'Supplier concentration and market power',
        hint: 'How much capacity the largest suppliers control and whether the grid can replace them',
        nav: { kind: 'analysis', id: 'market' },
        alias: 'hhi concentration supplier residual supply index rsi',
      },
      {
        slug: 'reserve-market',
        label: 'Backup capacity market (reserves)',
        hint: 'How buying backup capacity with energy affects the energy price',
        nav: { kind: 'analysis', id: 'reserve' },
        scoped: true,
        alias: 'ancillary services co-clear regulating',
      },
      {
        slug: 'emissions',
        label: 'Emissions',
        hint: 'Solved tonnes per hour plus the carbon-price effect',
        nav: { kind: 'analysis', id: 'emissions' },
        alias: 'carbon co2 intensity',
      },
    ],
  },
  {
    id: 'buildout',
    label: 'What new capacity is needed',
    dests: [
      {
        slug: 'long-term',
        label: 'Long-term supply plan',
        hint: 'Capacity needed over time compared with announced projects',
        nav: { kind: 'phase', id: 'lt' },
        alias: 'lt plan capacity expansion horizon',
      },
      {
        slug: 'expansion-mix',
        label: 'Lowest-cost expansion mix',
        hint: 'Technology chosen by the least-cost build and its cost basis',
        nav: { kind: 'analysis', id: 'expansion' },
        alias: 'build new entry technology screening',
      },
      {
        slug: 'future-year',
        label: 'A whole year, solved',
        hint: 'Every date in a target year, on the published demand path and build list',
        nav: { kind: 'analysis', id: 'futureyear' },
        scoped: true,
        alias: '8760 annual 2028 chronology year run planning horizon',
      },
      {
        slug: 'multi-year-path',
        label: 'Prices and spare capacity by year',
        hint: 'The price and margin path across years',
        nav: { kind: 'analysis', id: 'multiyear' },
        alias: 'trajectory 2028 2030 path',
      },
      {
        slug: 'portfolio',
        label: 'Generator portfolio value',
        hint: 'Assets and earnings for one owner',
        nav: { kind: 'analysis', id: 'portfolio' },
        alias: 'owner company fleet revenue',
      },
    ],
  },
  {
    id: 'scenarios',
    label: 'Build and compare scenarios',
    dests: [
      {
        slug: 'quick-scenario',
        label: 'Quick what-if',
        hint: 'Move a slider and all three grids recalculate immediately',
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
        label: 'Saved simulation runs',
        hint: 'Runs kept in this browser, ready to restore',
        nav: { kind: 'runs' },
        alias: 'history restore bookmark',
      },
      {
        slug: 'cross-run',
        label: 'Compare one measure across runs',
        hint: 'One measure tracked across every saved run',
        nav: { kind: 'analysis', id: 'crossrun' },
        alias: 'across runs comparison trend',
      },
      {
        slug: 'ensembles',
        label: 'Range across repeated simulations',
        hint: 'Repeated simulations of one scenario and the range of results',
        nav: { kind: 'analysis', id: 'ensemble' },
        alias: 'sampling uncertainty draws band',
      },
    ],
  },
  {
    id: 'trust',
    label: 'Check the model against market records',
    dests: [
      {
        slug: 'backcast',
        label: 'Historical replay',
        hint: 'Every market day replayed against the observed price',
        nav: { kind: 'analysis', id: 'backcast' },
        scoped: true,
        alias: 'validation mae bias correlation historical comparison',
      },
      {
        slug: 'loss-validation',
        label: 'Transmission-loss check',
        hint: 'Whether estimated transmission losses reproduce recorded price differences between connection points',
        nav: { kind: 'analysis', id: 'lossval' },
        alias: 'losses surface nodal check',
      },
      {
        slug: 'commitment-test',
        label: 'Unit-commitment test',
        hint: 'What happened when each thermal block had to commit and hold a floor',
        nav: { kind: 'analysis', id: 'commitment' },
        alias: 'uc mixed integer milp minimum stable start cost why linear',
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
    label: 'Review and edit model inputs',
    dests: [
      {
        slug: 'generators',
        label: 'Generators',
        hint: 'Each sourced unit and its capacity, fuel price, and random-outage rate',
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
        label: 'Inter-grid links',
        hint: 'The power-flow limits between island grids',
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
// as `v=<slug>` so both survive the same link. Any of the 42 destinations is
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
