import { describe, expect, it } from 'vitest'
import { ALL_DESTS } from './nav'
import {
  DEFAULT_DESTINATION,
  EVIDENCE_LABELS,
  WORKSPACES,
  evidenceForSlug,
  glossarySearch,
  workspaceCoverage,
  workspaceForSlug,
} from './workflows'

describe('analyst workspaces', () => {
  it('opens on the recorded market-day workflow', () => {
    expect(DEFAULT_DESTINATION).toBe('chronology')
    expect(workspaceForSlug(DEFAULT_DESTINATION)?.label).toBe('Market day')
  })

  it('puts each current destination in one workspace or the model-and-data library', () => {
    expect(ALL_DESTS).toHaveLength(42)
    expect(workspaceCoverage(ALL_DESTS.map((dest) => dest.slug))).toEqual({
      missing: [],
      duplicates: [],
    })
  })

  it('routes representative analyst tasks without exposing model categories', () => {
    expect(workspaceForSlug('chronology')?.label).toBe('Market day')
    expect(workspaceForSlug('quick-scenario')?.label).toBe('Scenario analysis')
    expect(workspaceForSlug('adequacy')?.label).toBe('Supply risk')
    expect(workspaceForSlug('siting')?.label).toBe('Connection study')
    expect(workspaceForSlug('contract-position')?.label).toBe('Prices and exposure')
    expect(workspaceForSlug('future-year')?.label).toBe('Planning')
    expect(workspaceForSlug('assumptions')?.label).toBe('Model and data')
    expect(WORKSPACES.map((workspace) => workspace.label)).toEqual([
      'Market day',
      'Scenario analysis',
      'Supply risk',
      'Connection study',
      'Prices and exposure',
      'Planning',
      'Model and data',
    ])
  })
})

describe('evidence states', () => {
  it('separates records, replays, scenarios, and assumptions', () => {
    expect(EVIDENCE_LABELS).toEqual({
      recorded: 'Recorded',
      replayed: 'Model replay',
      scenario: 'Scenario result',
      assumed: 'Assumption',
    })
    expect(evidenceForSlug('five-minute-replay').kind).toBe('recorded')
    expect(evidenceForSlug('backcast').kind).toBe('replayed')
    expect(evidenceForSlug('quick-scenario').kind).toBe('scenario')
    expect(evidenceForSlug('assumptions').kind).toBe('assumed')
  })

  it('does not label a fixed replay as a scenario after unrelated edits', () => {
    expect(evidenceForSlug('chronology', true).kind).toBe('scenario')
    expect(evidenceForSlug('backcast', true).kind).toBe('replayed')
  })
})

describe('market glossary', () => {
  it('finds both an acronym and its expanded market term', () => {
    expect(glossarySearch('LWAP')[0]).toMatchObject({
      acronym: 'LWAP',
      term: 'Load-weighted average price',
    })
    expect(glossarySearch('high-voltage')[0]).toMatchObject({ acronym: 'HVDC' })
    expect(glossarySearch('shortfall probability')[0]).toMatchObject({ acronym: 'LOLP' })
  })
})
