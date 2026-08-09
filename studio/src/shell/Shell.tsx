// The studio shell: top bar, question-first rail, command palette, run dock.
//
// It replaces a three-tab ribbon plus a two-tab object tree plus a breadcrumb,
// which together spent 190 of a 900-pixel laptop before any data appeared and
// clipped at 390. The rule here is that the scenario controls never move and
// the answer never leaves the screen, whichever of the 42 views is open.

import { useEffect, useMemo, useRef, useState } from 'react'
import type { GridKey } from '../lib/types'
import { GRIDS } from '../lib/types'
import { php, pct } from '../lib/data'
import type { SolvedModel } from '../studio/model'
import {
  ALL_DESTS,
  GROUPS,
  type Dest,
  type Nav,
  destOf,
  groupOf,
  sameNav,
  searchDests,
} from './nav'

const GRID_LABEL: Record<GridKey, string> = {
  luzon: 'Luzon',
  visayas: 'Visayas',
  mindanao: 'Mindanao',
}

// --- top bar ----------------------------------------------------------------

export function TopBar({
  nav,
  grid,
  onGrid,
  gridScoped,
  scenarios,
  ai,
  onPickScenario,
  onAddScenario,
  editCount,
  dirty,
  onRun,
  onOpenPalette,
  onOpenNav,
  onExit,
  theme,
  onToggleTheme,
}: {
  nav: Nav
  grid: GridKey
  onGrid: (g: GridKey) => void
  gridScoped: boolean
  scenarios: { name: string; overrides: Record<string, number> }[]
  ai: number
  onPickScenario: (i: number) => void
  onAddScenario: () => void
  editCount: number
  dirty: boolean
  onRun: () => void
  onOpenPalette: () => void
  onOpenNav: () => void
  onExit: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}) {
  const dest = destOf(nav)
  return (
    <header className="bar">
      <button
        className="bar__navbtn"
        onClick={onOpenNav}
        aria-label="Open the view list"
        title="Open view list"
      >
        <IconMenu />
      </button>

      <div className="bar__brand">
        <BrandMark />
        <div className="bar__brandtext">
          <span className="bar__name">Power Dispatch Studio</span>
          <span className="bar__tag">Philippine spot power market (WESM)</span>
        </div>
      </div>

      <button className="bar__search" onClick={onOpenPalette} aria-label="Find a view">
        <IconSearch />
        <span className="bar__searchtxt">{dest ? dest.label : 'Find a view'}</span>
        <kbd className="bar__kbd">⌘K</kbd>
      </button>

      <div className="bar__group" role="group" aria-label="Region">
        {GRIDS.map((g) => (
          <button
            key={g}
            className={`bar__seg ${g === grid ? 'is-on' : ''}`}
            aria-pressed={g === grid}
            disabled={!gridScoped}
            title={
              gridScoped
                ? `Read ${GRID_LABEL[g]}`
                : `${dest?.label ?? 'This view'} reads all three grids together`
            }
            onClick={() => onGrid(g)}
          >
            {GRID_LABEL[g]}
          </button>
        ))}
      </div>

      <label className="bar__scn">
        <span className="bar__scnlabel">Active scenario</span>
        <select
          value={ai}
          onChange={(e) => onPickScenario(Number(e.target.value))}
          aria-label="Active scenario"
        >
          {scenarios.map((s, i) => (
            <option key={i} value={i}>
              {s.name}
              {i > 0 ? ` (${Object.keys(s.overrides).length} edits)` : ''}
            </option>
          ))}
        </select>
      </label>
      <button
        className="bar__icon"
        onClick={onAddScenario}
        title="Create a copy of this scenario"
        aria-label="New scenario"
      >
        <IconPlus />
      </button>

      <div className="bar__spacer" />

      <button
        className={`bar__run ${dirty ? 'is-dirty' : ''}`}
        onClick={onRun}
        disabled={!dirty}
        aria-label="Run the simulation"
        title={
          dirty
            ? `Re-solve with ${editCount} edit${editCount === 1 ? '' : 's'}`
            : 'Solved and current. Edit a value to re-run.'
        }
      >
        <IconPlay />
        {dirty ? `Run ${editCount} edit${editCount === 1 ? '' : 's'}` : 'Solved'}
      </button>

      {/* the Run button already carries the solve state in its own label and
          colour, so a second chip beside it would report the same thing twice */}
      <span className="sr-only" aria-live="polite">
        {dirty ? `${editCount} edits are not solved yet` : 'Solved and current'}
      </span>

      <button
        className="bar__icon"
        onClick={onToggleTheme}
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
        title="Change color theme"
      >
        {theme === 'light' ? <IconMoon /> : <IconSun />}
      </button>
      <button
        className="bar__icon"
        onClick={onExit}
        aria-label="Close the studio"
        title="Close the studio"
      >
        <IconClose />
      </button>
    </header>
  )
}

