// vitest runs in node: load the HiGHS wasm once before any suite solves
import { beforeAll } from 'vitest'
import { initSolver } from './src/studio/solver'

beforeAll(async () => {
  await initSolver()
})

// vitest runs in node, so runs.ts's localStorage-backed persistence would
// otherwise silently no-op (the ReferenceError is swallowed by its own
// try/catch). A minimal in-memory polyfill lets those tests exercise the
// real save/load path instead of only the in-memory return value.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>()
  globalThis.localStorage = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() {
      return store.size
    },
  } as Storage
}
