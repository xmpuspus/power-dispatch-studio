// vitest runs in node: load the HiGHS wasm once before any suite solves
import { beforeAll } from 'vitest'
import { initSolver } from './src/studio/solver'

beforeAll(async () => {
  await initSolver()
})
