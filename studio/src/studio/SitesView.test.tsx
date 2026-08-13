import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../lib/data', () => ({
  useProfiles: () => ({
    loading: false,
    error: null,
    data: { solar_profile: Array(24).fill(0) },
  }),
  useSites: () => ({
    loading: false,
    error: null,
    data: {
      available: true,
      day: '2026-07-22',
      n_sites: 1,
      note: 'Test network.',
      disclaimer: 'Estimate only.',
      sites: [
        {
          id: 'zero-headroom',
          name: 'Zero-headroom site',
          kind: 'data center',
          lon: 121,
          lat: 14,
          mw: 100,
          bus: 'BUS-1',
          grid: 'luzon',
          snap_km: 1,
          circuits: [],
          limit_mw_by_hour: Array(24).fill(0),
          limit_min_mw: 0,
          limit_max_mw: 0,
          outages: [],
          radially_fed: false,
          already_over_rating: true,
          worst_base_loading: 1.1,
          linearity_max_error: 0,
        },
      ],
    },
  }),
}))

import { SitesView } from './SitesView'

describe('SitesView hourly headroom', () => {
  it('uses one label when headroom is unchanged all day', () => {
    const html = renderToStaticMarkup(<SitesView />)

    expect(html).toContain('0 MW throughout the day')
    expect(html.match(/0 MW throughout the day/g)).toHaveLength(1)
    expect(html).toMatch(
      /<text[^>]*text-anchor="middle"[^>]*>0 MW throughout the day<\/text>/
    )
  })
})
