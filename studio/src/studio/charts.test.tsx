import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { DispatchArea, DurationCurve, HourLines, ShareBars, SocChart } from './charts'

describe('quantitative charts', () => {
  it('replaces a sub-centavo duration curve with its exact range', () => {
    const html = renderToStaticMarkup(
      <DurationCurve
        modeled={[
          { pct: 0, price: 6.004 },
          { pct: 50, price: 6.0 },
          { pct: 100, price: 6.0 },
        ]}
      />
    )

    expect(html).toContain('Price changed by less than ₱0.01/kWh')
    expect(html).toContain('₱6.000 to ₱6.004/kWh across 3 modeled hours')
    expect(html).not.toContain('<svg')
  })

  it('pads a narrow but material duration range instead of magnifying it', () => {
    const html = renderToStaticMarkup(
      <DurationCurve
        modeled={[
          { pct: 0, price: 6.02 },
          { pct: 100, price: 6.0 },
        ]}
      />
    )

    expect(html).toContain('<svg')
    expect(html).toContain('₱6.26')
    expect(html).toContain('₱6.01')
    expect(html).toContain('₱5.76')
  })

  it('draws percentage shares against 100 percent', () => {
    const html = renderToStaticMarkup(
      <ShareBars
        rows={[
          { block: 'coal', share_pct: 25 },
          { block: 'oil', share_pct: 75 },
        ]}
      />
    )

    expect(html).toContain('style="width:25%')
    expect(html).toContain('style="width:75%')
    expect(html).not.toContain('style="width:100%')
  })

  it('keeps zero-series axis labels from stacking on each other', () => {
    const html = renderToStaticMarkup(
      <HourLines series={[{ label: 'Modeled price', color: '#123456', pts: [0, 0] }]} />
    )

    expect(html.match(/>0<\/text>/g)).toHaveLength(1)
  })

  it('labels small dispatch charts in MW instead of repeated zero thousands', () => {
    const html = renderToStaticMarkup(
      <DispatchArea fuelGen={[{ coal: 300 }, { coal: 600 }]} demand={[300, 600]} />
    )

    expect(html).toContain('>600</text>')
    expect(html).toContain('>312</text>')
    expect(html).not.toContain('>0k</text>')
  })

  it('states when configured storage never dispatches', () => {
    const html = renderToStaticMarkup(
      <SocChart
        soc={[0, 0, 0]}
        charge={[0, 0, 0]}
        discharge={[0, 0, 0]}
        energyMwh={4_000}
      />
    )

    expect(html).toContain('No storage dispatch')
    expect(html).toContain('State of charge stayed at 0 MWh throughout this run')
    expect(html).not.toContain('<svg')
  })
})
