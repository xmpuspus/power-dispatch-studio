import { useEffect, useMemo, useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { GRIDS } from '../lib/types'
import { pct, useGenerators } from '../lib/data'
import { Segmented, ThemeToggle } from '../ui/kit'
import { DurationView, MarginalView, ReliabilityView, ReserveView } from './views'
import { ScenarioView } from './Scenario'
import { BillView } from './Bill'
import { MarketPowerView } from './MarketPower'
import {
  CLASSES,
  baseObjects,
  overrideKey,
  solveModel,
  type ClassId,
  type Scenario,
  type SolvedModel,
} from './model'
import {
  ObjectsList,
  PropertiesGrid,
  SolvedFlowsView,
  SolvedMeritView,
  SolvedN1View,
  SolvedRegionsView,
} from './model-views'

type SolId =
  'merit' | 'flows' | 'n1' | 'regions' | 'duration' | 'marginal' | 'reliability'
type AnalysisId = 'reserve' | 'bill' | 'market'
type Nav =
  | { kind: 'class'; id: ClassId }
  | { kind: 'quick' }
  | { kind: 'sol'; id: SolId }
  | { kind: 'analysis'; id: AnalysisId }

const SOL_LABEL: Record<SolId, string> = {
  merit: 'Merit order',
  flows: 'Coupled flows',
  n1: 'N-1 contingency',
  regions: 'Regions',
  duration: 'Price duration',
  marginal: 'Marginal units',
  reliability: 'Reliability',
}
const ANALYSIS_LABEL: Record<AnalysisId, string> = {
  reserve: 'Reserve market',
  bill: 'Bill impact',
  market: 'Market power',
}
// views that recompute from the current model (the rest read the calibrated base case)
const LIVE_SOL = new Set<SolId>(['merit', 'flows', 'n1', 'regions'])
// navs that pick a grid
const GRID_SOL = new Set<SolId>(['merit', 'n1', 'duration', 'marginal'])
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
  const genRows = useMemo(
    () => (gens.data?.features ?? []).map((f) => f.properties),
    [gens.data]
  )
  const objects = useMemo(() => baseObjects(d, genRows), [d, genRows])

  const [scenarios, setScenarios] = useState<Scenario[]>([
    { name: 'Base Case', overrides: {} },
  ])
  const [ai, setAi] = useState(0)
  const active = scenarios[ai]
  const [nav, setNav] = useState<Nav>({ kind: 'class', id: 'generator' })
  const [grid, setGrid] = useState<GridKey>('luzon')
  const [solved, setSolved] = useState<SolvedModel>(() => solveModel(d, objects, {}))
  const [dirty, setDirty] = useState(false)

  // re-solve the base when the generator list arrives, as long as nothing is pending
  useEffect(() => {
    if (!dirty) setSolved(solveModel(d, objects, active.overrides))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [objects])

  const run = () => {
    setSolved(solveModel(d, objects, active.overrides))
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
    (nav.kind === 'analysis' && nav.id === 'reserve')

  return (
    <div className="studio" data-testid="studio">
      <header className="studio__bar">
        <div className="studio__brand">
          <BrandMark />
          <div>
            <div className="studio__name">
              PLEXOS<span className="studio__from">from Temu</span>
            </div>
            <div className="studio__tag">open dispatch studio</div>
          </div>
        </div>

        <div className="studio__ribbon">
          <label className="ribbon__scn">
            <span>Scenario</span>
            <select
              value={ai}
              onChange={(e) => pickScenario(Number(e.target.value))}
              aria-label="Active scenario"
            >
              {scenarios.map((s, i) => (
                <option key={i} value={i}>
                  {s.name}
                  {i > 0 ? ` (${Object.keys(s.overrides).length})` : ''}
                </option>
              ))}
            </select>
          </label>
          <button className="btn btn--ghost btn--sm" onClick={addScenario}>
            + Scenario
          </button>
          <button
            className={`btn btn--run${dirty ? ' is-dirty' : ''}`}
            onClick={run}
            aria-label="Run the simulation"
          >
            <PlayIcon /> Run
          </button>
          <span className={`statuschip statuschip--${dirty ? 'unsolved' : 'solved'}`}>
            <Dot /> {dirty ? 'Unsolved' : 'Solved'}
          </span>
        </div>

        <div className="studio__barright">
          {gridScoped && (
            <Segmented
              ariaLabel="Select grid"
              value={grid}
              onChange={setGrid}
              options={GRIDS.map((g) => ({
                value: g,
                label: g[0].toUpperCase() + g.slice(1),
              }))}
            />
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button className="btn btn--ghost" onClick={onExit}>
            Close studio
          </button>
        </div>
      </header>

      <div className="studio__body">
        <Explorer nav={nav} setNav={setNav} editCount={editCount} />

        <main className="studio__main">
          <Crumbs nav={nav} grid={grid} gridScoped={gridScoped} dirty={dirty} />
          <div className="studio__scroll">
            <DataPane
              d={d}
              nav={nav}
              grid={grid}
              solved={solved}
              objects={objects}
              overrides={active.overrides}
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
  nav,
  grid,
  solved,
  objects,
  overrides,
  dirty,
  onEdit,
  onRevert,
  onRun,
}: {
  d: Dispatch
  nav: Nav
  grid: GridKey
  solved: SolvedModel
  objects: ReturnType<typeof baseObjects>
  overrides: Scenario['overrides']
  dirty: boolean
  onEdit: (cls: ClassId, id: string, prop: string, value: number) => void
  onRevert: (cls: ClassId, id: string, prop: string) => void
  onRun: () => void
}) {
  if (nav.kind === 'class') {
    const cls = CLASSES.find((c) => c.id === nav.id)!
    const rows = objects[nav.id]
    return (
      <div className="datapane">
        <DataTabs active="properties" />
        <div className="datapane__hint">
          Edit a value and it is tagged to the active scenario. Press <b>Run</b> to
          re-solve. The base value returns with the × on a changed cell.
          {dirty && (
            <button className="btn btn--run btn--sm datapane__run" onClick={onRun}>
              <PlayIcon /> Run
            </button>
          )}
        </div>
        <PropertiesGrid
          cls={cls.id}
          rows={rows}
          overrides={overrides}
          onEdit={onEdit}
          onRevert={onRevert}
        />
        <div className="datapane__objects">
          <h3 className="panel__title">Objects</h3>
          <ObjectsList rows={rows} />
        </div>
      </div>
    )
  }
  if (nav.kind === 'quick') return <ScenarioView d={d} grid={grid} />
  if (nav.kind === 'analysis') {
    if (nav.id === 'reserve') return <ReserveView d={d} grid={grid} />
    if (nav.id === 'bill') return <BillView />
    return <MarketPowerView d={d} />
  }
  // solution views
  const sol = nav.id
  if (sol === 'merit') return <SolvedMeritView s={solved} grid={grid} />
  if (sol === 'flows') return <SolvedFlowsView s={solved} />
  if (sol === 'n1') return <SolvedN1View s={solved} grid={grid} />
  if (sol === 'regions') return <SolvedRegionsView s={solved} />
  // baked, calibrated base-case reference views
  return (
    <div>
      <div className="basecase-banner">
        Base case reference. This view is calibrated against the observed window and is
        not recomputed from your edits.
      </div>
      {sol === 'duration' && <DurationView d={d} grid={grid} />}
      {sol === 'marginal' && <MarginalView d={d} grid={grid} />}
      {sol === 'reliability' && <ReliabilityView d={d} />}
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

function DataTabs({ active }: { active: 'objects' | 'memberships' | 'properties' }) {
  const tabs: { id: typeof active; label: string; on: boolean }[] = [
    { id: 'objects', label: 'Objects', on: true },
    { id: 'memberships', label: 'Memberships', on: false },
    { id: 'properties', label: 'Properties', on: true },
  ]
  return (
    <div className="datatabs" role="tablist">
      {tabs.map((t) => (
        <span
          key={t.id}
          role="tab"
          aria-selected={t.id === active}
          className={`datatabs__tab ${t.id === active ? 'is-active' : ''} ${t.on ? '' : 'is-off'}`}
        >
          {t.label}
        </span>
      ))}
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
