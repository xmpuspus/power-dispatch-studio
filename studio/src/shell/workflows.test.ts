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
    expect(ALL_DESTS).toHaveLength(26)
    expect(workspaceCoverage(ALL_DESTS.map((dest) => dest.slug))).toEqual({
      missing: [],
      duplicates: [],
    })
  })

  it('routes representative analyst tasks without exposing model categories', () => {
    expect(workspaceForSlug('chronology')?.label).toBe('Market day')
    expect(workspaceForSlug('quick-scenario')?.label).toBe('Planning and scenarios')
    expect(workspaceForSlug('adequacy')?.label).toBe('Supply and risk')
    expect(workspaceForSlug('siting')?.label).toBe('Grid and connection')
    expect(workspaceForSlug('contract-position')?.label).toBe('Prices and exposure')
    expect(workspaceForSlug('long-term')?.label).toBe('Planning and scenarios')
    expect(workspaceForSlug('model-inputs')?.label).toBe('Model and data')
    expect(WORKSPACES.map((workspace) => workspace.label)).toEqual([
      'Market day',
      'Supply and risk',
      'Grid and connection',
      'Prices and exposure',
      'Planning and scenarios',
      'Model and data',
    ])
  })

  it('keeps old deep links useful without showing retired views', () => {
    expect(ALL_DESTS.map((dest) => dest.slug)).not.toContain('regional-split')
    expect(ALL_DESTS.map((dest) => dest.slug)).not.toContain('ensembles')
    expect(ALL_DESTS.map((dest) => dest.slug)).not.toContain('expansion-mix')
    expect(ALL_DESTS.map((dest) => dest.slug)).not.toContain('commitment-test')
  })
})

describe('evidence states', () => {
  it('separates records, replays, scenarios, and assumptions', () => {
    expect(EVIDENCE_LABELS).toEqual({
      recorded: 'Recorded',
      derived: 'Derived from records',
      replayed: 'Model replay',
      scenario: 'Scenario result',
      assumed: 'Assumption',
      mixed: 'Recorded and modeled',
    })
    expect(evidenceForSlug('five-minute-replay').kind).toBe('replayed')
    expect(evidenceForSlug('explain-a-day').kind).toBe('mixed')
    expect(evidenceForSlug('market-power').kind).toBe('derived')
    expect(evidenceForSlug('backcast').kind).toBe('replayed')
    expect(evidenceForSlug('quick-scenario').kind).toBe('scenario')
    expect(evidenceForSlug('model-inputs').kind).toBe('assumed')
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
