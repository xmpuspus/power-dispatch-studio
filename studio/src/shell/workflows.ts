export type WorkspaceId =
  | 'market-day'
  | 'scenario-analysis'
  | 'supply-risk'
  | 'connection-study'
  | 'prices-exposure'
  | 'planning'
  | 'model-data'

export type Workspace = {
  id: WorkspaceId
  label: string
  summary: string
  primary: string
  slugs: string[]
  utility?: boolean
}

export const DEFAULT_DESTINATION = 'chronology'

export const WORKSPACES: Workspace[] = [
  {
    id: 'market-day',
    label: 'Market day',
    summary: 'Review one recorded day, then check the model replay.',
    primary: 'chronology',
    slugs: [
      'chronology',
      'explain-a-day',
      'five-minute-replay',
      'merit-order',
      'marginal-units',
      'native-week',
    ],
  },
  {
    id: 'scenario-analysis',
    label: 'Scenario analysis',
    summary: 'Change the base case, run it, and compare the result.',
    primary: 'quick-scenario',
    slugs: ['quick-scenario', 'compare', 'saved-runs', 'cross-run', 'ensembles'],
  },
  {
    id: 'supply-risk',
    label: 'Supply risk',
    summary: 'Check outages, reserves, contingencies, and shortfall risk.',
    primary: 'adequacy',
    slugs: [
      'adequacy',
      'reliability',
      'n-1',
      'load-sweep',
      'window-band',
      'price-duration',
    ],
  },
  {
    id: 'connection-study',
    label: 'Connection study',
    summary: 'Check a site against grid limits, transfers, and regional prices.',
    primary: 'siting',
    slugs: ['siting', 'coupled-flows', 'nodal-prices', 'regional-split'],
  },
  {
    id: 'prices-exposure',
    label: 'Prices and exposure',
    summary: 'Review price effects on bills, contracts, technologies, and suppliers.',
    primary: 'contract-position',
    slugs: [
      'contract-position',
      'bill-impact',
      'capture-prices',
      'forward-prices',
      'market-power',
      'reserve-market',
      'emissions',
    ],
  },
  {
    id: 'planning',
    label: 'Planning',
    summary: 'Test future demand, new capacity, and portfolio outcomes.',
    primary: 'long-term',
    slugs: ['long-term', 'expansion-mix', 'future-year', 'multi-year-path', 'portfolio'],
  },
  {
    id: 'model-data',
    label: 'Model and data',
    summary: 'Review replay accuracy, assumptions, and editable inputs.',
    primary: 'backcast',
    utility: true,
    slugs: [
      'backcast',
      'loss-validation',
      'commitment-test',
      'assumptions',
      'generators',
      'fuels',
      'interfaces',
      'regions',
      'storage',
    ],
  },
]

export function workspaceForSlug(slug: string): Workspace | undefined {
  return WORKSPACES.find((workspace) => workspace.slugs.includes(slug))
}

export function workspaceCoverage(slugs: string[]) {
  const counts = new Map<string, number>()
  for (const workspace of WORKSPACES) {
    for (const slug of workspace.slugs) counts.set(slug, (counts.get(slug) ?? 0) + 1)
  }
  return {
    missing: slugs.filter((slug) => !counts.has(slug)).sort(),
    duplicates: slugs.filter((slug) => (counts.get(slug) ?? 0) > 1).sort(),
  }
}

export type EvidenceKind = 'recorded' | 'replayed' | 'scenario' | 'assumed'

export const EVIDENCE_LABELS: Record<EvidenceKind, string> = {
  recorded: 'Recorded',
  replayed: 'Model replay',
  scenario: 'Scenario result',
  assumed: 'Assumption',
}

export type Evidence = {
  kind: EvidenceKind
  source: string
  resolution: string
  note: string
}

const RECORDED = new Set([
  'explain-a-day',
  'five-minute-replay',
  'adequacy',
  'nodal-prices',
  'market-power',
])

