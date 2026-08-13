import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Dispatch } from '../lib/types'
import { baseObjects, overrideKey, type Scenario } from './model'
import { buildResultContext, describeScenario } from './resultContext'

const dispatch: Dispatch = JSON.parse(
  readFileSync(
    fileURLToPath(new URL('../../public/data/dispatch.json', import.meta.url)),
    'utf8'
  )
)
const objects = baseObjects(dispatch, [])

describe('active assumption descriptions', () => {
  it('states the edited value and change from the sourced base', () => {
    const base = objects.region.find((row) => row.id === 'visayas')!.props
      .demand_mw as number
    const scenario: Scenario = {
      name: 'Visayas +4,000 MW stress test',
      overrides: {
        [overrideKey('region', 'visayas', 'demand_mw')]: base + 4000,
      },
    }
    expect(describeScenario(objects, scenario).map((item) => item.text)).toEqual([
      `Visayas modeled load ${Math.round(base + 4000).toLocaleString('en-US')} MW (+4,000 MW)`,
    ])
  })

  it('includes non-object run settings and source notes', () => {
    const scenario: Scenario = {
      name: 'Reserve holdback',
      overrides: {},
      settings: { reserveHoldback: true },
      sourceNotes: ['Average reserve requirements from the recorded window.'],
    }
    const items = describeScenario(objects, scenario)
    expect(items.map((item) => item.text).join(' ')).toContain(
      'Reserve requirements held back from energy clearing'
    )
  })
})

describe('result identity', () => {
  it('does not label recorded values as a model result', () => {
    const context = buildResultContext({
      evidenceKind: 'recorded',
      scenario: { name: 'Base Case', overrides: {} },
      objects,
      dirty: false,
      date: '2026-07-22',
    })
    expect(context.label).toBe('Recorded market data')
    expect(context.summary).toContain('IEMOP')
    expect(context.summary).not.toContain('forecast')
  })

  it('marks pending edits as a preview that needs Run', () => {
    const context = buildResultContext({
      evidenceKind: 'scenario',
      scenario: { name: 'Visayas stress test', overrides: {} },
      objects,
      dirty: true,
      date: '2026-07-22',
    })
    expect(context.label).toBe('Preview, not calculated')
    expect(context.summary).toContain('Press Run')
  })
})
