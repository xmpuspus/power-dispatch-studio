import {
  Component,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { GRIDS } from '../lib/types'
import { php, pct, useFleet, useGenerators, useProfiles } from '../lib/data'
import {
  CommandPalette,
  EvidenceSummary,
  GlossaryDrawer,
  NavRail,
  RunDock,
  TopBar,
} from '../shell/Shell'
import { MarketStrip } from '../shell/MarketStrip'
import { buildMarketStrip } from '../shell/marketStripData'
import { usePaletteKey } from '../shell/usePaletteKey'
import {
  type Nav,
  destBySlug,
  destOf,
  groupOf,
  readHashView,
  writeHashView,
} from '../shell/nav'
import {
  DEFAULT_DESTINATION,
  EVIDENCE_LABELS,
  evidenceForSlug,
  workspaceForSlug,
} from '../shell/workflows'
import { MarginalView, ReserveView } from './views'
import { ScenarioView } from './Scenario'
import { MarketPowerView } from './MarketPower'
import { ChronologyView } from './ChronoView'
import { runChronology } from './chrono'
import { BackcastView } from './BackcastView'
import { DayExplainerView } from './DayExplainerView'
import { RunsView } from './RunsView'
import { SweepView } from './SweepView'
import { DistributionView } from './DistributionView'
import { LTPlanView } from './LTPlanView'
import { PasaView } from './PasaView'
import { EmissionsView } from './EmissionsView'
import { CaptureView } from './CaptureView'
import { VintageView } from './VintageView'
import { PortfolioView } from './PortfolioView'
import { Rtdoe5View } from './Rtdoe5View'
import { NodalView } from './NodalView'
import { SitesView } from './SitesView'
import { LossValidationView } from './LossValidationView'
import { FutureYearView } from './FutureYearView'
import { ContractView } from './ContractView'
import { WeekView } from './WeekView'
import { ForwardView } from './ForwardView'
import { decodeShare, downloadCsv, loadRuns, type SavedRun } from './runs'
import { fromScenarioFile, scenarioFileText, toScenarioFile } from './scenarioFile'
import {
  baseObjects,
  chronoOptsFrom,
  overrideKey,
  solveModel,
  type ClassId,
  type Overrides,
  type Scenario,
  type SolvedModel,
} from './model'
import { parseImportCsv, type ImportResult } from './importData'
import {
  CompareView,
  MembershipsView,
  ObjectsList,
  PropertiesGrid,
  SolvedFlowsView,
  SolvedMeritView,
  SolvedN1View,
  SolvedReliabilityView,
} from './model-views'

// The nav shape, the 26 destinations, and which of them read one grid at a time
// all live in shell/nav.ts. Studio keeps the model state and the panes; the
// shell owns how an analyst reaches them.

export function Studio({
  d,
  onExit,
  theme,
  onToggleTheme,
}: {
  d: Dispatch
  onExit: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}) {
  const gens = useGenerators()
  const profiles = useProfiles()
  const fleet = useFleet()
  const genRows = useMemo(
    () => (gens.data?.features ?? []).map((f) => f.properties),
    [gens.data]
  )
  const objects = useMemo(
    () =>
      baseObjects(
        d,
        genRows,
        profiles.data?.storage_defaults ?? [],
        fleet.data?.available ? fleet.data.plants : []
      ),
    [d, genRows, profiles.data, fleet.data]
  )

  // a share link carries a scenario (and a chronology window) in the URL hash
  const shared = useMemo(() => decodeShare(window.location.hash), [])
  const [scenarios, setScenarios] = useState<Scenario[]>(() =>
    shared
      ? [
          { name: 'Base Case', overrides: {} },
          { name: `${shared.scenarioName} (shared)`, overrides: shared.overrides },
        ]
      : [{ name: 'Base Case', overrides: {} }]
  )
  const [ai, setAi] = useState(shared ? 1 : 0)
  const active = scenarios[ai]
  // a deep link picks the opening view; a shared scenario without one lands on
  // the chronology it was captured from; everything else opens on the lever
  // panel, which is where a first-time analyst can do something in one drag
  const linked = useMemo(() => readHashView(window.location.hash), [])
  const [nav, setNav] = useState<Nav>(() => {
    const d0 = linked.slug ? destBySlug(linked.slug) : undefined
    if (d0) return d0.nav
    return shared
      ? { kind: 'sol', id: 'chrono' }
      : (destBySlug(DEFAULT_DESTINATION)?.nav ?? { kind: 'sol', id: 'chrono' })
  })
  const [grid, setGrid] = useState<GridKey>((linked.grid as GridKey) ?? 'luzon')
  const [navOpen, setNavOpen] = useState(false)
  const [palette, setPalette] = useState(false)
  const [glossaryOpen, setGlossaryOpen] = useState(false)
  const [selectedHour, setSelectedHour] = useState(19)
  const [dockOpen, setDockOpen] = useState(
    () => !window.matchMedia?.('(max-width: 1180px)').matches
  )
  const [copied, setCopied] = useState<'idle' | 'ok' | 'fail'>('idle')
  // the Quick scenario levers preview live; they report the clear here so the
  // dock can show it beside the solved model instead of silently disagreeing
  const [live, setLive] = useState<Record<GridKey, number> | null>(null)
  const onLive = useCallback((p: Record<GridKey, number> | null) => setLive(p), [])
  usePaletteKey(() => setPalette(true))
  const [chronoDate, setChronoDate] = useState<string | null>(shared?.date ?? null)
  const [chronoSpan, setChronoSpan] = useState<'day' | 'week'>(shared?.span ?? 'day')
  const [runsList, setRunsList] = useState<SavedRun[]>(() => loadRuns())
  const [solved, setSolved] = useState<SolvedModel>(() =>
    solveModel(d, objects, shared?.overrides ?? {})
  )
  // overrides snapshot at the last Run: the chronological view re-runs from this,
  // so it moves with Run exactly like the other live solution views
  const [ranOv, setRanOv] = useState<Overrides>(shared?.overrides ?? {})
  const [dirty, setDirty] = useState(false)

  // The chronology window defaults to the generated widest-swing day after profiles load.
  useEffect(() => {
    const p = profiles.data
    if (!p) return
    setChronoDate((cur) =>
      cur && p.days.some((x) => x.date === cur)
        ? cur
        : (p.default_day ?? p.days[p.days.length - 1]?.date ?? null)
    )
  }, [profiles.data])

  const restoreRun = (run: SavedRun) => {
    setScenarios((prev) => [
      ...prev,
      { name: `${run.scenarioName} (restored)`, overrides: { ...run.overrides } },
    ])
    setAi(scenarios.length)
    // the IEMOP window rolls; a saved run's day can age out of the archive
    const p = profiles.data
    setChronoDate(
      p && p.days.some((x) => x.date === run.date)
        ? run.date
        : (p?.default_day ?? run.date)
    )
    setChronoSpan(run.span)
    setSolved(solveModel(d, objects, run.overrides))
    setRanOv(run.overrides)
    setDirty(false)
    setNav({ kind: 'sol', id: 'chrono' })
  }

  // re-solve the base when the generator list arrives, as long as nothing is pending
  useEffect(() => {
    if (!dirty) {
      setSolved(solveModel(d, objects, active.overrides))
      setRanOv(active.overrides)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objects])

  const run = () => {
    setSolved(solveModel(d, objects, active.overrides))
    setRanOv(active.overrides)
    setDirty(false)
  }
  const edit = (cls: ClassId, id: string, prop: string, value: number) => {
    const k = overrideKey(cls, id, prop)
    setScenarios((prev) =>
      prev.map((s, i) =>
        i === ai
          ? {
              ...s,
              overrides: { ...s.overrides, [k]: value },
              // a manual edit supersedes an imported value: it is no longer
              // user-supplied data, it is a studio edit
              importedKeys: (s.importedKeys ?? []).filter((x) => x !== k),
            }
          : s
      )
    )
    setDirty(true)
  }
  const revert = (cls: ClassId, id: string, prop: string) => {
    const k = overrideKey(cls, id, prop)
    setScenarios((prev) =>
      prev.map((s, i) => {
        if (i !== ai) return s
        const o = { ...s.overrides }
        delete o[k]
        return {
          ...s,
          overrides: o,
          importedKeys: (s.importedKeys ?? []).filter((x) => x !== k),
        }
      })
    )
    setDirty(true)
  }
  const importCsv = (text: string): ImportResult => {
    const res = parseImportCsv(text, objects)
    if (res.matched > 0) {
      setScenarios((prev) =>
        prev.map((s, i) =>
          i === ai
            ? {
                ...s,
                overrides: { ...s.overrides, ...res.overrides },
                importedKeys: [
                  ...new Set([...(s.importedKeys ?? []), ...res.importedKeys]),
                ],
              }
            : s
        )
      )
      setDirty(true)
    }
    return res
  }
  // The scenario file: the same bytes the command line reads. Saving writes the
  // current edits, loading replaces them and reports what the object tables
  // could not hold, because a silent half-load is worse than no load.
  const [scenarioMsg, setScenarioMsg] = useState('')
  const scenarioFile = (mode: 'save' | 'load', file?: File) => {
    const date = chronoDate ?? profiles.data?.default_day ?? ''
    if (mode === 'save') {
      const f = toScenarioFile(active.name, date, objects, active.overrides)
      downloadCsv(
        `${active.name.replace(/\W+/g, '-').toLowerCase()}.json`,
        scenarioFileText(f)
      )
      const n = Object.keys(f.opts).length
      setScenarioMsg(`Wrote ${n} option${n === 1 ? '' : 's'} for ${date}.`)
      return
    }
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const r = fromScenarioFile(JSON.parse(String(reader.result ?? '')), objects)
        setScenarios((prev) => [
          ...prev,
          { name: `${r.name} (file)`, overrides: r.overrides },
        ])
        setAi(scenarios.length)
        if (profiles.data?.days.some((x) => x.date === r.date)) setChronoDate(r.date)
        setDirty(true)
        setScenarioMsg(
          `Loaded ${Object.keys(r.overrides).length} edits.` +
            (r.warnings.length ? ` ${r.warnings.join(' ')}` : '')
        )
      } catch (e) {
        setScenarioMsg(e instanceof Error ? e.message : 'Could not read that file.')
      }
    }
    reader.onerror = () => setScenarioMsg('Could not read that file.')
    reader.readAsText(file)
  }

  const pickScenario = (idx: number) => {
    setAi(idx)
    setDirty(true) // must Run to see the switched scenario's solution
  }
  const addScenario = () => {
    setScenarios((prev) => [
      ...prev,
      {
        name: `Scenario ${prev.length}`,
        overrides: { ...prev[ai].overrides },
        importedKeys: [...(prev[ai].importedKeys ?? [])],
      },
    ])
    setAi(scenarios.length)
    setDirty(true)
  }

  const editCount = Object.keys(active.overrides).length
  const dest = destOf(nav)
  const group = groupOf(nav)
  const workspace = dest ? workspaceForSlug(dest.slug) : undefined
  const gridScoped = !!dest?.scoped
  const dateContext = !!dest?.dateContext
  const scenarioContext = !!dest?.scenarioContext

  // the calibrated base case, solved once. Every figure in the run dock reads
  // its move against this, so an analyst sees the size of what they changed
  // rather than a level they must remember the old value of
  const base = useMemo(() => solveModel(d, objects, {}), [d, objects])

  const stripRun = useMemo(() => {
    if (!profiles.data || !chronoDate) return null
    try {
      return runChronology(d, profiles.data, chronoDate, chronoOptsFrom(objects, ranOv))
    } catch {
      return null
    }
  }, [d, profiles.data, chronoDate, objects, ranOv])
  const stripDay = profiles.data?.days.find((day) => day.date === chronoDate)
  const stripItems = useMemo(
    () =>
      stripRun
        ? buildMarketStrip(stripRun.hours, stripDay?.lwap?.[grid] ?? [], grid)
        : [],
    [stripRun, stripDay, grid]
  )
  const dates = profiles.data?.days.map((day) => day.date) ?? []
  const coverage =
    dates.length > 0 ? `${dates[0]} to ${dates[dates.length - 1]}` : 'Unavailable'
  const evidence = evidenceForSlug(
    dest?.slug ?? DEFAULT_DESTINATION,
    Object.keys(ranOv).length > 0
  )

  // the open view rides in the URL beside any shared scenario, so a colleague
  // can be sent one view rather than told which one to click to
  useEffect(() => {
    if (dest) writeHashView(dest.slug, gridScoped ? grid : undefined)
  }, [dest, grid, gridScoped])

  // Back and Forward walk the views, and a link pasted into an already-open
  // studio moves it. Without this the hash is write-only and Back leaves the app.
  useEffect(() => {
    const sync = () => {
      const h = readHashView(window.location.hash)
      const target = h.slug ? destBySlug(h.slug) : undefined
      if (target) setNav(target.nav)
      if (h.grid) setGrid(h.grid as GridKey)
    }
    window.addEventListener('popstate', sync)
    window.addEventListener('hashchange', sync)
    return () => {
      window.removeEventListener('popstate', sync)
      window.removeEventListener('hashchange', sync)
    }
  }, [])

  const revertAll = () => {
    setScenarios((prev) =>
      prev.map((s, i) => (i === ai ? { ...s, overrides: {}, importedKeys: [] } : s))
    )
    setDirty(true)
  }
  const copySummary = async () => {
    const g = (k: GridKey) =>
      `${k[0].toUpperCase() + k.slice(1)} ${php(solved.coupled.price[k])}/kWh, margin ${pct(solved.reserveMarginPct[k] / 100, 1)}, LOLP ${pct(solved.reliability[k].lolp_pct / 100, 2)}`
    const text = `Power Dispatch Studio, scenario "${active.name}"\n${GRIDS.map(g).join('\n')}`
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        return true
      }
    } catch {
      // insecure origin or denied permission; fall through to the textarea path
    }
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      return ok
    } catch {
      return false
    }
  }
  return (
    <div className="studio" data-testid="studio">
      <TopBar
        nav={nav}
        grid={grid}
        onGrid={setGrid}
        gridScoped={gridScoped}
        dateEnabled={dateContext}
        scenarioEnabled={scenarioContext}
        dates={dates}
        date={chronoDate ?? ''}
        onDate={setChronoDate}
        scenarios={scenarios}
        ai={ai}
        onPickScenario={pickScenario}
        onAddScenario={addScenario}
        editCount={editCount}
        dirty={dirty}
        onRun={run}
        onOpenPalette={() => setPalette(true)}
        onOpenNav={() => setNavOpen(true)}
        onOpenGlossary={() => setGlossaryOpen(true)}
        onExit={onExit}
        theme={theme}
        onToggleTheme={onToggleTheme}
      />

      <div
        className={`studio__body ${scenarioContext ? (dockOpen ? 'dock-open' : 'dock-closed') : 'no-dock'}`}
      >
        <NavRail
          nav={nav}
          onNav={setNav}
          open={navOpen}
          onClose={() => setNavOpen(false)}
          editCount={editCount}
        />

        <main className="studio__main">
          {dateContext && chronoDate && (
            <MarketStrip
              date={chronoDate}
              grid={grid}
              items={stripItems}
              selectedHour={selectedHour}
              onSelectHour={setSelectedHour}
            />
          )}
          <div className="viewhead">
            <span className="viewhead__group">
              {workspace?.label ?? group?.label ?? 'Studio'}
            </span>
            <h1 className="viewhead__title">{dest?.label ?? 'View'}</h1>
            <p className="viewhead__hint">
              {dirty && dest?.live
                ? `${editCount} edit${editCount === 1 ? '' : 's'} are not in this yet. Press Run.`
                : (dest?.hint ?? '')}
            </p>
            <span className={`viewhead__state is-${evidence.kind}`}>
              {EVIDENCE_LABELS[evidence.kind]}
            </span>
            {scenarioContext && editCount > 0 && (
              <button className="btn btn--ghost btn--sm" onClick={revertAll}>
                Revert {editCount} edit{editCount === 1 ? '' : 's'}
              </button>
            )}
            {scenarioContext && (
              <button
                className="btn btn--ghost btn--sm"
                onClick={async () => {
                  const ok = await copySummary()
                  setCopied(ok ? 'ok' : 'fail')
                  window.setTimeout(() => setCopied('idle'), 1600)
                }}
                title="Copy this scenario's clearing prices and adequacy"
              >
                {copied === 'ok'
                  ? 'Copied'
                  : copied === 'fail'
                    ? 'Copy failed'
                    : 'Copy summary'}
              </button>
            )}
          </div>
          <details className="viewevidence">
            <summary>Evidence and sources</summary>
            <EvidenceSummary
              evidence={evidence}
              date={dateContext ? (chronoDate ?? undefined) : undefined}
              coverage={dateContext ? coverage : undefined}
            />
          </details>
          <div className="studio__scroll">
            <div className="studio__measure">
              <SolveBoundary key={`${JSON.stringify(nav)}:${editCount}:${dirty}:${grid}`}>
                <DataPane
                  d={d}
                  profiles={profiles.data}
                  nav={nav}
                  grid={grid}
                  solved={solved}
                  objects={objects}
                  scenarios={scenarios}
                  overrides={active.overrides}
                  ranOv={ranOv}
                  scenarioName={active.name}
                  chronoDate={chronoDate}
                  chronoSpan={chronoSpan}
                  selectedHour={selectedHour}
                  onChronoDate={setChronoDate}
                  onChronoSpan={setChronoSpan}
                  runsList={runsList}
                  onRunsChange={setRunsList}
                  onRestore={restoreRun}
                  onNav={setNav}
                  dirty={dirty}
                  onEdit={edit}
                  onRevert={revert}
                  onImportCsv={importCsv}
                  importedKeys={active.importedKeys}
                  onScenarioFile={scenarioFile}
                  scenarioMsg={scenarioMsg}
                  onRun={run}
                  onLive={onLive}
                />
              </SolveBoundary>
            </div>
          </div>
        </main>

        {scenarioContext && (
          <RunDock
            solved={solved}
            base={base}
            live={live}
            grid={grid}
            onGrid={setGrid}
            scenarioName={active.name}
            dirty={dirty}
            open={dockOpen}
            onToggle={() => setDockOpen((v) => !v)}
            onTakeAway={() => setNav({ kind: 'runs' })}
          />
        )}
      </div>

      <CommandPalette
        open={palette}
        onClose={() => setPalette(false)}
        onNav={(n) => setNav(n)}
      />

      <GlossaryDrawer open={glossaryOpen} onClose={() => setGlossaryOpen(false)} />
    </div>
  )
}

