export type UsageEventName =
  | 'workflow_opened'
  | 'journey_stopped'
  | 'export_failed'
  | 'stale_result_attempt'
  | 'scenario_saved'

type WorkflowProperties = { workflow: string }
type ExportProperties = { format: 'case' | 'csv' | 'report' | 'runs' | 'diagnostics' }
type SaveProperties = {
  span: 'day' | 'week'
  editCountBand: '0' | '1-3' | '4-10' | '11+'
}

export type UsageProperties = {
  workflow_opened: WorkflowProperties
  journey_stopped: WorkflowProperties
  export_failed: ExportProperties
  stale_result_attempt: WorkflowProperties
  scenario_saved: SaveProperties
}

export interface UsageEvent {
  name: UsageEventName
  hour: string
  properties: Record<string, string>
}

interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

const KEY = 'power-dispatch-studio-usage-v1'
const MAX_EVENTS = 500
const WORKFLOW = /^[a-z0-9-]{1,48}$/

function hourOf(iso: string) {
  return `${iso.slice(0, 13)}:00:00.000Z`
}

function cleanProperties(name: UsageEventName, input: unknown): Record<string, string> {
  if (!input || typeof input !== 'object') return {}
  const value = input as Record<string, unknown>
  if (
    name === 'workflow_opened' ||
    name === 'journey_stopped' ||
    name === 'stale_result_attempt'
  ) {
    return typeof value.workflow === 'string' && WORKFLOW.test(value.workflow)
      ? { workflow: value.workflow }
      : {}
  }
  if (name === 'export_failed') {
    const allowed = ['case', 'csv', 'report', 'runs', 'diagnostics']
    return typeof value.format === 'string' && allowed.includes(value.format)
      ? { format: value.format }
      : {}
  }
  const spans = ['day', 'week']
  const bands = ['0', '1-3', '4-10', '11+']
  return {
    ...(typeof value.span === 'string' && spans.includes(value.span)
      ? { span: value.span }
      : {}),
    ...(typeof value.editCountBand === 'string' && bands.includes(value.editCountBand)
      ? { editCountBand: value.editCountBand }
      : {}),
  }
}

export function createUsageRecorder(
  storage: StorageLike,
  now: () => string = () => new Date().toISOString()
) {
  const read = (): UsageEvent[] => {
    try {
      const parsed = JSON.parse(storage.getItem(KEY) ?? '[]') as unknown
      return Array.isArray(parsed) ? (parsed as UsageEvent[]) : []
    } catch {
      return []
    }
  }
  const track = <Name extends UsageEventName>(
    name: Name,
    properties: UsageProperties[Name]
  ) => {
    const events = [
      ...read(),
      { name, hour: hourOf(now()), properties: cleanProperties(name, properties) },
    ].slice(-MAX_EVENTS)
    try {
      storage.setItem(KEY, JSON.stringify(events))
    } catch {
      // Diagnostics never block the analyst workflow.
    }
  }
  return {
    track,
    read,
    exportText: () =>
      JSON.stringify({ schema: 'power-dispatch-usage/v1', events: read() }, null, 2),
    clear: () => storage.removeItem(KEY),
  }
}

export const editCountBand = (count: number): SaveProperties['editCountBand'] =>
  count === 0 ? '0' : count <= 3 ? '1-3' : count <= 10 ? '4-10' : '11+'
