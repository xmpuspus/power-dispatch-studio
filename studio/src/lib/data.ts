import { useEffect, useState } from 'react'
import type {
  Bill,
  Dispatch,
  Emissions,
  Fleet,
  GeneratorProps,
  MarketAnchors,
  MarketOps,
  MarketPower,
  Meta,
  Pasa,
  Profiles,
  Projects,
  DemandPath,
  Reserve,
} from './types'

const BASE = `${import.meta.env.BASE_URL}data`
const cache = new Map<string, Promise<unknown>>()

function load<T>(file: string): Promise<T> {
  if (!cache.has(file)) {
    cache.set(
      file,
      fetch(`${BASE}/${file}`).then((r) => {
        if (!r.ok) throw new Error(`${file}: ${r.status}`)
        return r.json()
      })
    )
  }
  return cache.get(file) as Promise<T>
}

export interface Async<T> {
  data: T | null
  error: string | null
  loading: boolean
}

function useJson<T>(file: string): Async<T> {
  const [state, setState] = useState<Async<T>>({
    data: null,
    error: null,
    loading: true,
  })
  useEffect(() => {
    let live = true
    load<T>(file)
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch(
        (e: Error) => live && setState({ data: null, error: e.message, loading: false })
      )
    return () => {
      live = false
    }
  }, [file])
  return state
}

export const useDispatch = () => useJson<Dispatch>('dispatch.json')
export const useReserve = () => useJson<Reserve>('reserve.json')
export const useMarketOps = () => useJson<MarketOps>('market_ops.json')
// per-day observed offer book (chronology's offer mode); 404 = no book
// derived for that date, surfaced as the hook's error state
export const useOfferDay = (date: string | null) =>
  useJson<import('../studio/chrono').OfferDay>(
    date ? `offers/OFFERD_${date.replace(/-/g, '')}.json` : 'offers/none.json'
  )
export const useBill = () => useJson<Bill>('bill.json')
export const useMarketPower = () => useJson<MarketPower>('market_power.json')
export const useProfiles = () => useJson<Profiles>('profiles.json')
export const useFleet = () => useJson<Fleet>('fleet.json')
export const usePasa = () => useJson<Pasa>('pasa.json')
export const useRtdoe5 = () => useJson<import('./types').Rtdoe5>('rtdoe5.json')
export const useNodalObs = () => useJson<import('./types').NodalObs>('nodal_obs.json')
export const useExpansion = () => useJson<import('./types').Expansion>('expansion.json')
export const useProjects = () => useJson<Projects>('projects.json')
export const useDemandPath = () => useJson<DemandPath>('demand_path.json')
export const useEmissions = () => useJson<Emissions>('emissions.json')
export const useMeta = () => useJson<Meta>('meta.json')
export const useMarketAnchors = () => useJson<MarketAnchors>('market_anchors.json')
// the day-by-day archive feed (also drives the map's Drivers mode); the
// day-explainer reads its per-day binding equipment and context
export const useDrivers = () => useJson<import('./types').Drivers>('drivers.json')

export interface FeatureCollection<P> {
  type: 'FeatureCollection'
  features: {
    type: 'Feature'
    geometry: { type: string; coordinates: number[] }
    properties: P
  }[]
}
export const useGenerators = () =>
  useJson<FeatureCollection<GeneratorProps>>('generators.geojson')

// formatting: tabular figures throughout, so grids never jitter
const nf = (min = 0, max = 0) =>
  new Intl.NumberFormat('en-US', {
    minimumFractionDigits: min,
    maximumFractionDigits: max,
  })

export const num = (v: number | null | undefined, dp = 0): string =>
  v == null || Number.isNaN(v) ? '-' : nf(dp, dp).format(v)

export const php = (v: number | null | undefined, dp = 2): string =>
  v == null || Number.isNaN(v) ? '-' : `₱${nf(dp, dp).format(v)}`

export const pct = (frac: number | null | undefined, dp = 0): string =>
  frac == null || Number.isNaN(frac) ? '-' : `${nf(dp, dp).format(frac * 100)}%`

export const fuelLabel = (f: string): string => f.replace(/_/g, ' ')

// client-side CSV download: serialize a row array into a file the browser saves,
// so any view can hand the analyst its own numbers without a server round-trip.
// The first row's keys are the header; values are quote-escaped.
export function downloadCsv(
  rows: Record<string, string | number | null | undefined>[],
  filename: string
): void {
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v: string | number | null | undefined) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const body = [
    cols.join(','),
    ...rows.map((r) => cols.map((c) => esc(r[c])).join(',')),
  ].join('\n')
  const url = URL.createObjectURL(new Blob([body], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// fuel -> design-token color, shared by the charts and their legends
const FUEL_VAR: Record<string, string> = {
  coal: 'var(--fuel-coal)',
  oil: 'var(--fuel-oil)',
  natural_gas: 'var(--fuel-gas)',
  hydro: 'var(--fuel-hydro)',
  geothermal: 'var(--fuel-geothermal)',
  solar: 'var(--fuel-solar)',
  wind: 'var(--series-flow)',
  biomass: 'var(--positive)',
  storage: 'var(--series-storage)',
  firm: 'var(--primary)',
  import: 'var(--series-flow)',
  export: 'var(--series-flow)',
  shortage: 'var(--negative)',
}
export const fuelColor = (f: string): string => FUEL_VAR[f] ?? 'var(--text-faint)'
