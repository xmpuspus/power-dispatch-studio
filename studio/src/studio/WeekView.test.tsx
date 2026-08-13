import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { Dispatch, Profiles } from '../lib/types'
import { WeekView } from './WeekView'

const read = <T,>(name: string): T =>
  JSON.parse(
    readFileSync(
      fileURLToPath(new URL(`../../public/data/${name}`, import.meta.url)),
      'utf8'
    )
  )

const dispatch = read<Dispatch>('dispatch.json')
const profiles = read<Profiles>('profiles.json')

describe('WeekView', () => {
  it('prompts for a battery instead of charting an all-zero default', () => {
    const html = renderToStaticMarkup(
      <WeekView d={dispatch} profiles={profiles} grid="luzon" />
    )

    expect(html).toContain('Choose a battery size to calculate inter-day storage value')
    expect(html).not.toContain('aria-label="Storage state of charge across the week"')
  })
})