const SCENARIO = new Set([
  'quick-scenario',
  'compare',
  'saved-runs',
  'cross-run',
  'ensembles',
  'siting',
  'bill-impact',
  'contract-position',
  'forward-prices',
  'long-term',
  'expansion-mix',
  'future-year',
  'multi-year-path',
  'portfolio',
])

const ASSUMED = new Set([
  'assumptions',
  'generators',
  'fuels',
  'interfaces',
  'regions',
  'storage',
])

const SCENARIO_REACTIVE = new Set([
  'chronology',
  'merit-order',
  'adequacy',
  'reliability',
  'n-1',
  'load-sweep',
  'window-band',
  'coupled-flows',
  'regional-split',
  'emissions',
  'contract-position',
])

export function evidenceForSlug(slug: string, hasScenarioEdits = false): Evidence {
  if (hasScenarioEdits && SCENARIO_REACTIVE.has(slug)) {
    return {
      kind: 'scenario',
      source: 'Recorded base case with your current edits',
      resolution: 'Depends on the open analysis',
      note: 'This result changes when the scenario is run.',
    }
  }
  if (RECORDED.has(slug)) {
    return {
      kind: 'recorded',
      source: 'IEMOP public market records',
      resolution:
        slug === 'five-minute-replay'
          ? '5-minute dispatch intervals'
          : 'Published record',
      note: 'The screen reads published or directly derived market records.',
    }
  }
  if (SCENARIO.has(slug)) {
    return {
      kind: 'scenario',
      source: 'Power Dispatch Studio calculation',
      resolution: 'Scenario output',
      note: 'This is a calculated case, not a published market result.',
    }
  }
  if (ASSUMED.has(slug)) {
    return {
      kind: 'assumed',
      source: 'Sourced model input and stated assumptions',
      resolution: 'Model input',
      note: 'Open Assumptions for the source, date, and treatment of each value.',
    }
  }
  return {
    kind: 'replayed',
    source: 'IEMOP records replayed by Power Dispatch Studio',
    resolution: 'Calculated from the archive',
    note: 'The model result is shown separately from the recorded market value.',
  }
}

export type GlossaryEntry = {
  acronym: string
  term: string
  definition: string
}

export const GLOSSARY: GlossaryEntry[] = [
  {
    acronym: 'WESM',
    term: 'Wholesale Electricity Spot Market',
    definition: 'The Philippine market for spot electricity and reserve transactions.',
  },
  {
    acronym: 'RTD',
    term: 'Real-time dispatch',
    definition:
      'The market schedule and price calculated for each five-minute dispatch interval.',
  },
  {
    acronym: 'LWAP',
    term: 'Load-weighted average price',
    definition:
      'An average price weighted by the electricity bought at each location or interval.',
  },
  {
    acronym: 'MCP',
    term: 'Market clearing price',
    definition:
      'The price produced by the market clearing calculation before later settlement adjustments.',
  },
  {
    acronym: 'HVDC',
    term: 'High-voltage direct current',
    definition:
      'The inter-island links that transfer power between the Luzon, Visayas, and Mindanao grids.',
  },
  {
    acronym: 'LOLP',
    term: 'Loss of load probability',
    definition:
      'The probability of a supply shortfall when available generation cannot meet demand.',
  },
  {
    acronym: 'PASA',
    term: 'Projected assessment of system adequacy',
    definition:
      'An outlook comparing expected demand with available generation after scheduled outages.',
  },
  {
    acronym: 'N-1',
    term: 'Single-contingency test',
    definition:
      'A check of the system after one major generator or network element is removed.',
  },
  {
    acronym: 'HHI',
    term: 'Herfindahl-Hirschman Index',
    definition: 'A concentration measure calculated from supplier market shares.',
  },
]

export function glossarySearch(query: string): GlossaryEntry[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return GLOSSARY
  const words = needle.split(/\s+/)
  return GLOSSARY.filter((entry) => {
    const haystack = `${entry.acronym} ${entry.term} ${entry.definition}`.toLowerCase()
    return words.every((word) => haystack.includes(word))
  })
}
