import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../lib/data', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/data')>()
  return {
    ...actual,
    useBill: () => ({
      loading: false,
      error: null,
      data: {
        available: true,
        period: 'June 2026',
        supply_mix_pct: { psa: 69, ipp_first_gas_prime_coregen: 21, wesm: 10 },
        wesm_price_php_kwh: 7.03,
        generation_charge_php_kwh: 9.07,
        pass_through_factor: 0.1,
        household_kwh_month: 200,
        note: 'Published supply mix.',
      },
    }),
    useMarketPower: () => ({
      loading: false,
      error: null,
      data: {
        available: true,
        as_of: 'June 2026',
        companies: [
          { name: 'Firm A', mw: 6_000, share_pct: 22.44 },
          { name: 'Firm B', mw: 5_500, share_pct: 21.75 },
        ],
        others_share_pct: 55.81,
        cap_demand_pct: 25,
        cap_installed_pct: 30,
        hhi_floor: 1_600,
        hhi_band: 'moderately concentrated',
        top2_combined_pct: 44.19,
        largest: { name: 'Firm A', share_pct: 22.44 },
        note: 'Published capacity shares.',
        src: 'https://example.com/shares',
        src_cap: 'https://example.com/cap',
      },
    }),
  }
})

import { BillView } from './Bill'
import { MarketPowerView } from './MarketPower'

describe('part-to-whole bars', () => {
  it('draws each supply source as its share of the whole', () => {
    const html = renderToStaticMarkup(<BillView />)

    expect(html).toContain('style="width:69%')
    expect(html).toContain('style="width:21%')
    expect(html).toContain('style="width:10%')
    expect(html).not.toContain('style="width:100%')
  })

  it('draws each firm as its share of national capacity', () => {
    const html = renderToStaticMarkup(<MarketPowerView />)

    expect(html).toContain('style="width:22.44%')
    expect(html).toContain('style="width:21.75%')
    expect(html).toContain('style="width:55.81%')
    expect(html).toContain('the bars are not a compliance test')
    expect(html).not.toContain('mixbars__cap')
  })
})
