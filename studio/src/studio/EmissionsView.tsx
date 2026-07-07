// Emissions: CO2 for the ran scenario over an observed day, from the same
// dispatched energy the Chronology view shows, priced in tCO2 with sourced
// per-technology factors. Operational (combustion) only, and it says so.

import { useMemo, useState } from 'react'
import type { Dispatch, EmissionFactor, GridKey, Profiles } from '../lib/types'
import { num, fuelLabel, useEmissions } from '../lib/data'
import { Panel, StatTile, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { runChronology } from './chrono'
import { chronoOptsFrom, type ClassId, type ObjRow, type Overrides } from './model'
import { emissionsByFuel, runEmissionsT } from './insights'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']

export function EmissionsView({
  d,
  profiles,
  objects,
  overrides,
}: {
  d: Dispatch
  profiles: Profiles
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
}) {
  const em = useEmissions()
  const days = profiles.days
  const [date, setDate] = useState<string | null>(null)
  const dayDate =
    (date && days.some((x) => x.date === date) ? date : null) ??
    profiles.default_day ??
    days[days.length - 1]?.date

  const opts = useMemo(() => chronoOptsFrom(objects, overrides), [objects, overrides])
  const run = useMemo(
    () => (dayDate ? runChronology(d, profiles, dayDate, opts) : null),
    [d, profiles, dayDate, opts]
  )
  const base = useMemo(
    () => (dayDate ? runChronology(d, profiles, dayDate, {}) : null),
    [d, profiles, dayDate]
  )

  if (em.loading) return <EmptyNote>Loading the emission factors.</EmptyNote>
  if (em.error || !em.data?.available)
    return <EmptyNote>Emission factors not baked. Run make data.</EmptyNote>
  if (!run || !base || !dayDate)
    return <EmptyNote>No observed day in the archive window yet.</EmptyNote>

  const factors = em.data.factor_map ?? {}
  const totalT = runEmissionsT(run.hours, factors)
  const baseT = runEmissionsT(base.hours, factors)
  const byFuel = emissionsByFuel(run.hours, factors)
  const energyMwh = byFuel.reduce((s, r) => s + r.mwh, 0)
  const intensity = energyMwh > 0 ? totalT / energyMwh : 0
  const edited = Object.keys(overrides).length > 0
  const ngef = em.data.ngef

  const fuelCols: Column<(typeof byFuel)[number]>[] = [
    { key: 'fuel', header: 'Fuel', render: (r) => fuelLabel(r.fuel) },
    {
      key: 'mwh',
      header: 'MWh dispatched',
      align: 'right',
      mono: true,
      render: (r) => num(r.mwh),
    },
    {
      key: 't',
      header: 'tCO2',
      align: 'right',
      mono: true,
      render: (r) =>
        r.fuel === 'biomass' && (factors.biomass ?? null) == null
          ? 'not counted'
          : num(r.tco2),
    },
  ]
  const factorCols: Column<EmissionFactor>[] = [
    { key: 'fuel', header: 'Technology', render: (f) => fuelLabel(f.fuel) },
    {
      key: 'v',
      header: 'tCO2/MWh',
      align: 'right',
      mono: true,
      render: (f) => (f.tco2_per_mwh == null ? 'excluded' : f.tco2_per_mwh.toFixed(3)),
    },
    { key: 'basis', header: 'Basis', render: (f) => f.basis },
    {
      key: 'src',
      header: '',
      render: (f) => <Source href={f.src} label="source" />,
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Observed day
          <select
            className="ribbon__select"
            value={dayDate}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Observed day for the emissions read"
          >
            {days.map((x) => (
              <option key={x.date} value={x.date}>
                {x.date}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="stat-row">
        <StatTile
          label="CO2, all grids, this day"
          value={num(totalT)}
          unit="tCO2"
          hint={edited ? `base model ${num(baseT)} tCO2` : 'base model'}
          tone={edited && totalT > baseT ? 'accent' : 'default'}
        />
        <StatTile
          label="Intensity"
          value={intensity.toFixed(3)}
          unit="tCO2/MWh"
          hint={
            ngef
              ? `DOE grid factor ${ngef.luzon_visayas_tco2_per_mwh.toFixed(2)} (LV, ${ngef.vintage.slice(0, 9)})`
              : undefined
          }
        />
        <StatTile
          label="Energy priced"
          value={num(energyMwh)}
          unit="MWh"
          hint={`${GRIDS.map((g) => g[0].toUpperCase() + g.slice(1)).join(', ')}, 24 hours`}
        />
      </div>

      <Panel
        title="CO2 by fuel, ran scenario"
        subtitle={`Dispatched energy per fuel over ${dayDate} times its factor. Storage carries no factor of its own; biomass is reported uncounted.`}
      >
        <DataGrid columns={fuelCols} rows={byFuel} getKey={(r) => r.fuel} />
      </Panel>

      <Panel
        title="The factors, with sources"
        subtitle={em.data.unit}
        right={ngef ? <Source href={ngef.src} label="DOE grid factor" /> : undefined}
      >
        <DataGrid
          columns={factorCols}
          rows={em.data.factors ?? []}
          getKey={(f) => f.fuel}
        />
        <p className="note">{em.data.note}</p>
        {ngef && <p className="note">{ngef.note}</p>}
      </Panel>

      <p className="note">
        A data-center scenario reads directly here: flat load raises the energy the
        marginal fuel serves, and the delta against the base model is that build's
        operational CO2 on this model. {em.data.disclaimer}
      </p>
    </div>
  )
}
