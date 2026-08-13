import { describe, expect, it } from 'vitest'
import { createUsageRecorder } from './usage'

class MemoryStorage implements Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> {
  values = new Map<string, string>()
  getItem(key: string) {
    return this.values.get(key) ?? null
  }
  setItem(key: string, value: string) {
    this.values.set(key, value)
  }
  removeItem(key: string) {
    this.values.delete(key)
  }
}

describe('privacy-safe usage diagnostics', () => {
  it('records the five approved event types without identifiers or model values', () => {
    const storage = new MemoryStorage()
    const usage = createUsageRecorder(storage, () => '2026-08-13T01:00:00.000Z')
    usage.track('workflow_opened', { workflow: 'chronology' })
    usage.track('journey_stopped', { workflow: 'quick-scenario' })
    usage.track('export_failed', { format: 'case' })
    usage.track('stale_result_attempt', { workflow: 'chronology' })
    usage.track('scenario_saved', { span: 'day', editCountBand: '1-3' })

    expect(usage.read().map((event) => event.name)).toEqual([
      'workflow_opened',
      'journey_stopped',
      'export_failed',
      'stale_result_attempt',
      'scenario_saved',
    ])
    const text = usage.exportText()
    expect(text).not.toContain('scenarioName')
    expect(text).not.toContain('overrides')
    expect(text).not.toContain('price')
    expect(text).not.toContain('userId')
  })

  it('drops unknown properties instead of persisting supplied data', () => {
    const storage = new MemoryStorage()
    const usage = createUsageRecorder(storage)
    usage.track('workflow_opened', {
      workflow: 'chronology',
      overrides: { 'region:luzon:demand_mw': 14500 },
      scenarioName: 'Confidential plan',
    } as never)
    expect(usage.read()[0].properties).toEqual({ workflow: 'chronology' })
  })

  it('caps the local log and can clear it', () => {
    const storage = new MemoryStorage()
    const usage = createUsageRecorder(storage)
    for (let i = 0; i < 550; i++)
      usage.track('workflow_opened', { workflow: 'chronology' })
    expect(usage.read()).toHaveLength(500)
    usage.clear()
    expect(usage.read()).toEqual([])
  })
})
