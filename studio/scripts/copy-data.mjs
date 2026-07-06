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
