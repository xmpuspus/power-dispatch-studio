import { Suspense, lazy, useEffect, useState } from 'react'
import { useDispatch, pct, php } from './lib/data'
import { initSolver, solverReady } from './studio/solver'
import { StatTile, ThemeToggle } from './ui/kit'

const MapView = lazy(() => import('./map/MapView').then((m) => ({ default: m.MapView })))
const Studio = lazy(() => import('./studio/Studio').then((m) => ({ default: m.Studio })))

// Two kinds of link open the studio directly. A shared scenario (ChronoView's
// copyLink, decoded for real by studio/runs.decodeShare once the studio mounts)
// carries `m=`; a view deep link carries `v=<slug>`. A plain pattern test is
// enough to decide whether to jump straight in, without pulling the studio's
// solver bundle into the main chunk just to check.
const HAS_SHARE_HASH = /[#&](m=[A-Za-z0-9_-]+|v=[a-z0-9-]+)/

type Theme = 'light' | 'dark'

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() =>
    window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'light' ? 'dark' : 'light'))]
}

export default function App() {
  const { data: d, loading, error } = useDispatch()
  // open straight to the studio for a shared-scenario link, instead of
  // leaving the recipient at the hero with no sign a scenario is waiting
  const [studio, setStudio] = useState(() => HAS_SHARE_HASH.test(window.location.hash))
  const [solverOk, setSolverOk] = useState(() => solverReady())
  const [solverErr, setSolverErr] = useState<string | null>(null)
  const [theme, toggleTheme] = useTheme()

  // the wasm solver (~2.5 MB) loads once; hovering Open starts the fetch early
  const warmSolver = () => {
    initSolver().then(
      () => setSolverOk(true),
      (e: Error) => setSolverErr(e.message)
    )
  }
  useEffect(() => {
    if (studio) warmSolver()
  }, [studio])

  return (
    <div className="app">
      <header className="app__bar">
        <div className="app__brand">
          <span className="app__logo">
            Power Dispatch<span className="app__logo-ph"> Studio</span>
          </span>
          <span className="app__brandsub">
            Philippine grid, priced from the operator's own files
          </span>
        </div>
        <div className="app__baractions">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <button
            className="btn btn--primary"
            onMouseEnter={warmSolver}
            onFocus={warmSolver}
            onClick={() => setStudio(true)}
          >
            Open Power Dispatch Studio
          </button>
        </div>
      </header>

      <main className="app__main">
        <section className="hero">
          <div className="hero__copy">
            <h1 className="hero__title">
              Test how much data-center demand the grid can carry
            </h1>
            <p className="hero__lede">
              This lowest-cost-first dispatch model (merit order) uses IEMOP's public
              5-minute files and checks its results against recorded prices. It clears the
              three grids together over the high-voltage direct-current (HVDC) links,
              accounts for baseload commitments and random plant outages, and tests where
              storage can cover a shortfall.
            </p>
            <div className="hero__stats">
              {d ? (
                <>
                  <StatTile
                    label="Spare dependable capacity, Luzon (reserve margin)"
                    value={pct((d.adequacy.luzon.reserve_margin_pct ?? 0) / 100, 1)}
                    hint="at the evening peak"
                  />
                  <StatTile
                    label="Shortfall chance with DICT 1.5 GW (LOLP)"
                    value={pct(
                      d.reliability_mc.dict_2028_luzon.distribution.lolp_pct / 100,
                      2
                    )}
                    hint="with the announced added demand"
                    tone="accent"
                  />
                  <StatTile
                    label="Visayas minus Luzon spread"
                    value={php(
                      d.coupling.spread_decomposition.visayas_vs_luzon.observed_php_kwh
                    )}
                    hint="the gap when the links bind"
                  />
                </>
              ) : (
                <div className="hero__loading">
                  {error ? `Data error: ${error}` : 'Loading the solution.'}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="app__mapsection" aria-label="Network map">
          <Suspense fallback={<div className="mapview__fallback">Loading map.</div>}>
            <MapView theme={theme} />
          </Suspense>
        </section>

        <footer className="app__foot">
          <span>
            Statistical indicators derived from public data (IEMOP, NGCP, Meralco, DOE,
            PCIJ). Patterns may have legitimate explanations.
          </span>
          <span className="app__footnote">
            Power Dispatch Studio is a free, open, independent production-cost tool for
            the Philippine Wholesale Electricity Spot Market (WESM), built on public data.
          </span>
        </footer>
      </main>

      {studio && d && solverOk && (
        <Suspense
          fallback={<div className="studio studio--loading">Loading the studio.</div>}
        >
          <Studio
            d={d}
            onExit={() => setStudio(false)}
            theme={theme}
            onToggleTheme={toggleTheme}
          />
        </Suspense>
      )}
      {studio && !(d && solverOk) && (
        <div className="studio studio--loading">
          <p>
            {error || solverErr
              ? `Data error: ${error ?? solverErr}`
              : !d && loading
                ? 'Loading the model.'
                : 'Loading the calculation engine.'}
          </p>
          <button className="btn btn--ghost" onClick={() => setStudio(false)}>
            Close
          </button>
        </div>
      )}
    </div>
  )
}
