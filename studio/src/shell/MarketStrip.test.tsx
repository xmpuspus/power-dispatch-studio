import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { MarketStrip } from './MarketStrip'

const items = [
  {
    hour: 18,
    recordedPrice: 7.1,
    replayedPrice: 6.8,
    demandMw: 9_400,
    marginal: 'coal',
    constraint: true,
    shortfallMw: 0,
  },
  {
    hour: 19,
    recordedPrice: 9.4,
    replayedPrice: 9.1,
    demandMw: 9_800,
    marginal: 'oil',
    constraint: false,
    shortfallMw: 20,
  },
]

describe('MarketStrip', () => {
  it('keeps each hour exposed as a button', () => {
    const html = renderToStaticMarkup(
      <MarketStrip
        date="2026-06-17"
        grid="luzon"
        items={items}
        selectedHour={19}
        onSelectHour={() => undefined}
      />
    )

    expect(html).toContain('<button')
    expect(html).toContain('aria-pressed="true"')
    expect(html).not.toContain('role="listitem"')
  })
})
