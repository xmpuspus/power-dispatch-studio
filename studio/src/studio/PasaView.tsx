// PASA: adequacy with the operator's own scheduled outages removed first.
// Pick an archive day, read which resources its RTD outage schedule lists as
// OUT, and re-run the live reliability Monte Carlo with the matched MW gone.
// The full PASA (maintenance scheduling as an optimisation) stays out of
// scope; this is the observed outage state, sized against the DOE fleet.

import { useMemo, useState } from 'react'
import type { Dispatch, GridKey, PasaResource } from '../lib/types'
import { num, pct, fuelLabel, usePasa } from '../lib/data'
import { Panel, StatTile, Chip, Source, EmptyNote } from '../ui/kit'
import { DataGrid, type Column } from '../ui/DataGrid'
import { CompareBars } from './charts'
import {
  solveAdequacyWithOutages,
  solveModel,
  type ClassId,
  type ObjRow,
  type Overrides,
  type ScheduledOut,
} from './model'

const GRIDS: GridKey[] = ['luzon', 'visayas', 'mindanao']
const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

export function PasaView({
  d,
  objects,
  overrides,
}: {
  d: Dispatch
  objects: Record<ClassId, ObjRow[]>
  overrides: Overrides
}) {
  const pasa = usePasa()
  const days = useMemo(() => pasa.data?.days ?? [], [pasa.data])
  const [date, setDate] = useState<string | null>(null)
  const day = days.find((x) => x.date === date) ?? days[days.length - 1]
  const byResource = useMemo(() => {
    const m = new Map<string, PasaResource>()
    for (const r of pasa.data?.resources ?? []) m.set(r.resource, r)
    return m
  }, [pasa.data])

  const outs = useMemo<ScheduledOut[]>(() => {
    if (!day) return []
    return day.out
      .map((name) => byResource.get(name))
      .filter((r): r is PasaResource => !!r && r.match === 'verified')
      .map((r) => ({
        grid: r.grid as GridKey,
        fuel: r.fuel as string,
        mw: r.unit_mw as number,
        plant: r.plant,
      }))
  }, [day, byResource])

  const base = useMemo(() => solveModel(d, objects, overrides), [d, objects, overrides])
  const withOut = useMemo(
    () => solveAdequacyWithOutages(d, objects, overrides, outs),
    [d, objects, overrides, outs]
  )

  if (pasa.loading) return <EmptyNote>Loading the outage schedules.</EmptyNote>
  if (pasa.error || !pasa.data?.available || !day)
    return <EmptyNote>PASA layer not baked. Run make data.</EmptyNote>
  const p = pasa.data

  const rows = day.out
    .map((name) => byResource.get(name))
    .filter((r): r is PasaResource => !!r)
  const cols: Column<PasaResource>[] = [
    { key: 'resource', header: 'Resource code', mono: true, render: (r) => r.resource },
    {
      key: 'plant',
      header: 'DOE plant',
      render: (r) =>
        r.plant ?? (
          <Chip tone={r.match === 'storage' ? 'default' : 'danger'}>
            {r.match === 'storage' ? 'grid battery' : 'unmatched'}
          </Chip>
        ),
    },
    { key: 'grid', header: 'Grid', render: (r) => (r.grid ? cap(r.grid) : '-') },
    { key: 'fuel', header: 'Fuel', render: (r) => (r.fuel ? fuelLabel(r.fuel) : '-') },
    {
      key: 'mw',
      header: 'MW out',
      align: 'right',
      mono: true,
      render: (r) => (r.unit_mw != null ? num(r.unit_mw) : 'not sized'),
    },
  ]

  return (
    <div className="view">
      <div className="chrono__controls">
        <label className="chrono__ctl">
          Outage-schedule day
          <select
            className="ribbon__select"
            value={day.date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Outage schedule day"
          >
            {days.map((x) => (
              <option key={x.date} value={x.date}>
                {x.date} ({x.n_out} out)
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="stat-row">
        {GRIDS.map((g) => (
          <StatTile
            key={g}
            label={`${cap(g)} scheduled out`}
            value={num(day.matched_mw[g])}
            unit="MW"
            hint="matched resources only, a floor"
            tone={day.matched_mw[g] > 200 ? 'danger' : 'default'}
          />
        ))}
        <StatTile
          label="Resources out"
          value={num(day.n_out)}
          hint={`${num(day.n_unmatched)} unmatched, carry no MW`}
        />
      </div>

      <Panel
        title="Adequacy with the day's outages removed"
        subtitle="The live Monte Carlo re-run with matched outage MW off the stack first; the out MW stops drawing its forced-outage rate while the same plant's in-service units keep theirs."
      >
        <CompareBars
          items={GRIDS.map((g) => ({
            label: `Loss-of-load probability, ${cap(g)}`,
            a: withOut.reliability[g].lolp_pct,
            b: base.reliability[g].lolp_pct,
            aLabel: `minus ${num(withOut.outMw[g])} MW scheduled out`,
            bLabel: 'all capacity in',
          }))}
        />
        <div className="stat-row">
          {GRIDS.map((g) => (
            <StatTile
              key={g}
              label={`${cap(g)} reserve margin`}
              value={pct(withOut.marginAfterPct[g] / 100, 1)}
              hint={`from ${pct(base.reserveMarginPct[g] / 100, 1)} with everything in`}
              tone={
                withOut.marginAfterPct[g] < 10
                  ? 'danger'
                  : withOut.marginAfterPct[g] < base.reserveMarginPct[g]
                    ? 'accent'
                    : 'default'
              }
            />
          ))}
        </div>
      </Panel>

      <Panel
        title={`Resources out on ${day.date}`}
        subtitle="The operator's outage schedule used in real-time dispatch, one row per resource, sized against the DOE fleet where the code maps."
        right={<Source href={p.src} label="IEMOP outage schedules" />}
      >
        <DataGrid columns={cols} rows={rows} getKey={(r) => r.resource} />
        <p className="note">{p.coverage_note}</p>
        <p className="note">{p.grid_mapping_note}</p>
      </Panel>

      <p className="note">
        {p.note} {p.disclaimer}
      </p>
    </div>
  )
}
