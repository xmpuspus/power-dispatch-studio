import { useEffect, useState } from 'react'
import type {
  Bill,
  Dispatch,
  Fleet,
  GeneratorProps,
  MarketPower,
  Profiles,
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
export const useBill = () => useJson<Bill>('bill.json')
export const useMarketPower = () => useJson<MarketPower>('market_power.json')
export const useProfiles = () => useJson<Profiles>('profiles.json')
export const useFleet = () => useJson<Fleet>('fleet.json')

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
