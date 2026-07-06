import { useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { GRIDS } from '../lib/types'
import { num, pct } from '../lib/data'
import { Segmented, ThemeToggle } from '../ui/kit'
import {
  MeritView,
  DurationView,
  MarginalView,
  FlowsView,
  ReliabilityView,
  ReserveView,
  N1View,
  RegionsView,
  InterfacesView,
} from './views'
import { ScenarioView } from './Scenario'
import { BillView } from './Bill'
import { MarketPowerView } from './MarketPower'

type ViewId =
  | 'scenario'
  | 'merit'
  | 'duration'
  | 'marginal'
  | 'flows'
  | 'reserve'
  | 'reliability'
  | 'bill'
  | 'market'
  | 'generators'
  | 'interfaces'
  | 'regions'

const GRID_SCOPED: ViewId[] = [
  'scenario',
  'merit',
  'duration',
  'marginal',
  'reserve',
  'generators',
]

const TREE: {
  group: string
  items: { id: ViewId; label: string; live?: boolean }[]
}[] = [
  {
    group: 'Scenario',
    items: [{ id: 'scenario', label: 'Scenario builder', live: true }],
  },
  {
    group: 'Objects',
    items: [
      { id: 'generators', label: 'Generators' },
      { id: 'interfaces', label: 'Interfaces' },
      { id: 'regions', label: 'Regions' },
    ],
  },
  {
    group: 'Solution',
    items: [
      { id: 'merit', label: 'Merit order' },
      { id: 'duration', label: 'Price duration' },
      { id: 'flows', label: 'Coupled flows' },
      { id: 'reserve', label: 'Reserve market' },
      { id: 'reliability', label: 'Reliability' },
      { id: 'bill', label: 'Bill impact' },
      { id: 'market', label: 'Market power' },
      { id: 'marginal', label: 'Marginal units' },
    ],
  },
]

const TITLE: Record<ViewId, string> = {
  scenario: 'Scenario builder',
  merit: 'Merit order',
  duration: 'Price duration',
  marginal: 'Marginal units',
  flows: 'Coupled flows',
  reserve: 'Reserve market',
  reliability: 'Reliability',
  bill: 'Bill impact',
  market: 'Market power',
  generators: 'Generators',
  interfaces: 'Interfaces',
  regions: 'Regions',
}

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
  const [view, setView] = useState<ViewId>('scenario')
  const [grid, setGrid] = useState<GridKey>('luzon')
  const scoped = GRID_SCOPED.includes(view)
  const dcLolp = d.reliability_mc.dict_2028_luzon.distribution.lolp_pct

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
        <span className="studio__homage" title="This is an independent, open homage.">
          An independent homage. Not affiliated with Energy Exemplar. Not PLEXOS.
        </span>
        <div className="studio__barright">
          {scoped && (
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
          <button className="btn btn--solved" disabled aria-label="Model already solved">
            <Dot /> Solved
          </button>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <button className="btn btn--ghost" onClick={onExit}>
            Close studio
          </button>
        </div>
      </header>

      <div className="studio__body">
        <nav className="tree" aria-label="Model explorer">
          {TREE.map((sec) => (
            <div className="tree__group" key={sec.group}>
              <div className="tree__grouphead">{sec.group}</div>
              <ul className="tree__list">
                {sec.items.map((it) => (
                  <li key={it.id}>
                    <button
                      className={`tree__item ${view === it.id ? 'is-active' : ''}`}
                      onClick={() => setView(it.id)}
                      aria-current={view === it.id}
                    >
                      <NodeIcon group={sec.group} />
                      {it.label}
                      {it.live && <span className="tree__live">live</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <div className="tree__foot">
            {d.model}. {num(d.coupling.n_coupled_intervals)} coupled intervals.
          </div>
        </nav>

        <main className="studio__main">
          <div className="studio__crumbs">
            Solution <span className="studio__crumbsep">/</span>{' '}
            <strong>{TITLE[view]}</strong>
            {scoped && (
              <>
                <span className="studio__crumbsep">/</span>{' '}
                {grid[0].toUpperCase() + grid.slice(1)}
              </>
            )}
          </div>
          <div className="studio__scroll">
            {view === 'scenario' && <ScenarioView d={d} grid={grid} />}
            {view === 'merit' && <MeritView d={d} grid={grid} />}
            {view === 'duration' && <DurationView d={d} grid={grid} />}
            {view === 'marginal' && <MarginalView d={d} grid={grid} />}
            {view === 'flows' && <FlowsView d={d} />}
            {view === 'reserve' && <ReserveView d={d} grid={grid} />}
            {view === 'reliability' && <ReliabilityView d={d} />}
            {view === 'bill' && <BillView />}
            {view === 'market' && <MarketPowerView d={d} />}
            {view === 'generators' && <N1View d={d} grid={grid} />}
            {view === 'interfaces' && <InterfacesView d={d} />}
            {view === 'regions' && <RegionsView d={d} />}
          </div>
        </main>
      </div>

      <footer className="studio__status mono">
        <span>
          Solved <b>{num(d.calibration.luzon.n_intervals)}</b> market intervals
        </span>
        <span>
          window from <b>{d.calibration_window.from}</b>
        </span>
        <span>
          DICT-wave LOLP <b>{pct(dcLolp / 100, 2)}</b>
        </span>
        <span className="studio__statspace" />
        <span>simplified merit-order model, calibrated against observed prices</span>
      </footer>
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