// --- question-first rail ----------------------------------------------------

export function NavRail({
  nav,
  onNav,
  open,
  onClose,
  editCount,
}: {
  nav: Nav
  onNav: (n: Nav) => void
  open: boolean
  onClose: () => void
  editCount: number
}) {
  const current = groupOf(nav)
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set([current?.id ?? 'tonight'])
  )
  useEffect(() => {
    if (current) setExpanded((s) => (s.has(current.id) ? s : new Set([...s, current.id])))
  }, [current])

  return (
    <>
      {open && <div className="rail__scrim" onClick={onClose} aria-hidden="true" />}
      <nav className={`rail ${open ? 'is-open' : ''}`} aria-label="Views by question">
        <div className="rail__head">
          <span>What do you want to know?</span>
          <button
            className="rail__close"
            onClick={onClose}
            aria-label="Close the view list"
          >
            <IconClose />
          </button>
        </div>
        <div className="rail__scroll">
          {GROUPS.map((g) => {
            const isOpen = expanded.has(g.id)
            const holdsActive = g.dests.some((d) => sameNav(d.nav, nav))
            return (
              <section key={g.id} className="rail__group">
                <button
                  className={`rail__grouphead ${holdsActive ? 'is-current' : ''}`}
                  aria-expanded={isOpen}
                  onClick={() =>
                    setExpanded((s) => {
                      const n = new Set(s)
                      if (n.has(g.id)) n.delete(g.id)
                      else n.add(g.id)
                      return n
                    })
                  }
                >
                  <IconChevron open={isOpen} />
                  <span>{g.label}</span>
                  <span className="rail__count">{g.dests.length}</span>
                </button>
                {isOpen && (
                  <ul className="rail__list">
                    {g.dests.map((d) => (
                      <li key={d.slug}>
                        <button
                          className={`rail__item ${sameNav(d.nav, nav) ? 'is-active' : ''}`}
                          onClick={() => {
                            onNav(d.nav)
                            onClose()
                          }}
                          title={d.hint}
                        >
                          <span className="rail__label">{d.label}</span>
                          {d.live && <span className="rail__live">live</span>}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )
          })}
        </div>
        <div className="rail__foot">
          {editCount === 0
            ? 'No edits yet. Open Quick what-if to change a scenario setting.'
            : `${editCount} edit${editCount === 1 ? '' : 's'} in this scenario. Press Run.`}
          {/* an analyst arriving from a licensed tool wants the capability list
              and the stated limits before the first click, not after an hour */}
          <a className="rail__doc" href="../for-analysts.html">
            Capability list, stated limits, and replay accuracy
          </a>
        </div>
      </nav>
    </>
  )
}

// --- command palette --------------------------------------------------------

export function CommandPalette({
  open,
  onClose,
  onNav,
}: {
  open: boolean
  onClose: () => void
  onNav: (n: Nav) => void
}) {
  const [q, setQ] = useState('')
  const [i, setI] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const hits = useMemo(() => searchDests(q), [q])

  useEffect(() => {
    if (open) {
      setQ('')
      setI(0)
      window.setTimeout(() => input.current?.focus(), 0)
    }
  }, [open])
  useEffect(() => {
    listRef.current?.querySelector('.is-sel')?.scrollIntoView({ block: 'nearest' })
  }, [i])

  if (!open) return null
  const go = (d: Dest | undefined) => {
    if (!d) return
    onNav(d.nav)
    onClose()
  }
  return (
    <div className="pal__scrim" onClick={onClose}>
      <div
        className="pal"
        role="dialog"
        aria-modal="true"
        aria-label="Find a view"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pal__inputrow">
          <IconSearch />
          <input
            ref={input}
            className="pal__input"
            value={q}
            placeholder="Search 42 views, such as bill, site, historical replay, or reserve"
            aria-label="Search views"
            onChange={(e) => {
              setQ(e.target.value)
              setI(0)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setI((n) => Math.min(n + 1, hits.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setI((n) => Math.max(n - 1, 0))
              } else if (e.key === 'Enter') {
                e.preventDefault()
                go(hits[i])
              } else if (e.key === 'Escape') {
                onClose()
              }
            }}
          />
          <kbd className="pal__kbd">esc</kbd>
        </div>
        {hits.length === 0 ? (
          <p className="pal__empty">
            No view matches "{q}". Try a plain word: price, margin, bill, site, outage.
          </p>
        ) : (
          <ul className="pal__list" ref={listRef}>
            {hits.slice(0, 40).map((d, n) => (
              <li key={d.slug}>
                <button
                  className={`pal__item ${n === i ? 'is-sel' : ''}`}
                  onMouseEnter={() => setI(n)}
                  onClick={() => go(d)}
                >
                  <span className="pal__label">{d.label}</span>
                  <span className="pal__hint">{d.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="pal__foot">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> move
          </span>
          <span>
            <kbd>enter</kbd> open
          </span>
          <span>
            {hits.length} of {ALL_DESTS.length} views
          </span>
        </div>
      </div>
    </div>
  )
}

// Run summary.
// The analyst switches views to look at the same
// scenario from a different angle, and the old shell dropped the answer off
// the screen every time. Here the three cleared grids and their move against
// the base case stay pinned, in every view.

export function RunDock({
  solved,
  base,
  live,
  grid,
  onGrid,
  scenarioName,
  dirty,
  open,
  onToggle,
  onTakeAway,
}: {
  solved: SolvedModel
  base: SolvedModel
  /** the Quick scenario's live coupled clear, when that panel is open */
  live: Record<GridKey, number> | null
  grid: GridKey
  onGrid: (g: GridKey) => void
  scenarioName: string
  dirty: boolean
  open: boolean
  onToggle: () => void
  /** opens Saved runs, where a run leaves as an HTML report or a CSV */
  onTakeAway?: () => void
}) {
  const isBase = scenarioName === 'Base Case'
  // The what-if controls preview against the calibrated base; they do not write the
  // model, so the preview gets its own band rather than overwriting the solved
  // figures. Showing one number from each source in one card would be a lie.
  const previewing =
    !!live && GRIDS.some((g) => Math.abs(live[g] - solved.coupled.price[g]) >= 0.005)
  return (
    <aside
      className={`dock ${open ? '' : 'is-collapsed'}`}
      aria-label="Current simulation run"
    >
      <button className="dock__toggle" onClick={onToggle} aria-expanded={open}>
        <IconChevronRight open={open} />
        <span className="dock__togglelabel">Current run</span>
      </button>
      {/* always rendered: below 980 the dock is the strip under the bar and CSS
          keeps it open, so the answer never leaves a phone screen either */}
      <div className="dock__body">
        {previewing && live && (
          <div className="dock__preview">
            <div className="dock__previewhead">What-if preview, not yet in the model</div>
            {GRIDS.map((g) => (
              <div key={g} className="dock__previewrow">
                <span className="dock__k">{GRID_LABEL[g]}</span>
                <span className="dock__v mono">{php(live[g])}</span>
                <Delta v={live[g] - base.coupled.price[g]} fmt={(x) => php(x)} small />
              </div>
            ))}
          </div>
        )}
        <div className="dock__scn">
          <span className="dock__scnname">{scenarioName}</span>
          {dirty && <span className="dock__stale">changes need a run</span>}
        </div>
        {GRIDS.map((g) => {
          const p = solved.coupled.price[g]
          const b = base.coupled.price[g]
          const dp = p - b
          const m = solved.reserveMarginPct[g]
          const dm = m - base.reserveMarginPct[g]
          const l = solved.reliability[g].lolp_pct
          return (
            <button
              key={g}
              className={`dock__grid ${g === grid ? 'is-on' : ''}`}
              onClick={() => onGrid(g)}
              title={`Show ${GRID_LABEL[g]} in views that analyze one grid`}
            >
              <div className="dock__gridhead">
                <span className="dock__gridname">{GRID_LABEL[g]}</span>
                {!isBase && <Delta v={dp} fmt={(x) => php(x)} />}
              </div>
              <div className="dock__price mono">{php(p)}</div>
              <div className="dock__rows">
                <span className="dock__k">Spare capacity (reserve margin)</span>
                <span className="dock__v mono">
                  {pct(m / 100, 1)}
                  {!isBase && (
                    <Delta
                      v={dm}
                      fmt={(x) => `${x >= 0 ? '+' : ''}${x.toFixed(1)}pp`}
                      small
                    />
                  )}
                </span>
                <span className="dock__k">Chance of demand shortfall</span>
                <span className="dock__v mono">{pct(l / 100, 2)}</span>
              </div>
            </button>
          )
        })}
        <p className="dock__note">
          {previewing
            ? 'The cards below show the solved model. The preview above shows the result of the current what-if settings.'
            : isBase
              ? 'The base case checked against recorded prices, at the evening reference hour. Edit a table value and press Run to change it.'
              : 'Change against Base Case, at the evening reference hour.'}
        </p>
        {onTakeAway && (
          <button className="dock__take" onClick={onTakeAway}>
            Take this run away
            <span className="dock__takehint">
              Saved runs writes a standalone HTML report and an hourly CSV
            </span>
          </button>
        )}
      </div>
    </aside>
  )
}

/** A signed move, coloured by direction, never by colour alone. */
function Delta({
  v,
  fmt,
  small,
}: {
  v: number
  fmt: (x: number) => string
  small?: boolean
}) {
  if (Math.abs(v) < 0.005)
    return (
      <span className={`delta delta--flat ${small ? 'delta--sm' : ''}`}>no change</span>
    )
  const up = v > 0
  return (
    <span className={`delta delta--${up ? 'up' : 'down'} ${small ? 'delta--sm' : ''}`}>
      {up ? '▲' : '▼'} {fmt(Math.abs(v))}
    </span>
  )
}

// --- icons ------------------------------------------------------------------

function BrandMark() {
  return (
    <svg
      className="bar__mark"
      width="22"
      height="22"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <rect
        x="1"
        y="1"
        width="22"
        height="22"
        rx="6"
        fill="currentColor"
        opacity="0.16"
      />
      <path d="M13 3L6 13h4.6L10 21l7.4-10.6H12.6L13 3z" fill="currentColor" />
    </svg>
  )
}
function IconSearch() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path
        d="M16 16l4.5 4.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconMenu() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4 7h16M4 12h16M4 17h16"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconClose() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M6 6l12 12M18 6L6 18"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconPlus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 5v14M5 12h14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconPlay() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 4l13 8-13 8z" fill="currentColor" />
    </svg>
  )
}
function IconChevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`chev ${open ? 'is-open' : ''}`}
      width="12"
      height="12"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        d="M9 5l7 7-7 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconChevronRight({ open }: { open: boolean }) {
  return (
    <svg
      className={`chev ${open ? '' : 'is-open'}`}
      width="12"
      height="12"
      viewBox="0 0 24 24"
      aria-hidden="true"
      style={{ transform: open ? 'rotate(0deg)' : 'rotate(180deg)' }}
    >
      <path
        d="M15 5l-7 7 7 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
    </svg>
  )
}
function IconMoon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"
      />
    </svg>
  )
}
function IconSun() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"
      />
    </svg>
  )
}
