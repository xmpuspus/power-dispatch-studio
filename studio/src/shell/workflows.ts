export type WorkspaceId =
  | 'market-day'
  | 'supply-risk'
  | 'grid-connection'
  | 'prices-exposure'
  | 'planning-scenarios'
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
      'backcast',
    ],
  },
  {
    id: 'supply-risk',
    label: 'Supply and risk',
    summary: 'Check outages, demand thresholds, and shortfall risk.',
    primary: 'adequacy',
    slugs: ['adequacy', 'reliability', 'load-sweep', 'window-band'],
  },
  {
    id: 'grid-connection',
    label: 'Grid and connection',
    summary: 'Screen a site and review recorded and modeled grid transfers.',
    primary: 'siting',
    slugs: ['siting', 'coupled-flows', 'nodal-prices'],
  },
  {
    id: 'prices-exposure',
    label: 'Prices and exposure',
    summary: 'Review price effects on bills, contracts, technologies, and suppliers.',
    primary: 'contract-position',
    slugs: [
      'contract-position',
      'capture-prices',
      'market-power',
      'reserve-market',
      'emissions',
      'portfolio',
    ],
  },
  {
    id: 'planning-scenarios',
    label: 'Planning and scenarios',
    summary: 'Change inputs, compare cases, and review future demand sensitivity.',
    primary: 'quick-scenario',
    slugs: [
      'forward-prices',
      'long-term',
      'native-week',
      'quick-scenario',
      'compare',
      'saved-runs',
    ],
  },
  {
    id: 'model-data',
    label: 'Model and data',
    summary: 'Review validation, sources, and editable inputs.',
    primary: 'model-inputs',
    utility: true,
    slugs: ['loss-validation', 'model-inputs'],
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

export type EvidenceKind =
  'recorded' | 'derived' | 'replayed' | 'scenario' | 'assumed' | 'mixed'

export const EVIDENCE_LABELS: Record<EvidenceKind, string> = {
  recorded: 'Recorded',
  derived: 'Derived from records',
  replayed: 'Model replay',
  scenario: 'Scenario result',
  assumed: 'Assumption',
  mixed: 'Recorded and modeled',
}

export type Evidence = {
  kind: EvidenceKind
  source: string
  resolution: string
  note: string
}

const RECORDED = new Set(['reserve-market'])

const DERIVED = new Set(['market-power', 'loss-validation'])

const MIXED = new Set([
  'chronology',
  'explain-a-day',
  'adequacy',
  'coupled-flows',
  'nodal-prices',
])

const SCENARIO = new Set([
  'quick-scenario',
  'compare',
  'siting',
  'contract-position',
  'forward-prices',
  'long-term',
  'portfolio',
  'native-week',
  'saved-runs',
])

const ASSUMED = new Set(['model-inputs'])

const SCENARIO_REACTIVE = new Set([
  'chronology',
  'merit-order',
  'adequacy',
  'reliability',
  'load-sweep',
  'window-band',
  'coupled-flows',
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
      resolution: 'Published market record',
      note: 'Values in this screen come from the cited market records.',
    }
  }
  if (DERIVED.has(slug)) {
    return {
      kind: 'derived',
      source: 'Published records, calculated measures',
      resolution: 'Derived statistic',
      note: 'The source values are published records; the displayed measure is calculated.',
    }
  }
  if (MIXED.has(slug)) {
    return {
      kind: 'mixed',
      source: 'IEMOP records beside a labeled model calculation',
      resolution: 'Depends on the panel',
      note: 'Recorded and modeled values are labeled separately in this screen.',
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