class SolveBoundary extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null }
  static getDerivedStateFromError(e: Error) {
    return { err: e.message }
  }
  render() {
    if (this.state.err)
      return (
        <div className="view">
          <div className="basecase-banner">
            This scenario could not be solved. {this.state.err}. Open Review and edit
            model inputs, then use the x beside a changed value or the Revert edits
            button.
          </div>
        </div>
      )
    return this.props.children
  }
}

function DataPane({
  d,
  profiles,
  nav,
  grid,
  solved,
  objects,
  scenarios,
  overrides,
  ranOv,
  scenarioName,
  chronoDate,
  chronoSpan,
  selectedHour,
  onChronoDate,
  onChronoSpan,
  runsList,
  onRunsChange,
  onRestore,
  onNav,
  dirty,
  onEdit,
  onRevert,
  onImportCsv,
  importedKeys,
  onScenarioFile,
  scenarioMsg,
  onRun,
  onLive,
}: {
  d: Dispatch
  profiles: Profiles | null
  nav: Nav
  grid: GridKey
  solved: SolvedModel
  objects: ReturnType<typeof baseObjects>
  scenarios: Scenario[]
  overrides: Scenario['overrides']
  ranOv: Overrides
  scenarioName: string
  chronoDate: string | null
  chronoSpan: 'day' | 'week'
  selectedHour: number
  onChronoDate: (v: string) => void
  onChronoSpan: (v: 'day' | 'week') => void
  runsList: SavedRun[]
  onRunsChange: (runs: SavedRun[]) => void
  onRestore: (run: SavedRun) => void
  onNav: (n: Nav) => void
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onImportCsv: (text: string) => ImportResult
  onScenarioFile: (mode: 'save' | 'load', file?: File) => void
  scenarioMsg: string
  importedKeys: string[] | undefined
  onRun: () => void
  onLive: (p: Record<GridKey, number> | null) => void
}) {
  if (nav.kind === 'compare')
    return <CompareView d={d} objects={objects} scenarios={scenarios} />
  if (nav.kind === 'runs')
    return (
      <RunsView
        runs={runsList}
        onRunsChange={onRunsChange}
        onRestore={onRestore}
        onOpenReplay={() => onNav({ kind: 'sol', id: 'chrono' })}
      />
    )
  if (nav.kind === 'quick')
    return (
      <ScenarioView
        d={d}
        grid={grid}
        objects={objects}
        overrides={overrides}
        onEdit={onEdit}
        onRevert={onRevert}
        onImportCsv={onImportCsv}
        onScenarioFile={onScenarioFile}
        scenarioMsg={scenarioMsg}
        importedKeys={importedKeys}
        onLive={onLive}
      />
    )
  if (nav.kind === 'phase') {
    if (nav.id === 'lt')
      return (
        <div className="view">
          <LTPlanView objects={objects} onEdit={onEdit} />
          <FutureYearView grid={grid} />
        </div>
      )
    return (
      <PasaView
        d={d}
        objects={objects}
        overrides={ranOv}
        date={chronoDate}
        onDate={onChronoDate}
      />
    )
  }
  if (nav.kind === 'analysis') {
    if (nav.id === 'backcast') {
      if (!profiles)
        return <div className="basecase-banner">Loading recorded market days.</div>
      return (
        <BackcastView
          d={d}
          profiles={profiles}
          grid={grid}
          date={chronoDate}
          onDate={onChronoDate}
        />
      )
    }
    if (nav.id === 'explain') {
      if (!profiles)
        return <div className="basecase-banner">Loading recorded market days.</div>
      return (
        <DayExplainerView
          d={d}
          profiles={profiles}
          grid={grid}
          date={chronoDate}
          onDate={onChronoDate}
        />
      )
    }
    if (nav.id === 'emissions') {
      if (!profiles)
        return <div className="basecase-banner">Loading recorded market days.</div>
      return (
        <EmissionsView
          d={d}
          profiles={profiles}
          objects={objects}
          overrides={ranOv}
          date={chronoDate}
          onDate={onChronoDate}
        />
      )
    }
    if (nav.id === 'reserve') return <ReserveView d={d} grid={grid} />
    if (nav.id === 'capture') return <CaptureView runsList={runsList} grid={grid} />
    if (nav.id === 'portfolio') return <PortfolioView runsList={runsList} />
    if (nav.id === 'rtdoe5')
      return <Rtdoe5View grid={grid} date={chronoDate} onDate={onChronoDate} />
    if (nav.id === 'nodal') return <NodalView grid={grid} />
    if (nav.id === 'sites') return <SitesView />
    if (nav.id === 'lossval') return <LossValidationView />
    if (nav.id === 'contracts') {
      if (!profiles)
        return <div className="basecase-banner">Loading recorded market days.</div>
      return (
        <ContractView
          d={d}
          profiles={profiles}
          objects={objects}
          overrides={ranOv}
          date={chronoDate ?? profiles.default_day ?? ''}
          scenarioName={scenarioName}
        />
      )
    }
    if (nav.id === 'forward' && profiles)
      return <ForwardView d={d} profiles={profiles} grid={grid} />
    if (nav.id === 'week') {
      if (!profiles)
        return <div className="basecase-banner">Loading recorded market days.</div>
      return <WeekView d={d} profiles={profiles} grid={grid} />
    }
    if (nav.id === 'inputs')
      return (
        <ModelInputsView
          d={d}
          objects={objects}
          overrides={overrides}
          importedKeys={importedKeys}
          dirty={dirty}
          onEdit={onEdit}
          onRevert={onRevert}
          onRun={onRun}
        />
      )
    return <MarketPowerView />
  }
  // solution views
  const sol = nav.id
  if (sol === 'merit')
    return (
      <div className="view">
        <SolvedMeritView s={solved} grid={grid} />
        <MarginalView d={d} grid={grid} />
      </div>
    )
  if (sol === 'chrono') {
    if (!profiles || !chronoDate)
      return <div className="basecase-banner">Loading recorded market days.</div>
    return (
      <ChronologyView
        d={d}
        profiles={profiles}
        objects={objects}
        overrides={ranOv}
        importedKeys={importedKeys}
        grid={grid}
        scenarioName={scenarioName}
        date={chronoDate}
        span={chronoSpan}
        onDate={onChronoDate}
        onSpan={onChronoSpan}
        selectedHour={selectedHour}
        onSaved={onRunsChange}
      />
    )
  }
  if (sol === 'sweep')
    return <SweepView d={d} objects={objects} overrides={ranOv} grid={grid} />
  if (sol === 'distribution') {
    if (!profiles)
      return <div className="basecase-banner">Loading recorded market days.</div>
    return (
      <DistributionView
        d={d}
        profiles={profiles}
        objects={objects}
        overrides={ranOv}
        grid={grid}
      />
    )
  }
  if (sol === 'flows')
    return (
      <SolvedFlowsView
        s={solved}
        d={d}
        day={profiles?.days.find((day) => day.date === chronoDate)}
        run={
          profiles && chronoDate
            ? runChronology(d, profiles, chronoDate, chronoOptsFrom(objects, ranOv))
            : null
        }
        hour={selectedHour}
      />
    )
  if (sol === 'reliability')
    return (
      <div className="view">
        <SolvedReliabilityView s={solved} units={objects.generator.length} />
        <SolvedN1View s={solved} grid={grid} />
      </div>
    )
  return null
}

