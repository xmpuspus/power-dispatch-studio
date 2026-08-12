import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { destBySlug } from './nav'
import { EvidenceSummary, GlossaryDrawer, NavRail, TopBar } from './Shell'
import { evidenceForSlug } from './workflows'

const noop = () => undefined

describe('workflow navigation', () => {
  it('shows analyst workspaces and only the active workspace steps', () => {
    const nav = destBySlug('chronology')!.nav
    const html = renderToStaticMarkup(
      <NavRail nav={nav} onNav={noop} open={false} onClose={noop} editCount={0} />
    )

    expect(html).toContain('Analyst workflows')
    expect(html).toContain('Market day')
    expect(html).toContain('Scenario analysis')
    expect(html).toContain('Hourly market replay')
    expect(html).toContain('Model and data')
    expect(html).not.toContain('>live<')
    expect(html).not.toContain('>Generators<')
  })
})

describe('persistent market context', () => {
  it('keeps the market date, terms, and result state in the top bar', () => {
    const html = renderToStaticMarkup(
      <TopBar
        nav={destBySlug('chronology')!.nav}
        grid="luzon"
        onGrid={noop}
        gridScoped
        dates={['2026-06-16', '2026-06-17']}
        date="2026-06-17"
        onDate={noop}
        scenarios={[{ name: 'Base Case', overrides: {} }]}
        ai={0}
        onPickScenario={noop}
        onAddScenario={noop}
        editCount={0}
        dirty={false}
        onRun={noop}
        onOpenPalette={noop}
        onOpenNav={noop}
        onOpenGlossary={noop}
        onExit={noop}
        theme="light"
        onToggleTheme={noop}
      />
    )

    expect(html).toContain('Market date')
    expect(html).toContain('2026-06-17')
    expect(html).toContain('Terms')
    expect(html).toContain('Results current')
    expect(html).not.toContain('>Solved<')
  })
})

describe('evidence and definitions', () => {
  it('states the source type without mixing a replay with a record', () => {
    const evidence = evidenceForSlug('backcast')
    const html = renderToStaticMarkup(
      <EvidenceSummary
        evidence={evidence}
        date="2026-06-17"
        coverage="2026-04-07 to 2026-08-11"
      />
    )
    expect(html).toContain('Model replay')
    expect(html).toContain('IEMOP records replayed')
    expect(html).toContain('2026-04-07 to 2026-08-11')
  })

  it('renders expanded market terms in a keyboard-accessible glossary dialog', () => {
    const html = renderToStaticMarkup(<GlossaryDrawer open onClose={noop} />)
    expect(html).toContain('Market terms')
    expect(html).toContain('Load-weighted average price')
    expect(html).toContain('High-voltage direct current')
    expect(html).toContain('Search market terms')
  })
})
