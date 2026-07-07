import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, GridKey, Profiles } from '../lib/types'
import { GRIDS } from '../lib/types'
import { php, pct, useFleet, useGenerators, useProfiles } from '../lib/data'
import { Segmented, ThemeToggle } from '../ui/kit'
import { DurationView, MarginalView, ReliabilityView, ReserveView } from './views'
import { ScenarioView } from './Scenario'
import { BillView } from './Bill'
import { MarketPowerView } from './MarketPower'
import { ChronologyView } from './ChronoView'
import { BackcastView } from './BackcastView'
import { RunsView } from './RunsView'
import { decodeShare, loadRuns, type SavedRun } from './runs'
import {
  CLASSES,
  baseObjects,
  overrideKey,
  solveModel,
  type ClassId,
  type Overrides,
  type Scenario,
  type SolvedModel,
} from './model'
import {
  CompareView,
  MembershipsView,
  ObjectsList,
  PropertiesGrid,
  SolvedFlowsView,
  SolvedMeritView,
  SolvedN1View,
  SolvedRegionsView,
  SolvedReliabilityView,
} from './model-views'

type SolId =
  | 'merit'
  | 'chrono'
  | 'flows'
  | 'n1'
  | 'regions'
  | 'duration'
  | 'marginal'
  | 'reliability'
type AnalysisId = 'reserve' | 'bill' | 'market' | 'backcast'
type Nav =
  | { kind: 'class'; id: ClassId }
  | { kind: 'quick' }
  | { kind: 'compare' }
  | { kind: 'runs' }
  | { kind: 'sol'; id: SolId }
  | { kind: 'analysis'; id: AnalysisId }

