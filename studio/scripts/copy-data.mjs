// Copy the pipeline's baked JSON into public/data so the app reads the same
// artifacts the map ships. The pipeline (../pipeline) stays the single source of
// truth; public/data is gitignored and regenerated on every dev/build.
import { mkdir, readdir, copyFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = join(here, '..', '..', 'web', 'data')
const dest = join(here, '..', 'public', 'data')

await mkdir(dest, { recursive: true })
const files = (await readdir(src)).filter((f) => f.endsWith('.json') || f.endsWith('.geojson'))
await Promise.all(files.map((f) => copyFile(join(src, f), join(dest, f))))
console.log(`copied ${files.length} baked artifacts -> public/data`)

// per-day observed offer books (lazy-fetched by the chronology's offer mode)
const offersSrc = join(src, 'offers')
try {
  const offerFiles = (await readdir(offersSrc)).filter((f) => f.endsWith('.json'))
  await mkdir(join(dest, 'offers'), { recursive: true })
  await Promise.all(
    offerFiles.map((f) => copyFile(join(offersSrc, f), join(dest, 'offers', f)))
  )
  console.log(`copied ${offerFiles.length} offer days -> public/data/offers`)
} catch {
  console.log('no offer days baked (web/data/offers absent)')
}

// analyst-facing CSV exports (baked to web/data/exports); served from the
// studio origin too so the archive is reachable from either front door
const exportsSrc = join(src, 'exports')
try {
  const exportFiles = await readdir(exportsSrc)
  await mkdir(join(dest, 'exports'), { recursive: true })
  await Promise.all(
    exportFiles.map((f) => copyFile(join(exportsSrc, f), join(dest, 'exports', f)))
  )
  console.log(`copied ${exportFiles.length} exports -> public/data/exports`)
} catch {
  console.log('no exports baked (web/data/exports absent)')
}

// the HiGHS wasm binary ships as a static asset; solver.ts locateFile()
// resolves it from the app base at runtime
await copyFile(
  join(here, '..', 'node_modules', 'highs', 'build', 'highs.wasm'),
  join(here, '..', 'public', 'highs.wasm')
)
console.log('copied highs.wasm -> public/')
