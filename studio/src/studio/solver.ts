// The HiGHS solver, loaded once. The wasm build initialises asynchronously
// (about 2.5 MB, fetched when the studio opens and cached after); every solve
// after that is synchronous, so the engines and views stay synchronous code.

import loadHighs from 'highs'

type Highs = Awaited<ReturnType<typeof loadHighs>>

let instance: Highs | null = null
let loading: Promise<void> | null = null

/** Load the wasm solver once. The studio shell awaits this before mounting. */
export function initSolver(): Promise<void> {
  if (instance) return Promise.resolve()
  if (!loading) {
    const opts =
      typeof window !== 'undefined'
        ? { locateFile: (f: string) => `${import.meta.env.BASE_URL}${f}` }
        : undefined
    loading = loadHighs(opts).then(
      (h) => {
        instance = h
      },
      (e: unknown) => {
        // a transient load failure must stay retryable, not cached forever
        loading = null
        throw e
      }
    )
  }
  return loading
}

export function solverReady(): boolean {
  return instance !== null
}

export interface LpSolution {
  objective: number
  /** primal values by column name (absent columns are 0) */
  col: (name: string) => number
  /** duals by row name (absent rows are 0) */
  dual: (name: string) => number
}

/** Solve canonical LP text. Throws if the solver is not loaded or the model
 * does not solve to optimality (the model is always feasible by construction:
 * unserved load is a bounded slack). */
export function solveLp(text: string): LpSolution {
  if (!instance) throw new Error('solver not loaded; await initSolver() first')
  const res = instance.solve(text)
  if (res.Status !== 'Optimal') throw new Error(`LP status ${res.Status}`)
  const cols = res.Columns as unknown as Record<string, { Primal: number }>
  const duals = new Map<string, number>()
  for (const r of res.Rows as unknown as { Name?: string; Dual?: number }[]) {
    if (r.Name != null && r.Dual != null) duals.set(r.Name, r.Dual)
  }
  return {
    objective: (res as unknown as { ObjectiveValue: number }).ObjectiveValue,
    col: (name) => cols[name]?.Primal ?? 0,
    dual: (name) => duals.get(name) ?? 0,
  }
}