const SOL_LABEL: Record<SolId, string> = {
  merit: 'Merit order',
  chrono: 'Chronology',
  flows: 'Coupled flows',
  n1: 'N-1 contingency',
  regions: 'Regions',
  duration: 'Price duration',
  marginal: 'Marginal units',
  reliability: 'Reliability',
}
const ANALYSIS_LABEL: Record<AnalysisId, string> = {
  backcast: 'Backcast',
  reserve: 'Reserve market',
  bill: 'Bill impact',
  market: 'Market power',
}
// views that recompute from the current model (the rest read the calibrated base case)
const LIVE_SOL = new Set<SolId>([
  'merit',
  'chrono',
  'flows',
  'n1',
  'regions',
  'reliability',
])
// navs that pick a grid
const GRID_SOL = new Set<SolId>(['merit', 'chrono', 'n1', 'duration', 'marginal'])
const PHASES = ['LT Plan', 'PASA', 'MT Schedule', 'ST Schedule']

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
  const [nav, setNav] = useState<Nav>(
    shared ? { kind: 'sol', id: 'chrono' } : { kind: 'class', id: 'generator' }
  )
  const [grid, setGrid] = useState<GridKey>('luzon')
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

  // the chronology window defaults to the baked widest-swing day once profiles land
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
    setChronoDate(run.date)
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
    setScenarios((prev) =>
      prev.map((s, i) =>
        i === ai
          ? { ...s, overrides: { ...s.overrides, [overrideKey(cls, id, prop)]: value } }
          : s
      )
    )
    setDirty(true)
  }
  const revert = (cls: ClassId, id: string, prop: string) => {
    setScenarios((prev) =>
      prev.map((s, i) => {
        if (i !== ai) return s
        const o = { ...s.overrides }
        delete o[overrideKey(cls, id, prop)]
        return { ...s, overrides: o }
      })
    )
    setDirty(true)
  }
  const pickScenario = (idx: number) => {
    setAi(idx)
    setDirty(true) // must Run to see the switched scenario's solution
  }
  const addScenario = () => {
    setScenarios((prev) => [
      ...prev,
      { name: `Scenario ${prev.length}`, overrides: { ...prev[ai].overrides } },
    ])
    setAi(scenarios.length)
    setDirty(true)
  }

  const editCount = Object.keys(active.overrides).length
  const gridScoped =
    (nav.kind === 'sol' && GRID_SOL.has(nav.id)) ||
    (nav.kind === 'analysis' && (nav.id === 'reserve' || nav.id === 'backcast'))

  const revertAll = () => {
    setScenarios((prev) => prev.map((s, i) => (i === ai ? { ...s, overrides: {} } : s)))
    setDirty(true)
  }
  const copySummary = () => {
    const g = (k: GridKey) =>
      `${k[0].toUpperCase() + k.slice(1)} ${php(solved.coupled.price[k])}/kWh, margin ${pct(solved.reserveMarginPct[k] / 100, 1)}, LOLP ${pct(solved.reliability[k].lolp_pct / 100, 2)}`
    const text = `gridbill-ph studio, scenario "${active.name}"\n${GRIDS.map(g).join('\n')}`
    void navigator.clipboard?.writeText(text)
  }

  return (
    <div className="studio" data-testid="studio">
      <header className="studio__titlebar">
        <div className="studio__brand">
          <BrandMark />
          <div>
            <div className="studio__name">
              PLEXOS<span className="studio__from">from Temu</span>
            </div>
            <div className="studio__tag">open dispatch studio</div>
          </div>
        </div>
        <span className="studio__homage" title="An independent, open homage.">
          An independent homage. Not affiliated with Energy Exemplar. Not PLEXOS.
        </span>
        <div className="studio__barright">
          <span className={`statuschip statuschip--${dirty ? 'unsolved' : 'solved'}`}>
            <Dot /> {dirty ? 'Unsolved' : 'Solved'}
          </span>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button className="btn btn--ghost" onClick={onExit}>
            Close studio
          </button>
        </div>
      </header>

      <Ribbon
        scenarios={scenarios}
        ai={ai}
        dirty={dirty}
        editCount={editCount}
        grid={grid}
        gridScoped={gridScoped}
        onRun={run}
        onPick={pickScenario}
        onAdd={addScenario}
        onRevertAll={revertAll}
        onCopy={copySummary}
        onGrid={setGrid}
      />

      <div className="studio__body">
        <Explorer nav={nav} setNav={setNav} editCount={editCount} />

        <main className="studio__main">
          <Crumbs nav={nav} grid={grid} gridScoped={gridScoped} dirty={dirty} />
          <div className="studio__scroll">
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
              onChronoDate={setChronoDate}
              onChronoSpan={setChronoSpan}
              runsList={runsList}
              onRunsChange={setRunsList}
              onRestore={restoreRun}
              dirty={dirty}
              onEdit={edit}
              onRevert={revert}
              onRun={run}
            />
          </div>
        </main>
      </div>

      <footer className="studio__status mono">
        <span>
          Phase <b>ST Schedule</b>
        </span>
        <span>
          Scenario <b>{active.name}</b>, {editCount} edit{editCount === 1 ? '' : 's'}
        </span>
        <span>
          Luzon reserve margin <b>{pct(solved.reserveMarginPct.luzon / 100, 1)}</b>
        </span>
        <span className="studio__statspace" />
        <span>simplified merit-order model, calibrated against observed prices</span>
      </footer>
    </div>
  )
}

