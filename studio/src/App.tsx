import { Suspense, lazy, useEffect, useState } from 'react'
import { useDispatch } from './lib/data'
import { initSolver, solverReady } from './studio/solver'
import { ThemeToggle } from './ui/kit'

const Studio = lazy(() => import('./studio/Studio').then((m) => ({ default: m.Studio })))

type Theme = 'light' | 'dark'

const THEME_KEY = 'pds.theme'

// The choice survives a reload. Without this, an analyst who picks light on a
// dark-set machine gets dark back on every refresh and every deep link.
// No stored choice means the system preference still decides, and the app keeps
// following it as the system flips.
function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved === 'light' || saved === 'dark') return saved
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const follow = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem(THEME_KEY)) setTheme(e.matches ? 'dark' : 'light')
    }
    mq.addEventListener('change', follow)
    return () => mq.removeEventListener('change', follow)
  }, [])
  const toggle = () =>
    setTheme((t) => {
      const next = t === 'light' ? 'dark' : 'light'
      localStorage.setItem(THEME_KEY, next)
      return next
    })
  return [theme, toggle]
}

export default function App() {
  const { data: d, loading, error } = useDispatch()
  // /studio/ opens the studio. A share link and a view deep link always did;
  // the bare URL used to stop at a second copy of the map, which carried the
  // copy the real map replaced on 2026-08-03.
  const [studio] = useState(true)
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
          <a className="btn btn--ghost" href="../">
            Back to the map
          </a>
        </div>
      </header>

      {/* The map lives at / and was redrawn on 2026-08-03. This bundle kept a
          second copy of it with the older copy, and every /studio/ visitor met
          that copy first. One map, one studio: the close button goes to the
          real one. */}
      <main className="app__main app__main--studioonly">
        <p className="app__await">
          {error || solverErr
            ? `Data error: ${error ?? solverErr}`
            : 'Opening the studio.'}
        </p>
      </main>

      {studio && d && solverOk && (
        <Suspense
          fallback={<div className="studio studio--loading">Loading the studio.</div>}
        >
          <Studio
            d={d}
            onExit={() => {
              window.location.href = '../'
            }}
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
          <a className="btn btn--ghost" href="../">
            Back to the map
          </a>
        </div>
      )}
    </div>
  )
}