type DataTab = 'objects' | 'memberships' | 'properties'

function ModelInputsView({
  d,
  objects,
  overrides,
  importedKeys,
  dirty,
  onEdit,
  onRevert,
  onRun,
}: {
  d: Dispatch
  objects: ReturnType<typeof baseObjects>
  overrides: Scenario['overrides']
  importedKeys: string[] | undefined
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onRun: () => void
}) {
  const [cls, setCls] = useState<ClassId>('fuel')
  const labels: Record<ClassId, string> = {
    fuel: 'Fuel groups',
    generator: 'Power plants',
    interface: 'Inter-grid links',
    region: 'Island-grid demand',
    storage: 'Storage',
  }
  return (
    <div className="view">
      <VintageView d={d} />
      <section aria-labelledby="editable-inputs">
        <h2 id="editable-inputs">Editable model inputs</h2>
        <p className="note">
          These tables are model inputs, not recorded market values. Select a table, edit
          the active scenario, then run it before reading scenario results.
        </p>
        <div className="datatabs" role="tablist" aria-label="Model input tables">
          {(Object.keys(labels) as ClassId[]).map((id) => (
            <button
              key={id}
              role="tab"
              aria-selected={id === cls}
              className={`datatabs__tab ${id === cls ? 'is-active' : ''}`}
              onClick={() => setCls(id)}
            >
              {labels[id]}
            </button>
          ))}
        </div>
        <ClassPane
          cls={cls}
          objects={objects}
          overrides={overrides}
          importedKeys={importedKeys}
          dirty={dirty}
          onEdit={onEdit}
          onRevert={onRevert}
          onRun={onRun}
        />
      </section>
    </div>
  )
}