function Ribbon({
  scenarios,
  ai,
  dirty,
  editCount,
  grid,
  gridScoped,
  onRun,
  onPick,
  onAdd,
  onRevertAll,
  onCopy,
  onGrid,
}: {
  scenarios: Scenario[]
  ai: number
  dirty: boolean
  editCount: number
  grid: GridKey
  gridScoped: boolean
  onRun: () => void
  onPick: (i: number) => void
  onAdd: () => void
  onRevertAll: () => void
  onCopy: () => void
  onGrid: (g: GridKey) => void
}) {
  const [tab, setTab] = useState<'home' | 'model' | 'solution'>('home')
  const tabs = ['home', 'model', 'solution'] as const
  return (
    <div className="ribbon">
      <div className="ribbon__tabs" role="tablist">
        {tabs.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={t === tab}
            className={`ribbon__tab ${t === tab ? 'is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div className="ribbon__groups">
        {tab === 'home' && (
          <>
            <RibbonGroup label="Simulation">
              <button
                className={`btn btn--run${dirty ? ' is-dirty' : ''}`}
                onClick={onRun}
                aria-label="Run the simulation"
              >
                <PlayIcon /> Run
              </button>
            </RibbonGroup>
            <RibbonGroup label="Scenario">
              <select
                className="ribbon__select"
                value={ai}
                onChange={(e) => onPick(Number(e.target.value))}
                aria-label="Active scenario"
              >
                {scenarios.map((s, i) => (
                  <option key={i} value={i}>
                    {s.name}
                    {i > 0 ? ` (${Object.keys(s.overrides).length})` : ''}
                  </option>
                ))}
              </select>
              <button className="btn btn--ghost btn--sm" onClick={onAdd}>
                + New
              </button>
            </RibbonGroup>
            {gridScoped && (
              <RibbonGroup label="Region">
                <Segmented
                  ariaLabel="Select grid"
                  value={grid}
                  onChange={onGrid}
                  options={GRIDS.map((g) => ({
                    value: g,
                    label: g[0].toUpperCase() + g.slice(1),
                  }))}
                />
              </RibbonGroup>
            )}
          </>
        )}
        {tab === 'model' && (
          <>
            <RibbonGroup label="Edits">
              <button
                className="btn btn--ghost btn--sm"
                onClick={onRevertAll}
                disabled={editCount === 0}
              >
                Revert all
              </button>
              <span className="ribbon__meta mono">{editCount} edited</span>
            </RibbonGroup>
            <RibbonGroup label="Objects">
              <button
                className="btn btn--ghost btn--sm"
                disabled
                title="The fleet is fixed to the sourced units in this open build"
              >
                + Add object
              </button>
            </RibbonGroup>
          </>
        )}
        {tab === 'solution' && (
          <>
            <RibbonGroup label="Phase">
              <span className="ribbon__meta">
                ST Schedule <span className="tree__live">active</span>
              </span>
            </RibbonGroup>
            <RibbonGroup label="Export">
              <button className="btn btn--ghost btn--sm" onClick={onCopy}>
                Copy summary
              </button>
            </RibbonGroup>
          </>
        )}
      </div>
    </div>
  )
}

function RibbonGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="ribbon__group">
      <div className="ribbon__cmds">{children}</div>
      <div className="ribbon__grouplabel">{label}</div>
    </div>
  )
}

function Explorer({
  nav,
  setNav,
  editCount,
}: {
  nav: Nav
  setNav: (n: Nav) => void
  editCount: number
}) {
  const [tab, setTab] = useState<'system' | 'simulation'>('system')
  const isActive = (n: Nav) => JSON.stringify(n) === JSON.stringify(nav)
  return (
    <nav className="tree" aria-label="Model explorer">
      <div className="tree__tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === 'system'}
          className={`tree__tab ${tab === 'system' ? 'is-active' : ''}`}
          onClick={() => setTab('system')}
        >
          System
        </button>
        <button
          role="tab"
          aria-selected={tab === 'simulation'}
          className={`tree__tab ${tab === 'simulation' ? 'is-active' : ''}`}
          onClick={() => setTab('simulation')}
        >
          Simulation
        </button>
      </div>

      {tab === 'system' ? (
        <>
          <TreeGroup label="Objects">
            {CLASSES.map((c) => (
              <TreeItem
                key={c.id}
                label={c.label}
                icon="obj"
                active={isActive({ kind: 'class', id: c.id })}
                onClick={() => setNav({ kind: 'class', id: c.id })}
              />
            ))}
          </TreeGroup>
          <TreeGroup label="Shortcut">
            <TreeItem
              label="Quick scenario"
              icon="obj"
              live
              active={isActive({ kind: 'quick' })}
              onClick={() => setNav({ kind: 'quick' })}
            />
          </TreeGroup>
          <div className="tree__foot">
            {editCount} property edit{editCount === 1 ? '' : 's'} in this scenario. Edit
            cells, then Run.
          </div>
        </>
      ) : (
        <>
          <TreeGroup label="Phases">
            {PHASES.map((p) => (
              <div
                key={p}
                className={`tree__phase ${p === 'ST Schedule' ? 'is-active' : 'is-off'}`}
              >
                <NodeIcon group="Solution" />
                {p}
                {p === 'ST Schedule' && <span className="tree__live">active</span>}
              </div>
            ))}
          </TreeGroup>
          <TreeGroup label="Solution">
            {(Object.keys(SOL_LABEL) as SolId[]).map((id) => (
              <TreeItem
                key={id}
                label={SOL_LABEL[id]}
                icon="sol"
                live={LIVE_SOL.has(id)}
                active={isActive({ kind: 'sol', id })}
                onClick={() => setNav({ kind: 'sol', id })}
              />
            ))}
            <TreeItem
              label="Compare scenarios"
              icon="sol"
              live
              active={isActive({ kind: 'compare' })}
              onClick={() => setNav({ kind: 'compare' })}
            />
            <TreeItem
              label="Saved runs"
              icon="sol"
              active={isActive({ kind: 'runs' })}
              onClick={() => setNav({ kind: 'runs' })}
            />
          </TreeGroup>
          <TreeGroup label="Analysis">
            {(Object.keys(ANALYSIS_LABEL) as AnalysisId[]).map((id) => (
              <TreeItem
                key={id}
                label={ANALYSIS_LABEL[id]}
                icon="sol"
                active={isActive({ kind: 'analysis', id })}
                onClick={() => setNav({ kind: 'analysis', id })}
              />
            ))}
          </TreeGroup>
        </>
      )}
    </nav>
  )
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
  onChronoDate,
  onChronoSpan,
  runsList,
  onRunsChange,
  onRestore,
  dirty,
  onEdit,
  onRevert,
  onRun,
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
  onChronoDate: (v: string) => void
  onChronoSpan: (v: 'day' | 'week') => void
  runsList: SavedRun[]
  onRunsChange: (runs: SavedRun[]) => void
  onRestore: (run: SavedRun) => void
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onRun: () => void
}) {
  if (nav.kind === 'compare')
    return <CompareView d={d} objects={objects} scenarios={scenarios} />
  if (nav.kind === 'runs')
    return <RunsView runs={runsList} onRunsChange={onRunsChange} onRestore={onRestore} />
  if (nav.kind === 'class') {
    return (
      <ClassPane
        cls={nav.id}
        objects={objects}
        overrides={overrides}
        dirty={dirty}
        onEdit={onEdit}
        onRevert={onRevert}
        onRun={onRun}
      />
    )
  }
  if (nav.kind === 'quick') return <ScenarioView d={d} grid={grid} />
  if (nav.kind === 'analysis') {
    if (nav.id === 'backcast') {
      if (!profiles)
        return <div className="basecase-banner">Loading the observed day profiles.</div>
      return <BackcastView d={d} profiles={profiles} grid={grid} />
    }
    if (nav.id === 'reserve') return <ReserveView d={d} grid={grid} />
    if (nav.id === 'bill') return <BillView />
    return <MarketPowerView d={d} />
  }
  // solution views
  const sol = nav.id
  if (sol === 'merit') return <SolvedMeritView s={solved} grid={grid} />
  if (sol === 'chrono') {
    if (!profiles || !chronoDate)
      return <div className="basecase-banner">Loading the observed day profiles.</div>
    return (
      <ChronologyView
        d={d}
        profiles={profiles}
        objects={objects}
        overrides={ranOv}
        grid={grid}
        scenarioName={scenarioName}
        date={chronoDate}
        span={chronoSpan}
        onDate={onChronoDate}
        onSpan={onChronoSpan}
        onSaved={onRunsChange}
      />
    )
  }
  if (sol === 'flows') return <SolvedFlowsView s={solved} />
  if (sol === 'n1') return <SolvedN1View s={solved} grid={grid} />
  if (sol === 'regions') return <SolvedRegionsView s={solved} />
  if (sol === 'reliability')
    return (
      <div>
        <SolvedReliabilityView s={solved} />
        <div className="basecase-banner">
          Base case reference: the 20,000-draw pipeline distribution and the storage
          buy-back, calibrated and not recomputed from your edits.
        </div>
        <ReliabilityView d={d} />
      </div>
    )
  // baked, calibrated base-case reference views
  return (
    <div>
      <div className="basecase-banner">
        Base case reference. This view is calibrated against the observed window and is
        not recomputed from your edits.
      </div>
      {sol === 'duration' && <DurationView d={d} grid={grid} />}
      {sol === 'marginal' && <MarginalView d={d} grid={grid} />}
    </div>
  )
}

function Crumbs({
  nav,
  grid,
  gridScoped,
  dirty,
}: {
  nav: Nav
  grid: GridKey
  gridScoped: boolean
  dirty: boolean
}) {
  let root = 'System'
  let leaf = ''
  if (nav.kind === 'class') {
    root = 'System'
    leaf = CLASSES.find((c) => c.id === nav.id)?.label ?? ''
  } else if (nav.kind === 'quick') {
    root = 'System'
    leaf = 'Quick scenario'
  } else if (nav.kind === 'compare') {
    root = 'Solution'
    leaf = 'Compare scenarios'
  } else if (nav.kind === 'runs') {
    root = 'Solution'
    leaf = 'Saved runs'
  } else if (nav.kind === 'sol') {
    root = 'Solution'
    leaf = SOL_LABEL[nav.id]
  } else {
    root = 'Analysis'
    leaf = ANALYSIS_LABEL[nav.id]
  }
  return (
    <div className="studio__crumbs">
      {root} <span className="studio__crumbsep">/</span> <strong>{leaf}</strong>
      {gridScoped && (
        <>
          <span className="studio__crumbsep">/</span>{' '}
          {grid[0].toUpperCase() + grid.slice(1)}
        </>
      )}
      {nav.kind === 'sol' && LIVE_SOL.has(nav.id) && dirty && (
        <span className="crumbs__stale">edits pending, Run to update</span>
      )}
    </div>
  )
}

function TreeGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="tree__group">
      <div className="tree__grouphead">{label}</div>
      <ul className="tree__list">{children}</ul>
    </div>
  )
}

function TreeItem({
  label,
  icon,
  live,
  active,
  onClick,
}: {
  label: string
  icon: 'obj' | 'sol'
  live?: boolean
  active: boolean
  onClick: () => void
}) {
  return (
    <li>
      <button
        className={`tree__item ${active ? 'is-active' : ''}`}
        onClick={onClick}
        aria-current={active}
      >
        <NodeIcon group={icon === 'obj' ? 'Objects' : 'Solution'} />
        {label}
        {live && <span className="tree__live">live</span>}
      </button>
    </li>
  )
}

type DataTab = 'objects' | 'memberships' | 'properties'

function ClassPane({
  cls,
  objects,
  overrides,
  dirty,
  onEdit,
  onRevert,
  onRun,
}: {
  cls: ClassId
  objects: ReturnType<typeof baseObjects>
  overrides: Scenario['overrides']
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onRun: () => void
}) {
  const [tab, setTab] = useState<DataTab>('properties')
  const rows = objects[cls]
  const tabs: { id: DataTab; label: string }[] = [
    { id: 'objects', label: 'Objects' },
    { id: 'memberships', label: 'Memberships' },
    { id: 'properties', label: 'Properties' },
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
            Edit a value and it is tagged to the active scenario. Press <b>Run</b> to
            re-solve. The base value returns with the × on a changed cell.
            {cls === 'generator' && rows.length > 40 && (
              <span>
                {' '}
                Units and dependable capacities are the DOE list of existing power plants
                (2025 editions); units under 20 MW dependable stay in the data but out of
                this grid.
              </span>
            )}
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

function BrandMark() {
  return (
    <svg
      width="26"
      height="26"
      viewBox="0 0 32 32"
      aria-hidden="true"
      className="brandmark"
    >
      <rect x="1.5" y="1.5" width="29" height="29" rx="7" fill="var(--primary)" />
      <path
        d="M9 22V10h5.5a3.8 3.8 0 010 7.6H12"
        fill="none"
        stroke="var(--on-primary)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M18 10l5 12M23 10l-5 12"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Dot() {
  return <span className="livedot" aria-hidden="true" />
}

function PlayIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 5l12 7-12 7z" fill="currentColor" />
    </svg>
  )
}

function NodeIcon({ group }: { group: string }) {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="nodeicon"
    >
      {group === 'Objects' ? (
        <rect
          x="4"
          y="4"
          width="16"
          height="16"
          rx="3"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        />
      ) : (
        <path
          d="M4 12h16M12 4v16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      )}
    </svg>
  )
}
