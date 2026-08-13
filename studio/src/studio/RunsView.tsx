// Saved runs: frozen chronological solves compared side by side. Commercial tools make
// you dig through solution files for this; here a run is a named row, a diff, a CSV.

import { useState } from 'react'
import type { GridKey } from '../lib/types'
import { num, php, useEmissions } from '../lib/data'
import { Chip, Panel } from '../ui/kit'
import { HourLines } from './charts'
import { buildRunReport, downloadReport } from './report'
import {
  deleteRun,
  downloadCsv,
  exportRuns,
  importRuns,
  isStale,
  MAX_RUNS,
  runCsv,
  type SavedRun,
} from './runs'
import { ScrollBox } from '../ui/ScrollBox'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

function meanOf(run: SavedRun, g: GridKey): number {
  const s = run.summaries
  return s.length ? s.reduce((acc, x) => acc + x.meanPrice[g], 0) / s.length : NaN
}
function peakOf(run: SavedRun, g: GridKey): number {
  return Math.max(...run.summaries.map((x) => x.peakPrice[g]))
}
function unservedOf(run: SavedRun): number {
  return run.summaries.reduce(
    (acc, x) => acc + GRIDS.reduce((a, g) => a + x.unservedMwh[g], 0),
    0
  )
}
function rentOf(run: SavedRun): number {
  return run.summaries.reduce((acc, x) => acc + x.leyteRentMPhp + x.mvipRentMPhp, 0)
}

function mostChangedPriceGrid(a: SavedRun, b: SavedRun): GridKey {
  return GRIDS.reduce((largest, grid) =>
    Math.abs(meanOf(b, grid) - meanOf(a, grid)) >
    Math.abs(meanOf(b, largest) - meanOf(a, largest))
      ? grid
      : largest
  )
}

