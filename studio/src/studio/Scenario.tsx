import { useMemo, useState } from 'react'
import type { Dispatch, GridKey } from '../lib/types'
import { fuelLabel, num, php, useGenerators } from '../lib/data'
import { Panel, StatTile, Chip, EmptyNote } from '../ui/kit'
import { MeritStack, FlowDiagram } from './charts'
import { solveScenario, type Levers, type TrippableUnit } from './engine'

const cap = (g: string) => g[0].toUpperCase() + g.slice(1)

function initLevers(d: Dispatch, grid: GridKey): Levers {
  return {
    grid,
    addDC: 0,
    addSolar: 0,
    addGas: 0,
    addCoal: 0,
    addStorage: 0,
    trip: '',
    coalPrice: d.assumptions.fuel_marginal_cost_php_kwh.coal,
    reliefMW: 0,
    lngSwitch: false,
  }
}

export function ScenarioView({ d, grid }: { d: Dispatch; grid: GridKey }) {
  const gens = useGenerators()
  const [lv, setLv] = useState<Levers>(() => initLevers(d, grid))

  // reset the levers when the grid changes (levers are grid-scoped)
  const [lastGrid, setLastGrid] = useState<GridKey>(grid)
  if (grid !== lastGrid) {
    setLastGrid(grid)
    setLv(initLevers(d, grid))
  }

  const units: TrippableUnit[] = useMemo(
    () =>
      (gens.data?.features ?? []).map((f) => ({
        name: f.properties.name,
        grid: f.properties.grid,
        fuel: f.properties.fuel,
        capacity_mw: f.properties.capacity_mw,
      })),
    [gens.data]
  )
  const gridUnits = units
    .filter((u) => u.grid.toLowerCase() === grid)
    .sort((a, b) => b.capacity_mw - a.capacity_mw)

  const out = useMemo(() => solveScenario(d, lv, units), [d, lv, units])
  const mo = d.merit_order[grid]
  const set = (patch: Partial<Levers>) => setLv((p) => ({ ...p, ...patch }))

  const delta = out.single.price - out.base.price
  const feedName =
    out.feed === 'mvip' ? 'MVIP (from Visayas)' : 'Leyte-Luzon (from Luzon)'
  const feedCor = out.feed ? out.coupled[out.feed] : null

  const prices: Record<string, number | null> = {
    luzon: out.coupled.price.luzon,
    visayas: out.coupled.price.visayas,
    mindanao: out.coupled.price.mindanao,
  }
  const corridors = [
    {
      from: 'luzon',
      to: 'visayas',
      flow_mw: out.coupled.leyte.flow,
      saturated: out.coupled.leyte.sat,
      rent: out.coupled.leyte.rent,
    },
    {
      from: 'visayas',
      to: 'mindanao',
      flow_mw: out.coupled.mvip.flow,
      saturated: out.coupled.mvip.sat,
      rent: out.coupled.mvip.rent,
    },
  ]

  const coalFloor = d.assumptions.coal_commit_php_kwh
  const storageOnGrid = grid === 'luzon' ? d.storage.assets.luzon.total_mw : 0

  return (
    <div className="view" data-testid="scenario">
      <p className="scn__lede">
        A simplified merit-order model, <b>not PLEXOS</b>: it stacks the sourced fleet by
        marginal cost against demand and reads the clearing price. Move the levers and the
        price re-clears here in your browser, on the same stack the pipeline baked and
        against the same coupled solve its Python engine runs. It is calibrated against
        observed prices, not a predictor of them.
      </p>

      <div className="scn">
        <Panel
          title="Levers"
          subtitle={`${cap(grid)}, evening reference hour ${mo.reference_hour}:00.`}
        >
          <div className="levers">
            <Slider
              label="Add a data center (flat 24/7 load)"
              value={lv.addDC}
              min={0}
              max={4000}
              step={50}
              tick="DICT 2028 forecast: 1,500 MW"
              onChange={(v) => set({ addDC: v })}
            />
            <Slider
              label="Add solar"
              value={lv.addSolar}
              min={0}
              max={4000}
              step={100}
              tick={`delivers ${num(out.solarDeliveredMW)} MW now, ${num(out.solarMiddayMW)} MW at midday`}
              onChange={(v) => set({ addSolar: v })}
            />
            <Slider
              label="Add gas"
              value={lv.addGas}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at ₱${d.assumptions.fuel_marginal_cost_php_kwh.natural_gas.toFixed(2)}/kWh`}
              onChange={(v) => set({ addGas: v })}
            />
            <Slider
              label="Add coal"
              value={lv.addCoal}
              min={0}
              max={3000}
              step={50}
              tick={`firm, at the coal price below`}
              onChange={(v) => set({ addCoal: v })}
            />
            <Slider
              label="Discharge storage at the peak"
              value={lv.addStorage}
              min={0}
              max={2000}
              step={50}
              tick={
                grid === 'luzon'
                  ? `Luzon has ${num(storageOnGrid)} MW today`
                  : 'no grid-scale storage sourced here yet'
              }
              onChange={(v) => set({ addStorage: v })}
            />
            <Slider
              label="Administered coal price (marginal tranche)"
              value={lv.coalPrice}
              min={coalFloor}
              max={12}
              step={0.25}
              fmt={(v) => `₱${v.toFixed(2)}`}
              tick={`committed tranche stays at ₱${coalFloor.toFixed(2)}`}
              onChange={(v) => set({ coalPrice: v })}
            />
            {out.feed && (
              <Slider
                label={`Relieve the feeding corridor (${feedName})`}
                value={lv.reliefMW}
                min={0}
                max={500}
                step={25}
                tick="extra operating limit on the HVDC link"
                onChange={(v) => set({ reliefMW: v })}
              />
            )}
            <label className="lever lever--check">
              <input
                type="checkbox"
                checked={lv.lngSwitch}
                onChange={(e) => set({ lngSwitch: e.target.checked })}
              />
              <span>
                <span className="lever__label">Switch gas to imported LNG</span>
                <span className="lever__tick">
                  Malampaya depletes around 2027; gas reprices from ₱
                  {d.assumptions.fuel_marginal_cost_php_kwh.natural_gas.toFixed(2)} to ₱
                  {d.assumptions.fuel_marginal_cost_php_kwh.lng.toFixed(2)}/kWh
                </span>
              </span>
            </label>
            <label className="lever">
              <span className="lever__label">Trip a unit (N-1)</span>
              <select
                className="lever__select"
                value={lv.trip}
                onChange={(e) => set({ trip: e.target.value })}
              >
                <option value="">none (all units running)</option>
                {gridUnits.map((u) => (
                  <option key={u.name} value={u.name}>
                    {u.name} (-{num(u.capacity_mw)} MW {fuelLabel(u.fuel)})
                  </option>
                ))}
              </select>
            </label>
            <button
              className="btn btn--ghost lever__reset"
              onClick={() => setLv(initLevers(d, grid))}
            >
              Reset levers
            </button>
          </div>
        </Panel>

        <div className="scn__results">
          <Panel
            title="Clearing price"
            subtitle="The selected grid, cleared on its own stack."
          >
            <div className="stat-row">
              <StatTile
                label="Clearing price"
                value={php(out.single.price)}
                hint={out.single.marginal ? fuelLabel(out.single.marginal) : 'unserved'}
                tone={out.single.shortfall > 0 ? 'danger' : 'default'}
              />
              <StatTile
                label="vs base case"
                value={`${delta >= 0 ? '+' : ''}${php(delta)}`}
                hint={`base ${php(out.base.price)}`}
                tone={delta > 0.001 ? 'accent' : delta < -0.001 ? 'positive' : 'default'}
              />
              <StatTile
                label="Available vs demand"
                value={num(out.single.avail)}
                unit="MW"
                hint={`demand ${num(out.demandSel)} MW`}
              />
              {out.single.shortfall > 0 && (
                <StatTile
                  label="Supply shortfall"
                  value={num(out.single.shortfall)}
                  unit="MW"
                  hint="load shed"
                  tone="danger"
                />
              )}
            </div>
            <MeritStack blocks={out.stack} demand={out.demandSel} />
          </Panel>

          <Panel
            title="Coupled with the two other islands"
            subtitle="The selected grid cleared together with the others over the HVDC links."
          >
            <FlowDiagram prices={prices} corridors={corridors} />
            {out.feed ? (
              <div className="kvs">
                <div className="kv">
                  <span>Coupled clearing price</span>
                  <span className="mono">
                    <b>{php(out.coupled.price[grid])}</b>
                  </span>
                </div>
                <div className="kv">
                  <span>{feedName} link</span>
                  <span className="mono">
                    {num(Math.abs(feedCor?.flow ?? 0))} MW{' '}
                    {feedCor?.sat ? (
                      <Chip tone="danger">saturated</Chip>
                    ) : (
                      <Chip tone="default">open</Chip>
                    )}
                  </span>
                </div>
                {feedCor?.sat && (
                  <div className="kv">
                    <span>Congestion rent across the binding link</span>
                    <span className="mono">
                      <b>{php(feedCor.rent)}</b>
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <p className="note">
                Luzon is the exporting grid: it sets the floor the others import from.
                Relieving a corridor helps the grid downstream, not Luzon.
              </p>
            )}
          </Panel>
        </div>
      </div>

      <p className="note">
        Solar is derated by the availability profile at the evening reference hour, which
        is near zero: adding solar barely moves the evening peak the headline is about.
        Storage (a time-shifter that discharges at the peak) does. A unit trip is
        subtracted from raw fuel availability before the coal commit tranche is split, so
        it reproduces the pipeline dispatch exactly. Every price traces to a sourced fuel
        cost; the scarcity premium lives in the calibration residual, not a tuned number.
      </p>
      {gens.error && <EmptyNote>Generator list unavailable: {gens.error}.</EmptyNote>}
    </div>
  )
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  tick,
  fmt,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  tick?: string
  fmt?: (v: number) => string
  onChange: (v: number) => void
}) {
  const shown = fmt ? fmt(value) : `${num(value)} MW`
  return (
    <label className="lever">
      <span className="lever__label">
        {label} <b className="lever__val mono">{shown}</b>
      </span>
      {tick && <span className="lever__tick">{tick}</span>}
      <input
        type="range"
        className="lever__range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}
