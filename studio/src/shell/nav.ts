// The studio exposes one destination per analyst task. Technical probes and
// duplicate charts stay in methodology or inside the task that uses them.

export type SolId =
  'merit' | 'chrono' | 'sweep' | 'distribution' | 'flows' | 'reliability'
export type AnalysisId =
  | 'reserve'
  | 'market'
  | 'backcast'
  | 'explain'
  | 'emissions'
  | 'capture'
  | 'portfolio'
  | 'rtdoe5'
  | 'forward'
  | 'week'
  | 'nodal'
  | 'sites'
  | 'lossval'
  | 'contracts'
  | 'inputs'
export type PhaseId = 'lt' | 'pasa'

export type Nav =
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
  /** consumes the shared recorded market date and selected hour */
  dateContext?: boolean
  /** consumes the active scenario and its solved result */
  scenarioContext?: boolean
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
    id: 'market-day',
    label: 'Market day',
    dests: [
      {
        slug: 'chronology',
        label: 'Hourly market replay',
        hint: 'Every hour of one recorded day, three grids cleared together',
        nav: { kind: 'sol', id: 'chrono' },
        live: true,
        scoped: true,
        dateContext: true,
        scenarioContext: true,
        alias: 'hourly clearing price day week short-term',
      },
      {
        slug: 'explain-a-day',
        label: 'Explain a day',
        hint: 'What set the price on a chosen day, hour by hour',
        nav: { kind: 'analysis', id: 'explain' },
        scoped: true,
        dateContext: true,
        alias: 'driver why price spike',
      },
      {
        slug: 'five-minute-replay',
        label: '5-minute dispatch replay',
        hint: 'Published five-minute dispatch intervals compared with the replay',
        nav: { kind: 'analysis', id: 'rtdoe5' },
        scoped: true,
        dateContext: true,
        alias: 'rtd rtdoe interval real time',
      },
      {
        slug: 'merit-order',
        label: 'Supply stack and marginal block',
        hint: 'Which fuel blocks run and which block sets the modeled price',
        nav: { kind: 'sol', id: 'merit' },
        live: true,
        scoped: true,
        scenarioContext: true,
        alias: 'supply curve stack dispatch',
      },
      {
        slug: 'backcast',
        label: 'Replay accuracy',
        hint: 'Recorded prices and flows compared with the cost and offer replays',
        nav: { kind: 'analysis', id: 'backcast' },
        scoped: true,
        dateContext: true,
        alias: 'validation mae bias correlation historical comparison',
      },
    ],
  },
  {
    id: 'supply-risk',
    label: 'Supply and risk',
    dests: [
      {
        slug: 'reliability',
        label: 'Power-shortfall risk',
        hint: 'Chance that demand exceeds supply across repeated random-outage cases',
        nav: { kind: 'sol', id: 'reliability' },
        live: true,
        scoped: true,
        scenarioContext: true,
        alias: 'lolp monte carlo outage risk',
      },
      {
        slug: 'adequacy',
        label: 'Supply after scheduled outages',
        hint: 'Whether supply covers demand across the outage schedule',
        nav: { kind: 'phase', id: 'pasa' },
        dateContext: true,
        scenarioContext: true,
        alias: 'pasa margin outlook',
      },
      {
        slug: 'load-sweep',
        label: 'Price as demand grows',
        hint: 'Price against demand, swept across the whole range',
        nav: { kind: 'sol', id: 'sweep' },
        live: true,
        scoped: true,
        scenarioContext: true,
        alias: 'demand curve sensitivity',
      },
      {
        slug: 'window-band',
        label: 'Price range across recorded days',
        hint: 'The price band the model produces when it replays every recorded day',
        nav: { kind: 'sol', id: 'distribution' },
        live: true,
        scoped: true,
        scenarioContext: true,
        alias: 'distribution spread percentile',
      },
    ],
  },
  {
    id: 'grid-connection',
    label: 'Grid and connection',
    dests: [
      {
        slug: 'siting',
        label: 'Site headroom check',
        hint: 'Recorded and estimated site headroom, with unavailable line limits marked',
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
        dateContext: true,
        scenarioContext: true,
        alias: 'hvdc corridor interconnector leyte',
      },
      {
        slug: 'nodal-prices',
        label: 'Recorded connection-point price differences',
        hint: 'Observed price differences from each island grid reference price',
        nav: { kind: 'analysis', id: 'nodal' },
        scoped: true,
        alias: 'bus dipcef connection point locational',
      },
    ],
  },
  {
    id: 'prices-exposure',
    label: 'Prices and exposure',
    dests: [
      {
        slug: 'contract-position',
        label: 'Contract position',
        hint: 'What a scenario does to a book of contracts, in pesos',
        nav: { kind: 'analysis', id: 'contracts' },
        dateContext: true,
        scenarioContext: true,
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
        slug: 'market-power',
        label: 'Supplier concentration',
        hint: 'Published national capacity shares and concentration measures',
        nav: { kind: 'analysis', id: 'market' },
        alias: 'hhi concentration supplier ownership share',
      },
      {
        slug: 'reserve-market',
        label: 'Reserve market',
        hint: 'Published reserve prices and the offer replay against final results',
        nav: { kind: 'analysis', id: 'reserve' },
        scoped: true,
        alias: 'ancillary services co-clear regulating',
      },
      {
        slug: 'emissions',
        label: 'Emissions',
        hint: 'Solved tonnes per hour plus the carbon-price effect',
        nav: { kind: 'analysis', id: 'emissions' },
        dateContext: true,
        scenarioContext: true,
        alias: 'carbon co2 intensity',
      },
      {
        slug: 'portfolio',
        label: 'Generator portfolio value',
        hint: 'Value a declared fuel-share position against a saved run',
        nav: { kind: 'analysis', id: 'portfolio' },
        alias: 'owner company fleet revenue',
      },
    ],
  },
  {
    id: 'planning-scenarios',
    label: 'Planning and scenarios',
    dests: [
      {
        slug: 'forward-prices',
        label: 'PDP demand-path price sensitivity',
        hint: 'Recorded days re-priced under the published demand path and stated ranges',
        nav: { kind: 'analysis', id: 'forward' },
        scoped: true,
        alias: 'future scenario range demand path',
      },
      {
        slug: 'long-term',
        label: 'Annual demand and supply outlook',
        hint: 'Published demand growth and project additions, with assumptions and limits',
        nav: { kind: 'phase', id: 'lt' },
        scoped: true,
        scenarioContext: true,
        alias: 'lt plan future year capacity horizon',
      },
      {
        slug: 'native-week',
        label: 'Inter-day storage test',
        hint: 'A 168-hour storage case with energy carried across midnight',
        nav: { kind: 'analysis', id: 'week' },
        scoped: true,
        alias: '168 hour weekly storage lp',
      },
      {
        slug: 'quick-scenario',
        label: 'Scenario builder',
        hint: 'Change load, fuel cost, fuel availability, or transfer capacity',
        nav: { kind: 'quick' },
        live: true,
        scenarioContext: true,
        alias: 'lever slider what if simulate add data center storage',
      },
      {
        slug: 'compare',
        label: 'Compare scenarios',
        hint: 'Two scenarios side by side, property by property',
        nav: { kind: 'compare' },
        live: true,
        scenarioContext: true,
        alias: 'diff side by side versus',
      },
      {
        slug: 'saved-runs',
        label: 'Saved runs',
        hint: 'Runs kept in this browser, ready to restore',
        nav: { kind: 'runs' },
        alias: 'history restore bookmark',
      },
    ],
  },
  {
    id: 'model-data',
    label: 'Model and data',
    dests: [
      {
        slug: 'loss-validation',
        label: 'Transmission-loss check',
        hint: 'Whether estimated transmission losses reproduce recorded price differences between connection points',
        nav: { kind: 'analysis', id: 'lossval' },
        alias: 'losses surface nodal check',
      },
      {
        slug: 'model-inputs',
        label: 'Assumptions and model inputs',
        hint: 'Sources, dates, and editable plant, fuel, grid, link, and storage inputs',
        nav: { kind: 'analysis', id: 'inputs' },
        alias: 'vintage generators fuels interfaces regions storage provenance',
      },
    ],
  },
]

export const ALL_DESTS: Dest[] = GROUPS.flatMap((g) => g.dests)

const BY_SLUG = new Map(ALL_DESTS.map((d) => [d.slug, d]))

const LEGACY_SLUGS: Record<string, string> = {
  'marginal-units': 'merit-order',
  'n-1': 'reliability',
  'price-duration': 'window-band',
  'regional-split': 'chronology',
  'bill-impact': 'contract-position',
  'future-year': 'long-term',
  'expansion-mix': 'long-term',
  'multi-year-path': 'long-term',
  'cross-run': 'saved-runs',
  ensembles: 'saved-runs',
  'commitment-test': 'loss-validation',
  assumptions: 'model-inputs',
  generators: 'model-inputs',
  fuels: 'model-inputs',
  interfaces: 'model-inputs',
  regions: 'model-inputs',
  storage: 'model-inputs',
}

export function destBySlug(slug: string): Dest | undefined {
  return BY_SLUG.get(LEGACY_SLUGS[slug] ?? slug)
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
// as `v=<slug>` so both survive the same link. Retired destinations resolve to
// the task that now contains their useful content.

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
