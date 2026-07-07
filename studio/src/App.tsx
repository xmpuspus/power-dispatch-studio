import { Suspense, lazy, useEffect, useState } from 'react'
import { useDispatch, pct, php } from './lib/data'
import { StatTile, ThemeToggle } from './ui/kit'

const MapView = lazy(() => import('./map/MapView').then((m) => ({ default: m.MapView })))
const Studio = lazy(() => import('./studio/Studio').then((m) => ({ default: m.Studio })))

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
  const [studio, setStudio] = useState(false)
  const [theme, toggleTheme] = useTheme()

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
          <button className="btn btn--primary" onClick={() => setStudio(true)}>
            Open Power Dispatch Studio
          </button>
        </div>
      </header>

      <main className="app__main">
        <section className="hero">
          <div className="hero__copy">
            <h1 className="hero__title">Can the grid host the data-center wave?</h1>
            <p className="hero__lede">
              A merit-order dispatch model built on IEMOP's public 5-minute files,
              calibrated against observed prices. It couples the three grids over the HVDC
              links, commits baseload, runs forced-outage Monte Carlo, and shows where
              storage buys back the gap. Open the studio to explore the solution.
            </p>
            <div className="hero__stats">
              {d ? (
                <>
                  <StatTile
                    label="Reserve margin, Luzon"
                    value={pct((d.adequacy.luzon.reserve_margin_pct ?? 0) / 100, 1)}
                    hint="at the evening peak"
                  />
                  <StatTile
                    label="LOLP with DICT 1.5 GW"
                    value={pct(
                      d.reliability_mc.dict_2028_luzon.distribution.lolp_pct / 100,
                      2
                    )}
                    hint="the data-center wave"
                    tone="accent"
                  />
                  <StatTile
                    label="Visayas minus Luzon spread"
                    value={php(
                      d.coupling.spread_decomposition.visayas_vs_luzon.observed_php_kwh
                    )}
                    hint="driven by scarcity"
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
            Power Dispatch Studio is an independent open homage to the PLEXOS workflow.
            Not affiliated with Energy Exemplar. Not PLEXOS.
          </span>
        </footer>
      </main>

      {studio && d && (
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
      {studio && !d && (
        <div className="studio studio--loading">
          <p>{loading ? 'Loading the model.' : `Data error: ${error}`}</p>
          <button className="btn btn--ghost" onClick={() => setStudio(false)}>
            Close
          </button>
        </div>
      )}
    </div>
  )
}