export function RunsView({
  runs,
  onRunsChange,
  onRestore,
  onOpenReplay,
}: {
  runs: SavedRun[]
  onRunsChange: (runs: SavedRun[]) => void
  onRestore: (run: SavedRun) => void
  onOpenReplay: () => void
}) {
  const [aId, setAId] = useState<string>('')
  const [bId, setBId] = useState<string>('')
  const [selectedChartGrid, setSelectedChartGrid] = useState<GridKey | null>(null)
  const [importMsg, setImportMsg] = useState<string>('')
  const a = runs.find((r) => r.id === aId) ?? runs[0]
  const b = runs.find((r) => r.id === bId) ?? runs[1]
  const chartGrid =
    selectedChartGrid ?? (a && b ? mostChangedPriceGrid(a, b) : ('luzon' as GridKey))
  const emissions = useEmissions()

  const onExportAll = () => {
    downloadCsv(
      `power-dispatch-runs-${new Date().toISOString().slice(0, 10)}.json`,
      exportRuns()
    )
  }
  const onImportFile = (file: File | undefined) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const merged = importRuns(String(reader.result ?? ''))
        onRunsChange(merged)
        setImportMsg(`Imported. Archive now holds ${merged.length} runs.`)
      } catch (e) {
        setImportMsg(e instanceof Error ? e.message : 'Could not read that file.')
      }
    }
    reader.onerror = () => setImportMsg('Could not read that file.')
    reader.readAsText(file)
  }

  const exportReport = (r: SavedRun) => {
    downloadReport(
      `power-dispatch-report-${r.name.replace(/\W+/g, '-')}.html`,
      buildRunReport(r, {
        emissionsFactors: emissions.data?.factor_map ?? null,
        emissionsSrc: 'emission factors and sources in the methodology page',
        appUrl: `${window.location.origin}${window.location.pathname}`,
      })
    )
  }

  // The empty state used to name the view that creates a run and then leave the
  // reader to find it. It now names the three steps and opens step one.
  if (!runs.length)
    return (
      <div className="view">
        <Panel
          title="Save a run for comparison"
          subtitle="Nothing is saved in this browser yet. Runs stay on this machine; nothing is uploaded."
        >
          <ol className="empty-steps">
            <li>
              <span>
                <b>Open Hourly market replay</b> and pick a date range.
              </span>
            </li>
            <li>
              <span>
                <b>Edit the scenario</b>, then press Run to solve it.
              </span>
            </li>
            <li>
              <span>
                <b>Press Save run</b> to keep that solve. It appears here.
              </span>
            </li>
          </ol>
          <div className="runs__archive-bar">
            <button className="btn btn--primary btn--sm" onClick={onOpenReplay}>
              Open Hourly market replay
            </button>
            <label className="btn btn--ghost btn--sm">
              Import runs from a file
              <input
                type="file"
                accept="application/json,.json"
                style={{ display: 'none' }}
                onChange={(e) => {
                  onImportFile(e.target.files?.[0])
                  e.target.value = ''
                }}
              />
            </label>
            {importMsg && <span className="runs__import-msg">{importMsg}</span>}
          </div>
        </Panel>
      </div>
    )

  const metrics: { label: string; of: (r: SavedRun) => number; php?: boolean }[] = [
    ...GRIDS.map((g) => ({
      label: `Mean price, ${cap(g)}`,
      of: (r: SavedRun) => meanOf(r, g),
      php: true,
    })),
    { label: 'Peak price, Luzon', of: (r) => peakOf(r, 'luzon'), php: true },
    { label: 'Unserved MWh, all grids', of: unservedOf },
    { label: 'Value across constrained links (congestion rent), M₱', of: rentOf },
  ]

  return (
    <div className="view">
      <Panel
        title="Saved runs"
        subtitle="Each saved run keeps its scenario settings, date range, calculation version, and hourly results."
      >
        <div className="runs__archive-bar">
          <button className="btn btn--ghost btn--sm" onClick={onExportAll}>
            Export runs
          </button>
          <label className="btn btn--ghost btn--sm">
            Import runs
            <input
              type="file"
              accept="application/json,.json"
              style={{ display: 'none' }}
              onChange={(e) => {
                onImportFile(e.target.files?.[0])
                e.target.value = ''
              }}
            />
          </label>
          {importMsg && <span className="runs__import-msg">{importMsg}</span>}
        </div>
        <ScrollBox className="propgrid-wrap">
          <table className="propgrid">
            <thead>
              <tr>
                <th className="propgrid__obj">Saved run</th>
                <th>Scenario settings</th>
                <th>Window</th>
                <th className="propgrid__num">Mean Luzon price (₱/kWh)</th>
                <th className="propgrid__num">Unserved MWh</th>
                <th>Saved</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="propgrid__obj">
                    {r.name}
                    {isStale(r) && (
                      <>
                        {' '}
                        <Chip tone="danger">saved with older model version</Chip>
                      </>
                    )}
                  </td>
                  <td>
                    {r.scenarioName}
                    <span className="propgrid__unit">
                      {' '}
                      ({Object.keys(r.overrides).length} edit
                      {Object.keys(r.overrides).length === 1 ? '' : 's'})
                    </span>
                  </td>
                  <td className="mono">
                    {r.date}
                    {r.span === 'week' ? ' (week)' : ''}
                  </td>
                  <td className="propgrid__num mono">{php(meanOf(r, 'luzon'))}</td>
                  <td className="propgrid__num mono">{num(unservedOf(r))}</td>
                  <td className="mono">{r.savedAt.slice(0, 16).replace('T', ' ')}</td>
                  <td className="runs__actions">
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => onRestore(r)}
                    >
                      Restore
                    </button>
                    <button
                      className="btn btn--ghost btn--sm"
                      disabled={!r.hours.length}
                      title={
                        r.hours.length
                          ? 'Hourly results as CSV'
                          : 'Hourly detail was evicted to fit storage'
                      }
                      onClick={() =>
                        downloadCsv(
                          `power-dispatch-run-${r.name.replace(/\W+/g, '-')}.csv`,
                          runCsv(
                            r.hours,
                            r.summaries.map((s) => s.date)
                          )
                        )
                      }
                    >
                      CSV
                    </button>
                    <button
                      className="btn btn--ghost btn--sm"
                      title="Self-contained HTML report of this run"
                      onClick={() => exportReport(r)}
                    >
                      Report
                    </button>
                    <button
                      className="btn btn--ghost btn--sm"
                      onClick={() => onRunsChange(deleteRun(r.id))}
                    >
                      Delete
                    </button>
                    {!r.hours.length && (
                      <span className="runs__actions-note">
                        Hourly detail was evicted to fit storage
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollBox>
        <p className="note">
          Runs live in this browser's storage, newest first, {MAX_RUNS} at most. A run
          saved under an older engine is flagged instead of silently re-read.
        </p>
      </Panel>

      {runs.length >= 2 && a && b && (
        <Panel
          title="Run comparison"
          subtitle="Run A is compared with Run B. Changed values are highlighted."
        >
          <div className="chrono__controls">
            <label className="chrono__ctl">
              Run A
              <select
                className="ribbon__select"
                value={a.id}
                onChange={(e) => setAId(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="chrono__ctl">
              Run B
              <select
                className="ribbon__select"
                value={b.id}
                onChange={(e) => setBId(e.target.value)}
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="chrono__ctl">
              Hourly price chart
              <select
                className="ribbon__select"
                value={chartGrid}
                onChange={(e) => setSelectedChartGrid(e.target.value as GridKey)}
                aria-label="Hourly price chart"
              >
                {GRIDS.map((grid) => (
                  <option key={grid} value={grid}>
                    {cap(grid)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ScrollBox className="propgrid-wrap">
            <table className="propgrid compare">
              <thead>
                <tr>
                  <th className="propgrid__obj">Metric</th>
                  <th className="propgrid__num">{a.name}</th>
                  <th className="propgrid__num">{b.name}</th>
                  <th className="propgrid__num">B - A</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m) => {
                  const va = m.of(a)
                  const vb = m.of(b)
                  const diff = vb - va
                  const fmt = (v: number) => (m.php ? php(v) : num(v, 2))
                  return (
                    <tr key={m.label}>
                      <td className="propgrid__obj">{m.label}</td>
                      <td className="propgrid__num mono">{fmt(va)}</td>
                      <td className="propgrid__num mono">{fmt(vb)}</td>
                      <td
                        className={`propgrid__num mono${
                          Math.abs(diff) > 1e-6 ? ' compare__diff' : ''
                        }`}
                      >
                        {diff > 0 ? '+' : ''}
                        {fmt(diff)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </ScrollBox>
          {a.hours.length > 0 && b.hours.length > 0 && (
            <HourLines
              series={[
                {
                  label: `A: ${cap(chartGrid)}`,
                  color: 'var(--series-modeled)',
                  pts: a.hours.map((h) => h.price[chartGrid]),
                },
                {
                  label: `B: ${cap(chartGrid)}`,
                  color: 'var(--accent)',
                  pts: b.hours.map((h) => h.price[chartGrid]),
                  dash: '4 3',
                },
              ]}
            />
          )}
        </Panel>
      )}
    </div>
  )
}