function ClassPane({
  cls,
  objects,
  overrides,
  importedKeys,
  dirty,
  onEdit,
  onRevert,
  onRun,
}: {
  cls: ClassId
  objects: ReturnType<typeof baseObjects>
  overrides: Scenario['overrides']
  importedKeys: string[] | undefined
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onRun: () => void
}) {
  const [tab, setTab] = useState<DataTab>('properties')
  const rows = objects[cls]
  const tabs: { id: DataTab; label: string }[] = [
    { id: 'objects', label: 'Items' },
    { id: 'memberships', label: 'Connections' },
    { id: 'properties', label: 'Inputs' },
  ]
  return (
    <div className="datapane">
      <div className="datatabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === tab}
            className={`datatabs__tab ${t.id === tab ? 'is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'properties' && (
        <>
          <div className="datapane__hint">
            {/* one flex item, not five: the bare text nodes and the <b> used to
                become separate flex children and the sentence broke into
                misaligned columns across the pane */}
            <p className="datapane__hinttext">
              Edit a value and it is tagged to the active scenario. Press <b>Run</b> to
              re-solve. The base value returns with the × on a changed cell.
              {cls === 'generator' && rows.length > 40 && (
                <span>
                  {' '}
                  Units and dependable capacities are the DOE list of existing power
                  plants (2025 editions). Units with less than 20 MW of dependable
                  capacity remain in the source data but are not shown in this table.
                </span>
              )}
            </p>
            {dirty && (
              <button className="btn btn--run btn--sm datapane__run" onClick={onRun}>
                <PlayIcon /> Run
              </button>
            )}
          </div>
          <PropertiesGrid
            cls={cls}
            rows={rows}
            overrides={overrides}
            importedKeys={importedKeys}
            onEdit={onEdit}
            onRevert={onRevert}
          />
        </>
      )}
      {tab === 'memberships' && <MembershipsView cls={cls} objects={objects} />}
      {tab === 'objects' && <ObjectsList rows={rows} />}
    </div>
  )
}

function PlayIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 5l12 7-12 7z" fill="currentColor" />
    </svg>
  )
}
